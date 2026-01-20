"""Activity routes for browsing SQLite activity data.

This module provides API endpoints for viewing:
- Sessions (Claude Code sessions from launch to exit)
- Prompt batches (activities grouped by user prompt)
- Activities (raw tool execution events)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Query

from open_agent_kit.features.codebase_intelligence.daemon.models import (
    ActivityItem,
    ActivityListResponse,
    ActivitySearchResponse,
    PromptBatchItem,
    SessionDetailResponse,
    SessionItem,
    SessionListResponse,
)
from open_agent_kit.features.codebase_intelligence.daemon.state import get_state

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.store import (
        Activity,
        PromptBatch,
        Session,
    )

logger = logging.getLogger(__name__)

router = APIRouter(tags=["activity"])


def _activity_to_item(activity: Activity) -> ActivityItem:
    """Convert Activity dataclass to ActivityItem Pydantic model."""
    return ActivityItem(
        id=str(activity.id) if activity.id is not None else "",
        session_id=activity.session_id,
        prompt_batch_id=str(activity.prompt_batch_id) if activity.prompt_batch_id else None,
        tool_name=activity.tool_name,
        tool_input=activity.tool_input,
        tool_output_summary=activity.tool_output_summary,
        file_path=activity.file_path,
        success=activity.success,
        error_message=activity.error_message,
        created_at=activity.timestamp,
    )


def _session_to_item(session: Session, stats: dict | None = None) -> SessionItem:
    """Convert Session dataclass to SessionItem Pydantic model."""
    return SessionItem(
        id=session.id,
        agent=session.agent,
        project_root=session.project_root,
        started_at=session.started_at,
        ended_at=session.ended_at,
        status=session.status,
        summary=session.summary,
        prompt_batch_count=stats.get("prompt_batch_count", 0) if stats else 0,
        activity_count=stats.get("activity_count", 0) if stats else 0,
    )


def _prompt_batch_to_item(batch: PromptBatch, activity_count: int = 0) -> PromptBatchItem:
    """Convert PromptBatch dataclass to PromptBatchItem Pydantic model."""
    return PromptBatchItem(
        id=str(batch.id) if batch.id is not None else "",
        session_id=batch.session_id,
        prompt_number=batch.prompt_number,
        user_prompt=batch.user_prompt,
        classification=batch.classification,
        started_at=batch.started_at,
        ended_at=batch.ended_at,
        activity_count=activity_count,
    )


@router.get("/api/activity/sessions", response_model=SessionListResponse)
async def list_sessions(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None, description="Filter by status (active, completed)"),
) -> SessionListResponse:
    """List recent sessions with optional status filter.

    Returns sessions ordered by start time (most recent first).
    """
    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail="Activity store not initialized")

    logger.debug(f"Listing sessions: limit={limit}, offset={offset}, status={status}")

    try:
        # Get sessions from activity store
        sessions = state.activity_store.get_recent_sessions(limit=limit + offset)

        # Apply offset manually (activity store doesn't support offset natively)
        sessions = sessions[offset : offset + limit]

        # Filter by status if provided
        if status:
            sessions = [s for s in sessions if s.status == status]

        # Build response with stats for each session
        items = []
        for session in sessions:
            try:
                stats = state.activity_store.get_session_stats(session.id)
            except (OSError, ValueError, RuntimeError):
                stats = {}
            items.append(_session_to_item(session, stats))

        # Get total count (approximation)
        total = len(items) + offset

        return SessionListResponse(
            sessions=items,
            total=total,
            limit=limit,
            offset=offset,
        )

    except (OSError, ValueError, RuntimeError, AttributeError) as e:
        logger.error(f"Failed to list sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/api/activity/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session(session_id: str) -> SessionDetailResponse:
    """Get detailed session information including stats and recent activities."""
    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail="Activity store not initialized")

    logger.debug(f"Getting session: {session_id}")

    try:
        # Get session
        session = state.activity_store.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Get stats
        stats = state.activity_store.get_session_stats(session_id)

        # Get recent activities
        activities = state.activity_store.get_session_activities(session_id=session_id, limit=50)
        activity_items = [_activity_to_item(a) for a in activities]

        # Get prompt batches
        batches = state.activity_store.get_session_prompt_batches(session_id)
        batch_items = []
        for batch in batches:
            if batch.id is None:
                continue
            batch_stats = state.activity_store.get_prompt_batch_stats(batch.id)
            batch_items.append(_prompt_batch_to_item(batch, batch_stats.get("activity_count", 0)))

        return SessionDetailResponse(
            session=_session_to_item(session, stats),
            stats=stats,
            recent_activities=activity_items,
            prompt_batches=batch_items,
        )

    except HTTPException:
        raise
    except (OSError, ValueError, RuntimeError, AttributeError) as e:
        logger.error(f"Failed to get session: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get(
    "/api/activity/sessions/{session_id}/activities",
    response_model=ActivityListResponse,
)
async def list_session_activities(
    session_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    tool_name: str | None = Query(default=None, description="Filter by tool name"),
) -> ActivityListResponse:
    """List activities for a specific session."""
    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail="Activity store not initialized")

    logger.debug(
        f"Listing activities for session {session_id}: "
        f"limit={limit}, offset={offset}, tool={tool_name}"
    )

    try:
        # Get activities
        activities = state.activity_store.get_session_activities(
            session_id=session_id,
            tool_name=tool_name,
            limit=limit + offset,
        )

        # Apply offset
        activities = activities[offset : offset + limit]

        items = [_activity_to_item(a) for a in activities]

        return ActivityListResponse(
            activities=items,
            total=len(items) + offset,
            limit=limit,
            offset=offset,
        )

    except (OSError, ValueError, RuntimeError, AttributeError) as e:
        logger.error(f"Failed to list session activities: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get(
    "/api/activity/prompt-batches/{batch_id}/activities",
    response_model=ActivityListResponse,
)
async def list_prompt_batch_activities(
    batch_id: int,
    limit: int = Query(default=50, ge=1, le=200),
) -> ActivityListResponse:
    """List activities for a specific prompt batch."""
    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail="Activity store not initialized")

    logger.debug(f"Listing activities for prompt batch {batch_id}")

    try:
        activities = state.activity_store.get_prompt_batch_activities(
            batch_id=batch_id, limit=limit
        )

        items = [_activity_to_item(a) for a in activities]

        return ActivityListResponse(
            activities=items,
            total=len(items),
            limit=limit,
            offset=0,
        )

    except (OSError, ValueError, RuntimeError, AttributeError) as e:
        logger.error(f"Failed to list prompt batch activities: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/api/activity/search", response_model=ActivitySearchResponse)
async def search_activities(
    query: str = Query(..., min_length=1, description="Search query"),
    session_id: str | None = Query(default=None, description="Limit to specific session"),
    limit: int = Query(default=50, ge=1, le=200),
) -> ActivitySearchResponse:
    """Full-text search across activities.

    Uses SQLite FTS5 to search tool inputs, outputs, and file paths.
    """
    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail="Activity store not initialized")

    logger.info(f"Searching activities: query='{query}', session={session_id}")

    try:
        activities = state.activity_store.search_activities(
            query=query,
            session_id=session_id,
            limit=limit,
        )

        items = [_activity_to_item(a) for a in activities]

        return ActivitySearchResponse(
            query=query,
            activities=items,
            total=len(items),
        )

    except (OSError, ValueError, RuntimeError, AttributeError) as e:
        logger.error(f"Failed to search activities: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/api/activity/stats")
async def get_activity_stats() -> dict:
    """Get overall activity statistics."""
    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail="Activity store not initialized")

    try:
        # Get recent sessions to calculate stats
        sessions = state.activity_store.get_recent_sessions(limit=100)

        total_sessions = len(sessions)
        active_sessions = len([s for s in sessions if s.status == "active"])
        completed_sessions = len([s for s in sessions if s.status == "completed"])

        # Calculate total activities and tool breakdown
        total_activities = 0
        tool_counts: dict[str, int] = {}

        for session in sessions[:20]:  # Limit to recent 20 for perf
            try:
                stats = state.activity_store.get_session_stats(session.id)
                total_activities += stats.get("activity_count", 0)
                for tool, count in stats.get("tool_counts", {}).items():
                    tool_counts[tool] = tool_counts.get(tool, 0) + count
            except (OSError, ValueError, RuntimeError):
                logger.debug(f"Failed to get stats for session {session.id}")

        return {
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
            "completed_sessions": completed_sessions,
            "total_activities": total_activities,
            "tool_breakdown": tool_counts,
        }

    except (OSError, ValueError, RuntimeError, AttributeError) as e:
        logger.error(f"Failed to get activity stats: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/api/activity/reprocess-memories")
async def reprocess_memories(
    batch_ids: list[int] | None = None,
    recover_stuck: bool = True,
    process_immediately: bool = False,
) -> dict:
    """Reprocess prompt batches to regenerate memories.

    This is a comprehensive reprocessing endpoint that handles all batch states:
    1. Recovers stuck batches (still in 'active' status)
    2. Resets 'processed' flag on completed batches
    3. Optionally triggers immediate processing instead of waiting for background cycle

    Args:
        batch_ids: Optional list of specific batch IDs to reprocess.
                  If not provided, all batches are eligible for reprocessing.
        recover_stuck: If True, also marks stuck 'active' batches as 'completed'.
        process_immediately: If True, triggers processing now instead of waiting.

    Returns:
        Dictionary with counts of batches recovered and queued for reprocessing.
    """
    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail="Activity store not initialized")

    # Use typed local variables to avoid mypy issues with dict value types
    batches_recovered = 0
    batches_queued = 0
    batches_processed = 0
    observations_created = 0
    message = ""

    try:
        conn = state.activity_store._get_connection()
        cursor = conn.cursor()

        # Step 1: Recover stuck batches (mark 'active' as 'completed')
        if recover_stuck:
            if batch_ids:
                placeholders = ",".join("?" * len(batch_ids))
                cursor.execute(
                    f"UPDATE prompt_batches SET status = 'completed' WHERE id IN ({placeholders}) AND status = 'active'",
                    batch_ids,
                )
            else:
                cursor.execute(
                    "UPDATE prompt_batches SET status = 'completed' WHERE status = 'active'"
                )
            batches_recovered = cursor.rowcount
            conn.commit()
            if batches_recovered > 0:
                logger.info(f"Recovered {batches_recovered} stuck batches")

        # Step 2: Reset processed flag on completed batches
        if batch_ids:
            placeholders = ",".join("?" * len(batch_ids))
            cursor.execute(
                f"UPDATE prompt_batches SET processed = 0 WHERE id IN ({placeholders}) AND status = 'completed'",
                batch_ids,
            )
        else:
            # Reset ALL completed batches, not just those with processed=1
            cursor.execute("UPDATE prompt_batches SET processed = 0 WHERE status = 'completed'")

        batches_queued = cursor.rowcount
        conn.commit()

        logger.info(f"Queued {batches_queued} prompt batches for memory reprocessing")

        # Step 3: Optionally trigger immediate processing
        if process_immediately and state.activity_processor:
            logger.info("Triggering immediate processing...")
            process_results = state.activity_processor.process_pending_batches(max_batches=100)
            batches_processed = len(process_results)
            observations_created = sum(r.observations_extracted for r in process_results)
            logger.info(
                f"Immediate processing: {batches_processed} batches → "
                f"{observations_created} observations"
            )

        # Build message
        parts = []
        if batches_recovered > 0:
            parts.append(f"recovered {batches_recovered} stuck batches")
        if batches_queued > 0:
            parts.append(f"queued {batches_queued} batches")
        if batches_processed > 0:
            parts.append(
                f"processed {batches_processed} batches → {observations_created} observations"
            )

        if parts:
            message = f"Reprocessing: {', '.join(parts)}."
        else:
            message = "No batches needed reprocessing."

        if not process_immediately and batches_queued > 0:
            message += " Memories will be regenerated in the next processing cycle (60s)."

        return {
            "success": True,
            "batches_recovered": batches_recovered,
            "batches_queued": batches_queued,
            "batches_processed": batches_processed,
            "observations_created": observations_created,
            "message": message,
        }

    except (OSError, ValueError, TypeError) as e:
        logger.error(f"Failed to queue batches for reprocessing: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
