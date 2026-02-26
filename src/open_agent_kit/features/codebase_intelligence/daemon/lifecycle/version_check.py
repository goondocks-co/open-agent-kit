"""Version, upgrade, and stale-install detection.

Extracted from ``server.py`` -- groups all version-related lifecycle
checks into a single module.
"""

import asyncio
import logging
import os
import shlex
import signal
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from open_agent_kit.features.codebase_intelligence.constants import (
    CI_RESTART_SHUTDOWN_DELAY_SECONDS,
    CI_RESTART_SUBPROCESS_DELAY_SECONDS,
    CI_STALE_INSTALL_DETECTED_LOG,
)
from open_agent_kit.features.codebase_intelligence.daemon.state import get_state
from open_agent_kit.utils.platform import get_process_detach_kwargs

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.daemon.state import DaemonState

logger = logging.getLogger(__name__)


def check_version(state: "DaemonState") -> None:
    """Check if installed version differs from running version (sync)."""
    import importlib.metadata

    from open_agent_kit.config.paths import OAK_DIR
    from open_agent_kit.constants import VERSION
    from open_agent_kit.features.codebase_intelligence.constants import (
        CI_CLI_VERSION_FILE,
        CI_DATA_DIR,
    )
    from open_agent_kit.features.codebase_intelligence.utils.version import (
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
    state.update_available = installed is not None and is_meaningful_upgrade(VERSION, installed)


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
    from open_agent_kit.features.codebase_intelligence.utils.version import parse_base_release
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


async def _trigger_stale_restart() -> None:
    """Spawn a self-restart when the daemon's install path is gone."""
    from open_agent_kit.features.codebase_intelligence.cli_command import (
        resolve_ci_cli_command,
    )

    state = get_state()
    if not state.project_root:
        return
    cli_command = resolve_ci_cli_command(state.project_root)
    restart_cmd = (
        f"sleep {CI_RESTART_SUBPROCESS_DELAY_SECONDS} && {shlex.quote(cli_command)} ci restart"
    )
    subprocess.Popen(
        ["/bin/sh", "-c", restart_cmd],
        cwd=str(state.project_root),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        **get_process_detach_kwargs(),
    )
    await asyncio.sleep(CI_RESTART_SHUTDOWN_DELAY_SECONDS)
    os.kill(os.getpid(), signal.SIGTERM)


async def periodic_version_check() -> None:
    """Periodically check for version/upgrade issues (power-state-aware)."""
    from open_agent_kit.features.codebase_intelligence.constants import (
        CI_VERSION_CHECK_INTERVAL_SECONDS,
        POWER_STATE_DEEP_SLEEP,
    )

    state = get_state()
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

        # Auto-restart when installed package version is newer than running
        # version.  This handles in-place package upgrades where the daemon's
        # Python process still runs old bytecode but the on-disk package has
        # already been replaced.  File-existence checks (_is_install_stale)
        # miss this case because the files still exist -- just with new content.
        if state.update_available:
            from open_agent_kit.constants import VERSION

            logger.warning(
                "Package version mismatch (running=%s, installed=%s) "
                "-- auto-restarting daemon to pick up new code",
                VERSION,
                state.installed_version,
            )
            await _trigger_stale_restart()
            return  # Stop loop -- process is about to exit

        # Detect stale installation (e.g. package upgraded, old cellar deleted)
        try:
            if _is_install_stale():
                logger.warning(CI_STALE_INSTALL_DETECTED_LOG)
                await _trigger_stale_restart()
                return  # Stop loop -- process is about to exit
        except (OSError, RuntimeError):
            logger.debug("Stale install check failed", exc_info=True)
