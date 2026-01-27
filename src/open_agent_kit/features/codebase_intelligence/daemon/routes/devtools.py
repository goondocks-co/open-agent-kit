import logging
import sqlite3
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from open_agent_kit.features.codebase_intelligence.constants import (
    DEFAULT_SUMMARIZATION_MODEL,
)
from open_agent_kit.features.codebase_intelligence.daemon.models import MemoryType
from open_agent_kit.features.codebase_intelligence.daemon.state import get_state

router = APIRouter(tags=["devtools"])
logger = logging.getLogger(__name__)


class RebuildIndexRequest(BaseModel):
    full_rebuild: bool = True


class ResetProcessingRequest(BaseModel):
    delete_memories: bool = True


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

    try:
        with store._transaction() as conn:
            # 1. Delete generated memories if requested
            if request.delete_memories:
                conn.execute("DELETE FROM memory_observations")
                # Also clear ChromaDB memories?
                # Ideally yes, but that's expensive to find them all in Chroma.
                # However, since we deleted the source of truth, the next indexing
                # loop might remove them if it syncs, OR we should explicitly wipe chroma memories.
                # For now, let's just wipe the SQLite source.
                # The User can use "Rebuild Index" (which re-indexed code)
                # but we might need a "Wipe Memory Vector Store" too.
                # Assuming simple reset for now.

            # 2. Reset sessions
            conn.execute(
                "UPDATE sessions SET processed = FALSE, summary = NULL WHERE status = 'completed'"
            )

            # 3. Reset prompt batches
            conn.execute(
                "UPDATE prompt_batches SET processed = FALSE, classification = NULL WHERE status = 'completed'"
            )

            # 4. Reset activities
            conn.execute("UPDATE activities SET processed = FALSE")

            logger.info("Reset processing state via DevTools")

    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}") from e

    return {
        "status": "success",
        "message": "Processing state reset. Background jobs will pick this up.",
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

    # Check for sync issues
    sync_status = "synced"
    if total_expected_in_chromadb != chromadb_count:
        sync_status = "out_of_sync"
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
        "needs_rebuild": (
            sqlite_unembedded > 0
            or sqlite_plans_unembedded > 0
            or total_expected_in_chromadb != chromadb_count
        ),
    }


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
