"""Configuration route for the swarm daemon.

Exposes GET/PUT ``/api/config`` so the UI can read and toggle ``log_level``.
The value is persisted in the swarm's ``config.json`` and takes effect on
the next daemon restart (mirroring the team daemon pattern).
"""

import logging
from http import HTTPStatus

from fastapi import APIRouter, HTTPException, Request

from open_agent_kit.features.swarm.config import load_swarm_config, save_swarm_config
from open_agent_kit.features.swarm.constants import (
    CI_CONFIG_SWARM_KEY_LOG_LEVEL,
    CI_CONFIG_SWARM_KEY_LOG_ROTATION,
    SWARM_DAEMON_API_PATH_CONFIG,
    SWARM_DAEMON_DEFAULT_LOG_LEVEL,
    SWARM_LOG_ROTATION_DEFAULT_BACKUP_COUNT,
    SWARM_LOG_ROTATION_DEFAULT_ENABLED,
    SWARM_LOG_ROTATION_DEFAULT_MAX_SIZE_MB,
    SWARM_LOG_ROTATION_MAX_BACKUP_COUNT,
    SWARM_LOG_ROTATION_MAX_SIZE_MB,
    SWARM_LOG_ROTATION_MIN_SIZE_MB,
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
    except (ValueError, Exception):
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
