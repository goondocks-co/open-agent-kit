import logging
import sqlite3
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from open_agent_kit.features.codebase_intelligence.activity.store import sessions
from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
    get_machine_identifier,
)
from open_agent_kit.features.codebase_intelligence.constants import (
    DEFAULT_SUMMARIZATION_MODEL,
    MIN_SESSION_ACTIVITIES,
)
from open_agent_kit.features.codebase_intelligence.daemon.models import MemoryType
from open_agent_kit.features.codebase_intelligence.daemon.state import get_state

router = APIRouter(tags=["devtools"])
logger = logging.getLogger(__name__)


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


@router.post("/api/devtools/backfill-hashes")
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

    from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
        compute_activity_hash,
        compute_observation_hash,
        compute_prompt_batch_hash,
    )

    store = state.activity_store
    conn = store._get_connection()

    batch_count = 0
    obs_count = 0
    activity_count = 0

    try:
        # Backfill prompt_batches
        cursor = conn.execute(
            "SELECT id, session_id, prompt_number FROM prompt_batches WHERE content_hash IS NULL"
        )
        for row in cursor.fetchall():
            batch_id, session_id, prompt_number = row
            hash_val = compute_prompt_batch_hash(str(session_id), int(prompt_number))
            conn.execute(
                "UPDATE prompt_batches SET content_hash = ? WHERE id = ?",
                (hash_val, batch_id),
            )
            batch_count += 1

        # Backfill memory_observations
        cursor = conn.execute(
            "SELECT id, observation, memory_type, context FROM memory_observations "
            "WHERE content_hash IS NULL"
        )
        for row in cursor.fetchall():
            obs_id, observation, memory_type, context = row
            hash_val = compute_observation_hash(str(observation), str(memory_type), context)
            conn.execute(
                "UPDATE memory_observations SET content_hash = ? WHERE id = ?",
                (hash_val, obs_id),
            )
            obs_count += 1

        # Backfill activities
        cursor = conn.execute(
            "SELECT id, session_id, timestamp_epoch, tool_name FROM activities "
            "WHERE content_hash IS NULL"
        )
        for row in cursor.fetchall():
            activity_id, session_id, timestamp_epoch, tool_name = row
            hash_val = compute_activity_hash(str(session_id), int(timestamp_epoch), str(tool_name))
            conn.execute(
                "UPDATE activities SET content_hash = ? WHERE id = ?",
                (hash_val, activity_id),
            )
            activity_count += 1

        conn.commit()

        logger.info(
            f"Backfilled content hashes: {batch_count} batches, "
            f"{obs_count} observations, {activity_count} activities"
        )

        return {
            "status": "success",
            "message": f"Backfilled {batch_count + obs_count + activity_count} hashes",
            "batches": batch_count,
            "observations": obs_count,
            "activities": activity_count,
        }

    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}") from e


@router.post("/api/devtools/rebuild-index")
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


@router.post("/api/devtools/reset-processing")
async def reset_processing(request: ResetProcessingRequest) -> dict[str, Any]:
    """Reset processing state to allow re-generation of memories."""
    state = get_state()
    if not state.activity_store:
        raise HTTPException(status_code=503, detail="Activity store not initialized")

    store = state.activity_store
    chromadb_cleared = 0

    try:
        with store._transaction() as conn:
            # 1. Delete generated memories if requested
            if request.delete_memories:
                conn.execute("DELETE FROM memory_observations")

                # Also clear ChromaDB memory collection to prevent orphaned vectors
                # This is the only way to reclaim space - ChromaDB has no vacuum
                if state.vector_store:
                    chromadb_cleared = state.vector_store.clear_memory_collection()
                    logger.info(f"Cleared {chromadb_cleared} items from ChromaDB memory collection")

            # 2. Reset sessions
            conn.execute(
                "UPDATE sessions SET processed = FALSE, summary = NULL WHERE status = 'completed'"
            )

            # 3. Reset prompt batches
            conn.execute(
                "UPDATE prompt_batches "
                "SET processed = FALSE, classification = NULL "
                "WHERE status = 'completed'"
            )

            # 4. Reset activities
            conn.execute("UPDATE activities SET processed = FALSE")

            logger.info("Reset processing state via DevTools")

    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}") from e

    return {
        "status": "success",
        "message": "Processing state reset. Background jobs will pick this up.",
        "chromadb_cleared": chromadb_cleared,
    }


@router.post("/api/devtools/trigger-processing")
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


