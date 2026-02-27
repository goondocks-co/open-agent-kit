"""Team management API routes for the dashboard UI.

These routes handle local team configuration, sync status, and
policy management. They are always included (both client and server mode).

Server-only endpoints (API key management) check the
``OAK_CI_TEAM_SERVER`` env var at request time.
"""

import hashlib
import logging
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from open_agent_kit.features.codebase_intelligence.constants.team import (
    TEAM_API_PATH_APPROVE_JOIN,
    TEAM_API_PATH_CONFIG,
    TEAM_API_PATH_JOIN,
    TEAM_API_PATH_JOIN_STATUS,
    TEAM_API_PATH_KEYS,
    TEAM_API_PATH_LEAVE,
    TEAM_API_PATH_PENDING_JOINS,
    TEAM_API_PATH_POLICY,
    TEAM_API_PATH_REJECT_JOIN,
    TEAM_API_PATH_SERVE,
    TEAM_API_PATH_STATUS,
    TEAM_API_PATH_SYNC_FLUSH,
    TEAM_API_PATH_SYNC_PULL,
    TEAM_JOIN_STATUS_APPROVED,
    TEAM_LOOPBACK_KEY_NAME,
    TEAM_LOOPBACK_URL_TEMPLATE,
    TEAM_ROUTE_TAG,
    TEAM_ROUTER_PREFIX,
    TEAM_SERVER_MODE_ENV_VAR,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes._utils import (
    handle_route_errors,
)
from open_agent_kit.features.codebase_intelligence.daemon.state import get_state

logger = logging.getLogger(__name__)

router = APIRouter(tags=[TEAM_ROUTE_TAG])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class TeamConfigResponse(BaseModel):
    """Current team configuration (read-only view, API key excluded)."""

    server_url: str | None = None
    auto_sync: bool = False
    sync_interval_seconds: int = 3
    pull_interval_seconds: int = 15
    project_slug: str | None = None
    transport: str = "direct"
    server_mode: bool = False


class TeamConfigUpdate(BaseModel):
    """Partial update for team configuration."""

    server_url: str | None = None
    api_key: str | None = None
    auto_sync: bool | None = None
    sync_interval_seconds: int | None = None
    pull_interval_seconds: int | None = None
    project_slug: str | None = None
    transport: str | None = None


class TeamJoinRequest(BaseModel):
    """Request body for joining a team server.

    The client no longer sends an API key -- one is auto-generated at
    startup and sent as a SHA-256 hash during the join request.
    """

    server_url: str


class TeamStatusResponse(BaseModel):
    """Overall team status (connection, sync workers)."""

    configured: bool = False
    server_url: str | None = None
    connected: bool = False
    project_id: str | None = None
    sync: dict[str, Any] | None = None
    members_online: int = 0
    pending_approval: bool = False
    pending_key_id: str | None = None


class PolicyResponse(BaseModel):
    """Data-collection policy (governance.data_collection)."""

    collect_activities: bool = True
    collect_prompts: bool = True
    sync_observations: bool = True
    sync_activities: bool = False
    sync_prompts: bool = False
    allow_server_llm: bool = False


class PolicyUpdate(BaseModel):
    """Partial update for data-collection policy."""

    collect_activities: bool | None = None
    collect_prompts: bool | None = None
    sync_observations: bool | None = None
    sync_activities: bool | None = None
    sync_prompts: bool | None = None
    allow_server_llm: bool | None = None


class ServerModeRequest(BaseModel):
    """Request body for toggling server mode."""

    enable: bool


class KeyCreateRequest(BaseModel):
    """Request body to create an API key (server mode only)."""

    name: str


class KeyResponse(BaseModel):
    """Metadata for an existing API key (no plaintext)."""

    id: str
    name: str
    machine_id: str | None = None
    created_at: str
    last_used_at: str | None = None
    revoked_at: str | None = None
    permissions: str = "member"


class KeyCreateResponse(BaseModel):
    """Response after creating a new API key. Contains the plaintext key."""

    id: str
    name: str
    key: str  # Plaintext, shown only once


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_project_root() -> Path:
    """Return project_root from state or raise 500."""
    state = get_state()
    if not state.project_root:
        raise HTTPException(status_code=500, detail="Project root not set")
    return state.project_root


def _require_server_mode() -> None:
    """Raise 403 if not running as team server."""
    if not os.environ.get(TEAM_SERVER_MODE_ENV_VAR):
        raise HTTPException(status_code=403, detail="Server mode only")


def _require_activity_store() -> Any:
    """Return activity_store from state or raise 500."""
    state = get_state()
    if not state.activity_store:
        raise HTTPException(status_code=500, detail="Store not initialized")
    return state.activity_store


# ---------------------------------------------------------------------------
# Config routes
# ---------------------------------------------------------------------------


@router.get(TEAM_API_PATH_CONFIG)
@handle_route_errors("team config get")
async def get_team_config() -> TeamConfigResponse:
    """Return current team configuration (API key excluded)."""
    state = get_state()
    ci_config = state.ci_config
    if not ci_config:
        return TeamConfigResponse()
    tc = ci_config.team
    return TeamConfigResponse(
        server_url=tc.server_url,
        auto_sync=tc.auto_sync,
        sync_interval_seconds=tc.sync_interval_seconds,
        pull_interval_seconds=tc.pull_interval_seconds,
        project_slug=tc.project_slug,
        transport=tc.transport,
        server_mode=tc.server_mode,
    )


@router.post(TEAM_API_PATH_CONFIG)
@handle_route_errors("team config update")
async def update_team_config(update: TeamConfigUpdate) -> TeamConfigResponse:
    """Update team configuration fields."""
    project_root = _require_project_root()

    from open_agent_kit.features.codebase_intelligence.config import (
        load_ci_config,
        save_ci_config,
    )

    ci_config = load_ci_config(project_root)
    tc = ci_config.team

    if update.server_url is not None:
        tc.server_url = update.server_url
    if update.api_key is not None:
        tc.api_key = update.api_key
    if update.auto_sync is not None:
        tc.auto_sync = update.auto_sync
    if update.sync_interval_seconds is not None:
        tc.sync_interval_seconds = update.sync_interval_seconds
    if update.pull_interval_seconds is not None:
        tc.pull_interval_seconds = update.pull_interval_seconds
    if update.project_slug is not None:
        tc.project_slug = update.project_slug
    if update.transport is not None:
        tc.transport = update.transport

    save_ci_config(project_root, ci_config)
    # Invalidate cached config so subsequent reads pick up changes
    state = get_state()
    state.ci_config = None

    return await get_team_config()


# ---------------------------------------------------------------------------
# Join / Leave
# ---------------------------------------------------------------------------


@router.post(TEAM_API_PATH_JOIN)
@handle_route_errors("team join")
async def join_team(req: TeamJoinRequest) -> dict[str, Any]:
    """Join a team server: test connectivity, submit join request.

    The new flow:
    1. Test connectivity via GET {server_url}/api/team/status
    2. Read auto-generated API key from config (guaranteed present after startup)
    3. Compute key_hash = SHA256(api_key)
    4. POST {server_url}/api/team/request-join with join details
    5. Save server_url, set auto_sync=False (pending), save key_id
    6. Return pending status with key_id for polling
    """
    project_root = _require_project_root()

    import httpx

    from open_agent_kit.features.codebase_intelligence.config import (
        load_ci_config,
        save_ci_config,
    )
    from open_agent_kit.features.codebase_intelligence.constants.team import (
        TEAM_HTTP_REQUEST_JOIN_PATH,
        TEAM_HTTP_STATUS_PATH,
    )

    server_url = req.server_url.rstrip("/")

    # 1. Test connectivity
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{server_url}{TEAM_ROUTER_PREFIX}{TEAM_HTTP_STATUS_PATH}",
                timeout=10,
            )
            resp.raise_for_status()
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot connect to server: {exc}",
        ) from exc

    # 2. Read auto-generated API key
    state = get_state()
    ci_config = load_ci_config(project_root)
    api_key = ci_config.team.api_key
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="No API key available. Restart daemon to auto-generate.",
        )

    # 3. Compute key hash (never send plaintext)
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    # 4. Get machine identity
    from open_agent_kit.features.codebase_intelligence.team.identity import (
        get_project_identity,
    )

    identity = get_project_identity(project_root)
    machine_id = state.machine_id or "unknown"
    display_name = machine_id

    # 5. Submit join request
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{server_url}{TEAM_ROUTER_PREFIX}{TEAM_HTTP_REQUEST_JOIN_PATH}",
                json={
                    "machine_id": machine_id,
                    "display_name": display_name,
                    "key_hash": key_hash,
                    "project_id": identity.full_id,
                },
                timeout=10,
            )
            resp.raise_for_status()
            join_result = resp.json()
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Join request failed: {exc}",
        ) from exc

    key_id = join_result.get("key_id", "")

    # 6. Save config: server_url set, auto_sync=False (pending), save key_id
    ci_config.team.server_url = server_url
    ci_config.team.auto_sync = False  # Pending approval
    ci_config.team.pending_key_id = key_id
    save_ci_config(project_root, ci_config)
    state.ci_config = None

    return {
        "status": "pending_approval",
        "key_id": key_id,
        "server_url": server_url,
    }


