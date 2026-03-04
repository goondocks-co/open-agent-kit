"""Devtools processing routes (observation reprocessing, summaries, cleanup).

This module provides API endpoints for:
- Memory statistics (sync status between SQLite and ChromaDB)
- Triggering background processing manually
- Reprocessing observations with updated extraction prompts
- Regenerating session summaries
- Cleaning up minimal/low-quality sessions
- Resolving stale observations

Split from ``devtools.py`` to keep route files under 500 lines.
"""

import logging
import sqlite3
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from open_agent_kit.features.team.activity.store import sessions
from open_agent_kit.features.team.constants import (
    DEFAULT_SUMMARIZATION_MODEL,
    MIN_SESSION_ACTIVITIES,
)
from open_agent_kit.features.team.daemon.routes.devtools import (
    require_devtools_confirm,
)
from open_agent_kit.features.team.daemon.state import get_state

logger = logging.getLogger(__name__)

router = APIRouter(tags=["devtools"])

# Per-endpoint dependency for destructive operations.
_devtools_confirm = [Depends(require_devtools_confirm)]


@router.get("/api/devtools/memory-stats")
async def get_memory_stats() -> dict[str, Any]:
    """Get detailed memory statistics for debugging sync issues."""
    state = get_state()
    if not state.activity_store:
        raise HTTPException(status_code=503, detail="Activity store not initialized")

    sqlite_total = state.activity_store.count_observations()
    sqlite_embedded = state.activity_store.count_embedded_observations()
    sqlite_unembedded = state.activity_store.count_unembedded_observations()
    sqlite_session_summaries = state.activity_store.count_sessions_with_summaries()

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
        sync_status = "orphaned"
    elif sync_difference < 0:
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
        "sync_difference": sync_difference,
        "needs_rebuild": (
            sqlite_unembedded > 0 or sqlite_plans_unembedded > 0 or sync_difference != 0
        ),
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

    This is a v1 stub -- full LLM-based analysis is future work.
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
