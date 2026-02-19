"""Activity routes for browsing SQLite activity data.

This module provides the core API endpoints for viewing:
- Plans (design documents from plan mode)
- Sessions (Claude Code sessions from launch to exit)
- Prompt batches (activities grouped by user prompt)
- Activities (raw tool execution events)
- Search, stats, reprocessing, and batch promotion

Session lifecycle (lineage, linking, completion, summary) routes live in
``activity_sessions.py``.  Relationship routes live in
``activity_relationships.py``.  Delete routes live in
``activity_management.py``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Query

from open_agent_kit.features.codebase_intelligence.constants import (
    DEFAULT_BACKGROUND_PROCESSING_INTERVAL_SECONDS,
    ERROR_MSG_ACTIVITY_STORE_NOT_INITIALIZED,
    ERROR_MSG_SESSION_NOT_FOUND,
    PAGINATION_ACTIVITIES_MAX,
    PAGINATION_DEFAULT_LIMIT,
    PAGINATION_DEFAULT_OFFSET,
    PAGINATION_MIN_LIMIT,
    PAGINATION_SEARCH_MAX,
    PAGINATION_SESSIONS_MAX,
    PAGINATION_STATS_DETAIL_LIMIT,
    PAGINATION_STATS_SESSION_LIMIT,
    SESSION_STATUS_ACTIVE,
    SESSION_STATUS_COMPLETED,
)
from open_agent_kit.features.codebase_intelligence.daemon.models import (
    ActivityItem,
    ActivityListResponse,
    ActivitySearchResponse,
    PlanListItem,
    PlansListResponse,
    PromptBatchItem,
    RefreshPlanResponse,
    SessionDetailResponse,
    SessionItem,
    SessionListResponse,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes._utils import (
    handle_route_errors,
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


def _resolve_resume_agent(agent: str) -> str:
    """Resolve captured agent label to manifest key for resume commands."""
    normalized_agent = agent.strip().lower()
    try:
        from open_agent_kit.services.agent_service import AgentService

        agent_service = AgentService()
        known_agents = sorted(agent_service.list_available_agents(), key=len, reverse=True)
        for known_agent in known_agents:
            if known_agent in normalized_agent:
                return known_agent
    except (OSError, ValueError, KeyError, AttributeError):
        logger.debug("Failed to resolve normalized agent label", exc_info=True)
    return normalized_agent


def _get_resume_command(agent: str, session_id: str) -> str | None:
    """Get the resolved resume command for a session.

    Looks up the agent manifest to get the resume_command template,
    then substitutes the session_id placeholder.

    Args:
        agent: Agent name (e.g., 'claude', 'codex').
        session_id: The session ID to substitute.

    Returns:
        Resolved resume command string, or None if not available.
    """
    try:
        from open_agent_kit.services.agent_service import AgentService

        agent_service = AgentService()
        manifest = agent_service.get_agent_manifest(_resolve_resume_agent(agent))
        if manifest and manifest.ci and manifest.ci.resume_command:
            return manifest.ci.resume_command.replace("{session_id}", session_id)
    except (OSError, ValueError, KeyError, AttributeError) as e:
        logger.debug(f"Failed to get resume command for agent {agent}: {e}")

    return None


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
    resume_command: str | None = None,
) -> SessionItem:
    """Convert Session dataclass to SessionItem Pydantic model.

    Args:
        session: Session dataclass from the store.
        stats: Session statistics dict.
        first_prompt_preview: Preview of the first prompt.
        child_session_count: Number of child sessions.
        summary_text: Optional summary text from observations (overrides session.summary).
        resume_command: Resolved resume command for this session (from agent manifest).
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
        title_manually_edited=session.title_manually_edited,
        first_prompt_preview=first_prompt_preview,
        prompt_batch_count=stats.get("prompt_batch_count", 0) if stats else 0,
        activity_count=stats.get("activity_count", 0) if stats else 0,
        parent_session_id=session.parent_session_id,
        parent_session_reason=session.parent_session_reason,
        child_session_count=child_session_count,
        resume_command=resume_command,
        summary_embedded=session.summary_embedded,
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
        response_summary=batch.response_summary,
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
@handle_route_errors("list plans")
async def list_plans(
    limit: int = Query(
        default=PAGINATION_DEFAULT_LIMIT, ge=PAGINATION_MIN_LIMIT, le=PAGINATION_SESSIONS_MAX
    ),
    offset: int = Query(default=PAGINATION_DEFAULT_OFFSET, ge=0),
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
        raise HTTPException(status_code=503, detail=ERROR_MSG_ACTIVITY_STORE_NOT_INITIALIZED)

    logger.debug(
        f"Listing plans: limit={limit}, offset={offset}, session_id={session_id}, sort={sort}"
    )

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


@router.post("/api/activity/plans/{batch_id}/refresh", response_model=RefreshPlanResponse)
@handle_route_errors("refresh plan")
async def refresh_plan_from_source(
    batch_id: int,
    graceful: bool = Query(default=False),
) -> RefreshPlanResponse:
    """Re-read plan content from source file on disk.

    This is useful when a plan file has been edited outside of the normal
    plan mode workflow (e.g., manual edits) and you want to update the
    stored content in the CI database.

    Also marks the plan as unembedded so it will be re-indexed.

    Args:
        batch_id: The prompt batch ID containing the plan.
        graceful: When True, return success=False instead of HTTP errors for
            expected conditions (file not found, no file path). Useful for
            automatic background refreshes where the plan file may not exist
            on the current machine.

    Returns:
        RefreshPlanResponse with updated content length.

    Raises:
        HTTPException: If batch not found, has no plan file, or file not found
            (only when graceful=False).
    """
    from pathlib import Path

    from open_agent_kit.features.codebase_intelligence.constants import PROMPT_SOURCE_PLAN

    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ERROR_MSG_ACTIVITY_STORE_NOT_INITIALIZED)

    logger.info(f"Refreshing plan from disk: batch_id={batch_id} graceful={graceful}")

    # Get the batch
    batch = state.activity_store.get_prompt_batch(batch_id)
    if not batch:
        if graceful:
            return RefreshPlanResponse(
                success=False,
                batch_id=batch_id,
                message="Plan batch not found",
            )
        raise HTTPException(status_code=404, detail="Plan batch not found")

    # Verify it's a plan with a file path
    if batch.source_type != "plan":
        if graceful:
            return RefreshPlanResponse(
                success=False,
                batch_id=batch_id,
                message=f"Batch {batch_id} is not a plan (source_type={batch.source_type})",
            )
        raise HTTPException(
            status_code=400,
            detail=f"Batch {batch_id} is not a plan (source_type={batch.source_type})",
        )

    if not batch.plan_file_path:
        if graceful:
            return RefreshPlanResponse(
                success=False,
                batch_id=batch_id,
                message="No file path - content may be embedded in prompt",
            )
        raise HTTPException(
            status_code=400,
            detail=f"Plan batch {batch_id} has no file path - content may be embedded in prompt",
        )

    # Resolve the file path
    plan_path = Path(batch.plan_file_path)
    if not plan_path.is_absolute() and state.project_root:
        plan_path = state.project_root / plan_path

    if not plan_path.exists():
        if graceful:
            return RefreshPlanResponse(
                success=False,
                batch_id=batch_id,
                plan_file_path=batch.plan_file_path,
                message=f"Plan file not found on disk: {batch.plan_file_path}",
            )
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