@router.post("/api/devtools/compact-chromadb")
async def compact_chromadb(background_tasks: BackgroundTasks) -> dict[str, Any]:
    """Compact all ChromaDB by deleting directory and rebuilding from SQLite.

    This is the ONLY way to reclaim disk space - ChromaDB's delete_collection()
    does NOT release file space. This endpoint performs a "hard reset" that:

    1. Deletes the entire ChromaDB directory (actually frees disk space)
    2. Reinitializes with empty collections
    3. Re-embeds session summaries from SQLite
    4. Re-embeds memories from SQLite
    5. Re-indexes all code files

    Use after large refactors, file deletions, or periodically to reclaim space.
    All operations run in background to avoid timeout.
    """
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

    # Get sizes before compaction for reporting
    chroma_path = state.vector_store.persist_directory
    size_before_mb = 0.0
    try:
        if chroma_path.exists():
            size_before_mb = sum(
                f.stat().st_size for f in chroma_path.rglob("*") if f.is_file()
            ) / (1024 * 1024)
    except OSError:
        pass

    # Get current stats
    stats_before = state.vector_store.get_stats()
    memory_count = state.activity_store.count_observations()

    # Capture references for background task
    vector_store = state.vector_store
    activity_store = state.activity_store

    def _run_compaction() -> None:
        """Background task to run compaction with hard reset."""
        from open_agent_kit.features.codebase_intelligence.activity.processor.indexing import (
            compact_all_chromadb,
        )

        try:
            # 1. Hard reset + rebuild memories and session summaries
            stats = compact_all_chromadb(
                activity_store=activity_store,
                vector_store=vector_store,
                clear_code_index=True,
                hard_reset=True,  # Delete directory for true space reclamation
            )

            logger.info(
                f"Compaction: freed {stats['bytes_freed'] / 1024 / 1024:.1f} MB, "
                f"re-embedded {stats['memories_embedded']} memories, "
                f"{stats['sessions_embedded']} sessions"
            )

            # 2. Rebuild code index (this actually re-scans and re-embeds files)
            logger.info("Compaction: starting code index rebuild...")
            state.run_index_build(full_rebuild=True)
            logger.info("Compaction: code index rebuild complete")

        except (RuntimeError, ValueError, OSError) as e:
            logger.error(f"ChromaDB compaction error: {e}", exc_info=True)

    background_tasks.add_task(_run_compaction)

    return {
        "status": "started",
        "message": "ChromaDB hard reset + rebuild started (will delete directory to reclaim space)",
        "size_before_mb": round(size_before_mb, 2),
        "stats_before": {
            "code_chunks": stats_before.get("code_chunks", 0),
            "memory_observations": stats_before.get("memory_observations", 0),
            "session_summaries": stats_before.get("session_summaries", 0),
        },
        "sqlite_memories": memory_count,
    }


@router.post("/api/devtools/rebuild-memories")
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


