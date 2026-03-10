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
from open_agent_kit.features.team.constants.release_channel import (
    CI_CHANNEL_BETA,
    CI_CHANNEL_STABLE,
)
from open_agent_kit.features.team.daemon.lifecycle.update_checker import (
    check_for_update,
    should_check_now,
)
from open_agent_kit.features.team.daemon.lifecycle.update_downloader import (
    download_and_stage,
)
from open_agent_kit.features.team.daemon.lifecycle.update_installer import (
    apply_staged_update,
)
from open_agent_kit.features.team.daemon.state import get_state
from open_agent_kit.utils.daemon_lifecycle import delayed_shutdown
from open_agent_kit.utils.global_config import (
    UpdateConfig,
    ensure_global_dir,
    load_update_config,
    read_last_check,
    read_staged_update,
    read_update_error,
    save_update_config,
)
from open_agent_kit.utils.update_exempt import check_update_exempt

logger = logging.getLogger(__name__)

VALID_CHANNELS = (CI_CHANNEL_STABLE, CI_CHANNEL_BETA)
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

    # Guard against spawning duplicate background check tasks
    _active_bg_task: asyncio.Task | None = None  # type: ignore[type-arg]

    @router.get("/status")
    async def update_status() -> dict:
        """Return current self-update state.

        Triggers a background PyPI check when ``last_check`` is stale,
        so UI polling naturally drives update detection without needing
        a separate background loop.
        """
        nonlocal _active_bg_task

        exemption = check_update_exempt()
        if exemption:
            return {"exempt": True, "reason": exemption.reason, "message": exemption.message}

        config = load_update_config()
        staged = read_staged_update()
        last_check = read_last_check()
        error = read_update_error()

        # Trigger a background check if the last one is stale and no task is running
        if should_check_now(config.check_interval_hours, last_check=last_check):
            if _active_bg_task is None or _active_bg_task.done():
                _active_bg_task = asyncio.create_task(
                    _background_check_and_stage(config),
                    name="update_check_on_read",
                )

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

        # Kick off download immediately so user doesn't wait
        if result.update_available and result.latest_version:
            staged = read_staged_update()
            if not staged or staged.get("version") != result.latest_version:
                asyncio.create_task(
                    download_and_stage(
                        result.latest_version,
                        channel=config.channel,
                        pypi_raw=result.pypi_raw,
                    ),
                    name="update_download_manual",
                )

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

    async def _background_check_and_stage(config: UpdateConfig) -> None:
        """Run a PyPI check and optional download in the background.

        Shared by the status endpoint (check-on-read) and the manual check
        endpoint. Swallows all exceptions so fire-and-forget callers are safe.
        """
        try:
            result = await check_for_update(running_version=VERSION, config=config)
            if result.update_available and config.auto_download and result.latest_version:
                staged = read_staged_update()
                if not staged or staged.get("version") != result.latest_version:
                    await download_and_stage(
                        result.latest_version,
                        channel=config.channel,
                        pypi_raw=result.pypi_raw,
                    )
        except Exception as exc:
            logger.warning("Background update check failed: %s", exc)

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
