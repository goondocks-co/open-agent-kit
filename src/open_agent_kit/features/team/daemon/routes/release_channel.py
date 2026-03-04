"""Release channel info and channel-switch routes.

GET  /api/channel        — Returns current channel, version, install method,
                           and available PyPI versions (cached 5 min).
POST /api/channel/switch — Initiates an automated channel switch by spawning
                           a detached subprocess, then gracefully shuts down
                           the daemon (identical pattern to the restart route).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import subprocess
import time
import urllib.request
from http import HTTPStatus
from pathlib import Path
from typing import Final

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from open_agent_kit.constants import VERSION as OAK_VERSION
from open_agent_kit.features.team.cli_command import (
    resolve_ci_cli_command,
)
from open_agent_kit.features.team.constants.release_channel import (
    CI_CHANNEL_API_PATH,
    CI_CHANNEL_BETA,
    CI_CHANNEL_STABLE,
    CI_CHANNEL_SWITCH_API_PATH,
    CI_INSTALL_METHOD_UNKNOWN,
)
from open_agent_kit.features.team.daemon.state import get_state
from open_agent_kit.utils.platform import get_process_detach_kwargs

logger = logging.getLogger(__name__)

router = APIRouter(tags=["channel"])

_SHELL: Final[str] = "/bin/sh"
_PYPI_URL: Final[str] = "https://pypi.org/pypi/oak-ci/json"
_PYPI_TIMEOUT_SECONDS: Final[int] = 5
_PYPI_CACHE_TTL_SECONDS: Final[int] = 300  # 5 minutes
_SWITCH_SUBPROCESS_DELAY_SECONDS: Final[int] = 2
_SHUTDOWN_DELAY_SECONDS: Final[int] = 2

# ---------------------------------------------------------------------------
# PyPI version cache
# ---------------------------------------------------------------------------

_pypi_cache: dict = {"data": None, "ts": 0.0}
_pypi_cache_lock: asyncio.Lock | None = None


def _get_pypi_lock() -> asyncio.Lock:
    """Lazily create the asyncio.Lock (must be created inside an event loop)."""
    global _pypi_cache_lock
    if _pypi_cache_lock is None:
        _pypi_cache_lock = asyncio.Lock()
    return _pypi_cache_lock


def _fetch_pypi_raw() -> bytes:
    """Blocking fetch of the PyPI JSON for oak-ci."""
    req = urllib.request.Request(
        _PYPI_URL,
        headers={"User-Agent": f"oak-ci/{OAK_VERSION} version-check"},
    )
    with urllib.request.urlopen(req, timeout=_PYPI_TIMEOUT_SECONDS) as resp:
        return resp.read()


def _parse_pypi_versions(raw: bytes) -> tuple[str | None, str | None]:
    """Parse stable and latest pre-release version from PyPI JSON response."""
    from packaging.version import Version

    data = json.loads(raw)
    releases = data.get("releases", {})

    stable_versions: list[Version] = []
    beta_versions: list[Version] = []

    for ver_str in releases:
        try:
            v = Version(ver_str)
            if v.pre is None:
                stable_versions.append(v)
            else:
                beta_versions.append(v)
        except Exception:
            pass  # skip unparseable version strings

    stable = str(max(stable_versions)) if stable_versions else None
    beta = str(max(beta_versions)) if beta_versions else None
    return stable, beta


async def _fetch_pypi_versions() -> tuple[str | None, str | None]:
    """Fetch stable and beta versions from PyPI, caching for 5 minutes."""
    lock = _get_pypi_lock()
    async with lock:
        now = time.monotonic()
        cached = _pypi_cache.get("data")
        if cached is not None and (now - _pypi_cache["ts"]) < _PYPI_CACHE_TTL_SECONDS:
            return cached

        try:
            loop = asyncio.get_running_loop()
            raw = await loop.run_in_executor(None, _fetch_pypi_raw)
            result = _parse_pypi_versions(raw)
        except Exception as exc:
            logger.debug("PyPI version fetch failed: %s", exc)
            result = (None, None)

        _pypi_cache["data"] = result
        _pypi_cache["ts"] = now
        return result


# ---------------------------------------------------------------------------
# Channel helpers
# ---------------------------------------------------------------------------


def _get_current_channel(cli_command: str) -> str:
    """Infer release channel from the CLI command name."""
    return CI_CHANNEL_BETA if cli_command == "oak-beta" else CI_CHANNEL_STABLE


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get(CI_CHANNEL_API_PATH)
async def get_channel() -> dict:
    """Return current channel, version, install method, and PyPI availability."""
    from open_agent_kit.features.team.utils.install_detect import (
        detect_install_method,
    )

    state = get_state()
    project_root = state.project_root or Path.cwd()

    cli_command = resolve_ci_cli_command(project_root)
    current_channel = _get_current_channel(cli_command)

    available_stable, available_beta = await _fetch_pypi_versions()

    # Apply no-downgrade rule: suppress beta option when available beta < current
    if available_beta is not None:
        try:
            from packaging.version import Version

            if Version(available_beta) < Version(OAK_VERSION):
                available_beta = None
        except Exception:
            pass  # best-effort comparison; keep beta if parsing fails

    install_method = detect_install_method(cli_command)
    switch_supported = install_method != CI_INSTALL_METHOD_UNKNOWN

    return {
        "current_channel": current_channel,
        "cli_command": cli_command,
        "current_version": OAK_VERSION,
        "install_method": install_method,
        "switch_supported": switch_supported,
        "available_stable_version": available_stable,
        "available_beta_version": available_beta,
    }


class SwitchChannelRequest(BaseModel):
    target_channel: str


@router.post(CI_CHANNEL_SWITCH_API_PATH, status_code=HTTPStatus.ACCEPTED)
async def switch_channel(request: SwitchChannelRequest) -> dict:
    """Initiate a channel switch and restart the daemon.

    Validates the request, builds the install command, pre-emptively updates
    cli_command in the CI config, spawns a detached subprocess to perform the
    switch, then signals the daemon to shut down.
    """
    from open_agent_kit.features.team.utils.install_detect import (
        build_channel_switch_command,
        detect_install_method,
    )

    state = get_state()
    if not state.project_root:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail="No project root configured.",
        )

    project_root = state.project_root
    cli_command = resolve_ci_cli_command(project_root)
    current_channel = _get_current_channel(cli_command)

    target = request.target_channel
    if target not in (CI_CHANNEL_STABLE, CI_CHANNEL_BETA):
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"Invalid target_channel '{target}'. Must be 'stable' or 'beta'.",
        )

    if target == current_channel:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"Already on the '{target}' channel.",
        )

    install_method = detect_install_method(cli_command)
    switch_cmd = build_channel_switch_command(
        from_channel=current_channel,
        to_channel=target,
        install_method=install_method,
        project_root=str(project_root),
    )

    if switch_cmd is None:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=(
                f"Automated channel switching is not supported for "
                f"install method '{install_method}'. Switch manually."
            ),
        )

    # Pre-emptively update cli_command in CI config to the new binary name.
    new_cli_command = "oak-beta" if target == CI_CHANNEL_BETA else "oak"
    try:
        from open_agent_kit.features.team.config import (
            load_ci_config,
            save_ci_config,
        )

        ci_config = load_ci_config(project_root)
        ci_config.cli_command = new_cli_command
        save_ci_config(project_root, ci_config)
    except Exception as exc:
        logger.warning("Could not pre-update cli_command in CI config: %s", exc)

    # Spawn detached subprocess: sleep briefly, then run the switch command.
    full_cmd = f"sleep {_SWITCH_SUBPROCESS_DELAY_SECONDS} && {switch_cmd}"
    detach_kwargs = get_process_detach_kwargs()
    logger.info("Spawning channel switch subprocess: %s", switch_cmd)
    try:
        subprocess.Popen(
            [_SHELL, "-c", full_cmd],
            cwd=str(project_root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            **detach_kwargs,
        )
    except OSError as exc:
        logger.error("Failed to spawn channel switch subprocess: %s", exc)
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Failed to spawn switch subprocess: {exc}",
        ) from exc

    # Gracefully shut down so the new daemon takes over.
    async def _delayed_shutdown() -> None:
        await asyncio.sleep(_SHUTDOWN_DELAY_SECONDS)
        logger.info("Channel switch initiated — shutting down daemon (SIGTERM).")
        os.kill(os.getpid(), signal.SIGTERM)

    asyncio.create_task(_delayed_shutdown(), name="channel_switch_shutdown")

    return {"status": "switching"}