@router.get("/api/activity/sessions", response_model=SessionListResponse)
@handle_route_errors("list sessions")
async def list_sessions(
    limit: int = Query(
        default=PAGINATION_DEFAULT_LIMIT, ge=PAGINATION_MIN_LIMIT, le=PAGINATION_SESSIONS_MAX
    ),
    offset: int = Query(default=PAGINATION_DEFAULT_OFFSET, ge=0),
    status: str | None = Query(default=None, description="Filter by status (active, completed)"),
    agent: str | None = Query(default=None, description="Filter by agent (claude, codex, etc.)"),
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
        raise HTTPException(status_code=503, detail=ERROR_MSG_ACTIVITY_STORE_NOT_INITIALIZED)

    logger.debug(
        f"Listing sessions: limit={limit}, offset={offset}, status={status}, "
        f"agent={agent}, sort={sort}"
    )

    # Get sessions from activity store with SQL-level pagination and status filter
    sessions = state.activity_store.get_recent_sessions(
        limit=limit, offset=offset, status=status, agent=agent, sort=sort
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

    # Get child session counts in bulk for lineage indicators
    try:
        child_counts_map = state.activity_store.get_bulk_child_session_counts(session_ids)
    except (OSError, ValueError, RuntimeError):
        child_counts_map = {}

    # Build response with stats, first prompts, and child counts for each session
    items = []
    for session in sessions:
        stats = stats_map.get(session.id, {})
        first_prompt = first_prompts_map.get(session.id)
        child_count = child_counts_map.get(session.id, 0)
        items.append(_session_to_item(session, stats, first_prompt, child_count))

    # Get accurate total count
    from open_agent_kit.features.codebase_intelligence.activity.store.sessions import (
        count_sessions,
    )

    total = count_sessions(state.activity_store, status=status, agent=agent)

    return SessionListResponse(
        sessions=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/api/activity/session-agents")
@handle_route_errors("list session agents")
async def list_session_agents() -> dict[str, list[str]]:
    """List supported coding agents for session filtering."""
    from open_agent_kit.services.agent_service import AgentService

    agent_service = AgentService()
    agents = sorted(agent_service.list_available_agents())
    return {"agents": agents}


@router.get("/api/activity/sessions/{session_id}", response_model=SessionDetailResponse)
@handle_route_errors("get session")
async def get_session(session_id: str) -> SessionDetailResponse:
    """Get detailed session information including stats and recent activities."""
    from open_agent_kit.features.codebase_intelligence.activity.store.sessions import (
        get_child_session_count,
    )

    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ERROR_MSG_ACTIVITY_STORE_NOT_INITIALIZED)

    logger.debug(f"Getting session: {session_id}")

    # Get session
    session = state.activity_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=ERROR_MSG_SESSION_NOT_FOUND)

    # Get stats
    stats = state.activity_store.get_session_stats(session_id)

    # Get child session count for lineage info
    child_count = get_child_session_count(state.activity_store, session_id)

    # Session summary lives on the session object (source of truth)
    summary_text = session.summary

    # Get recent activities
    activities = state.activity_store.get_session_activities(
        session_id=session_id, limit=PAGINATION_DEFAULT_LIMIT * 2
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

    # Get resume command from agent manifest
    resume_command = _get_resume_command(session.agent, session_id)

    return SessionDetailResponse(
        session=_session_to_item(
            session, stats, first_prompt, child_count, summary_text, resume_command
        ),
        stats=stats,
        recent_activities=activity_items,
        prompt_batches=batch_items,
    )


@router.get(
    "/api/activity/sessions/{session_id}/activities",
    response_model=ActivityListResponse,
)
@handle_route_errors("list session activities")
async def list_session_activities(
    session_id: str,
    limit: int = Query(
        default=PAGINATION_DEFAULT_LIMIT * 2, ge=PAGINATION_MIN_LIMIT, le=PAGINATION_ACTIVITIES_MAX
    ),
    offset: int = Query(default=PAGINATION_DEFAULT_OFFSET, ge=0),
    tool_name: str | None = Query(default=None, description="Filter by tool name"),
) -> ActivityListResponse:
    """List activities for a specific session."""
    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ERROR_MSG_ACTIVITY_STORE_NOT_INITIALIZED)

    logger.debug(
        f"Listing activities for session {session_id}: "
        f"limit={limit}, offset={offset}, tool={tool_name}"
    )

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


@router.get(
    "/api/activity/prompt-batches/{batch_id}/activities",
    response_model=ActivityListResponse,
)
@handle_route_errors("list prompt batch activities")
async def list_prompt_batch_activities(
    batch_id: int,
    limit: int = Query(
        default=PAGINATION_DEFAULT_LIMIT * 2, ge=PAGINATION_MIN_LIMIT, le=PAGINATION_ACTIVITIES_MAX
    ),
) -> ActivityListResponse:
    """List activities for a specific prompt batch."""
    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ERROR_MSG_ACTIVITY_STORE_NOT_INITIALIZED)

    logger.debug(f"Listing activities for prompt batch {batch_id}")

    activities = state.activity_store.get_prompt_batch_activities(batch_id=batch_id, limit=limit)

    items = [_activity_to_item(a) for a in activities]

    return ActivityListResponse(
        activities=items,
        total=len(items),
        limit=limit,
        offset=0,
    )


