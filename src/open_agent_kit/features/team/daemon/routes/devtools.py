"""Devtools routes for storage and index operations.

This module provides API endpoints for:
- Index rebuilding
- Processing state reset
- ChromaDB compaction
- Memory rebuilding and stats
- Orphan cleanup
- Database maintenance (vacuum, analyze, FTS optimize)
- Content hash backfilling

Processing-related routes (observation reprocessing, summaries, session cleanup,
stale observation resolution) live in ``devtools_processing.py``.
"""

import logging
import shutil
import sqlite3
import time
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from pydantic import BaseModel

from open_agent_kit.features.team.constants import (
    CI_DEVTOOLS_CONFIRM_HEADER,
    CI_DEVTOOLS_ERROR_CONFIRM_REQUIRED,
)
from open_agent_kit.features.team.daemon.state import get_state

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


class RebuildMemoriesRequest(BaseModel):
    full_rebuild: bool = True
    clear_chromadb_first: bool = False


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

    # ChromaDB cleanup stays in the route -- the store layer doesn't hold
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


@router.post("/api/devtools/compact-chromadb", dependencies=_devtools_confirm)
async def compact_chromadb() -> dict[str, Any]:
    """Compact ChromaDB by deleting directory, then signal frontend to restart.

    ChromaDB's in-process WAL locks and HNSW file handles don't fully
    release even after ``client.reset()`` -- so we only do the *delete*
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

    # ChromaDB compaction now requires a daemon restart -- use the dedicated endpoint
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
