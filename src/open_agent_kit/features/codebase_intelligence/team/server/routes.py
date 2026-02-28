"""Team server API routes.

Provides endpoints for event push/pull, member registration,
member listing, and server health status.

All endpoints except ``/status`` require team API key authentication.
"""

import logging
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from open_agent_kit.features.codebase_intelligence.constants.team import (
    TEAM_API_PATH_RECONCILE,
    TEAM_JOIN_STATUS_APPROVED,
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
    approve_join_request,
    create_pending_key,
    find_key_by_hash,
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


def _apply_events_locally(events: list) -> None:
    """Apply pushed events to the server's own activity store.

    Uses TeamEventApplier which writes via direct SQL (not store_observation)
    to avoid triggering outbox hooks and infinite sync loops.
    """
    from open_agent_kit.features.codebase_intelligence.daemon.state import get_state
    from open_agent_kit.features.codebase_intelligence.team.pull.applier import TeamEventApplier

    state = get_state()
    if state.activity_store is None:
        return
    try:
        applier = TeamEventApplier(state.activity_store)
        result = applier.apply_batch(events)
        if result.applied > 0:
            logger.debug("Applied %d pushed events to local store", result.applied)
    except Exception:
        logger.exception("Failed to apply pushed events locally")


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

    # Apply events to the server's own activity store so sessions/observations
    # from remote members appear in the server's dashboard.
    if accepted > 0:
        _apply_events_locally(batch.events)

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


@router.post("/members/heartbeat")
async def member_heartbeat(
    machine_id: str = Depends(verify_team_token),
) -> dict:
    """Update member presence without pushing events.

    Called by idle clients to keep their last_seen timestamp current
    so they don't appear offline when the outbox queue is empty.
    """
    svc = _get_membership_service()
    svc.update_last_seen(machine_id)
    return {"ok": True}


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

    Idempotent: if a non-revoked key with the same hash already exists,
    returns its current status instead of creating a duplicate.
    """
    conn = _get_conn()

    # Check for existing key with this hash (idempotent re-join)
    existing = find_key_by_hash(conn, req.key_hash)
    if existing and existing.revoked_at is None:
        # Already approved — return approved status
        if existing.approved_at is not None:
            return JoinRequestResponse(
                key_id=existing.id,
                status=TEAM_JOIN_STATUS_APPROVED,
            )
        # Still pending — return existing key_id
        return JoinRequestResponse(key_id=existing.id)

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

    success, key_info = approve_join_request(conn, key_id)
    if key_info is None:
        raise HTTPException(status_code=404, detail="Pending key not found")
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


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------


class ReconcileRequest(BaseModel):
    source_machine_id: str  # whose data to check
    content_hashes: list[str]  # hashes the client already has from that machine


class ReconcileResponse(BaseModel):
    missing_from_client: list[str]  # hashes server has that client doesn't


@router.post(TEAM_API_PATH_RECONCILE)
async def reconcile(
    req: ReconcileRequest,
    machine_id: str = Depends(verify_team_token),
) -> ReconcileResponse:
    """Return content_hashes present on the server but missing from the client."""
    conn = _get_conn()
    server_hashes = {
        row["content_hash"]
        for row in conn.execute(
            "SELECT DISTINCT content_hash FROM team_events "
            "WHERE source_machine_id = ? AND content_hash IS NOT NULL",
            (req.source_machine_id,),
        ).fetchall()
    }

    client_set = set(req.content_hashes)
    missing = list(server_hashes - client_set)

    return ReconcileResponse(missing_from_client=missing)