@router.post(TEAM_API_PATH_LEAVE)
@handle_route_errors("team leave")
async def leave_team() -> dict[str, str]:
    """Disconnect from team server and stop sync workers."""
    project_root = _require_project_root()

    from open_agent_kit.features.codebase_intelligence.config import (
        load_ci_config,
        save_ci_config,
    )

    ci_config = load_ci_config(project_root)
    ci_config.team.server_url = None
    ci_config.team.api_key = None
    ci_config.team.auto_sync = False
    ci_config.team.pending_key_id = None
    save_ci_config(project_root, ci_config)

    state = get_state()
    state.ci_config = None

    # Stop sync worker if running
    if state.team_sync_worker:
        state.team_sync_worker.stop()
        state.team_sync_worker = None

    return {"status": "disconnected"}


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


@router.get(TEAM_API_PATH_STATUS)
@handle_route_errors("team status")
async def get_team_status() -> TeamStatusResponse:
    """Return team connection and sync status."""
    state = get_state()
    ci_config = state.ci_config
    if not ci_config or not ci_config.team.server_url:
        return TeamStatusResponse(configured=False)

    sync_status = None
    if state.team_sync_worker:
        sync_status = state.team_sync_worker.get_status().model_dump()

    # Get project identity
    project_id = None
    if state.project_root:
        from open_agent_kit.features.codebase_intelligence.team.identity import (
            get_project_identity,
        )

        project_id = get_project_identity(state.project_root).full_id

    # Determine if waiting for approval (server_url set but auto_sync off
    # and not in server mode)
    pending_approval = bool(
        ci_config.team.server_url
        and not ci_config.team.auto_sync
        and not ci_config.team.server_mode
    )

    return TeamStatusResponse(
        configured=True,
        server_url=ci_config.team.server_url,
        connected=state.team_sync_worker is not None,
        project_id=project_id,
        sync=sync_status,
        pending_approval=pending_approval,
        pending_key_id=ci_config.team.pending_key_id if pending_approval else None,
    )


