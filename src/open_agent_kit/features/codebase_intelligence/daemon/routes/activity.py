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

from open_agent_kit.features.codebase_intelligence.daemon.constants import (
    ErrorMessages,
    Pagination,
    SessionStatus,
    Timing,
)
from open_agent_kit.features.codebase_intelligence.daemon.models import (
    ActivityItem,
    ActivityListResponse,
    ActivitySearchResponse,
    DeleteActivityResponse,
    DeleteBatchResponse,
    DeleteSessionResponse,
    DismissSuggestionResponse,
    LinkSessionRequest,
    LinkSessionResponse,
    PlanListItem,
    PlansListResponse,
    PromptBatchItem,
    ReembedSessionsResponse,
    RefreshPlanResponse,
    RegenerateSummaryResponse,
    SessionDetailResponse,
    SessionItem,
    SessionLineageItem,
    SessionLineageResponse,
    SessionListResponse,
    SuggestedParentResponse,
    UnlinkSessionResponse,
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


def _session_to_item(
    session: Session,
    stats: dict | None = None,
    first_prompt_preview: str | None = None,
    child_session_count: int = 0,
    summary_text: str | None = None,
) -> SessionItem:
    """Convert Session dataclass to SessionItem Pydantic model.

    Args:
        session: Session dataclass from the store.
        stats: Session statistics dict.
        first_prompt_preview: Preview of the first prompt.
        child_session_count: Number of child sessions.
        summary_text: Optional summary text from observations (overrides session.summary).
    """
    # Use summary_text from observations if provided, otherwise fall back to session.summary
    summary = summary_text if summary_text is not None else session.summary
    return SessionItem(
        id=session.id,
        agent=session.agent,
        project_root=session.project_root,
        started_at=session.started_at,
        ended_at=session.ended_at,
        status=session.status,
        summary=summary,
        title=session.title,
        first_prompt_preview=first_prompt_preview,
        prompt_batch_count=stats.get("prompt_batch_count", 0) if stats else 0,
        activity_count=stats.get("activity_count", 0) if stats else 0,
        parent_session_id=session.parent_session_id,
        parent_session_reason=session.parent_session_reason,
        child_session_count=child_session_count,
    )


def _session_to_lineage_item(
    session: Session,
    first_prompt_preview: str | None = None,
    prompt_batch_count: int = 0,
) -> SessionLineageItem:
    """Convert Session dataclass to SessionLineageItem for lineage display."""
    return SessionLineageItem(
        id=session.id,
        title=session.title,
        first_prompt_preview=first_prompt_preview,
        started_at=session.started_at,
        ended_at=session.ended_at,
        status=session.status,
        parent_session_reason=session.parent_session_reason,
        prompt_batch_count=prompt_batch_count,
    )


def _prompt_batch_to_item(batch: PromptBatch, activity_count: int = 0) -> PromptBatchItem:
    """Convert PromptBatch dataclass to PromptBatchItem Pydantic model."""
    return PromptBatchItem(
        id=str(batch.id) if batch.id is not None else "",
        session_id=batch.session_id,
        prompt_number=batch.prompt_number,
        user_prompt=batch.user_prompt,
        classification=batch.classification,
        source_type=batch.source_type,
        plan_file_path=batch.plan_file_path,
        plan_content=batch.plan_content,
        started_at=batch.started_at,
        ended_at=batch.ended_at,
        activity_count=activity_count,
    )


def _extract_plan_title(batch: PromptBatch) -> str:
    """Extract a title from a plan batch.

    Tries in order:
    1. First markdown heading (# Title) from plan_content
    2. Filename from plan_file_path
    3. Fallback to "Plan #{batch_id}"
    """
    import re

    # Try to extract first heading from plan_content
    if batch.plan_content:
        # Match first markdown heading (# or ##)
        heading_match = re.search(r"^#+ +(.+)$", batch.plan_content, re.MULTILINE)
        if heading_match:
            return heading_match.group(1).strip()

    # Try filename from plan_file_path
    if batch.plan_file_path:
        from pathlib import Path

        filename = Path(batch.plan_file_path).stem
        # Convert kebab-case or snake_case to title case
        title = filename.replace("-", " ").replace("_", " ").title()
        return title

    # Fallback
    return f"Plan #{batch.id}" if batch.id else "Untitled Plan"


def _plan_to_item(batch: PromptBatch) -> PlanListItem:
    """Convert a plan PromptBatch to PlanListItem."""
    # Get preview from plan_content (first 200 chars, skip heading)
    preview = ""
    if batch.plan_content:
        import re

        # Remove first heading line and get next 200 chars
        content = re.sub(r"^#+ +.+\n*", "", batch.plan_content, count=1).strip()
        preview = content[:200]
        if len(content) > 200:
            preview += "..."

    return PlanListItem(
        id=batch.id if batch.id is not None else 0,
        title=_extract_plan_title(batch),
        session_id=batch.session_id,
        created_at=batch.started_at,
        file_path=batch.plan_file_path,
        preview=preview,
        plan_embedded=batch.plan_embedded,
    )


@router.get("/api/activity/plans", response_model=PlansListResponse)
async def list_plans(
    limit: int = Query(
        default=Pagination.DEFAULT_LIMIT, ge=Pagination.MIN_LIMIT, le=Pagination.SESSIONS_MAX
    ),
    offset: int = Query(default=Pagination.DEFAULT_OFFSET, ge=0),
    session_id: str | None = Query(default=None, description="Filter by session"),
    sort: str = Query(
        default="created",
        description="Sort order: created (newest first, default) or created_asc (oldest first)",
    ),
) -> PlansListResponse:
    """List plans from prompt_batches (direct SQLite, not ChromaDB).

    Plans are prompt batches with source_type='plan' that contain design documents
    created during plan mode sessions.
    """
    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ErrorMessages.ACTIVITY_STORE_NOT_INITIALIZED)

    logger.debug(
        f"Listing plans: limit={limit}, offset={offset}, session_id={session_id}, sort={sort}"
    )

    try:
        plans, total = state.activity_store.get_plans(
            limit=limit,
            offset=offset,
            session_id=session_id,
            sort=sort,
        )

        items = [_plan_to_item(batch) for batch in plans]

        return PlansListResponse(
            plans=items,
            total=total,
            limit=limit,
            offset=offset,
        )

    except (OSError, ValueError, RuntimeError, AttributeError) as e:
        logger.error(f"Failed to list plans: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/api/activity/plans/{batch_id}/refresh", response_model=RefreshPlanResponse)