@router.post("/api/devtools/database-maintenance")
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

    # Check if indexing is in progress - can't compact ChromaDB while indexing
    if request.compact_chromadb and state.index_status.is_indexing:
        raise HTTPException(
            status_code=409,
            detail="Cannot compact ChromaDB while indexing is in progress. Please wait for the current index build to complete.",
        )

    store = state.activity_store
    conn = store._get_connection()

    # Get database size before maintenance
    db_path = store.db_path
    size_before_mb = 0.0
    chromadb_size_before_mb = 0.0
    try:
        import os

        size_before_mb = os.path.getsize(db_path) / (1024 * 1024)

        # Also get ChromaDB size if compaction requested
        if request.compact_chromadb and state.vector_store:
            chroma_path = state.vector_store.persist_directory
            if chroma_path.exists():
                chromadb_size_before_mb = sum(
                    f.stat().st_size for f in chroma_path.rglob("*") if f.is_file()
                ) / (1024 * 1024)
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
        and not request.compact_chromadb
    ):
        return {
            "status": "completed",
            "message": "Integrity check completed",
            "integrity_check": integrity_result,
            "size_mb": round(size_before_mb, 2),
        }

    # Capture references for background task closure
    activity_store = state.activity_store
    vector_store = state.vector_store

    def _run_maintenance() -> None:
        """Background task to run maintenance operations."""
        try:
            if request.reindex:
                conn.execute("REINDEX")
                logger.debug("Database maintenance: REINDEX complete")

            if request.analyze:
                conn.execute("ANALYZE")
                logger.debug("Database maintenance: ANALYZE complete")

            if request.fts_optimize:
                conn.execute("INSERT INTO activities_fts(activities_fts) VALUES('optimize')")
                logger.debug("Database maintenance: FTS optimize complete")

            if request.vacuum:
                conn.execute("VACUUM")
                logger.debug("Database maintenance: VACUUM complete")

            # ChromaDB compaction: hard reset + rebuild from SQLite
            if request.compact_chromadb and activity_store and vector_store:
                from open_agent_kit.features.codebase_intelligence.activity.processor.indexing import (
                    compact_all_chromadb,
                )

                logger.info("Starting ChromaDB compaction (hard reset + rebuild)...")

                # Use shared compaction logic with hard reset for true space reclamation
                stats = compact_all_chromadb(
                    activity_store=activity_store,
                    vector_store=vector_store,
                    clear_code_index=True,
                    hard_reset=True,
                )

                logger.info(
                    f"ChromaDB compaction complete: freed {stats['bytes_freed'] / 1024 / 1024:.1f} MB, "
                    f"{stats['memories_embedded']} memories re-embedded"
                )

                # Rebuild code index
                logger.info("Compaction: starting code index rebuild...")
                state.run_index_build(full_rebuild=True)
                logger.info("Compaction: code index rebuild complete")

            logger.info("Database maintenance completed successfully")
        except sqlite3.Error as e:
            logger.error(f"Database maintenance error: {e}", exc_info=True)
        except (RuntimeError, ValueError, OSError) as e:
            logger.error(f"ChromaDB compaction error: {e}", exc_info=True)

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
    if request.compact_chromadb:
        operations.append("compact_chromadb")

    response: dict[str, Any] = {
        "status": "started",
        "message": f"Database maintenance started: {', '.join(operations)}",
        "operations": operations,
        "integrity_check": integrity_result,
        "size_before_mb": round(size_before_mb, 2),
    }

    if request.compact_chromadb:
        response["chromadb_size_before_mb"] = round(chromadb_size_before_mb, 2)

    return response