@router.get(f"{TEAM_API_PATH_STATUS}/members")
@handle_route_errors("team members")
async def get_team_members() -> dict[str, Any]:
    """Return team member list.

    In server mode, queries the local DB directly (avoids loopback auth
    conflict with ``TokenAuthMiddleware``).  When connected to a remote
    server, proxies the request.
    """
    state = get_state()
    ci_config = state.ci_config
    if not ci_config or not ci_config.team.server_url:
        return {"members": []}

    # Server mode: query DB directly instead of HTTP loopback
    if ci_config.team.server_mode and state.activity_store:
        from open_agent_kit.features.codebase_intelligence.team.server.membership import (
            MembershipService,
        )

        conn = state.activity_store._get_connection()
        svc = MembershipService(conn_factory=lambda: conn)
        members = svc.list_members()
        return {"members": [m.model_dump() for m in members]}

    # Remote server: proxy the request
    import httpx

    try:
        headers: dict[str, str] = {}
        if ci_config.team.api_key:
            headers["Authorization"] = f"Bearer {ci_config.team.api_key}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{ci_config.team.server_url.rstrip('/')}/api/team/members",
                headers=headers,
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        logger.warning("Failed to fetch team members: %s", exc)
        return {"members": [], "error": str(exc)}


# ---------------------------------------------------------------------------
# Sync control
# ---------------------------------------------------------------------------


@router.post(TEAM_API_PATH_SYNC_FLUSH)
@handle_route_errors("team sync flush")
async def force_sync_flush() -> dict[str, int]:
    """Force-flush the outbox to the team server."""
    state = get_state()
    if not state.team_sync_worker:
        raise HTTPException(status_code=400, detail="Team sync not active")
    count = state.team_sync_worker._flush_outbox()
    return {"flushed": count}


@router.post(TEAM_API_PATH_SYNC_PULL)
@handle_route_errors("team sync pull")
async def force_sync_pull() -> dict[str, str]:
    """Placeholder for force-pulling events from the team server."""
    # Pull worker not yet implemented; return a descriptive status
    return {"status": "pull_worker_not_available"}