async def refresh_plan_from_source(batch_id: int) -> RefreshPlanResponse:
    """Re-read plan content from source file on disk.

    This is useful when a plan file has been edited outside of the normal
    plan mode workflow (e.g., manual edits) and you want to update the
    stored content in the CI database.

    Also marks the plan as unembedded so it will be re-indexed.

    Args:
        batch_id: The prompt batch ID containing the plan.

    Returns:
        RefreshPlanResponse with updated content length.

    Raises:
        HTTPException: If batch not found, has no plan file, or file not found.
    """
    from pathlib import Path

    from open_agent_kit.features.codebase_intelligence.constants import PROMPT_SOURCE_PLAN

    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ErrorMessages.ACTIVITY_STORE_NOT_INITIALIZED)

    logger.info(f"Refreshing plan from disk: batch_id={batch_id}")

    try:
        # Get the batch
        batch = state.activity_store.get_prompt_batch(batch_id)
        if not batch:
            raise HTTPException(status_code=404, detail="Plan batch not found")

        # Verify it's a plan with a file path
        if batch.source_type != "plan":
            raise HTTPException(
                status_code=400,
                detail=f"Batch {batch_id} is not a plan (source_type={batch.source_type})",
            )

        if not batch.plan_file_path:
            raise HTTPException(
                status_code=400,
                detail=f"Plan batch {batch_id} has no file path - content may be embedded in prompt",
            )

        # Resolve the file path
        plan_path = Path(batch.plan_file_path)
        if not plan_path.is_absolute() and state.project_root:
            plan_path = state.project_root / plan_path

        if not plan_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Plan file not found: {batch.plan_file_path}",
            )

        # Read fresh content from disk
        final_content = plan_path.read_text(encoding="utf-8")

        # Update the batch with fresh content
        state.activity_store.update_prompt_batch_source_type(
            batch_id,
            PROMPT_SOURCE_PLAN,
            plan_file_path=batch.plan_file_path,
            plan_content=final_content,
        )

        # Mark as unembedded for re-indexing
        state.activity_store.mark_plan_unembedded(batch_id)

        logger.info(
            f"Refreshed plan batch {batch_id} from {batch.plan_file_path} "
            f"({len(final_content)} chars)"
        )

        return RefreshPlanResponse(
            success=True,
            batch_id=batch_id,
            plan_file_path=batch.plan_file_path,
            content_length=len(final_content),
            message=f"Plan refreshed from disk ({len(final_content)} chars)",
        )

    except HTTPException:
        raise
    except (OSError, ValueError, RuntimeError, AttributeError) as e:
        logger.error(f"Failed to refresh plan: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/api/activity/sessions", response_model=SessionListResponse)
