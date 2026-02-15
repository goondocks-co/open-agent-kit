import logging
import shutil
import sqlite3
import time
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel

from open_agent_kit.features.codebase_intelligence.activity.store import sessions
from open_agent_kit.features.codebase_intelligence.constants import (
    CI_DEVTOOLS_CONFIRM_HEADER,
    CI_DEVTOOLS_ERROR_CONFIRM_REQUIRED,
    DEFAULT_SUMMARIZATION_MODEL,
    MIN_SESSION_ACTIVITIES,
)
from open_agent_kit.features.codebase_intelligence.daemon.models import MemoryType
from open_agent_kit.features.codebase_intelligence.daemon.state import get_state

logger = logging.getLogger(__name__)


def require_devtools_confirm(
    x_devtools_confirm: str | None = Header(None, alias=CI_DEVTOOLS_CONFIRM_HEADER),
) -> None:
    """FastAPI dependency that gates destructive devtools operations.

    Requires the ``X-Devtools-Confirm: true`` header to be present.
    This prevents accidental triggering of destructive operations
    from browser navigation or automated crawlers.

    Raises:
        HTTPException: 403 if the confirmation header is missing or not "true".
    """
    if x_devtools_confirm != "true":
        raise HTTPException(
            status_code=403,
            detail=CI_DEVTOOLS_ERROR_CONFIRM_REQUIRED,
        )


router = APIRouter(tags=["devtools"])

# Per-endpoint dependency for destructive operations.
# Applied to POST routes only; GET routes (e.g. memory-stats) are read-only.
_devtools_confirm = [Depends(require_devtools_confirm)]


class RebuildIndexRequest(BaseModel):
    full_rebuild: bool = True


class ResetProcessingRequest(BaseModel):
    delete_memories: bool = True


class DatabaseMaintenanceRequest(BaseModel):
    """Request model for database maintenance operations."""

    vacuum: bool = True  # Reclaim space and defragment
    analyze: bool = True  # Update query planner statistics
    fts_optimize: bool = True  # Optimize full-text search index
    reindex: bool = False  # Rebuild all indexes
    integrity_check: bool = False  # Run integrity check (slower)
    compact_chromadb: bool = False  # Rebuild ChromaDB to reclaim space (slower)


@router.post("/api/devtools/backfill-hashes", dependencies=_devtools_confirm)
async def backfill_content_hashes() -> dict[str, Any]:
    """Backfill content_hash for records missing them.

    New records created after the v11 migration don't get content_hash
    populated at insert time. This endpoint computes and stores hashes
    for all records that are missing them.

    Run this after reprocessing observations or periodically to ensure
    all records have hashes for deduplication during backup/restore.
    """
    state = get_state()
    if not state.activity_store:
        raise HTTPException(status_code=503, detail="Activity store not initialized")

    try:
        counts = state.activity_store.backfill_content_hashes()
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}") from e

    total = sum(counts.values())
    return {
        "status": "success",
        "message": f"Backfilled {total} hashes",
        "batches": counts["prompt_batches"],
        "observations": counts["observations"],
        "activities": counts["activities"],
    }


@router.post("/api/devtools/rebuild-index", dependencies=_devtools_confirm)
async def rebuild_index(
    request: RebuildIndexRequest, background_tasks: BackgroundTasks
) -> dict[str, Any]:
    """Trigger a manual rebuild of the codebase index."""
    state = get_state()
    if not state.indexer:
        raise HTTPException(
            status_code=503, detail="Indexer not initialized (check vector store config)"
        )

    # Check if already indexing
    if state.index_status.is_indexing:
        return {"status": "already_running", "message": "Index rebuild already in progress"}

    # Use unified run_index_build method (runs in background)
    background_tasks.add_task(state.run_index_build, full_rebuild=request.full_rebuild)
    return {"status": "started", "message": "Index rebuild started in background"}


