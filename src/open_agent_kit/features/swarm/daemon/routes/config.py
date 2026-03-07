"""Configuration route for the swarm daemon.

Exposes GET/PUT ``/api/config`` so the UI can read and toggle ``log_level``.
The value is persisted in the swarm's ``config.json`` and takes effect on
the next daemon restart (mirroring the team daemon pattern).
"""

import logging
import os
from http import HTTPStatus

from fastapi import APIRouter, HTTPException, Request

from open_agent_kit.features.swarm.config import load_swarm_config, save_swarm_config
from open_agent_kit.features.swarm.constants import (
    CI_CONFIG_SWARM_KEY_AGENT_TOKEN,
    CI_CONFIG_SWARM_KEY_CUSTOM_DOMAIN,
    CI_CONFIG_SWARM_KEY_LOG_LEVEL,
    CI_CONFIG_SWARM_KEY_LOG_ROTATION,
    CI_CONFIG_SWARM_KEY_URL,
    SWARM_DAEMON_API_PATH_CONFIG,
    SWARM_DAEMON_DEFAULT_LOG_LEVEL,
    SWARM_ENV_VAR_CUSTOM_DOMAIN,
    SWARM_ENV_VAR_URL,
    SWARM_ERROR_NOT_CONNECTED,
    SWARM_LOG_ROTATION_DEFAULT_BACKUP_COUNT,
    SWARM_LOG_ROTATION_DEFAULT_ENABLED,
    SWARM_LOG_ROTATION_DEFAULT_MAX_SIZE_MB,
    SWARM_LOG_ROTATION_MAX_BACKUP_COUNT,
    SWARM_LOG_ROTATION_MAX_SIZE_MB,
    SWARM_LOG_ROTATION_MIN_SIZE_MB,
    SWARM_RESPONSE_KEY_ERROR,
    SWARM_ROUTE_TAG,
)
from open_agent_kit.features.swarm.daemon.state import get_swarm_state

logger = logging.getLogger(__name__)

router = APIRouter(tags=[SWARM_ROUTE_TAG])

_VALID_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")


def _get_log_rotation(config: dict) -> dict:
    """Return log rotation settings with defaults applied."""
    rotation = config.get(CI_CONFIG_SWARM_KEY_LOG_ROTATION, {})
    return {
        "enabled": rotation.get("enabled", SWARM_LOG_ROTATION_DEFAULT_ENABLED),
        "max_size_mb": rotation.get("max_size_mb", SWARM_LOG_ROTATION_DEFAULT_MAX_SIZE_MB),
        "backup_count": rotation.get("backup_count", SWARM_LOG_ROTATION_DEFAULT_BACKUP_COUNT),
    }


@router.get(SWARM_DAEMON_API_PATH_CONFIG)
async def get_config() -> dict:
    """Return current swarm daemon configuration."""
    state = get_swarm_state()
    config = load_swarm_config(state.swarm_id) or {} if state.swarm_id else {}
    return {
        "log_level": config.get(CI_CONFIG_SWARM_KEY_LOG_LEVEL, SWARM_DAEMON_DEFAULT_LOG_LEVEL),
        "log_rotation": _get_log_rotation(config),
    }