async def list_sessions(
    limit: int = Query(
        default=Pagination.DEFAULT_LIMIT, ge=Pagination.MIN_LIMIT, le=Pagination.SESSIONS_MAX
    ),
    offset: int = Query(default=Pagination.DEFAULT_OFFSET, ge=0),
    status: str | None = Query(default=None, description="Filter by status (active, completed)"),
    sort: str = Query(
        default="last_activity",
        description="Sort order: last_activity (default), created, or status",
    ),
) -> SessionListResponse:
    """List recent sessions with optional status filter.

    Returns sessions ordered by the specified sort order (default: last_activity).
    """
    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ErrorMessages.ACTIVITY_STORE_NOT_INITIALIZED)

    logger.debug(f"Listing sessions: limit={limit}, offset={offset}, status={status}, sort={sort}")

    try:
        # Get sessions from activity store with SQL-level pagination and status filter
        sessions = state.activity_store.get_recent_sessions(
            limit=limit, offset=offset, status=status, sort=sort
        )

        # Get stats in bulk (1 query instead of N queries) - eliminates N+1 pattern
        session_ids = [s.id for s in sessions]
        try:
            stats_map = state.activity_store.get_bulk_session_stats(session_ids)
        except (OSError, ValueError, RuntimeError):
            stats_map = {}

        # Get first prompts in bulk for session titles
        try:
            first_prompts_map = state.activity_store.get_bulk_first_prompts(session_ids)
        except (OSError, ValueError, RuntimeError):
            first_prompts_map = {}

        # Build response with stats and first prompts for each session
        items = []
        for session in sessions:
            stats = stats_map.get(session.id, {})
            first_prompt = first_prompts_map.get(session.id)
            items.append(_session_to_item(session, stats, first_prompt))

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
    from open_agent_kit.features.codebase_intelligence.activity.store.sessions import (
        get_child_session_count,
    )

    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ErrorMessages.ACTIVITY_STORE_NOT_INITIALIZED)

    logger.debug(f"Getting session: {session_id}")

    try:
        # Get session
        session = state.activity_store.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=ErrorMessages.SESSION_NOT_FOUND)

        # Get stats
        stats = state.activity_store.get_session_stats(session_id)

        # Get child session count for lineage info
        child_count = get_child_session_count(state.activity_store, session_id)

        # Get session summary from observations (source of truth)
        summary_obs = state.activity_store.get_latest_session_summary(session_id)
        summary_text = summary_obs.observation if summary_obs else None

        # Get recent activities
        activities = state.activity_store.get_session_activities(
            session_id=session_id, limit=Pagination.DEFAULT_LIMIT * 2
        )
        activity_items = [_activity_to_item(a) for a in activities]

        # Get prompt batches
        batches = state.activity_store.get_session_prompt_batches(session_id)
        batch_items = []
        for batch in batches:
            if batch.id is None:
                continue
            batch_stats = state.activity_store.get_prompt_batch_stats(batch.id)
            batch_items.append(_prompt_batch_to_item(batch, batch_stats.get("activity_count", 0)))

        # Get first prompt preview for session title
        first_prompts_map = state.activity_store.get_bulk_first_prompts([session_id])
        first_prompt = first_prompts_map.get(session_id)

        return SessionDetailResponse(
            session=_session_to_item(session, stats, first_prompt, child_count, summary_text),
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
    limit: int = Query(
        default=Pagination.DEFAULT_LIMIT * 2, ge=Pagination.MIN_LIMIT, le=Pagination.ACTIVITIES_MAX
    ),
    offset: int = Query(default=Pagination.DEFAULT_OFFSET, ge=0),
    tool_name: str | None = Query(default=None, description="Filter by tool name"),
) -> ActivityListResponse:
    """List activities for a specific session."""
    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ErrorMessages.ACTIVITY_STORE_NOT_INITIALIZED)

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
    limit: int = Query(
        default=Pagination.DEFAULT_LIMIT * 2, ge=Pagination.MIN_LIMIT, le=Pagination.ACTIVITIES_MAX
    ),
) -> ActivityListResponse:
    """List activities for a specific prompt batch."""
    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ErrorMessages.ACTIVITY_STORE_NOT_INITIALIZED)

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
    limit: int = Query(
        default=Pagination.DEFAULT_LIMIT * 2, ge=Pagination.MIN_LIMIT, le=Pagination.SEARCH_MAX
    ),
) -> ActivitySearchResponse:
    """Full-text search across activities.

    Uses SQLite FTS5 to search tool inputs, outputs, and file paths.
    """
    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ErrorMessages.ACTIVITY_STORE_NOT_INITIALIZED)

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
        raise HTTPException(status_code=503, detail=ErrorMessages.ACTIVITY_STORE_NOT_INITIALIZED)

    try:
        # Get recent sessions to calculate stats
        sessions = state.activity_store.get_recent_sessions(limit=Pagination.STATS_SESSION_LIMIT)

        total_sessions = len(sessions)
        active_sessions = len([s for s in sessions if s.status == SessionStatus.ACTIVE])
        completed_sessions = len([s for s in sessions if s.status == SessionStatus.COMPLETED])

        # Calculate total activities and tool breakdown
        total_activities = 0
        tool_counts: dict[str, int] = {}

        for session in sessions[
            : Pagination.STATS_DETAIL_LIMIT
        ]:  # Limit to recent sessions for perf
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
        raise HTTPException(status_code=503, detail=ErrorMessages.ACTIVITY_STORE_NOT_INITIALIZED)

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
            message += f" Memories will be regenerated in the next processing cycle ({Timing.MEMORY_PROCESS_INTERVAL_SECONDS}s)."

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