@router.get("/api/activity/search", response_model=ActivitySearchResponse)
@handle_route_errors("search activities")
async def search_activities(
    query: str = Query(..., min_length=1, description="Search query"),
    session_id: str | None = Query(default=None, description="Limit to specific session"),
    limit: int = Query(
        default=PAGINATION_DEFAULT_LIMIT * 2, ge=PAGINATION_MIN_LIMIT, le=PAGINATION_SEARCH_MAX
    ),
) -> ActivitySearchResponse:
    """Full-text search across activities.

    Uses SQLite FTS5 to search tool inputs, outputs, and file paths.
    """
    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ERROR_MSG_ACTIVITY_STORE_NOT_INITIALIZED)

    logger.info(f"Searching activities: query='{query}', session={session_id}")

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


@router.get("/api/activity/stats")
@handle_route_errors("get activity stats")
async def get_activity_stats() -> dict:
    """Get overall activity statistics."""
    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ERROR_MSG_ACTIVITY_STORE_NOT_INITIALIZED)

    # Get recent sessions to calculate stats
    sessions = state.activity_store.get_recent_sessions(limit=PAGINATION_STATS_SESSION_LIMIT)

    total_sessions = len(sessions)
    active_sessions = len([s for s in sessions if s.status == SESSION_STATUS_ACTIVE])
    completed_sessions = len([s for s in sessions if s.status == SESSION_STATUS_COMPLETED])

    # Calculate total activities and tool breakdown
    total_activities = 0
    tool_counts: dict[str, int] = {}

    for session in sessions[:PAGINATION_STATS_DETAIL_LIMIT]:  # Limit to recent sessions for perf
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


