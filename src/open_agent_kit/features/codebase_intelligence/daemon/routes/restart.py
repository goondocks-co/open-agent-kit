"""Self-restart and upgrade-and-restart routes for the CI daemon.

Uses ``/bin/sh`` (not ``sys.executable``) for the restarter subprocess because
after a package-manager upgrade (e.g. Homebrew) the old Python interpreter that
started this daemon may have been deleted from disk.
"""

import asyncio
import logging
import os
import shlex
import signal
import subprocess
from http import HTTPStatus

from fastapi import APIRouter, HTTPException

from open_agent_kit.features.codebase_intelligence.cli_command import (
    resolve_ci_cli_command,
)
from open_agent_kit.features.codebase_intelligence.constants import (
    CI_RESTART_API_PATH,
    CI_RESTART_ERROR_NO_PROJECT_ROOT,
    CI_RESTART_LOG_SCHEDULING_SHUTDOWN,
    CI_RESTART_LOG_SPAWNING,
    CI_RESTART_ROUTE_TAG,
    CI_RESTART_SHUTDOWN_DELAY_SECONDS,
    CI_RESTART_STATUS_RESTARTING,
    CI_RESTART_SUBPROCESS_DELAY_SECONDS,
    CI_SHUTDOWN_LOG_SIGTERM,
    CI_UPGRADE_AND_RESTART_API_PATH,
    CI_UPGRADE_AND_RESTART_ERROR_SPAWN_DETAIL,
    CI_UPGRADE_AND_RESTART_ERROR_SPAWN_FAILED,
    CI_UPGRADE_AND_RESTART_LOG_SPAWNING,
    CI_UPGRADE_AND_RESTART_STATUS,
)
from open_agent_kit.features.codebase_intelligence.daemon.state import get_state
from open_agent_kit.utils.platform import get_process_detach_kwargs

logger = logging.getLogger(__name__)

router = APIRouter(tags=[CI_RESTART_ROUTE_TAG])

# /bin/sh is guaranteed to exist on all POSIX systems.  We use it instead of
# sys.executable because after a Homebrew (or similar) upgrade the old Python
# interpreter path baked into the running process may no longer exist on disk.
_SHELL = "/bin/sh"


async def _delayed_shutdown() -> None:
    """Wait briefly then send SIGTERM to trigger a graceful shutdown."""
    await asyncio.sleep(CI_RESTART_SHUTDOWN_DELAY_SECONDS)
    logger.info(CI_SHUTDOWN_LOG_SIGTERM)
    os.kill(os.getpid(), signal.SIGTERM)


@router.post(CI_RESTART_API_PATH)
async def self_restart() -> dict:
    """Trigger a graceful self-restart of the CI daemon.

    Spawns a detached ``/bin/sh`` subprocess that waits for the current process
    to exit, then runs ``<cli_command> ci restart`` to bring the daemon back up.
    """
    state = get_state()
    if not state.project_root:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=CI_RESTART_ERROR_NO_PROJECT_ROOT,
        )

    project_root = str(state.project_root)

    # Resolve CLI command from config (e.g. "oak" or a custom wrapper)
    cli_command = resolve_ci_cli_command(state.project_root)

    # Build a shell one-liner: sleep then restart via the CLI on $PATH.
    restart_cmd = (
        f"sleep {CI_RESTART_SUBPROCESS_DELAY_SECONDS} && {shlex.quote(cli_command)} ci restart"
    )

    detach_kwargs = get_process_detach_kwargs()
    logger.info(CI_RESTART_LOG_SPAWNING.format(command=f"{cli_command} ci restart"))
    try:
        subprocess.Popen(
            [_SHELL, "-c", restart_cmd],
            cwd=project_root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            **detach_kwargs,
        )
    except OSError as exc:
        logger.error("Failed to spawn restart subprocess: %s", exc)
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Failed to spawn restart process: {exc}",
        ) from exc

    # Schedule graceful shutdown
    logger.info(CI_RESTART_LOG_SCHEDULING_SHUTDOWN.format(delay=CI_RESTART_SHUTDOWN_DELAY_SECONDS))
    asyncio.create_task(_delayed_shutdown(), name="self_restart_shutdown")

    return {"status": CI_RESTART_STATUS_RESTARTING}


@router.post(CI_UPGRADE_AND_RESTART_API_PATH)
async def upgrade_and_restart() -> dict:
    """Run ``oak upgrade --force`` then restart the daemon.

    Spawns a detached subprocess that runs ``oak upgrade --force ; oak ci restart``.
    The semicolon ensures the restart happens regardless of upgrade exit code —
    if upgrade truly failed the banner will reappear with a fallback message.
    """
    state = get_state()
    if not state.project_root:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=CI_RESTART_ERROR_NO_PROJECT_ROOT,
        )

    project_root = str(state.project_root)
    cli_command = resolve_ci_cli_command(state.project_root)
    quoted_cli = shlex.quote(cli_command)

    # Use ; so restart happens even if upgrade exits non-zero
    upgrade_restart_cmd = (
        f"sleep {CI_RESTART_SUBPROCESS_DELAY_SECONDS} && "
        f"{quoted_cli} upgrade --force ; "
        f"{quoted_cli} ci restart"
    )

    detach_kwargs = get_process_detach_kwargs()
    full_command = f"{cli_command} upgrade --force ; {cli_command} ci restart"
    logger.info(CI_UPGRADE_AND_RESTART_LOG_SPAWNING.format(command=full_command))
    try:
        subprocess.Popen(
            [_SHELL, "-c", upgrade_restart_cmd],
            cwd=project_root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            **detach_kwargs,
        )
    except OSError as exc:
        logger.error(CI_UPGRADE_AND_RESTART_ERROR_SPAWN_FAILED.format(error=exc))
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=CI_UPGRADE_AND_RESTART_ERROR_SPAWN_DETAIL.format(error=exc),
        ) from exc

    # Same shutdown pattern as self_restart
    logger.info(CI_RESTART_LOG_SCHEDULING_SHUTDOWN.format(delay=CI_RESTART_SHUTDOWN_DELAY_SECONDS))
    asyncio.create_task(_delayed_shutdown(), name="upgrade_restart_shutdown")

    return {"status": CI_UPGRADE_AND_RESTART_STATUS}
