"""Version, upgrade, and stale-install detection.

Extracted from ``server.py`` -- groups all version-related lifecycle
checks into a single module.
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from open_agent_kit.features.team.daemon.state import DaemonState

logger = logging.getLogger(__name__)


def check_version(state: "DaemonState") -> None:
    """Check if installed version differs from running version (sync)."""
    import importlib.metadata

    from open_agent_kit.config.paths import OAK_DIR
    from open_agent_kit.constants import VERSION
    from open_agent_kit.features.team.constants import (
        CI_CLI_VERSION_FILE,
        CI_DATA_DIR,
    )
    from open_agent_kit.features.team.utils.version import (
        is_meaningful_upgrade,
    )

    if not state.project_root:
        return

    installed = None
    # Primary: read stamp file
    stamp = state.project_root / OAK_DIR / CI_DATA_DIR / CI_CLI_VERSION_FILE
    try:
        if stamp.exists():
            installed = stamp.read_text().strip()
    except OSError:
        pass

    # Secondary: importlib.metadata fallback
    if installed is None:
        try:
            installed = importlib.metadata.version("open_agent_kit")
        except (ImportError, importlib.metadata.PackageNotFoundError):
            pass

    state.installed_version = installed

    # PEP 440 local-version builds (e.g. "1.3.1.dev1+g8585b791f") are editable
    # installs running directly from source.  The "+" local segment can never
    # appear on PyPI -- it always means the code is loaded from the working
    # tree, so restarting would loop forever (same source loaded each time).
    # Plain ".dev" versions without "+" may be published pre-releases and
    # correctly trigger a restart when a newer release stamp is found.
    is_local_build = "+" in VERSION
    state.update_available = (
        not is_local_build and installed is not None and is_meaningful_upgrade(VERSION, installed)
    )


def check_upgrade_needed(state: "DaemonState") -> None:
    """Check if the project needs ``oak upgrade`` (sync).

    Two lightweight signals:
    1. Config version differs from package VERSION -- the package was updated
       but ``oak upgrade`` hasn't been run yet (covers commands, skills,
       hooks, MCP servers, settings, gitignore, structural repairs).
    2. Pending migrations exist.
    """
    if not state.project_root:
        return

    from open_agent_kit.constants import VERSION
    from open_agent_kit.features.team.utils.version import parse_base_release
    from open_agent_kit.services.config_service import ConfigService
    from open_agent_kit.services.migrations import get_migrations
    from open_agent_kit.services.state_service import StateService

    # Signal 1: config version vs package version (base release only).
    # Compare base release tuples so dev suffixes (e.g. 1.2.6.dev0+ghash)
    # don't cause false "upgrade needed" in development environments.
    try:
        config = ConfigService(state.project_root).load_config()
        config_version_outdated = parse_base_release(config.version) != parse_base_release(VERSION)
    except (OSError, ValueError):
        config_version_outdated = False

    # Signal 2: pending migrations
    all_ids = {m[0] for m in get_migrations()}
    applied = set(StateService(state.project_root).get_applied_migrations())
    pending = all_ids - applied

    state.config_version_outdated = config_version_outdated
    state.pending_migration_count = len(pending)
    state.upgrade_needed = config_version_outdated or len(pending) > 0


def _is_install_stale() -> bool:
    """Check if the running daemon's package installation was removed from disk."""
    if not Path(sys.executable).exists():
        return True
    static_index = Path(__file__).parent.parent / "static" / "index.html"
    if not static_index.exists():
        return True
    return False


async def periodic_version_check() -> None:
    """Periodically check for version/upgrade issues (power-state-aware).

    Detects version mismatches and stale installs, setting state flags that
    the UI reads to show the upgrade banner.  Does NOT auto-restart — the
    user controls restarts via the UI banner or ``oak team restart``.

    Previous versions auto-restarted the daemon when a mismatch was detected,
    but this caused infinite restart loops when the condition persisted
    (e.g. editable installs, stamp file mismatches), accumulating hundreds
    of orphaned daemon processes.
    """
    from open_agent_kit.features.team.constants import (
        CI_VERSION_CHECK_INTERVAL_SECONDS,
        POWER_STATE_DEEP_SLEEP,
    )
    from open_agent_kit.features.team.daemon.state import get_state

    state = get_state()
    _stale_logged = False

    while True:
        await asyncio.sleep(CI_VERSION_CHECK_INTERVAL_SECONDS)

        # Skip all checks in deep sleep -- daemon is dormant, no UI viewers.
        # Checks resume when hook activity wakes the daemon back to ACTIVE.
        if state.power_state == POWER_STATE_DEEP_SLEEP:
            continue

        try:
            check_version(state)
        except (OSError, ValueError, RuntimeError):
            logger.debug("Version check failed", exc_info=True)

        try:
            check_upgrade_needed(state)
        except (OSError, ValueError, RuntimeError):
            logger.debug("Upgrade check failed", exc_info=True)

        if state.update_available:
            from open_agent_kit.constants import VERSION

            logger.info(
                "Package update available (running=%s, installed=%s) "
                "-- restart daemon to pick up new code",
                VERSION,
                state.installed_version,
            )

        # Detect stale installation (e.g. package upgraded, old cellar deleted).
        # Log once to avoid spamming; the UI banner handles user notification.
        try:
            if _is_install_stale() and not _stale_logged:
                logger.warning(
                    "Stale install detected (Python executable or static "
                    "assets missing from disk). Restart the daemon to resolve."
                )
                _stale_logged = True
        except (OSError, RuntimeError):
            logger.debug("Stale install check failed", exc_info=True)
