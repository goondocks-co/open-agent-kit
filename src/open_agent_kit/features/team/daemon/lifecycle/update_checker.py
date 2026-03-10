"""PyPI update checker for the self-update system.

Periodically polls PyPI to detect new OAK versions. Filters by channel
config (stable/beta) and applies no-downgrade rule.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

from packaging.version import Version

from open_agent_kit.utils.global_config import (
    UpdateConfig,
    load_update_config,
    read_last_check,
    write_last_check,
)
from open_agent_kit.utils.release_channel import fetch_pypi_raw, parse_pypi_versions

logger = logging.getLogger(__name__)

PYPI_PACKAGE_NAME = "oak-ci"


@dataclass
class UpdateCheckResult:
    """Result of a PyPI version check."""

    update_available: bool = False
    latest_version: str | None = None
    running_version: str | None = None
    channel: str = "stable"
    error: str | None = None
    checked_at: float = field(default_factory=time.time)


def should_check_now(check_interval_hours: int) -> bool:
    """Return True if enough time has passed since the last check."""
    last = read_last_check()
    if not last or "timestamp" not in last:
        return True
    elapsed_hours = (time.time() - last["timestamp"]) / 3600
    return elapsed_hours >= check_interval_hours


async def check_for_update(
    running_version: str,
    config: UpdateConfig | None = None,
) -> UpdateCheckResult:
    """Check PyPI for a newer version of OAK.

    Args:
        running_version: The currently running OAK version string.
        config: Update config (loaded from ~/.oak/update.yaml if None).

    Returns:
        UpdateCheckResult with version info and availability.
    """
    if config is None:
        config = load_update_config()

    try:
        # fetch_pypi_raw is synchronous — run in executor to avoid blocking
        loop = asyncio.get_running_loop()
        raw = await loop.run_in_executor(None, fetch_pypi_raw)
        stable_str, beta_str = parse_pypi_versions(raw)

        # Determine the best available version for this channel
        if config.channel == "beta":
            # Beta channel: max(stable, beta) — never downgrade
            candidates = []
            if stable_str:
                candidates.append(Version(stable_str))
            if beta_str:
                candidates.append(Version(beta_str))
            best = max(candidates) if candidates else None
        else:
            # Stable channel: only stable releases
            best = Version(stable_str) if stable_str else None

        if best is None:
            return UpdateCheckResult(
                running_version=running_version,
                channel=config.channel,
            )

        running = Version(running_version)
        is_newer = best > running

        result = UpdateCheckResult(
            update_available=is_newer,
            latest_version=str(best) if is_newer else None,
            running_version=running_version,
            channel=config.channel,
        )

        # Record the check
        write_last_check(
            {
                "timestamp": time.time(),
                "version": str(best),
                "update_available": is_newer,
                "channel": config.channel,
            }
        )

        return result

    except Exception as exc:
        logger.warning("PyPI update check failed: %s", exc)
        return UpdateCheckResult(
            running_version=running_version,
            channel=config.channel,
            error=str(exc),
        )