@router.post("/api/devtools/reset-processing", dependencies=_devtools_confirm)
async def reset_processing(request: ResetProcessingRequest) -> dict[str, Any]:
    """Reset processing state to allow re-generation of memories."""
    state = get_state()
    if not state.activity_store:
        raise HTTPException(status_code=503, detail="Activity store not initialized")

    chromadb_cleared = 0

    try:
        counts = state.activity_store.reset_processing_state(
            delete_memories=request.delete_memories
        )
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}") from e

    # ChromaDB cleanup stays in the route — the store layer doesn't hold
    # the vector store reference for this operation.
    if request.delete_memories and state.vector_store:
        chromadb_cleared = state.vector_store.clear_memory_collection()
        logger.info(f"Cleared {chromadb_cleared} items from ChromaDB memory collection")

    logger.info("Reset processing state via DevTools: %s", counts)

    return {
        "status": "success",
        "message": "Processing state reset. Background jobs will pick this up.",
        "chromadb_cleared": chromadb_cleared,
    }


@router.post("/api/devtools/trigger-processing", dependencies=_devtools_confirm)
async def trigger_processing() -> dict[str, Any]:
    """Manually trigger the background processing loop immediately."""
    state = get_state()
    if not state.activity_processor:
        raise HTTPException(
            status_code=503, detail="Activity processor not initialized properly (check config)"
        )

    # Run manually
    results = state.activity_processor.process_pending_batches(max_batches=50)

    return {
        "status": "success",
        "processed_batches": len(results),
        "details": [
            {"id": r.prompt_batch_id, "success": r.success, "extracted": r.observations_extracted}
            for r in results
        ],
    }


class RebuildMemoriesRequest(BaseModel):
    full_rebuild: bool = True
    clear_chromadb_first: bool = False


@router.post("/api/devtools/compact-chromadb", dependencies=_devtools_confirm)
async def compact_chromadb() -> dict[str, Any]:
    """Compact ChromaDB by deleting directory, then signal frontend to restart.

    ChromaDB's in-process WAL locks and HNSW file handles don't fully
    release even after ``client.reset()`` — so we only do the *delete*
    here and return ``restart_required: true``.  The frontend chains
    this with ``/api/self-restart`` so the daemon comes back fresh and
    ``_check_and_rebuild_chromadb()`` rebuilds everything on startup.
    """
    import asyncio

    state = get_state()
    if not state.vector_store:
        raise HTTPException(status_code=503, detail="Vector store not initialized")
    if not state.activity_store:
        raise HTTPException(status_code=503, detail="Activity store not initialized")
    if not state.indexer:
        raise HTTPException(status_code=503, detail="Indexer not initialized")

    # Check if indexing is already in progress - can't compact while indexing
    if state.index_status.is_indexing:
        raise HTTPException(
            status_code=409,
            detail="Cannot compact while indexing is in progress. Please wait for the current index build to complete.",
        )

    # Get size before compaction for reporting
    chroma_path = state.vector_store.persist_directory
    size_before_mb = 0.0
    try:
        if chroma_path.exists():
            size_before_mb = sum(
                f.stat().st_size for f in chroma_path.rglob("*") if f.is_file()
            ) / (1024 * 1024)
    except OSError:
        pass

    # Capture the path for the sync helper
    chroma_path_capture = chroma_path

    def _delete_chromadb() -> None:
        """Synchronous helper: detach, close, and delete ChromaDB directory."""
        # 1. Stop file watcher to release index handles
        if state.file_watcher:
            state.file_watcher.stop()
            logger.info("Compaction: stopped file watcher")

        # 2. Detach old VectorStore from state FIRST to prevent concurrent
        #    requests (health checks, status polls) from re-initializing
        #    the client via _ensure_initialized() during cleanup.
        old_vector_store = state.vector_store
        state.vector_store = None
        state.invalidate_retrieval_engine()

        # 3. Close the old VectorStore client
        if old_vector_store and old_vector_store._client:
            try:
                if hasattr(old_vector_store._client, "reset"):
                    old_vector_store._client.reset()
            except (OSError, RuntimeError, AttributeError) as e:
                logger.debug(f"Client reset failed (expected): {e}")

            old_vector_store._code_collection = None
            old_vector_store._memory_collection = None
            old_vector_store._session_summaries_collection = None
            old_vector_store._client = None

        del old_vector_store

        # 4. Delete ChromaDB directory
        time.sleep(0.5)  # Brief pause for OS to release handles
        if chroma_path_capture.exists():
            shutil.rmtree(chroma_path_capture)
            logger.info(f"Compaction: deleted ChromaDB directory ({size_before_mb:.1f} MB freed)")

    await asyncio.to_thread(_delete_chromadb)

    return {
        "status": "deleted",
        "restart_required": True,
        "message": "ChromaDB deleted. Restart the daemon to rebuild.",
        "size_before_mb": round(size_before_mb, 2),
    }


