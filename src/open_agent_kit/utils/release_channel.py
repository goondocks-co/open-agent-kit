"""Shared release-channel helpers used by both team and swarm daemon routes.

This module centralises PyPI version fetching (with caching) and the
``build_channel_info`` response builder so the two daemon route files only
contain their own wiring logic.

Channel switching is handled via ``~/.oak/update.yaml``
(``/api/update/channel`` PUT).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import urllib.request
from typing import Final

from open_agent_kit.constants import VERSION as OAK_VERSION

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PYPI_URL: Final[str] = "https://pypi.org/pypi/oak-ci/json"
PYPI_TIMEOUT_SECONDS: Final[int] = 5
PYPI_CACHE_TTL_SECONDS: Final[int] = 300  # 5 minutes

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


def fetch_pypi_raw() -> bytes:
    """Blocking fetch of the PyPI JSON for oak-ci."""
    req = urllib.request.Request(
        PYPI_URL,
        headers={"User-Agent": f"oak-ci/{OAK_VERSION} version-check"},
    )
    with urllib.request.urlopen(req, timeout=PYPI_TIMEOUT_SECONDS) as resp:
        result: bytes = resp.read()
        return result


def parse_pypi_versions(raw: bytes) -> tuple[str | None, str | None]:
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


async def fetch_pypi_versions() -> tuple[str | None, str | None]:
    """Fetch stable and beta versions from PyPI, caching for 5 minutes."""
    lock = _get_pypi_lock()
    async with lock:
        now = time.monotonic()
        cached: tuple[str | None, str | None] | None = _pypi_cache.get("data")
        if cached is not None and (now - _pypi_cache["ts"]) < PYPI_CACHE_TTL_SECONDS:
            return cached

        try:
            loop = asyncio.get_running_loop()
            raw = await loop.run_in_executor(None, fetch_pypi_raw)
            result = parse_pypi_versions(raw)
        except Exception as exc:
            logger.debug("PyPI version fetch failed: %s", exc)
            result = (None, None)

        _pypi_cache["data"] = result
        _pypi_cache["ts"] = now
        return result


# ---------------------------------------------------------------------------
# Swarm CLI helper (still needed for swarm channel info route)
# ---------------------------------------------------------------------------


def resolve_swarm_cli_command(env_var: str, default: str = "oak") -> str:
    """Resolve the CLI command for a swarm daemon subprocess.

    Reads the given *env_var* (set by ``SwarmDaemonManager.start()`` at daemon
    launch time) and resolves it to a full path via ``shutil.which``.  Falls
    back to *default* when the env var is unset.
    """
    import os
    import shutil

    from_env = os.environ.get(env_var, "").strip()
    if from_env:
        resolved = shutil.which(from_env)
        return resolved or from_env

    path = shutil.which(default)
    return path or default


# ---------------------------------------------------------------------------
# Shared response builder
# ---------------------------------------------------------------------------


async def build_channel_info() -> dict:
    """Build the channel info response dict used by GET /api/channel.

    Channel is read from ``~/.oak/update.yaml`` (the global update config)
    rather than inferred from the running binary name.  Both the team and
    swarm daemons return the same shape.
    """
    from open_agent_kit.utils.global_config import load_update_config

    config = load_update_config()
    current_channel = config.channel

    available_stable, available_beta = await fetch_pypi_versions()

    # Apply no-downgrade rule: suppress beta option when available beta < current
    if available_beta is not None:
        try:
            from packaging.version import Version

            if Version(available_beta) < Version(OAK_VERSION):
                available_beta = None
        except Exception:
            pass  # best-effort comparison; keep beta if parsing fails

    return {
        "current_channel": current_channel,
        "current_version": OAK_VERSION,
        "available_stable_version": available_stable,
        "available_beta_version": available_beta,
    }
