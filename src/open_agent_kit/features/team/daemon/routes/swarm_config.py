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
    SWARM_USER_CONFIG_KEY_AGENT_TOKEN,
    SWARM_USER_CONFIG_KEY_TOKEN,
    SWARM_USER_CONFIG_SECTION,
)
from open_agent_kit.features.team.cli_command import resolve_ci_cli_command
from open_agent_kit.features.team.config.user_store import (
    read_user_value,
    remove_user_value,
    write_user_value,
)
from open_agent_kit.features.team.constants.api import (
    CI_DAEMON_API_PATH_SWARM_DAEMON_LAUNCH,
    CI_DAEMON_API_PATH_SWARM_DAEMON_STATUS,
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

    relay_worker_url, relay_token = ci_config.resolve_relay_credentials()

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


async def _fetch_agent_token(swarm_url: str, swarm_token: str) -> str | None:
    """Fetch the agent_token from the swarm worker.

    The agent_token is used for MCP access to the cloud worker.
    Returns the token string on success, None on failure.
    """
    if not swarm_url:
        return None

    url = swarm_url.rstrip("/") + "/api/swarm/agent-token"
    try:
        async with httpx.AsyncClient(timeout=_RELAY_PUSH_TIMEOUT_SECONDS) as client:
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {swarm_token}"},
            )
        if resp.is_success:
            data = resp.json()
            token = data.get("agent_token")
            if token:
                logger.info("Fetched agent_token from swarm worker")
                return str(token)
        logger.warning(
            "Failed to fetch agent_token from swarm worker: %s %s",
            resp.status_code,
            resp.text[:200],
        )
    except httpx.HTTPError as exc:
        logger.warning("Failed to fetch agent_token from swarm worker: %s", exc)
    return None


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
        # Remove legacy token from config.yaml (stored in user config)
        swarm_section.pop(CI_CONFIG_SWARM_KEY_TOKEN, None)
        file_data[CI_CONFIG_KEY_SWARM] = swarm_section
        _save_config_yaml(project_root, file_data)

        # Write token to user config (not git-tracked)
        write_user_value(
            project_root,
            SWARM_USER_CONFIG_SECTION,
            SWARM_USER_CONFIG_KEY_TOKEN,
            request.swarm_token,
        )

        # Invalidate cached config
        state = get_state()
        state.ci_config = None

        # Push swarm config to relay worker so it registers with the swarm
        relay_ok = await _push_swarm_config_to_relay(
            request.swarm_url,
            request.swarm_token,
        )

        # Auto-fetch agent_token from swarm worker for MCP access
        agent_token = await _fetch_agent_token(request.swarm_url, request.swarm_token)
        if agent_token:
            write_user_value(
                project_root,
                SWARM_USER_CONFIG_SECTION,
                SWARM_USER_CONFIG_KEY_AGENT_TOKEN,
                agent_token,
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

        # Remove tokens from user config
        remove_user_value(project_root, SWARM_USER_CONFIG_SECTION, SWARM_USER_CONFIG_KEY_TOKEN)
        remove_user_value(
            project_root, SWARM_USER_CONFIG_SECTION, SWARM_USER_CONFIG_KEY_AGENT_TOKEN
        )

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
        has_token = bool(
            read_user_value(project_root, SWARM_USER_CONFIG_SECTION, SWARM_USER_CONFIG_KEY_TOKEN)
            or swarm_section.get(CI_CONFIG_SWARM_KEY_TOKEN)
        )

        cli_command = resolve_ci_cli_command(project_root)

        return {
            "joined": bool(swarm_url and has_token),
            "swarm_url": swarm_url,
            "cli_command": cli_command,
        }
    except Exception as exc:
        logger.error("Failed to get swarm status: %s", exc)
        return {SWARM_RESPONSE_KEY_ERROR: str(exc), "joined": False, "swarm_url": None}


# ---------------------------------------------------------------------------
# Swarm daemon management (launch local swarm daemon from team UI)
# ---------------------------------------------------------------------------


def _derive_swarm_name(swarm_url: str) -> str | None:
    """Derive swarm name from worker URL (e.g. oak-swarm-oss-swarm.… → oss-swarm)."""
    try:
        from urllib.parse import urlparse

        hostname = urlparse(swarm_url).hostname or ""
        prefix = "oak-swarm-"
        if not hostname.startswith(prefix):
            return None
        rest = hostname[len(prefix) :]
        dot_index = rest.find(".")
        return rest[:dot_index] if dot_index > 0 else rest
    except Exception:
        return None


@router.get(CI_DAEMON_API_PATH_SWARM_DAEMON_STATUS)
async def swarm_daemon_status() -> dict:
    """Check if a local swarm daemon config exists and if the daemon is running."""
    try:
        project_root = _require_project_root()
        file_data = _load_config_yaml(project_root)
        swarm_section = file_data.get(CI_CONFIG_KEY_SWARM, {})
        if not isinstance(swarm_section, dict):
            return {"configured": False, "running": False}

        swarm_url = swarm_section.get(CI_CONFIG_SWARM_KEY_URL)
        if not swarm_url:
            return {"configured": False, "running": False}

        swarm_name = _derive_swarm_name(swarm_url)
        if not swarm_name:
            return {"configured": False, "running": False}

        from open_agent_kit.features.swarm.config import load_swarm_config

        config = load_swarm_config(swarm_name)
        if not config:
            return {"configured": False, "running": False, "name": swarm_name}

        from open_agent_kit.features.swarm.daemon.manager import SwarmDaemonManager

        manager = SwarmDaemonManager(swarm_id=swarm_name)
        running = manager.is_running()

        result: dict = {
            "configured": True,
            "running": running,
            "name": swarm_name,
        }
        if running:
            result["url"] = f"http://localhost:{manager.port}"

        return result
    except Exception as exc:
        logger.error("Failed to check swarm daemon status: %s", exc)
        return {SWARM_RESPONSE_KEY_ERROR: str(exc), "configured": False, "running": False}


@router.post(CI_DAEMON_API_PATH_SWARM_DAEMON_LAUNCH)
async def swarm_daemon_launch() -> dict:
    """Create local swarm daemon config if needed and start the daemon.

    Uses the swarm_url from config.yaml and swarm_token from user config to create
    the local ~/.oak/swarms/{name}/config.json, then starts the daemon.
    Returns the daemon URL for the UI to open in a new tab.
    """
    try:
        project_root = _require_project_root()
        file_data = _load_config_yaml(project_root)
        swarm_section = file_data.get(CI_CONFIG_KEY_SWARM, {})
        if not isinstance(swarm_section, dict):
            raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="No swarm configured")

        swarm_url = swarm_section.get(CI_CONFIG_SWARM_KEY_URL)
        if not swarm_url:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST, detail="No swarm URL configured"
            )

        swarm_name = _derive_swarm_name(swarm_url)
        if not swarm_name:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Cannot derive swarm name from URL",
            )

        # Get swarm token from user config (or legacy config.yaml)
        swarm_token = read_user_value(
            project_root, SWARM_USER_CONFIG_SECTION, SWARM_USER_CONFIG_KEY_TOKEN
        )
        if not swarm_token:
            swarm_token = swarm_section.get(CI_CONFIG_SWARM_KEY_TOKEN)
        if not swarm_token:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST, detail="No swarm token available"
            )

        # Ensure local swarm daemon config exists (delegates to swarm domain)
        from open_agent_kit.features.swarm.config import ensure_swarm_config

        agent_token = read_user_value(
            project_root, SWARM_USER_CONFIG_SECTION, SWARM_USER_CONFIG_KEY_AGENT_TOKEN
        )
        ensure_swarm_config(
            swarm_name,
            swarm_token,
            swarm_url,
            agent_token=agent_token,
        )

        # Start the daemon
        from open_agent_kit.features.swarm.daemon.manager import SwarmDaemonManager

        manager = SwarmDaemonManager(swarm_id=swarm_name)
        if not manager.is_running():
            started = manager.start(wait=True)
            if not started:
                raise HTTPException(
                    status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                    detail="Swarm daemon failed to start. Check logs.",
                )
            logger.info("Started swarm daemon '%s' on port %d", swarm_name, manager.port)

        return {
            "success": True,
            "name": swarm_name,
            "url": f"http://localhost:{manager.port}",
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to launch swarm daemon: %s", exc)
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