@router.post("/api/devtools/rebuild-memories", dependencies=_devtools_confirm)
async def rebuild_memories(
    request: RebuildMemoriesRequest, background_tasks: BackgroundTasks
) -> dict[str, Any]:
    """Re-embed memories from SQLite source of truth to ChromaDB search index.

    Use this when ChromaDB has been cleared (e.g., embedding model change) but
    SQLite still has the memory observations. This will re-embed all memories
    without re-running the LLM extraction.

    Set clear_chromadb_first=True to remove orphaned entries from ChromaDB before
    rebuilding. Use this after restore operations where memories may have been
    deleted from SQLite but still exist in ChromaDB.
    """
    state = get_state()
    if not state.activity_processor:
        raise HTTPException(
            status_code=503, detail="Activity processor not initialized (check config)"
        )
    if not state.activity_store:
        raise HTTPException(status_code=503, detail="Activity store not initialized")

    # Get current stats before rebuild
    sqlite_count = state.activity_store.count_observations()
    unembedded_count = state.activity_store.count_unembedded_observations()

    if sqlite_count == 0:
        return {
            "status": "skipped",
            "message": "No memories in SQLite to embed",
            "stats": {"sqlite_total": 0, "unembedded": 0},
        }

    # Run rebuild in background for large datasets
    if sqlite_count > 100:
        background_tasks.add_task(
            state.activity_processor.rebuild_chromadb_from_sqlite,
            batch_size=50,
            reset_embedded_flags=request.full_rebuild,
            clear_chromadb_first=request.clear_chromadb_first,
        )
        return {
            "status": "started",
            "message": f"Memory re-embedding started in background ({sqlite_count} memories)",
            "stats": {"sqlite_total": sqlite_count, "unembedded": unembedded_count},
        }

    # For small datasets, run synchronously
    stats = state.activity_processor.rebuild_chromadb_from_sqlite(
        batch_size=50,
        reset_embedded_flags=request.full_rebuild,
        clear_chromadb_first=request.clear_chromadb_first,
    )

    return {
        "status": "completed",
        "message": f"Re-embedded {stats['embedded']} memories ({stats['failed']} failed)",
        "stats": stats,
    }


@router.get("/api/devtools/memory-stats")
async def get_memory_stats() -> dict[str, Any]:
    """Get detailed memory statistics for debugging sync issues."""
    state = get_state()
    if not state.activity_store:
        raise HTTPException(status_code=503, detail="Activity store not initialized")

    sqlite_total = state.activity_store.count_observations()
    sqlite_embedded = state.activity_store.count_embedded_observations()
    sqlite_unembedded = state.activity_store.count_unembedded_observations()
    sqlite_session_summaries = state.activity_store.count_observations_by_type(
        MemoryType.SESSION_SUMMARY.value
    )

    # Plans are also stored in ChromaDB memory collection (with memory_type='plan')
    # but tracked in prompt_batches table, not memory_observations
    sqlite_plans_embedded = state.activity_store.count_embedded_plans()
    sqlite_plans_unembedded = state.activity_store.count_unembedded_plans()

    chromadb_count = 0
    if state.vector_store:
        stats = state.vector_store.get_stats()
        chromadb_count = stats.get("memory_observations", 0)

    # Total expected in ChromaDB = embedded memories + embedded plans
    total_expected_in_chromadb = sqlite_embedded + sqlite_plans_embedded

    # Calculate the difference to determine sync direction
    # Positive = ChromaDB has more (orphaned entries)
    # Negative = SQLite has more (missing from ChromaDB)
    sync_difference = chromadb_count - total_expected_in_chromadb

    # Check for sync issues with direction
    sync_status = "synced"
    if sync_difference > 0:
        # ChromaDB has MORE than SQLite expects - orphaned entries
        sync_status = "orphaned"
    elif sync_difference < 0:
        # ChromaDB has LESS than SQLite expects - missing entries
        sync_status = "missing"
    elif sqlite_unembedded > 0 or sqlite_plans_unembedded > 0:
        sync_status = "pending_embed"

    return {
        "sqlite": {
            "total": sqlite_total,
            "embedded": sqlite_embedded,
            "unembedded": sqlite_unembedded,
            "plans_embedded": sqlite_plans_embedded,
            "plans_unembedded": sqlite_plans_unembedded,
            "session_summaries": sqlite_session_summaries,
        },
        "chromadb": {
            "count": chromadb_count,
        },
        "summarization": {
            "enabled": bool(state.ci_config and state.ci_config.summarization.enabled),
            "model": (
                state.ci_config.summarization.model
                if state.ci_config
                else DEFAULT_SUMMARIZATION_MODEL
            ),
        },
        "sync_status": sync_status,
        "sync_difference": sync_difference,  # Positive = orphaned, negative = missing
        "needs_rebuild": (
            sqlite_unembedded > 0 or sqlite_plans_unembedded > 0 or sync_difference != 0
        ),
    }