@router.post("/api/activity/prompt-batches/{batch_id}/promote")
async def promote_batch_to_memory(batch_id: int) -> dict:
    """Promote an agent batch to extract memories using LLM.

    This endpoint allows manual promotion of background agent findings to the
    memory store. Agent batches (source_type='agent_notification') are normally
    skipped during memory extraction to prevent pollution. This endpoint forces
    user-style LLM extraction on those batches.

    Use this when a background agent discovered something valuable that should
    be preserved in the memory store for future sessions.

    Args:
        batch_id: The prompt batch ID to promote.

    Returns:
        Dictionary with promotion results including observation count.

    Raises:
        HTTPException: If batch not found, not promotable, or processing fails.
    """
    from open_agent_kit.features.codebase_intelligence.activity.processor import (
        promote_agent_batch_async,
    )

    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ErrorMessages.ACTIVITY_STORE_NOT_INITIALIZED)

    if not state.activity_processor:
        raise HTTPException(
            status_code=503,
            detail="Activity processor not initialized - LLM extraction unavailable",
        )

    logger.info(f"Promoting agent batch to memory: {batch_id}")

    try:
        # Check batch exists
        batch = state.activity_store.get_prompt_batch(batch_id)
        if not batch:
            raise HTTPException(status_code=404, detail="Prompt batch not found")

        # Promote using async wrapper
        result = await promote_agent_batch_async(state.activity_processor, batch_id)

        if not result.success:
            raise HTTPException(
                status_code=400,
                detail=result.error or "Failed to promote batch",
            )

        return {
            "success": True,
            "batch_id": batch_id,
            "observations_extracted": result.observations_extracted,
            "activities_processed": result.activities_processed,
            "classification": result.classification,
            "duration_ms": result.duration_ms,
            "message": f"Promoted batch {batch_id}: {result.observations_extracted} observations extracted",
        }

    except HTTPException:
        raise
    except (OSError, ValueError, RuntimeError, AttributeError) as e:
        logger.error(f"Failed to promote batch: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# =============================================================================
# Delete Endpoints
# =============================================================================


@router.delete("/api/activity/sessions/{session_id}", response_model=DeleteSessionResponse)
async def delete_session(session_id: str) -> DeleteSessionResponse:
    """Delete a session and all related data (cascade delete).

    Deletes:
    - The session record
    - All prompt batches for this session
    - All activities for this session
    - All memory observations for this session (SQLite + ChromaDB)
    """
    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ErrorMessages.ACTIVITY_STORE_NOT_INITIALIZED)

    logger.info(f"Deleting session: {session_id}")

    try:
        # Check session exists
        session = state.activity_store.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=ErrorMessages.SESSION_NOT_FOUND)

        # Get observation IDs for ChromaDB cleanup before deleting from SQLite
        observation_ids = state.activity_store.get_session_observation_ids(session_id)

        # Delete from SQLite (cascade)
        result = state.activity_store.delete_session(session_id)

        # Delete from ChromaDB
        memories_deleted = 0
        if observation_ids and state.vector_store:
            memories_deleted = state.vector_store.delete_memories(observation_ids)

        logger.info(
            f"Deleted session {session_id}: "
            f"{result['batches_deleted']} batches, "
            f"{result['activities_deleted']} activities, "
            f"{result['observations_deleted']} SQLite observations, "
            f"{memories_deleted} ChromaDB memories"
        )

        return DeleteSessionResponse(
            success=True,
            deleted_count=1,
            message=f"Session {session_id[:8]}... deleted successfully",
            batches_deleted=result["batches_deleted"],
            activities_deleted=result["activities_deleted"],
            memories_deleted=result["observations_deleted"],
        )

    except HTTPException:
        raise
    except (OSError, ValueError, RuntimeError, AttributeError) as e:
        logger.error(f"Failed to delete session: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete(
    "/api/activity/prompt-batches/{batch_id}",
    response_model=DeleteBatchResponse,
)
async def delete_prompt_batch(batch_id: int) -> DeleteBatchResponse:
    """Delete a prompt batch and all related data (cascade delete).

    Deletes:
    - The prompt batch record
    - All activities for this batch
    - All memory observations for this batch (SQLite + ChromaDB)
    """
    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ErrorMessages.ACTIVITY_STORE_NOT_INITIALIZED)

    logger.info(f"Deleting prompt batch: {batch_id}")

    try:
        # Check batch exists
        batch = state.activity_store.get_prompt_batch(batch_id)
        if not batch:
            raise HTTPException(status_code=404, detail="Prompt batch not found")

        # Get observation IDs for ChromaDB cleanup before deleting from SQLite
        observation_ids = state.activity_store.get_batch_observation_ids(batch_id)

        # Delete from SQLite (cascade)
        result = state.activity_store.delete_prompt_batch(batch_id)

        # Delete from ChromaDB
        memories_deleted = 0
        if observation_ids and state.vector_store:
            memories_deleted = state.vector_store.delete_memories(observation_ids)

        logger.info(
            f"Deleted prompt batch {batch_id}: "
            f"{result['activities_deleted']} activities, "
            f"{result['observations_deleted']} SQLite observations, "
            f"{memories_deleted} ChromaDB memories"
        )

        return DeleteBatchResponse(
            success=True,
            deleted_count=1,
            message=f"Prompt batch {batch_id} deleted successfully",
            activities_deleted=result["activities_deleted"],
            memories_deleted=result["observations_deleted"],
        )

    except HTTPException:
        raise
    except (OSError, ValueError, RuntimeError, AttributeError) as e:
        logger.error(f"Failed to delete prompt batch: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete(
    "/api/activity/activities/{activity_id}",
    response_model=DeleteActivityResponse,
)
async def delete_activity(activity_id: int) -> DeleteActivityResponse:
    """Delete a single activity.

    If the activity has a linked observation, also deletes it from SQLite and ChromaDB.
    """
    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ErrorMessages.ACTIVITY_STORE_NOT_INITIALIZED)

    logger.info(f"Deleting activity: {activity_id}")

    try:
        # Delete activity and get linked observation_id (if any)
        observation_id = state.activity_store.delete_activity(activity_id)

        if observation_id is None:
            raise HTTPException(status_code=404, detail="Activity not found")

        # If there was a linked observation, delete it too
        memory_deleted = False
        if observation_id:
            state.activity_store.delete_observation(observation_id)
            if state.vector_store:
                state.vector_store.delete_memories([observation_id])
            memory_deleted = True
            logger.info(f"Also deleted linked observation: {observation_id}")

        return DeleteActivityResponse(
            success=True,
            deleted_count=1,
            message=f"Activity {activity_id} deleted successfully",
            memory_deleted=memory_deleted,
        )

    except HTTPException:
        raise
    except (OSError, ValueError, RuntimeError, AttributeError) as e:
        logger.error(f"Failed to delete activity: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# =============================================================================
# Session Linking Endpoints
# =============================================================================


@router.get(
    "/api/activity/sessions/{session_id}/lineage",
    response_model=SessionLineageResponse,
)
async def get_session_lineage(session_id: str) -> SessionLineageResponse:
    """Get the lineage (ancestors and children) of a session.

    Returns the ancestry chain (parent, grandparent, etc.) and direct children
    of the specified session. Useful for understanding session relationships
    created through clear/compact cycles or manual linking.
    """
    from open_agent_kit.features.codebase_intelligence.activity.store.sessions import (
        get_child_sessions,
    )
    from open_agent_kit.features.codebase_intelligence.activity.store.sessions import (
        get_session_lineage as store_get_lineage,
    )

    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ErrorMessages.ACTIVITY_STORE_NOT_INITIALIZED)

    logger.debug(f"Getting lineage for session: {session_id}")

    try:
        # Get the session first to verify it exists
        session = state.activity_store.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=ErrorMessages.SESSION_NOT_FOUND)

        # Get ancestors (returns [self, parent, grandparent, ...])
        lineage = store_get_lineage(state.activity_store, session_id)

        # Get children
        children = get_child_sessions(state.activity_store, session_id)

        # Get first prompts for all sessions in lineage and children
        all_session_ids = [s.id for s in lineage] + [c.id for c in children]
        first_prompts_map = state.activity_store.get_bulk_first_prompts(all_session_ids)
        stats_map = state.activity_store.get_bulk_session_stats(all_session_ids)

        # Convert ancestors (skip self - first item)
        ancestor_items = []
        for ancestor in lineage[1:]:  # Skip self
            ancestor_items.append(
                _session_to_lineage_item(
                    ancestor,
                    first_prompt_preview=first_prompts_map.get(ancestor.id),
                    prompt_batch_count=stats_map.get(ancestor.id, {}).get("prompt_batch_count", 0),
                )
            )

        # Convert children
        child_items = [
            _session_to_lineage_item(
                child,
                first_prompt_preview=first_prompts_map.get(child.id),
                prompt_batch_count=stats_map.get(child.id, {}).get("prompt_batch_count", 0),
            )
            for child in children
        ]

        return SessionLineageResponse(
            session_id=session_id,
            ancestors=ancestor_items,
            children=child_items,
        )

    except HTTPException:
        raise
    except (OSError, ValueError, RuntimeError, AttributeError) as e:
        logger.error(f"Failed to get session lineage: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post(
    "/api/activity/sessions/{session_id}/link",
    response_model=LinkSessionResponse,
)
async def link_session(session_id: str, request: LinkSessionRequest) -> LinkSessionResponse:
    """Link a session to a parent session.

    Creates a parent-child relationship between sessions. This is useful for
    manually connecting related sessions that weren't automatically linked
    during clear/compact operations.

    Validates that:
    - Both sessions exist
    - The link would not create a cycle
    - The session doesn't already have this parent
    """
    from open_agent_kit.features.codebase_intelligence.activity.store.sessions import (
        update_session_parent,
        would_create_cycle,
    )

    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ErrorMessages.ACTIVITY_STORE_NOT_INITIALIZED)

    logger.info(f"Linking session {session_id} to parent {request.parent_session_id}")

    try:
        # Verify child session exists
        child_session = state.activity_store.get_session(session_id)
        if not child_session:
            raise HTTPException(status_code=404, detail=ErrorMessages.SESSION_NOT_FOUND)

        # Verify parent session exists
        parent_session = state.activity_store.get_session(request.parent_session_id)
        if not parent_session:
            raise HTTPException(status_code=404, detail="Parent session not found")

        # Check if already linked to this parent
        if child_session.parent_session_id == request.parent_session_id:
            return LinkSessionResponse(
                success=True,
                session_id=session_id,
                parent_session_id=request.parent_session_id,
                reason=request.reason,
                message="Session already linked to this parent",
            )

        # Check for cycles
        if would_create_cycle(state.activity_store, session_id, request.parent_session_id):
            raise HTTPException(
                status_code=400,
                detail="Cannot link: would create a cycle in the session lineage",
            )

        # Create the link
        update_session_parent(
            state.activity_store,
            session_id,
            request.parent_session_id,
            request.reason,
        )

        return LinkSessionResponse(
            success=True,
            session_id=session_id,
            parent_session_id=request.parent_session_id,
            reason=request.reason,
            message="Session linked to parent successfully",
        )

    except HTTPException:
        raise
    except (OSError, ValueError, RuntimeError, AttributeError) as e:
        logger.error(f"Failed to link session: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete(
    "/api/activity/sessions/{session_id}/link",
    response_model=UnlinkSessionResponse,
)
async def unlink_session(session_id: str) -> UnlinkSessionResponse:
    """Remove the parent link from a session.

    Clears the parent_session_id and parent_session_reason fields,
    making this session a root session in its lineage.
    """
    from open_agent_kit.features.codebase_intelligence.activity.store.sessions import (
        clear_session_parent,
    )

    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ErrorMessages.ACTIVITY_STORE_NOT_INITIALIZED)

    logger.info(f"Unlinking session {session_id} from parent")

    try:
        # Verify session exists
        session = state.activity_store.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=ErrorMessages.SESSION_NOT_FOUND)

        # Check if already unlinked
        if not session.parent_session_id:
            return UnlinkSessionResponse(
                success=True,
                session_id=session_id,
                previous_parent_id=None,
                message="Session has no parent link to remove",
            )

        # Clear the link
        previous_parent = clear_session_parent(state.activity_store, session_id)

        return UnlinkSessionResponse(
            success=True,
            session_id=session_id,
            previous_parent_id=previous_parent,
            message="Session unlinked from parent successfully",
        )

    except HTTPException:
        raise
    except (OSError, ValueError, RuntimeError, AttributeError) as e:
        logger.error(f"Failed to unlink session: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get(
    "/api/activity/sessions/{session_id}/suggested-parent",
    response_model=SuggestedParentResponse,
)
async def get_suggested_parent(session_id: str) -> SuggestedParentResponse:
    """Get the suggested parent session for an unlinked session.

    Uses vector similarity search and optional LLM refinement to find
    the most likely parent session for manual linking.

    Returns suggestion info if found, or has_suggestion=False if:
    - Session already has a parent
    - Session has no summary for similarity search
    - No suitable candidate sessions found
    - Suggestion was previously dismissed
    """
    from open_agent_kit.features.codebase_intelligence.activity.processor.suggestions import (
        compute_suggested_parent,
    )

    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ErrorMessages.ACTIVITY_STORE_NOT_INITIALIZED)

    if not state.vector_store:
        raise HTTPException(status_code=503, detail="Vector store not initialized")

    logger.debug(f"Getting suggested parent for session: {session_id}")

    try:
        # Verify session exists
        session = state.activity_store.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=ErrorMessages.SESSION_NOT_FOUND)

        # Check if suggestion was dismissed
        conn = state.activity_store._get_connection()
        cursor = conn.execute(
            "SELECT suggested_parent_dismissed FROM sessions WHERE id = ?",
            (session_id,),
        )
        row = cursor.fetchone()
        dismissed = bool(row and row[0]) if row else False

        if dismissed:
            return SuggestedParentResponse(
                session_id=session_id,
                has_suggestion=False,
                dismissed=True,
            )

        # Compute suggestion (without LLM for now - just vector similarity)
        # LLM refinement can be added later when call_llm is available
        suggestion = compute_suggested_parent(
            activity_store=state.activity_store,
            vector_store=state.vector_store,
            session_id=session_id,
            call_llm=None,  # Vector-only for now
        )

        if not suggestion:
            return SuggestedParentResponse(
                session_id=session_id,
                has_suggestion=False,
                dismissed=False,
            )

        # Get suggested parent session details
        suggested_session = state.activity_store.get_session(suggestion.session_id)
        if not suggested_session:
            return SuggestedParentResponse(
                session_id=session_id,
                has_suggestion=False,
                dismissed=False,
            )

        # Get first prompt preview for the suggested session
        first_prompts_map = state.activity_store.get_bulk_first_prompts([suggestion.session_id])
        stats_map = state.activity_store.get_bulk_session_stats([suggestion.session_id])

        suggested_item = _session_to_lineage_item(
            suggested_session,
            first_prompt_preview=first_prompts_map.get(suggestion.session_id),
            prompt_batch_count=stats_map.get(suggestion.session_id, {}).get(
                "prompt_batch_count", 0
            ),
        )

        return SuggestedParentResponse(
            session_id=session_id,
            has_suggestion=True,
            suggested_parent=suggested_item,
            confidence=suggestion.confidence,
            confidence_score=suggestion.confidence_score,
            reason=suggestion.reason,
            dismissed=False,
        )

    except HTTPException:
        raise
    except (OSError, ValueError, RuntimeError, AttributeError) as e:
        logger.error(f"Failed to get suggested parent: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post(
    "/api/activity/sessions/{session_id}/dismiss-suggestion",
    response_model=DismissSuggestionResponse,
)
async def dismiss_suggestion(session_id: str) -> DismissSuggestionResponse:
    """Dismiss the suggestion for a session.

    Marks the session so that no suggestion will be shown until the user
    manually links or the dismissal is reset.
    """
    from open_agent_kit.features.codebase_intelligence.activity.processor.suggestions import (
        dismiss_suggestion as store_dismiss_suggestion,
    )

    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ErrorMessages.ACTIVITY_STORE_NOT_INITIALIZED)

    logger.info(f"Dismissing suggestion for session: {session_id}")

    try:
        # Verify session exists
        session = state.activity_store.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=ErrorMessages.SESSION_NOT_FOUND)

        success = store_dismiss_suggestion(state.activity_store, session_id)

        if success:
            return DismissSuggestionResponse(
                success=True,
                session_id=session_id,
                message="Suggestion dismissed successfully",
            )
        else:
            return DismissSuggestionResponse(
                success=False,
                session_id=session_id,
                message="Failed to dismiss suggestion",
            )

    except HTTPException:
        raise
    except (OSError, ValueError, RuntimeError, AttributeError) as e:
        logger.error(f"Failed to dismiss suggestion: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post(
    "/api/activity/reembed-sessions",
    response_model=ReembedSessionsResponse,
)
async def reembed_sessions() -> ReembedSessionsResponse:
    """Re-embed all session summaries to ChromaDB.

    Useful after:
    - Backup restore (sessions exist in SQLite but not in ChromaDB)
    - Embedding model changes
    - Index corruption

    Clears existing session summary embeddings and re-embeds from SQLite.
    """
    from open_agent_kit.features.codebase_intelligence.activity.processor.session_index import (
        reembed_session_summaries,
    )

    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ErrorMessages.ACTIVITY_STORE_NOT_INITIALIZED)

    if not state.vector_store:
        raise HTTPException(status_code=503, detail="Vector store not initialized")

    logger.info("Re-embedding all session summaries")

    try:
        sessions_processed, sessions_embedded = reembed_session_summaries(
            activity_store=state.activity_store,
            vector_store=state.vector_store,
            clear_first=True,
        )

        return ReembedSessionsResponse(
            success=True,
            sessions_processed=sessions_processed,
            sessions_embedded=sessions_embedded,
            message=f"Re-embedded {sessions_embedded}/{sessions_processed} session summaries",
        )

    except (OSError, ValueError, RuntimeError, AttributeError) as e:
        logger.error(f"Failed to re-embed sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# =============================================================================
# Summary Regeneration Endpoint
# =============================================================================


@router.post(
    "/api/activity/sessions/{session_id}/regenerate-summary",
    response_model=RegenerateSummaryResponse,
)
async def regenerate_session_summary(session_id: str) -> RegenerateSummaryResponse:
    """Regenerate the summary and title for a specific session.

    Triggers LLM-based summary generation for the session. The session must:
    - Exist
    - Have at least some activity (tool calls)

    Note: This will overwrite any existing summary and title for the session.
    The title is regenerated from the summary for better accuracy.
    """
    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ErrorMessages.ACTIVITY_STORE_NOT_INITIALIZED)

    if not state.activity_processor:
        raise HTTPException(
            status_code=503,
            detail="Activity processor not initialized - LLM summarization unavailable",
        )

    logger.info(f"Regenerating summary and title for session: {session_id}")

    try:
        # Verify session exists
        session = state.activity_store.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=ErrorMessages.SESSION_NOT_FOUND)

        # Get session stats to check if it has enough data
        stats = state.activity_store.get_session_stats(session_id)
        activity_count = stats.get("activity_count", 0)

        if activity_count < 3:
            return RegenerateSummaryResponse(
                success=False,
                session_id=session_id,
                summary=None,
                title=None,
                message=f"Insufficient data: session has only {activity_count} activities (minimum 3 required)",
            )

        # Generate the summary and title (force regenerate both)
        summary, title = state.activity_processor.process_session_summary_with_title(
            session_id, regenerate_title=True
        )

        if summary:
            logger.info(f"Regenerated summary and title for session {session_id[:8]}")
            return RegenerateSummaryResponse(
                success=True,
                session_id=session_id,
                summary=summary,
                title=title,
                message="Summary and title regenerated successfully",
            )
        else:
            return RegenerateSummaryResponse(
                success=False,
                session_id=session_id,
                summary=None,
                title=None,
                message="Failed to generate summary - check logs for details",
            )

    except HTTPException:
        raise
    except (OSError, ValueError, RuntimeError, AttributeError) as e:
        logger.error(f"Failed to regenerate session summary: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
