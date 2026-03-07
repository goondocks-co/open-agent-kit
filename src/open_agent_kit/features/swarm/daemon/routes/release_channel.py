"""Release channel info and channel-switch routes for the swarm daemon.

GET  /api/channel        — Returns current channel, version, and available
                           PyPI versions (cached 5 min).
POST /api/channel/switch — Updates cli_command in config, runs upgrade to
                           re-render skills/hooks, then restarts the swarm
                           daemon with the new binary.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shlex
import shutil
import signal
import subprocess
import time
import urllib.request
from http import HTTPStatus
from typing import Final

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from open_agent_kit.constants import VERSION as OAK_VERSION
from open_agent_kit.features.swarm.constants import (
    SWARM_CLI_COMMAND_ENV_VAR,
    SWARM_ENV_VAR_ID,
)
from open_agent_kit.features.team.constants.release_channel import (
    CI_CHANNEL_API_PATH,
    CI_CHANNEL_BETA,
    CI_CHANNEL_STABLE,
    CI_CHANNEL_SWITCH_API_PATH,
)
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
        result: bytes = resp.read()
        return result


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

    stable: str | None = str(max(stable_versions)) if stable_versions else None
    beta: str | None = str(max(beta_versions)) if beta_versions else None
    return stable, beta


async def _fetch_pypi_versions() -> tuple[str | None, str | None]:
    """Fetch stable and beta versions from PyPI, caching for 5 minutes."""
    lock = _get_pypi_lock()
    async with lock:
        now = time.monotonic()
        cached: tuple[str | None, str | None] | None = _pypi_cache.get("data")
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
# Channel / CLI command helpers
# ---------------------------------------------------------------------------


def _resolve_cli_command() -> str:
    """Resolve the CLI command from the env var set at daemon launch."""
    from_env = os.environ.get(SWARM_CLI_COMMAND_ENV_VAR, "").strip()
    if from_env:
        resolved = shutil.which(from_env)
        return resolved or from_env

    path = shutil.which("oak")
    return path or "oak"


def _get_current_channel(cli_command: str) -> str:
    """Infer release channel from the CLI command name."""
    from pathlib import Path

    name = Path(cli_command).name
    return CI_CHANNEL_BETA if name == "oak-beta" else CI_CHANNEL_STABLE


def _target_binary_name(target_channel: str) -> str:
    """Return the binary name for a target channel."""
    return "oak-beta" if target_channel == CI_CHANNEL_BETA else "oak"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get(CI_CHANNEL_API_PATH)
async def get_channel() -> dict:
    """Return current channel, version, and PyPI availability."""
    cli_command = _resolve_cli_command()
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

    # Switch is supported if the target binary is installed on the system
    target_channel = CI_CHANNEL_BETA if current_channel == CI_CHANNEL_STABLE else CI_CHANNEL_STABLE
    target_binary = _target_binary_name(target_channel)
    switch_supported = shutil.which(target_binary) is not None

    return {
        "current_channel": current_channel,
        "cli_command": cli_command,
        "current_version": OAK_VERSION,
        "switch_supported": switch_supported,
        "available_stable_version": available_stable,
        "available_beta_version": available_beta,
    }


class SwitchChannelRequest(BaseModel):
    target_channel: str


@router.post(CI_CHANNEL_SWITCH_API_PATH, status_code=HTTPStatus.ACCEPTED)
async def switch_channel(request: SwitchChannelRequest) -> dict:
    """Switch channel: update config, run upgrade, restart swarm daemon.

    1. Validate the target binary exists on PATH.
    2. Update ``cli_command`` in ``.oak/config.yaml`` (if a project root
       is available via the team config).
    3. Spawn a detached subprocess that runs ``{binary} upgrade --force``
       followed by ``{binary} swarm restart -n {swarm_id}``.
    4. Shut down the current daemon so the new one takes over.
    """
    cli_command = _resolve_cli_command()
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

    swarm_id = os.environ.get(SWARM_ENV_VAR_ID, "")
    if not swarm_id:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail="No swarm ID configured. Cannot restart after switch.",
        )

    new_binary = _target_binary_name(target)
    resolved_binary = shutil.which(new_binary)
    if not resolved_binary:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=(
                f"Binary '{new_binary}' not found on PATH. "
                f"Install it first (e.g. brew install goondocks-co/oak/"
                f"{'oak-ci-beta' if target == CI_CHANNEL_BETA else 'oak-ci'})."
            ),
        )

    # Build the switch command: upgrade assets then restart swarm daemon
    switch_cmd = (
        f"{shlex.quote(resolved_binary)} upgrade --force && "
        f"{shlex.quote(resolved_binary)} swarm restart -n {shlex.quote(swarm_id)}"
    )

    # Spawn detached subprocess: sleep briefly, then run the switch command.
    full_cmd = f"sleep {_SWITCH_SUBPROCESS_DELAY_SECONDS} && {switch_cmd}"
    detach_kwargs = get_process_detach_kwargs()
    logger.info("Spawning channel switch subprocess: %s", switch_cmd)
    try:
        subprocess.Popen(
            [_SHELL, "-c", full_cmd],
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
        logger.info("Channel switch initiated — shutting down swarm daemon (SIGTERM).")
        os.kill(os.getpid(), signal.SIGTERM)

    asyncio.create_task(_delayed_shutdown(), name="swarm_channel_switch_shutdown")

    return {"status": "switching"}
