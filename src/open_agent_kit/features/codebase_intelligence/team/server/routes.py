"""Team server API routes.

Provides endpoints for event push/pull, member registration,
member listing, and server health status.

All endpoints except ``/status`` require team API key authentication.
"""

import logging
import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from open_agent_kit.features.codebase_intelligence.constants.team import (
    TEAM_PULL_DEFAULT_LIMIT,
    TEAM_ROUTE_TAG,
    TEAM_ROUTER_PREFIX,
    TEAM_SERVER_LOG_EVENT_DEDUP,
    TEAM_SERVER_LOG_EVENT_STORED,
    TEAM_SERVER_LOG_MEMBER_REGISTERED,
    TEAM_SERVER_STATUS_KEY_SERVER_MODE,
    TEAM_SERVER_STATUS_OK,
)
from open_agent_kit.features.codebase_intelligence.team.protocol import (
    PushResult,
    TeamEventBatch,
    TeamMemberInfo,
    TeamPullRequest,
)
from open_agent_kit.features.codebase_intelligence.team.server.auth import (
    verify_team_token,
)
from open_agent_kit.features.codebase_intelligence.team.server.cursors import (
    get_events_since,
    get_latest_cursor,
    store_events,
)
from open_agent_kit.features.codebase_intelligence.team.server.membership import (
    MembershipService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix=TEAM_ROUTER_PREFIX, tags=[TEAM_ROUTE_TAG])


def _get_conn() -> sqlite3.Connection:
    """Get database connection from daemon state."""
    from open_agent_kit.features.codebase_intelligence.daemon.state import get_state

    state = get_state()
    if state.activity_store is None:
        raise HTTPException(status_code=503, detail="Activity store not initialized")
    return state.activity_store._get_connection()


def _get_membership_service() -> MembershipService:
    """Get a MembershipService backed by the daemon's database."""
    return MembershipService(conn_factory=_get_conn)


@router.post("/events/push")
async def push_events(
    batch: TeamEventBatch, machine_id: str = Depends(verify_team_token)
) -> PushResult:
    """Receive batched events from a team member, dedup by content_hash."""
    conn = _get_conn()
    total = len(batch.events)

    accepted = store_events(
        conn, batch.events, project_id=batch.events[0].project_id if batch.events else ""
    )

    rejected = total - accepted
    if accepted > 0:
        logger.info(TEAM_SERVER_LOG_EVENT_STORED.format(count=accepted, machine_id=machine_id))
    if rejected > 0:
        logger.debug(TEAM_SERVER_LOG_EVENT_DEDUP.format(count=rejected))

    # Update membership tracking
    svc = _get_membership_service()
    svc.update_last_seen(machine_id)
    if accepted > 0:
        svc.increment_event_count(machine_id, accepted)

    cursor = get_latest_cursor(conn)

    return PushResult(accepted=accepted, rejected=rejected, cursor=cursor)


@router.post("/events/pull")
async def pull_events(
    request: TeamPullRequest, machine_id: str = Depends(verify_team_token)
) -> TeamEventBatch:
    """Return events since cursor, excluding the requester's own events."""
    conn = _get_conn()

    # Use the requester's machine_id as exclude if the request asks for it
    exclude = request.exclude_machine_id or machine_id
    limit = min(request.limit, TEAM_PULL_DEFAULT_LIMIT)

    events, new_cursor = get_events_since(
        conn,
        cursor=request.since_cursor,
        limit=limit,
        exclude_machine=exclude,
    )

    return TeamEventBatch(events=events, cursor=new_cursor)


@router.post("/members/register")
async def register_member(
    info: TeamMemberInfo, machine_id: str = Depends(verify_team_token)
) -> TeamMemberInfo:
    """Register or update a team member."""
    svc = _get_membership_service()
    member = svc.register(
        machine_id=info.machine_id,
        display_name=info.display_name,
        project_id=info.project_id,
    )
    logger.info(
        TEAM_SERVER_LOG_MEMBER_REGISTERED.format(
            machine_id=info.machine_id, display_name=info.display_name
        )
    )
    return member


@router.get("/members")
async def list_members(
    machine_id: str = Depends(verify_team_token),
) -> list[TeamMemberInfo]:
    """List all registered team members."""
    svc = _get_membership_service()
    return svc.list_members()


@router.get("/status")
async def server_status() -> dict:
    """Server health check -- no auth required for connectivity testing."""
    return {
        "status": TEAM_SERVER_STATUS_OK,
        TEAM_SERVER_STATUS_KEY_SERVER_MODE: True,
    }