# ---------------------------------------------------------------------------
# Server mode toggle
# ---------------------------------------------------------------------------


@router.post(TEAM_API_PATH_SERVE)
@handle_route_errors("team serve toggle")
async def toggle_server_mode(req: ServerModeRequest) -> dict[str, Any]:
    """Enable or disable team server mode. Requires daemon restart."""
    project_root = _require_project_root()

    from open_agent_kit.config.paths import OAK_DIR
    from open_agent_kit.features.codebase_intelligence.config import (
        load_ci_config,
        save_ci_config,
    )
    from open_agent_kit.features.codebase_intelligence.constants import CI_DATA_DIR
    from open_agent_kit.features.codebase_intelligence.daemon.manager import (
        get_project_port,
    )

    ci_config = load_ci_config(project_root)

    if req.enable:
        # 1. Resolve daemon port
        ci_data_dir = project_root / OAK_DIR / CI_DATA_DIR
        port = get_project_port(project_root, ci_data_dir)

        # 2. Create server tables idempotently
        store = _require_activity_store()
        conn = store._get_connection()

        from open_agent_kit.features.codebase_intelligence.team.server.auth import (
            TEAM_API_KEYS_DDL,
            create_api_key,
            delete_revoked_keys_by_name,
            revoke_keys_by_name,
        )
        from open_agent_kit.features.codebase_intelligence.team.server.cursors import (
            TEAM_EVENTS_DDL,
        )
        from open_agent_kit.features.codebase_intelligence.team.server.membership import (
            TEAM_MEMBERS_DDL,
        )

        conn.executescript(TEAM_API_KEYS_DDL)
        conn.executescript(TEAM_MEMBERS_DDL)
        conn.executescript(TEAM_EVENTS_DDL)

        # 3. Revoke stale loopback keys, purge old revoked ones, create fresh
        revoke_keys_by_name(conn, TEAM_LOOPBACK_KEY_NAME)
        delete_revoked_keys_by_name(conn, TEAM_LOOPBACK_KEY_NAME)
        _key_id, plaintext = create_api_key(conn, TEAM_LOOPBACK_KEY_NAME)

        # 4. Update config
        server_url = TEAM_LOOPBACK_URL_TEMPLATE.format(port=port)
        ci_config.team.server_mode = True
        ci_config.team.server_url = server_url
        ci_config.team.api_key = plaintext
        ci_config.team.auto_sync = True
        save_ci_config(project_root, ci_config)

        state = get_state()
        state.ci_config = None

        return {
            "enabled": True,
            "server_url": server_url,
            "restart_required": True,
        }
    else:
        # Disable: revoke loopback keys, purge revoked, clear config
        from open_agent_kit.features.codebase_intelligence.team.server.auth import (
            delete_revoked_keys_by_name,
            revoke_keys_by_name,
        )

        try:
            store = _require_activity_store()
            conn = store._get_connection()
            revoke_keys_by_name(conn, TEAM_LOOPBACK_KEY_NAME)
            delete_revoked_keys_by_name(conn, TEAM_LOOPBACK_KEY_NAME)
        except Exception:
            pass  # DB may not have team tables yet

        loopback_prefix = "http://127.0.0.1:"
        was_loopback = ci_config.team.server_url and ci_config.team.server_url.startswith(
            loopback_prefix
        )

        ci_config.team.server_mode = False
        if was_loopback:
            ci_config.team.server_url = None
            ci_config.team.api_key = None
            ci_config.team.auto_sync = False

        save_ci_config(project_root, ci_config)

        state = get_state()
        state.ci_config = None

        return {
            "enabled": False,
            "restart_required": True,
        }


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------


@router.get(TEAM_API_PATH_POLICY)
@handle_route_errors("team policy get")
async def get_team_policy() -> PolicyResponse:
    """Return current data-collection policy."""
    state = get_state()
    ci_config = state.ci_config
    if not ci_config:
        return PolicyResponse()
    dc = ci_config.governance.data_collection
    return PolicyResponse(
        collect_activities=dc.collect_activities,
        collect_prompts=dc.collect_prompts,
        sync_observations=dc.sync_observations,
        sync_activities=dc.sync_activities,
        sync_prompts=dc.sync_prompts,
        allow_server_llm=dc.allow_server_llm,
    )