@router.put(SWARM_DAEMON_API_PATH_CONFIG)
async def update_config(request: Request) -> dict:
    """Update swarm daemon configuration.

    Currently supports ``log_level``. Changes are persisted to
    ``config.json`` and take effect after a daemon restart.
    """
    state = get_swarm_state()
    if not state.swarm_id:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail="No swarm ID configured",
        )

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Invalid JSON") from None

    config = load_swarm_config(state.swarm_id) or {}
    changed = False

    if CI_CONFIG_SWARM_KEY_LOG_LEVEL in data:
        new_level = str(data[CI_CONFIG_SWARM_KEY_LOG_LEVEL]).upper()
        if new_level not in _VALID_LOG_LEVELS:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=f"Invalid log level: {new_level}. Valid: {list(_VALID_LOG_LEVELS)}",
            )
        old_level = config.get(CI_CONFIG_SWARM_KEY_LOG_LEVEL, SWARM_DAEMON_DEFAULT_LOG_LEVEL)
        if new_level != old_level:
            config[CI_CONFIG_SWARM_KEY_LOG_LEVEL] = new_level
            changed = True
            logger.info("Log level changed: %s -> %s (restart required)", old_level, new_level)

    if CI_CONFIG_SWARM_KEY_LOG_ROTATION in data:
        rotation_data = data[CI_CONFIG_SWARM_KEY_LOG_ROTATION]
        if not isinstance(rotation_data, dict):
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="log_rotation must be an object",
            )
        current_rotation = config.get(CI_CONFIG_SWARM_KEY_LOG_ROTATION, {})
        new_rotation = dict(current_rotation)

        if "enabled" in rotation_data:
            new_rotation["enabled"] = bool(rotation_data["enabled"])

        if "max_size_mb" in rotation_data:
            size = int(rotation_data["max_size_mb"])
            if not SWARM_LOG_ROTATION_MIN_SIZE_MB <= size <= SWARM_LOG_ROTATION_MAX_SIZE_MB:
                raise HTTPException(
                    status_code=HTTPStatus.BAD_REQUEST,
                    detail=f"max_size_mb must be {SWARM_LOG_ROTATION_MIN_SIZE_MB}-{SWARM_LOG_ROTATION_MAX_SIZE_MB}",
                )
            new_rotation["max_size_mb"] = size

        if "backup_count" in rotation_data:
            count = int(rotation_data["backup_count"])
            if not 0 <= count <= SWARM_LOG_ROTATION_MAX_BACKUP_COUNT:
                raise HTTPException(
                    status_code=HTTPStatus.BAD_REQUEST,
                    detail=f"backup_count must be 0-{SWARM_LOG_ROTATION_MAX_BACKUP_COUNT}",
                )
            new_rotation["backup_count"] = count

        if new_rotation != current_rotation:
            config[CI_CONFIG_SWARM_KEY_LOG_ROTATION] = new_rotation
            changed = True
            logger.info("Log rotation config changed: %s (restart required)", new_rotation)

    if changed:
        save_swarm_config(state.swarm_id, config)

    message = "Configuration updated. Restart daemon to apply." if changed else "No changes."
    return {
        "message": message,
        "log_level": config.get(CI_CONFIG_SWARM_KEY_LOG_LEVEL, SWARM_DAEMON_DEFAULT_LOG_LEVEL),
        "log_rotation": _get_log_rotation(config),
        "changed": changed,
    }


# ---------------------------------------------------------------------------
# MCP configuration — endpoint URL and agent token for cloud agents
# ---------------------------------------------------------------------------


@router.get("/api/config/mcp")
async def get_mcp_config() -> dict:
    """Get MCP endpoint configuration for cloud agents."""
    state = get_swarm_state()
    config = load_swarm_config(state.swarm_id) or {} if state.swarm_id else {}

    swarm_url = os.environ.get(SWARM_ENV_VAR_URL, "") or (config or {}).get(
        CI_CONFIG_SWARM_KEY_URL, ""
    )
    custom_domain = os.environ.get(SWARM_ENV_VAR_CUSTOM_DOMAIN, "") or (config or {}).get(
        CI_CONFIG_SWARM_KEY_CUSTOM_DOMAIN, ""
    )

    # Build base URL: prefer custom domain with worker name, fall back to swarm_url
    if custom_domain and state.swarm_id:
        from open_agent_kit.features.swarm.scaffold import make_worker_name

        worker_name = make_worker_name(state.swarm_id)
        base_url = f"https://{worker_name}.{custom_domain}"
    else:
        base_url = swarm_url

    agent_token = (config or {}).get(CI_CONFIG_SWARM_KEY_AGENT_TOKEN, "")

    return {
        "mcp_endpoint": f"{base_url}/mcp" if base_url else "",
        "agent_token": agent_token,
        "has_agent_token": bool(agent_token),
    }


# ---------------------------------------------------------------------------
# min_oak_version — proxied to the swarm DO's swarm_config table
# ---------------------------------------------------------------------------


@router.get("/api/config/min-oak-version")
async def get_min_oak_version() -> dict:
    """Get the minimum OAK version configured on the swarm DO."""
    state = get_swarm_state()
    if not state.http_client:
        return {SWARM_RESPONSE_KEY_ERROR: SWARM_ERROR_NOT_CONNECTED, "min_oak_version": ""}
    try:
        return await state.http_client.get_min_oak_version()
    except Exception as exc:
        logger.error("Failed to fetch min_oak_version: %s", exc)
        return {SWARM_RESPONSE_KEY_ERROR: str(exc), "min_oak_version": ""}


@router.put("/api/config/min-oak-version")
async def set_min_oak_version(request: Request) -> dict:
    """Set the minimum OAK version on the swarm DO."""
    state = get_swarm_state()
    if not state.http_client:
        raise HTTPException(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            detail=SWARM_ERROR_NOT_CONNECTED,
        )
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Invalid JSON") from None

    try:
        result = await state.http_client.set_min_oak_version(data)
        logger.info("min_oak_version updated: %s", result.get("min_oak_version", ""))
        return result
    except Exception as exc:
        logger.error("Failed to set min_oak_version: %s", exc)
        raise HTTPException(
            status_code=HTTPStatus.BAD_GATEWAY,
            detail=str(exc),
        ) from exc
