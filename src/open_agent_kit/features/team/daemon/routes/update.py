"""Self-update API routes.

Mounted on both team and swarm daemon routers. Provides endpoints for
checking update status, triggering checks, applying updates, switching
channels, and fetching release notes.
"""

from __future__ import annotations

import asyncio
import logging
from http import HTTPStatus

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from open_agent_kit.constants import VERSION
from open_agent_kit.features.team.daemon.lifecycle.update_checker import (
    check_for_update,
)
from open_agent_kit.features.team.daemon.lifecycle.update_installer import (
    apply_staged_update,
)
from open_agent_kit.features.team.daemon.state import get_state
from open_agent_kit.utils.daemon_lifecycle import delayed_shutdown
from open_agent_kit.utils.global_config import (
    ensure_global_dir,
    load_update_config,
    read_last_check,
    read_staged_update,
    read_update_error,
    save_update_config,
)
from open_agent_kit.utils.update_exempt import check_update_exempt

logger = logging.getLogger(__name__)

VALID_CHANNELS = ("stable", "beta")
GITHUB_RELEASES_URL = (
    "https://api.github.com/repos/goondocks-co/open-agent-kit/releases/tags/v{version}"
)
RELEASE_NOTES_TIMEOUT_SECONDS = 10


class ChannelRequest(BaseModel):
    """Request body for channel switch."""

    channel: str


def create_update_router(daemon_type: str = "team") -> APIRouter:
    """Create an independent update router, parameterised by daemon type.

    Each call returns a **new** ``APIRouter`` with its own closure over
    ``daemon_type``, so team and swarm daemons never share mutable state.
    """
    router = APIRouter(prefix="/api/update", tags=["update"])

    @router.get("/status")
    async def update_status() -> dict:
        """Return current self-update state."""
        exemption = check_update_exempt()
        if exemption:
            return {"exempt": True, "reason": exemption.reason, "message": exemption.message}

        config = load_update_config()
        staged = read_staged_update()
        last_check = read_last_check()
        error = read_update_error()

        return {
            "exempt": False,
            "running_version": VERSION,
            "channel": config.channel,
            "auto_download": config.auto_download,
            "check_interval_hours": config.check_interval_hours,
            "staged_update": staged,
            "last_check": last_check,
            "error": error,
        }

    @router.post("/check")
    async def update_check() -> dict:
        """Trigger an on-demand PyPI version check."""
        exemption = check_update_exempt()
        if exemption:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=exemption.message,
            )

        config = load_update_config()
        result = await check_for_update(running_version=VERSION, config=config)

        return {
            "update_available": result.update_available,
            "latest_version": result.latest_version,
            "channel": result.channel,
            "error": result.error,
        }

    @router.post("/apply")
    async def update_apply() -> dict:
        """Apply a staged update: spawn update script and shut down."""
        exemption = check_update_exempt()
        if exemption:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=exemption.message,
            )

        staged = read_staged_update()
        if not staged:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="No staged update available. Run a check first.",
            )

        state = get_state()
        if not state.project_root:
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail="No project root configured.",
            )

        success = apply_staged_update(
            project_root=state.project_root,
            daemon_type=daemon_type,
        )

        if not success:
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail="Failed to spawn update script.",
            )

        # Schedule daemon shutdown after response is sent
        asyncio.create_task(delayed_shutdown(2, log_message="Shutting down for self-update."))

        return {"status": "applying", "version": staged.get("version")}

    @router.put("/channel")
    async def update_channel(request: ChannelRequest) -> dict:
        """Switch the update channel (stable/beta)."""
        exemption = check_update_exempt()
        if exemption:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=exemption.message,
            )

        if request.channel not in VALID_CHANNELS:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=f"Invalid channel '{request.channel}'. Must be one of: {', '.join(VALID_CHANNELS)}",
            )

        ensure_global_dir()
        config = load_update_config()
        config.channel = request.channel
        save_update_config(config)

        return {
            "channel": config.channel,
            "message": f"Switched to {config.channel} channel.",
        }

    @router.get("/release-notes")
    async def update_release_notes(version: str) -> dict:
        """Fetch release notes from GitHub Releases API."""
        url = GITHUB_RELEASES_URL.format(version=version)
        try:
            async with httpx.AsyncClient(timeout=RELEASE_NOTES_TIMEOUT_SECONDS) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
                return {
                    "version": version,
                    "name": data.get("name", ""),
                    "body": data.get("body", ""),
                    "published_at": data.get("published_at", ""),
                    "html_url": data.get("html_url", ""),
                }
        except Exception as exc:
            logger.warning("Failed to fetch release notes for v%s: %s", version, exc)
            raise HTTPException(
                status_code=HTTPStatus.BAD_GATEWAY,
                detail="Could not fetch release notes.",
            ) from exc

    return router