@router.post(TEAM_API_PATH_POLICY)
@handle_route_errors("team policy update")
async def update_team_policy(update: PolicyUpdate) -> PolicyResponse:
    """Update data-collection policy fields."""
    project_root = _require_project_root()

    from open_agent_kit.features.codebase_intelligence.config import (
        load_ci_config,
        save_ci_config,
    )

    ci_config = load_ci_config(project_root)
    dc = ci_config.governance.data_collection

    if update.collect_activities is not None:
        dc.collect_activities = update.collect_activities
    if update.collect_prompts is not None:
        dc.collect_prompts = update.collect_prompts
    if update.sync_observations is not None:
        dc.sync_observations = update.sync_observations
    if update.sync_activities is not None:
        dc.sync_activities = update.sync_activities
    if update.sync_prompts is not None:
        dc.sync_prompts = update.sync_prompts
    if update.allow_server_llm is not None:
        dc.allow_server_llm = update.allow_server_llm

    save_ci_config(project_root, ci_config)
    state = get_state()
    state.ci_config = None

    return await get_team_policy()


# ---------------------------------------------------------------------------
# API Key management (server mode only)
# ---------------------------------------------------------------------------


@router.get(TEAM_API_PATH_KEYS)
@handle_route_errors("team keys list")
async def list_keys() -> list[KeyResponse]:
    """List all API keys. Server mode only."""
    _require_server_mode()
    store = _require_activity_store()

    from open_agent_kit.features.codebase_intelligence.team.server.auth import (
        list_api_keys,
    )

    conn = store._get_connection()
    keys = list_api_keys(conn)
    return [
        KeyResponse(
            id=k.id,
            name=k.name,
            machine_id=k.machine_id,
            created_at=k.created_at,
            last_used_at=k.last_used_at,
            revoked_at=k.revoked_at,
            permissions=k.permissions,
        )
        for k in keys
        if k.name != TEAM_LOOPBACK_KEY_NAME
    ]


@router.post(TEAM_API_PATH_KEYS)
@handle_route_errors("team key create")
async def create_key(req: KeyCreateRequest) -> KeyCreateResponse:
    """Create a new API key. Returns plaintext once. Server mode only."""
    _require_server_mode()
    store = _require_activity_store()

    from open_agent_kit.features.codebase_intelligence.team.server.auth import (
        create_api_key,
    )

    conn = store._get_connection()
    key_id, plaintext = create_api_key(conn, req.name)
    return KeyCreateResponse(id=key_id, name=req.name, key=plaintext)


@router.delete(f"{TEAM_API_PATH_KEYS}/{{key_id}}")
@handle_route_errors("team key revoke")
async def revoke_key(key_id: str) -> dict[str, bool]:
    """Revoke an API key. Server mode only."""
    _require_server_mode()
    store = _require_activity_store()

    from open_agent_kit.features.codebase_intelligence.team.server.auth import (
        revoke_api_key,
    )

    conn = store._get_connection()
    success = revoke_api_key(conn, key_id)
    if not success:
        raise HTTPException(status_code=404, detail="Key not found")
    return {"revoked": True}


# ---------------------------------------------------------------------------
# Join request approval (server mode -- dashboard admin)
# ---------------------------------------------------------------------------


@router.get(TEAM_API_PATH_PENDING_JOINS)
@handle_route_errors("team pending joins")
async def get_pending_joins() -> list[dict[str, Any]]:
    """List pending join requests. Server mode only (dashboard admin)."""
    _require_server_mode()
    store = _require_activity_store()

    from open_agent_kit.features.codebase_intelligence.team.server.auth import (
        list_pending_keys as _list_pending_keys,
    )

    conn = store._get_connection()
    keys = _list_pending_keys(conn)
    return [
        {
            "key_id": k.id,
            "name": k.name,
            "machine_id": k.machine_id or "",
            "display_name": k.display_name or "",
            "created_at": k.created_at,
        }
        for k in keys
    ]


