"""Team server API routes.

Provides endpoints for event push/pull, member registration,
member listing, and server health status.

All endpoints except ``/status`` require team API key authentication.
"""

import logging
import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from open_agent_kit.features.codebase_intelligence.constants.team import (
    TEAM_LOG_JOIN_APPROVED,
    TEAM_LOG_JOIN_REJECTED,
    TEAM_LOG_JOIN_REQUEST_CREATED,
    TEAM_LOG_JOIN_STATUS_POLL,
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
    JoinRequest,
    JoinRequestResponse,
    JoinRequestStatus,
    PendingJoinInfo,
    PushResult,
    TeamEventBatch,
    TeamMemberInfo,
    TeamPullRequest,
)
from open_agent_kit.features.codebase_intelligence.team.server.auth import (
    approve_key,
    create_pending_key,
    get_key_join_status,
    list_pending_keys,
    reject_key,
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


# ---------------------------------------------------------------------------
# Join request / approval flow
# ---------------------------------------------------------------------------


@router.post("/request-join")
async def request_join(req: JoinRequest) -> JoinRequestResponse:
    """Submit a join request -- unauthenticated.

    The client generates its own API key locally, computes a SHA-256 hash,
    and sends only the hash. The server stores the hash as a pending key.
    """
    conn = _get_conn()
    name = f"join:{req.machine_id}"
    key_id = create_pending_key(
        conn,
        name=name,
        key_hash=req.key_hash,
        machine_id=req.machine_id,
        display_name=req.display_name,
    )
    logger.info(TEAM_LOG_JOIN_REQUEST_CREATED.format(key_id=key_id, machine_id=req.machine_id))
    return JoinRequestResponse(key_id=key_id)


@router.get("/pending-joins")
async def get_pending_joins(
    machine_id: str = Depends(verify_team_token),
) -> list[PendingJoinInfo]:
    """List pending join requests -- authenticated (server admin)."""
    conn = _get_conn()
    keys = list_pending_keys(conn)
    return [
        PendingJoinInfo(
            key_id=k.id,
            name=k.name,
            machine_id=k.machine_id or "",
            display_name=k.display_name or "",
            created_at=k.created_at,
        )
        for k in keys
    ]


@router.post("/approve-join/{key_id}")
async def approve_join(
    key_id: str,
    machine_id: str = Depends(verify_team_token),
) -> dict[str, bool]:
    """Approve a pending join request -- authenticated (server admin)."""
    conn = _get_conn()
    success = approve_key(conn, key_id)
    if not success:
        raise HTTPException(status_code=404, detail="Pending key not found")
    logger.info(TEAM_LOG_JOIN_APPROVED.format(key_id=key_id))
    return {"approved": True}


@router.post("/reject-join/{key_id}")
async def reject_join(
    key_id: str,
    machine_id: str = Depends(verify_team_token),
) -> dict[str, bool]:
    """Reject a pending join request -- authenticated (server admin)."""
    conn = _get_conn()
    success = reject_key(conn, key_id)
    if not success:
        raise HTTPException(status_code=404, detail="Key not found")
    logger.info(TEAM_LOG_JOIN_REJECTED.format(key_id=key_id))
    return {"rejected": True}


@router.get("/join-status/{key_id}")
async def get_join_status(key_id: str) -> JoinRequestStatus:
    """Poll join request status -- unauthenticated (client polling)."""
    conn = _get_conn()
    status = get_key_join_status(conn, key_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Key not found")
    logger.debug(TEAM_LOG_JOIN_STATUS_POLL.format(key_id=key_id, status=status))
    return JoinRequestStatus(key_id=key_id, status=status)