@router.post("/api/activity/reprocess-memories")
@handle_route_errors("reprocess memories")
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
        raise HTTPException(status_code=503, detail=ERROR_MSG_ACTIVITY_STORE_NOT_INITIALIZED)

    # Use typed local variables to avoid mypy issues with dict value types
    batches_recovered = 0
    batches_queued = 0
    batches_processed = 0
    observations_created = 0
    message = ""

    # Steps 1-2: Recover stuck batches and queue for reprocessing
    batches_recovered, batches_queued = state.activity_store.queue_batches_for_reprocessing(
        batch_ids=batch_ids,
        recover_stuck=recover_stuck,
    )

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
        parts.append(f"processed {batches_processed} batches → {observations_created} observations")

    if parts:
        message = f"Reprocessing: {', '.join(parts)}."
    else:
        message = "No batches needed reprocessing."

    if not process_immediately and batches_queued > 0:
        message += f" Memories will be regenerated in the next processing cycle ({DEFAULT_BACKGROUND_PROCESSING_INTERVAL_SECONDS}s)."

    return {
        "success": True,
        "batches_recovered": batches_recovered,
        "batches_queued": batches_queued,
        "batches_processed": batches_processed,
        "observations_created": observations_created,
        "message": message,
    }


@router.post("/api/activity/prompt-batches/{batch_id}/promote")
@handle_route_errors("promote batch")
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
        raise HTTPException(status_code=503, detail=ERROR_MSG_ACTIVITY_STORE_NOT_INITIALIZED)

    if not state.activity_processor:
        raise HTTPException(
            status_code=503,
            detail="Activity processor not initialized - LLM extraction unavailable",
        )

    logger.info(f"Promoting agent batch to memory: {batch_id}")

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
