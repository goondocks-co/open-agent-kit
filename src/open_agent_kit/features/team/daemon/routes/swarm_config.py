"""Swarm configuration routes for the team daemon.

Allows the team daemon to join/leave a swarm and check swarm connection status.
When a cloud relay is deployed, join/leave also pushes the swarm config to the
relay worker so it can register/unregister with the swarm autonomously.
"""

import logging
from http import HTTPStatus
from pathlib import Path

import httpx
import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from open_agent_kit.config.paths import OAK_DIR
from open_agent_kit.features.swarm.constants import (
    CI_CONFIG_KEY_SWARM,
    CI_CONFIG_SWARM_KEY_TOKEN,
    CI_CONFIG_SWARM_KEY_URL,
    SWARM_MESSAGE_MCP_HINT,
    SWARM_RESPONSE_KEY_ERROR,
)
from open_agent_kit.features.team.constants.api import (
    CI_DAEMON_API_PATH_SWARM_JOIN,
    CI_DAEMON_API_PATH_SWARM_LEAVE,
    CI_DAEMON_API_PATH_SWARM_STATUS,
)
from open_agent_kit.features.team.daemon.state import get_state

logger = logging.getLogger(__name__)

router = APIRouter(tags=["swarm"])

_RELAY_SWARM_CONFIG_PATH = "/api/swarm/config"
_RELAY_PUSH_TIMEOUT_SECONDS = 10


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class _JoinSwarmRequest(BaseModel):
    swarm_url: str
    swarm_token: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_project_root() -> Path:
    """Return project_root from state or raise."""
    state = get_state()
    if not state.project_root:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Project root not set"
        )
    return state.project_root


def _config_path(project_root: Path) -> Path:
    return project_root / OAK_DIR / "config.yaml"


def _load_config_yaml(project_root: Path) -> dict:
    path = _config_path(project_root)
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _save_config_yaml(project_root: Path, data: dict) -> None:
    path = _config_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def _get_relay_credentials() -> tuple[str, str] | None:
    """Return (relay_worker_url, relay_token) if a relay is configured, else None."""
    state = get_state()
    ci_config = state.ci_config
    if ci_config is None:
        return None

    relay_worker_url = ci_config.cloud_relay.worker_url or ci_config.team.relay_worker_url
    relay_token = ci_config.cloud_relay.token or ci_config.team.api_key

    if not relay_worker_url or not relay_token:
        return None

    return relay_worker_url, relay_token


async def _push_swarm_config_to_relay(
    swarm_url: str,
    swarm_token: str,
) -> bool:
    """Push swarm config to the relay worker's PUT /api/swarm/config endpoint.

    Returns True on success, False on failure (logged but not raised — the
    local config save is the primary action; relay push is best-effort).
    """
    creds = _get_relay_credentials()
    if creds is None:
        logger.debug("No relay credentials configured; skipping relay swarm config push")
        return False

    relay_worker_url, relay_token = creds
    url = relay_worker_url.rstrip("/") + _RELAY_SWARM_CONFIG_PATH

    try:
        async with httpx.AsyncClient(timeout=_RELAY_PUSH_TIMEOUT_SECONDS) as client:
            resp = await client.put(
                url,
                json={"swarm_url": swarm_url, "swarm_token": swarm_token},
                headers={"Authorization": f"Bearer {relay_token}"},
            )
        if resp.is_success:
            logger.info("Pushed swarm config to relay worker at %s", relay_worker_url)
            return True
        logger.warning(
            "Relay worker returned %s when pushing swarm config: %s",
            resp.status_code,
            resp.text[:200],
        )
        return False
    except httpx.HTTPError as exc:
        logger.warning("Failed to push swarm config to relay worker: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post(CI_DAEMON_API_PATH_SWARM_JOIN)
async def join_swarm(request: _JoinSwarmRequest) -> dict:
    """Join a swarm by saving URL/token to the config file and pushing to relay."""
    project_root = _require_project_root()
    try:
        file_data = _load_config_yaml(project_root)
        swarm_section = file_data.get(CI_CONFIG_KEY_SWARM, {})
        if not isinstance(swarm_section, dict):
            swarm_section = {}
        swarm_section[CI_CONFIG_SWARM_KEY_URL] = request.swarm_url
        swarm_section[CI_CONFIG_SWARM_KEY_TOKEN] = request.swarm_token
        file_data[CI_CONFIG_KEY_SWARM] = swarm_section
        _save_config_yaml(project_root, file_data)

        # Invalidate cached config
        state = get_state()
        state.ci_config = None

        # Push swarm config to relay worker so it registers with the swarm
        relay_ok = await _push_swarm_config_to_relay(
            request.swarm_url,
            request.swarm_token,
        )

        return {
            "success": True,
            "swarm_url": request.swarm_url,
            "relay_synced": relay_ok,
            "mcp_hint": SWARM_MESSAGE_MCP_HINT,
        }
    except Exception as exc:
        logger.error("Failed to join swarm: %s", exc)
        return {SWARM_RESPONSE_KEY_ERROR: str(exc)}


@router.post(CI_DAEMON_API_PATH_SWARM_LEAVE)
async def leave_swarm() -> dict:
    """Leave the swarm by clearing config and disconnecting relay from swarm."""
    project_root = _require_project_root()
    try:
        file_data = _load_config_yaml(project_root)
        file_data.pop(CI_CONFIG_KEY_SWARM, None)
        _save_config_yaml(project_root, file_data)

        # Invalidate cached config
        state = get_state()
        state.ci_config = None

        # Push empty swarm config to relay worker to trigger disconnectFromSwarm()
        relay_ok = await _push_swarm_config_to_relay("", "")

        return {"success": True, "relay_synced": relay_ok}
    except Exception as exc:
        logger.error("Failed to leave swarm: %s", exc)
        return {SWARM_RESPONSE_KEY_ERROR: str(exc)}


@router.get(CI_DAEMON_API_PATH_SWARM_STATUS)
async def swarm_status() -> dict:
    """Get current swarm connection status from team config."""
    try:
        project_root = _require_project_root()
        file_data = _load_config_yaml(project_root)
        swarm_section = file_data.get(CI_CONFIG_KEY_SWARM, {})
        if not isinstance(swarm_section, dict):
            return {"joined": False, "swarm_url": None}

        swarm_url = swarm_section.get(CI_CONFIG_SWARM_KEY_URL)
        has_token = bool(swarm_section.get(CI_CONFIG_SWARM_KEY_TOKEN))

        return {
            "joined": bool(swarm_url and has_token),
            "swarm_url": swarm_url,
        }
    except Exception as exc:
        logger.error("Failed to get swarm status: %s", exc)
        return {SWARM_RESPONSE_KEY_ERROR: str(exc), "joined": False, "swarm_url": None}