@router.post("/api/devtools/cleanup-orphans", dependencies=_devtools_confirm)
async def cleanup_orphans() -> dict[str, Any]:
    """Remove orphaned entries from ChromaDB that have no matching SQLite record.

    Orphans accumulate when SQLite deletes succeed but ChromaDB deletes fail
    (e.g., during session cleanup or batch reprocessing). This endpoint diffs
    ChromaDB IDs against SQLite embedded IDs and deletes only the orphans.
    """
    state = get_state()
    if not state.activity_store:
        raise HTTPException(status_code=503, detail="Activity store not initialized")
    if not state.vector_store:
        raise HTTPException(status_code=503, detail="Vector store not initialized")

    # Collect all IDs that SHOULD be in ChromaDB
    expected_ids = set(state.activity_store.get_embedded_observation_ids())
    expected_ids.update(state.activity_store.get_embedded_plan_chromadb_ids())

    # Collect all IDs that ARE in ChromaDB
    chromadb_ids = set(state.vector_store.get_all_memory_ids())

    orphaned_ids = list(chromadb_ids - expected_ids)

    if not orphaned_ids:
        return {
            "status": "clean",
            "message": "No orphaned entries found",
            "orphaned_count": 0,
            "deleted_count": 0,
        }

    deleted_count = state.vector_store.delete_memories(orphaned_ids)

    logger.info(f"Cleaned up {deleted_count} orphaned ChromaDB entries")

    return {
        "status": "success",
        "message": f"Removed {deleted_count} orphaned entries from ChromaDB",
        "orphaned_count": len(orphaned_ids),
        "deleted_count": deleted_count,
    }


