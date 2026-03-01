"""Team management API routes for the dashboard UI.

These routes handle local team configuration, sync status, and
policy management via the cloud relay.
"""

import logging
from http import HTTPStatus
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from open_agent_kit.features.codebase_intelligence.constants.team import (
    TEAM_API_PATH_CONFIG,
    TEAM_API_PATH_MEMBERS,
    TEAM_API_PATH_POLICY,
    TEAM_API_PATH_STATUS,
    TEAM_ROUTE_TAG,
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
    """Current team configuration."""

    auto_sync: bool = False
    sync_interval_seconds: int = 3
    relay_worker_url: str | None = None
    api_key: str | None = None


class TeamConfigUpdate(BaseModel):
    """Partial update for team configuration."""

    auto_sync: bool | None = None
    sync_interval_seconds: int | None = None
    relay_worker_url: str | None = None
    api_key: str | None = None


class TeamStatusResponse(BaseModel):
    """Overall team status (relay connection, sync workers)."""

    configured: bool = False
    connected: bool = False
    relay: dict[str, Any] | None = None
    online_nodes: list[dict[str, Any]] = []
    sync: dict[str, Any] | None = None
    relay_pending: dict[str, int] = {}


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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_project_root() -> Path:
    """Return project_root from state or raise 500."""
    state = get_state()
    if not state.project_root:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Project root not set"
        )
    return state.project_root


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
    relay = ci_config.cloud_relay
    # Relay URL and token: prefer explicit team config, fall back to cloud relay
    # (they're the same Worker, so the values should be identical after deploy).
    relay_worker_url = tc.relay_worker_url or (relay.worker_url if relay else None)
    api_key = tc.api_key or (relay.token if relay else None)
    return TeamConfigResponse(
        auto_sync=tc.auto_sync,
        sync_interval_seconds=tc.sync_interval_seconds,
        relay_worker_url=relay_worker_url,
        api_key=api_key,
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

    if update.auto_sync is not None:
        tc.auto_sync = update.auto_sync
    if update.sync_interval_seconds is not None:
        tc.sync_interval_seconds = update.sync_interval_seconds
    if update.relay_worker_url is not None:
        tc.relay_worker_url = update.relay_worker_url or None
    if update.api_key is not None:
        tc.api_key = update.api_key or None

    save_ci_config(project_root, ci_config)
    # Invalidate cached config so subsequent reads pick up changes
    state = get_state()
    state.ci_config = None

    return await get_team_config()


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


@router.get(TEAM_API_PATH_STATUS)
@handle_route_errors("team status")
async def get_team_status() -> TeamStatusResponse:
    """Return team connection and sync status via cloud relay."""
    import httpx

    from open_agent_kit.features.codebase_intelligence.constants import (
        CLOUD_RELAY_OBS_STATS_PATH,
    )

    state = get_state()

    relay_status = None
    online_nodes: list[dict[str, Any]] = []
    is_connected = False
    relay_pending: dict[str, int] = {}

    if state.cloud_relay_client:
        status = state.cloud_relay_client.get_status()
        relay_status = status.to_dict()
        is_connected = status.connected
        online_nodes = getattr(state.cloud_relay_client, "online_nodes", [])

        # Fetch pending obs counts from the relay DO when connected.
        if is_connected and status.worker_url:
            try:
                token = state.ci_config.cloud_relay.token if state.ci_config else None
                headers = {"Authorization": f"Bearer {token}"} if token else {}
                url = status.worker_url.rstrip("/") + CLOUD_RELAY_OBS_STATS_PATH
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    relay_pending = resp.json().get("pending", {})
            except Exception as exc:
                logger.debug("Failed to fetch relay obs stats: %s", exc)
    else:
        # No live client yet — surface the configured URL so the UI shows
        # "Disconnected" rather than "Not Configured".
        ci_config = state.ci_config
        if ci_config:
            tc = ci_config.team
            rc = ci_config.cloud_relay
            worker_url = tc.relay_worker_url or (rc.worker_url if rc else None)
            if worker_url:
                relay_status = {"connected": False, "worker_url": worker_url}

    sync_status = None
    if state.team_sync_worker:
        sync_status = state.team_sync_worker.get_status().model_dump()

    return TeamStatusResponse(
        configured=state.cloud_relay_client is not None,
        connected=is_connected,
        relay=relay_status,
        online_nodes=online_nodes,
        sync=sync_status,
        relay_pending=relay_pending,
    )


@router.get(TEAM_API_PATH_MEMBERS)
@handle_route_errors("team members")
async def get_team_members() -> dict[str, Any]:
    """Return team member list from cloud relay online nodes."""
    state = get_state()
    if not state.cloud_relay_client:
        return {"online_nodes": []}
    return {"online_nodes": getattr(state.cloud_relay_client, "online_nodes", [])}


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
