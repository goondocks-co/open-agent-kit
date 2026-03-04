"""Activity routes for browsing SQLite activity data.

This module provides the core API endpoints for viewing:
- Sessions (Claude Code sessions from launch to exit)
- Session agents and members
- Prompt batches and activities
- Search, stats

Plan routes live in ``activity_plans.py``.
Processing routes (reprocess-memories, promote) live in ``activity_processing.py``.
Session lifecycle (lineage, linking, completion, summary) routes live in
``activity_sessions.py``.  Relationship routes live in
``activity_relationships.py``.  Delete routes live in
``activity_management.py``.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from open_agent_kit.features.team.constants import (
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
from open_agent_kit.features.team.daemon.models import (
    ActivityListResponse,
    ActivitySearchResponse,
    SessionDetailResponse,
    SessionListResponse,
)
from open_agent_kit.features.team.daemon.routes._utils import (
    activity_to_item,
    get_resume_command,
    handle_route_errors,
    prompt_batch_to_item,
    session_to_item,
)
from open_agent_kit.features.team.daemon.state import get_state

logger = logging.getLogger(__name__)

router = APIRouter(tags=["activity"])


@router.get("/api/activity/sessions", response_model=SessionListResponse)
@handle_route_errors("list sessions")
async def list_sessions(
    limit: int = Query(
        default=PAGINATION_DEFAULT_LIMIT, ge=PAGINATION_MIN_LIMIT, le=PAGINATION_SESSIONS_MAX
    ),
    offset: int = Query(default=PAGINATION_DEFAULT_OFFSET, ge=0),
    status: str | None = Query(default=None, description="Filter by status (active, completed)"),
    agent: str | None = Query(default=None, description="Filter by agent (claude, codex, etc.)"),
    member: str | None = Query(default=None, description="Filter by team member username"),
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
        f"agent={agent}, member={member}, sort={sort}"
    )

    # Get sessions from activity store with SQL-level pagination and status filter
    sessions = state.activity_store.get_recent_sessions(
        limit=limit,
        offset=offset,
        status=status,
        agent=agent,
        sort=sort,
        member=member,
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

    # Get plan counts in bulk for inline plan access
    try:
        plan_counts_map = state.activity_store.get_bulk_plan_counts(session_ids)
    except (OSError, ValueError, RuntimeError):
        plan_counts_map = {}

    # Build response with stats, first prompts, child counts, and plan counts
    items = []
    for session in sessions:
        stats = stats_map.get(session.id, {})
        first_prompt = first_prompts_map.get(session.id)
        child_count = child_counts_map.get(session.id, 0)
        plan_count = plan_counts_map.get(session.id, 0)
        items.append(
            session_to_item(session, stats, first_prompt, child_count, plan_count=plan_count)
        )

    # Get accurate total count
    from open_agent_kit.features.team.activity.store.sessions import (
        count_sessions,
    )

    total = count_sessions(
        state.activity_store,
        status=status,
        agent=agent,
        member=member,
    )

    return SessionListResponse(
        sessions=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/api/activity/session-agents")
@handle_route_errors("list session agents")
async def list_session_agents() -> dict[str, list[str]]:
    """List coding agents for session filtering.

    Returns the union of package agents (from manifest.yaml files) and
    agents that have actual sessions in the activity store. This ensures
    agents like "oak" (ACP sessions) appear in the filter even though
    they don't have a package manifest.
    """
    from open_agent_kit.services.agent_service import AgentService

    agent_service = AgentService()
    agents: set[str] = set(agent_service.list_available_agents())

    # Also include agents that have sessions in the activity store
    state = get_state()
    if state.activity_store is not None:
        try:
            _columns, rows = state.activity_store.execute_readonly_query(
                "SELECT DISTINCT agent FROM sessions"
            )
            for row in rows:
                if row[0]:
                    agents.add(row[0])
        except (OSError, ValueError, RuntimeError):
            logger.debug("Failed to query session agents from DB, using manifests only")

    return {"agents": sorted(agents)}


@router.get("/api/activity/session-members")
@handle_route_errors("list session members")
async def list_session_members() -> dict:
    """List team members who have sessions (extracted from source_machine_id).

    The source_machine_id format is ``{github_username}_{6char_hash}``.
    This endpoint extracts unique usernames and returns them alongside
    the current machine's ID so the frontend can identify "me".
    """
    state = get_state()

    if not state.activity_store:
        raise HTTPException(status_code=503, detail=ERROR_MSG_ACTIVITY_STORE_NOT_INITIALIZED)

    machine_ids = state.activity_store.get_session_members()

    # Extract unique usernames: drop last 7 chars (separator + 6-char hash)
    seen: dict[str, str] = {}
    for mid in machine_ids:
        username = mid[:-7] if len(mid) > 7 else mid
        if username not in seen:
            seen[username] = mid

    members = [{"username": u, "machine_id": m} for u, m in sorted(seen.items())]
    return {"members": members, "current_machine_id": state.machine_id}


@router.get("/api/activity/sessions/{session_id}", response_model=SessionDetailResponse)
@handle_route_errors("get session")
async def get_session(session_id: str) -> SessionDetailResponse:
    """Get detailed session information including stats and recent activities."""
    from open_agent_kit.features.team.activity.store.sessions import (
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
    activity_items = [activity_to_item(a) for a in activities]

    # Get prompt batches
    batches = state.activity_store.get_session_prompt_batches(session_id)
    batch_items = []
    for batch in batches:
        if batch.id is None:
            continue
        batch_stats = state.activity_store.get_prompt_batch_stats(batch.id)
        batch_items.append(prompt_batch_to_item(batch, batch_stats.get("activity_count", 0)))

    # Get first prompt preview for session title
    first_prompts_map = state.activity_store.get_bulk_first_prompts([session_id])
    first_prompt = first_prompts_map.get(session_id)

    # Get resume command from agent manifest
    resume_command = get_resume_command(session.agent, session_id)

    return SessionDetailResponse(
        session=session_to_item(
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

    items = [activity_to_item(a) for a in activities]

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

    items = [activity_to_item(a) for a in activities]

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

    items = [activity_to_item(a) for a in activities]

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