@router.post("/api/devtools/database-maintenance", dependencies=_devtools_confirm)
async def database_maintenance(
    request: DatabaseMaintenanceRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Run SQLite and ChromaDB database maintenance operations.

    Recommended after heavy delete/rebuild operations or periodically (weekly/monthly).

    SQLite Operations:
    - vacuum: Reclaims unused space and defragments the database file
    - analyze: Updates statistics for the query planner (improves performance)
    - fts_optimize: Optimizes the full-text search index
    - reindex: Rebuilds all indexes (fixes corruption, improves performance)
    - integrity_check: Verifies database integrity (slower, use for diagnostics)

    ChromaDB Operations:
    - compact_chromadb: Rebuilds ChromaDB collections from SQLite source of truth.
      This is the ONLY way to reclaim disk space after deletions - ChromaDB has no
      built-in vacuum/compaction. Use after large refactors or deletions.

    Note: VACUUM and compact_chromadb can be slow for large databases.
    Runs in background for safety.
    """
    state = get_state()
    if not state.activity_store:
        raise HTTPException(status_code=503, detail="Activity store not initialized")

    # ChromaDB compaction now requires a daemon restart — use the dedicated endpoint
    if request.compact_chromadb:
        raise HTTPException(
            status_code=400,
            detail="ChromaDB compaction now requires a daemon restart. Use POST /api/devtools/compact-chromadb instead.",
        )

    store = state.activity_store
    conn = store._get_connection()

    # Get database size before maintenance
    db_path = store.db_path
    size_before_mb = 0.0
    try:
        import os

        size_before_mb = os.path.getsize(db_path) / (1024 * 1024)
    except OSError:
        pass

    # If integrity check requested, run it synchronously first (it's diagnostic)
    integrity_result = None
    if request.integrity_check:
        try:
            cursor = conn.execute("PRAGMA integrity_check")
            result = cursor.fetchone()
            integrity_result = result[0] if result else "unknown"
            logger.info(f"Database integrity check: {integrity_result}")
        except sqlite3.Error as e:
            integrity_result = f"error: {e}"
            logger.error(f"Integrity check failed: {e}")

    # If only integrity check was requested, return immediately
    if (
        not request.vacuum
        and not request.analyze
        and not request.fts_optimize
        and not request.reindex
    ):
        return {
            "status": "completed",
            "message": "Integrity check completed",
            "integrity_check": integrity_result,
            "size_mb": round(size_before_mb, 2),
        }

    def _run_maintenance() -> None:
        """Background task to run SQLite maintenance operations."""
        try:
            store.optimize_database(
                vacuum=request.vacuum,
                analyze=request.analyze,
                fts_optimize=request.fts_optimize,
                reindex=request.reindex,
            )
        except Exception as e:
            logger.error(f"Database maintenance error: {e}", exc_info=True)

    background_tasks.add_task(_run_maintenance)

    operations = []
    if request.reindex:
        operations.append("reindex")
    if request.analyze:
        operations.append("analyze")
    if request.fts_optimize:
        operations.append("fts_optimize")
    if request.vacuum:
        operations.append("vacuum")

    return {
        "status": "started",
        "message": f"Database maintenance started: {', '.join(operations)}",
        "operations": operations,
        "integrity_check": integrity_result,
        "size_before_mb": round(size_before_mb, 2),
    }


@router.post("/api/devtools/regenerate-summaries", dependencies=_devtools_confirm)
async def regenerate_summaries(
    background_tasks: BackgroundTasks,
    force: bool = False,
) -> dict[str, Any]:
    """Regenerate session summaries for completed sessions.

    By default, only backfills missing summaries. With force=true, regenerates
    ALL summaries (useful after fixing summary generation bugs like incorrect
    stat keys in prompts).

    Args:
        force: If true, regenerate all summaries, not just missing ones.
    """
    state = get_state()
    if not state.activity_processor:
        raise HTTPException(
            status_code=503, detail="Activity processor not initialized (check config)"
        )
    if not state.activity_store:
        raise HTTPException(status_code=503, detail="Activity store not initialized")

    # Capture processor reference for closure (mypy type narrowing)
    processor = state.activity_processor
    store = state.activity_store

    if force:
        min_activities = processor.min_session_activities
        sessions_list = store.get_completed_sessions(min_activities=min_activities, limit=500)
    else:
        sessions_list = store.get_sessions_missing_summaries(limit=100)

    if not sessions_list:
        return {
            "status": "skipped",
            "message": "No sessions to regenerate" if force else "No sessions missing summaries",
            "sessions_queued": 0,
        }

    regenerate_title = force  # Force title regeneration when force=true

    def _regenerate() -> None:
        count = 0
        for session in sessions_list:
            try:
                summary, _title = processor.process_session_summary_with_title(
                    session.id, regenerate_title=regenerate_title
                )
                if summary:
                    count += 1
                    logger.info(f"Regenerated summary for session {session.id[:8]}")
            except (OSError, ValueError, RuntimeError, AttributeError) as e:
                logger.warning(f"Failed to regenerate summary for {session.id[:8]}: {e}")
        logger.info(f"Regenerated {count} session summaries out of {len(sessions_list)} queued")

    background_tasks.add_task(_regenerate)
    mode = "force" if force else "backfill"
    return {"status": "started", "sessions_queued": len(sessions_list), "mode": mode}


@router.post("/api/devtools/cleanup-minimal-sessions", dependencies=_devtools_confirm)
async def cleanup_minimal_sessions() -> dict[str, Any]:
    """Manually trigger cleanup of low-quality sessions.

    Deletes completed sessions that don't meet the quality threshold
    (< min_activities tool calls as configured). These sessions will never be
    summarized or embedded, so keeping them just creates clutter.

    This is useful for immediate cleanup without waiting for the background
    stale session recovery job.

    Only affects COMPLETED sessions - active sessions are not touched.
    """
    state = get_state()
    if not state.activity_store:
        raise HTTPException(status_code=503, detail="Activity store not initialized")

    # Get configured threshold from config, fall back to constant default
    min_activities = MIN_SESSION_ACTIVITIES
    if state.ci_config:
        min_activities = state.ci_config.session_quality.min_activities

    try:
        deleted_ids = sessions.cleanup_low_quality_sessions(
            store=state.activity_store,
            vector_store=state.vector_store,
            min_activities=min_activities,
        )

        if not deleted_ids:
            return {
                "status": "skipped",
                "message": f"No sessions found below quality threshold ({min_activities} activities)",
                "deleted_count": 0,
                "deleted_ids": [],
            }

        return {
            "status": "success",
            "message": f"Deleted {len(deleted_ids)} low-quality sessions",
            "deleted_count": len(deleted_ids),
            "deleted_ids": deleted_ids,
            "threshold": min_activities,
        }

    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}") from e


@router.post("/api/devtools/resolve-stale-observations", dependencies=_devtools_confirm)
async def resolve_stale_observations(
    request: Request,
    dry_run: bool = Query(False, description="Preview without making changes"),
    max_observations: int = Query(
        100, description="Maximum observations to process", ge=1, le=1000
    ),
) -> dict[str, Any]:
    """Suggest and optionally resolve stale observations.

    Iterates active observations and uses file overlap heuristics to suggest
    which observations may be stale (addressed in later sessions).

    Requires X-Devtools-Confirm: true header (enforced by router dependency).

    This is a v1 stub — full LLM-based analysis is future work.
    """
    state = get_state()
    if not state.activity_store:
        raise HTTPException(status_code=503, detail="Activity store not initialized")

    store = state.activity_store

    active_observations = store.get_active_observations(limit=max_observations)

    suggestions: list[dict[str, Any]] = []
    resolved_count = 0

    for obs in active_observations:
        # Heuristic: check if there are later sessions that modified the same file
        target_path = obs.file_path or obs.context
        if not target_path:
            continue

        later_session_id = store.find_later_edit_session(
            file_path=target_path,
            after_epoch=obs.created_at.timestamp(),
            exclude_session_id=obs.session_id,
        )
        if not later_session_id:
            continue

        suggestion: dict[str, Any] = {
            "observation_id": obs.id,
            "reason": f"File {target_path} was modified in later session {later_session_id}",
            "suggested_resolved_by": later_session_id,
        }
        suggestions.append(suggestion)

        if not dry_run:
            engine = state.retrieval_engine
            if engine:
                engine.resolve_memory(
                    memory_id=obs.id,
                    status="resolved",
                    resolved_by_session_id=later_session_id,
                )
            resolved_count += 1

    return {
        "dry_run": dry_run,
        "total_scanned": len(active_observations),
        "suggestions": suggestions,
        "resolved_count": resolved_count,
        "message": (
            f"Found {len(suggestions)} potentially stale observations"
            if dry_run
            else f"Resolved {resolved_count} stale observations"
        ),
    }


class ReprocessObservationsRequest(BaseModel):
    """Request model for reprocessing observations."""

    mode: str = "all"  # all | date_range | session | low_importance
    start_date: str | None = None  # ISO format for date_range mode
    end_date: str | None = None  # ISO format for date_range mode
    session_id: str | None = None  # For session mode
    importance_threshold: int | None = None  # For low_importance mode (reprocess below this)
    delete_existing: bool = True  # Delete existing observations before reprocessing
    dry_run: bool = False  # Preview what would be reprocessed


@router.post("/api/devtools/reprocess-observations", dependencies=_devtools_confirm)
async def reprocess_observations(
    request: ReprocessObservationsRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    """Reprocess observations with updated extraction prompts.

    IMPORTANT: Only processes batches where source_machine_id matches the current
    machine. This prevents accidentally modifying teammates' imported data.

    Modes:
    - all: Reprocess all user batches from this machine
    - date_range: Reprocess batches in date range (start_date, end_date)
    - session: Reprocess specific session
    - low_importance: Reprocess batches with observations below importance_threshold

    The workflow:
    1. Get batch IDs based on mode (filtered by source_machine_id = current)
    2. Delete existing observations from SQLite AND ChromaDB if delete_existing=True
    3. Reset processing flags on batches
    4. Queue batches for re-extraction in background

    ChromaDB is cleaned inline (no manual rebuild-memories step needed).
    """
    state = get_state()
    if not state.activity_store:
        raise HTTPException(status_code=503, detail="Activity store not initialized")
    if not state.activity_processor:
        raise HTTPException(status_code=503, detail="Activity processor not initialized")

    store = state.activity_store
    machine_id = state.machine_id or ""

    # Parse date_range params to epoch before calling store layer
    start_epoch: float | None = None
    end_epoch: float | None = None
    if request.mode == "date_range":
        if not request.start_date or not request.end_date:
            raise HTTPException(
                status_code=400,
                detail="date_range mode requires start_date and end_date",
            )
        start_epoch = datetime.fromisoformat(request.start_date).timestamp()
        end_epoch = datetime.fromisoformat(request.end_date).timestamp()

    try:
        batch_ids = store.get_batch_ids_for_reprocessing(
            machine_id,
            mode=request.mode,
            session_id=request.session_id,
            start_epoch=start_epoch,
            end_epoch=end_epoch,
            importance_threshold=request.importance_threshold,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}") from e

    if not batch_ids:
        return {
            "status": "skipped",
            "message": f"No batches found for mode={request.mode} on machine={machine_id}",
            "batches_found": 0,
        }

    if request.dry_run:
        return {
            "status": "dry_run",
            "message": f"Would reprocess {len(batch_ids)} batches",
            "batches_found": len(batch_ids),
            "batch_ids": batch_ids[:20],  # Preview first 20
            "machine_id": machine_id,
        }

    # Count existing observations for these batches
    existing_obs_count = store.count_observations_for_batches(batch_ids, machine_id)

    # Delete existing observations and reset batch flags
    deleted_count = 0
    if request.delete_existing:
        try:
            old_obs_ids = store.delete_observations_for_batches(batch_ids, machine_id)
            deleted_count = len(old_obs_ids)

            # Clean ChromaDB so orphaned vectors don't pollute search results
            if old_obs_ids and state.vector_store:
                try:
                    state.vector_store.delete_memories(old_obs_ids)
                    logger.info(f"Cleaned {len(old_obs_ids)} observations from ChromaDB")
                except (ValueError, RuntimeError, KeyError, AttributeError) as e:
                    # SQLite cleanup succeeded; ChromaDB will be stale but not duplicated.
                    # process_prompt_batch also cleans at processing time as a safety net.
                    logger.warning(
                        f"ChromaDB cleanup failed (will be fixed at processing time): {e}"
                    )

        except (OSError, ValueError, TypeError) as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete observations: {e}",
            ) from e

    # Queue batches for background processing
    processor = state.activity_processor

    def _reprocess_batches() -> None:
        """Background task to reprocess batches."""
        logger.info(f"Starting reprocessing of {len(batch_ids)} batches")
        results = processor.process_pending_batches(max_batches=len(batch_ids))
        success_count = sum(1 for r in results if r.success)
        total_obs = sum(r.observations_extracted for r in results)
        logger.info(
            f"Reprocessing complete: {success_count}/{len(results)} batches successful, "
            f"{total_obs} observations extracted"
        )

    background_tasks.add_task(_reprocess_batches)

    return {
        "status": "started",
        "message": f"Reprocessing {len(batch_ids)} batches in background",
        "batches_queued": len(batch_ids),
        "observations_deleted": deleted_count,
        "previous_observations": existing_obs_count,
        "machine_id": machine_id,
        "mode": request.mode,
    }