@router.post("/api/devtools/regenerate-summaries")
async def regenerate_summaries(background_tasks: BackgroundTasks) -> dict[str, Any]:
    """Regenerate missing session summaries for completed sessions.

    Finds sessions that are completed but don't have summaries and
    triggers summary generation for each. Runs in background to avoid timeout.
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

    # Get sessions missing summaries (higher limit for backfill)
    missing = state.activity_store.get_sessions_missing_summaries(limit=100)

    if not missing:
        return {
            "status": "skipped",
            "message": "No sessions missing summaries",
            "sessions_queued": 0,
        }

    def _regenerate() -> None:
        count = 0
        for session in missing:
            try:
                summary = processor.process_session_summary(session.id)
                if summary:
                    count += 1
                    logger.info(f"Regenerated summary for session {session.id[:8]}")
            except (OSError, ValueError, RuntimeError, AttributeError) as e:
                logger.warning(f"Failed to regenerate summary for {session.id[:8]}: {e}")
        logger.info(f"Regenerated {count} session summaries out of {len(missing)} queued")

    background_tasks.add_task(_regenerate)
    return {"status": "started", "sessions_queued": len(missing)}


@router.post("/api/devtools/cleanup-minimal-sessions")
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


class ReprocessObservationsRequest(BaseModel):
    """Request model for reprocessing observations."""

    mode: str = "all"  # all | date_range | session | low_importance
    start_date: str | None = None  # ISO format for date_range mode
    end_date: str | None = None  # ISO format for date_range mode
    session_id: str | None = None  # For session mode
    importance_threshold: int | None = None  # For low_importance mode (reprocess below this)
    delete_existing: bool = True  # Delete existing observations before reprocessing
    dry_run: bool = False  # Preview what would be reprocessed


@router.post("/api/devtools/reprocess-observations")
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
    2. Delete existing observations if delete_existing=True
    3. Reset processing flags on batches
    4. Queue batches for re-extraction in background

    After reprocessing, run POST /api/devtools/rebuild-memories to sync ChromaDB.
    """
    state = get_state()
    if not state.activity_store:
        raise HTTPException(status_code=503, detail="Activity store not initialized")
    if not state.activity_processor:
        raise HTTPException(status_code=503, detail="Activity processor not initialized")

    store = state.activity_store
    machine_id = get_machine_identifier()

    # Build query to get batch IDs based on mode
    # Always filter by source_machine_id to only touch our own data
    batch_ids: list[int] = []

    try:
        conn = store._get_connection()

        if request.mode == "all":
            # All completed user batches from this machine
            cursor = conn.execute(
                """
                SELECT id FROM prompt_batches
                WHERE source_machine_id = ?
                  AND status = 'completed'
                  AND source_type = 'user'
                ORDER BY created_at_epoch ASC
                """,
                (machine_id,),
            )
            batch_ids = [row[0] for row in cursor.fetchall()]

        elif request.mode == "date_range":
            if not request.start_date or not request.end_date:
                raise HTTPException(
                    status_code=400,
                    detail="date_range mode requires start_date and end_date",
                )
            # Parse ISO dates to epoch
            start_epoch = datetime.fromisoformat(request.start_date).timestamp()
            end_epoch = datetime.fromisoformat(request.end_date).timestamp()

            cursor = conn.execute(
                """
                SELECT id FROM prompt_batches
                WHERE source_machine_id = ?
                  AND status = 'completed'
                  AND created_at_epoch >= ?
                  AND created_at_epoch <= ?
                ORDER BY created_at_epoch ASC
                """,
                (machine_id, start_epoch, end_epoch),
            )
            batch_ids = [row[0] for row in cursor.fetchall()]

        elif request.mode == "session":
            if not request.session_id:
                raise HTTPException(
                    status_code=400,
                    detail="session mode requires session_id",
                )
            # Check session belongs to this machine
            cursor = conn.execute(
                """
                SELECT id FROM sessions
                WHERE id = ? AND source_machine_id = ?
                """,
                (request.session_id, machine_id),
            )
            if not cursor.fetchone():
                raise HTTPException(
                    status_code=404,
                    detail=f"Session not found or not owned by this machine: {request.session_id}",
                )

            cursor = conn.execute(
                """
                SELECT id FROM prompt_batches
                WHERE session_id = ?
                  AND source_machine_id = ?
                  AND status = 'completed'
                ORDER BY created_at_epoch ASC
                """,
                (request.session_id, machine_id),
            )
            batch_ids = [row[0] for row in cursor.fetchall()]

        elif request.mode == "low_importance":
            threshold = request.importance_threshold or 4
            # Find batches that have observations below the threshold
            cursor = conn.execute(
                """
                SELECT DISTINCT pb.id
                FROM prompt_batches pb
                JOIN memory_observations mo ON mo.prompt_batch_id = pb.id
                WHERE pb.source_machine_id = ?
                  AND pb.status = 'completed'
                  AND mo.importance < ?
                ORDER BY pb.created_at_epoch ASC
                """,
                (machine_id, threshold),
            )
            batch_ids = [row[0] for row in cursor.fetchall()]

        else:
            valid_modes = "all, date_range, session, low_importance"
            raise HTTPException(
                status_code=400,
                detail=f"Invalid mode: {request.mode}. Use: {valid_modes}",
            )

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
    existing_obs_count = 0
    try:
        placeholders = ",".join("?" * len(batch_ids))
        cursor = conn.execute(
            f"""
            SELECT COUNT(*) FROM memory_observations
            WHERE prompt_batch_id IN ({placeholders})
              AND source_machine_id = ?
            """,
            (*batch_ids, machine_id),
        )
        existing_obs_count = cursor.fetchone()[0]
    except sqlite3.Error:
        pass  # Non-critical - just for reporting

    # Delete existing observations and reset batch flags
    deleted_count = 0
    if request.delete_existing:
        try:
            with store._transaction() as tx_conn:
                # Delete observations for these batches (only from this machine)
                placeholders = ",".join("?" * len(batch_ids))
                cursor = tx_conn.execute(
                    f"""
                    DELETE FROM memory_observations
                    WHERE prompt_batch_id IN ({placeholders})
                      AND source_machine_id = ?
                    """,
                    (*batch_ids, machine_id),
                )
                deleted_count = cursor.rowcount

                # Reset processed flag on batches
                tx_conn.execute(
                    f"""
                    UPDATE prompt_batches
                    SET processed = FALSE, classification = NULL
                    WHERE id IN ({placeholders})
                    """,
                    batch_ids,
                )

            logger.info(
                f"Deleted {deleted_count} observations and reset {len(batch_ids)} batches "
                f"for reprocessing (machine={machine_id})"
            )

        except sqlite3.Error as e:
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