@router.post(f"{TEAM_API_PATH_APPROVE_JOIN}/{{key_id}}")
@handle_route_errors("team approve join")
async def approve_join(key_id: str) -> dict[str, bool]:
    """Approve a pending join request. Server mode only (dashboard admin)."""
    _require_server_mode()
    store = _require_activity_store()

    from open_agent_kit.features.codebase_intelligence.team.server.auth import (
        approve_key as _approve_key,
    )
    from open_agent_kit.features.codebase_intelligence.team.server.auth import (
        get_key_by_id as _get_key_by_id,
    )

    conn = store._get_connection()

    # Look up key info before approving so we can register the member
    key_info = _get_key_by_id(conn, key_id)
    if not key_info:
        raise HTTPException(status_code=404, detail="Pending key not found")

    success = _approve_key(conn, key_id)
    if not success:
        raise HTTPException(status_code=404, detail="Pending key not found")

    # Register the member immediately so they appear in the members list
    if key_info.machine_id:
        from open_agent_kit.features.codebase_intelligence.team.server.membership import (
            MembershipService,
        )

        svc = MembershipService(conn_factory=lambda: conn)
        svc.register(
            machine_id=key_info.machine_id,
            display_name=key_info.display_name or key_info.machine_id,
            project_id=key_info.machine_id,  # Updated on first sync
        )

    return {"approved": True}


@router.post(f"{TEAM_API_PATH_REJECT_JOIN}/{{key_id}}")
@handle_route_errors("team reject join")
async def reject_join(key_id: str) -> dict[str, bool]:
    """Reject a pending join request. Server mode only (dashboard admin)."""
    _require_server_mode()
    store = _require_activity_store()

    from open_agent_kit.features.codebase_intelligence.team.server.auth import (
        reject_key as _reject_key,
    )

    conn = store._get_connection()
    success = _reject_key(conn, key_id)
    if not success:
        raise HTTPException(status_code=404, detail="Key not found")
    return {"rejected": True}


# ---------------------------------------------------------------------------
# Join status polling (client mode -- polls remote server)
# ---------------------------------------------------------------------------


@router.get(TEAM_API_PATH_JOIN_STATUS)
@handle_route_errors("team join status")
async def poll_join_status() -> dict[str, Any]:
    """Poll remote server for join approval status.

    Client mode only. On approval, enables auto_sync and returns the
    new status so the UI can start showing sync info.
    """
    state = get_state()
    ci_config = state.ci_config
    if not ci_config or not ci_config.team.server_url:
        raise HTTPException(status_code=400, detail="Not connected to a team server")

    # Server mode doesn't need to poll itself
    if ci_config.team.server_mode:
        return {"status": "server_mode", "pending_approval": False}

    # If already syncing, no need to poll
    if ci_config.team.auto_sync:
        return {"status": "approved", "pending_approval": False}

    # Without a key_id, we can only report the pending state.
    # The UI should use GET /api/team/join-status/{key_id} instead.
    return {"status": "pending", "pending_approval": True}


@router.get(f"{TEAM_API_PATH_JOIN_STATUS}/{{key_id}}")
@handle_route_errors("team join status poll")
async def poll_join_status_by_key(key_id: str) -> dict[str, Any]:
    """Poll remote server for join approval status by key_id.

    On approval, enables auto_sync so sync workers can start.
    """
    state = get_state()
    ci_config = state.ci_config
    if not ci_config or not ci_config.team.server_url:
        raise HTTPException(status_code=400, detail="Not connected to a team server")

    if ci_config.team.server_mode:
        return {"status": "server_mode", "pending_approval": False}

    if ci_config.team.auto_sync:
        return {"status": TEAM_JOIN_STATUS_APPROVED, "pending_approval": False}

    import httpx

    from open_agent_kit.features.codebase_intelligence.constants.team import (
        TEAM_HTTP_JOIN_STATUS_PATH,
    )

    server_url = ci_config.team.server_url.rstrip("/")

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{server_url}{TEAM_ROUTER_PREFIX}{TEAM_HTTP_JOIN_STATUS_PATH}/{key_id}",
                timeout=10,
            )
            resp.raise_for_status()
            result = resp.json()
    except Exception as exc:
        logger.warning("Failed to poll join status: %s", exc)
        return {"status": "error", "error": str(exc), "pending_approval": True}

    status = result.get("status", "pending")

    # On approval, enable auto_sync so sync workers start
    if status == TEAM_JOIN_STATUS_APPROVED:
        project_root = _require_project_root()

        from open_agent_kit.features.codebase_intelligence.config import (
            load_ci_config,
            save_ci_config,
        )

        fresh_config = load_ci_config(project_root)
        fresh_config.team.auto_sync = True
        fresh_config.team.pending_key_id = None  # Clear pending state
        save_ci_config(project_root, fresh_config)
        state.ci_config = None

        return {"status": TEAM_JOIN_STATUS_APPROVED, "pending_approval": False}

    return {"status": status, "pending_approval": status == "pending"}
