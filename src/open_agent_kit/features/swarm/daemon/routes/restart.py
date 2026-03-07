"""Self-restart route for the swarm daemon.

Spawns a detached subprocess that runs ``oak swarm restart -n <swarm_id>``
after the current process exits, then sends SIGTERM to trigger graceful
shutdown.

Uses ``/bin/sh`` (not ``sys.executable``) for the restarter subprocess because
after a package-manager upgrade the old Python interpreter that started this
daemon may have been deleted from disk.
"""

import asyncio
import logging
import os
import shlex
import signal
import subprocess
from http import HTTPStatus

from fastapi import APIRouter, HTTPException

from open_agent_kit.features.swarm.constants import (
    SWARM_CLI_COMMAND_ENV_VAR,
    SWARM_DAEMON_API_PATH_RESTART,
    SWARM_ENV_VAR_ID,
    SWARM_RESPONSE_KEY_STATUS,
    SWARM_RESTART_ERROR_NO_SWARM_ID,
    SWARM_RESTART_ERROR_SPAWN_DETAIL,
    SWARM_RESTART_LOG_SCHEDULING_SHUTDOWN,
    SWARM_RESTART_LOG_SIGTERM,
    SWARM_RESTART_LOG_SPAWN_FAILED,
    SWARM_RESTART_LOG_SPAWNING,
    SWARM_RESTART_ROUTE_TAG,
    SWARM_RESTART_SHUTDOWN_DELAY_SECONDS,
    SWARM_RESTART_STATUS_RESTARTING,
    SWARM_RESTART_SUBPROCESS_DELAY_SECONDS,
)
from open_agent_kit.utils.platform import get_process_detach_kwargs

logger = logging.getLogger(__name__)

router = APIRouter(tags=[SWARM_RESTART_ROUTE_TAG])

# /bin/sh is guaranteed to exist on all POSIX systems.  We use it instead of
# sys.executable because after a Homebrew (or similar) upgrade the old Python
# interpreter path baked into the running process may no longer exist on disk.
_SHELL = "/bin/sh"

# Default CLI command — matches CI_CLI_COMMAND_DEFAULT from team constants.
_CLI_COMMAND_DEFAULT = "oak"


def _resolve_cli_command() -> str:
    """Resolve the CLI command to use for the restart subprocess.

    Reads ``OAK_CLI_COMMAND`` env var (set by ``SwarmDaemonManager.start()``
    at daemon launch time).  This ensures the restart uses the same binary
    that started the daemon (e.g. ``oak-dev`` in development).

    Falls back to ``shutil.which("oak")`` if the env var is unset.
    """
    import shutil

    from_env = os.environ.get(SWARM_CLI_COMMAND_ENV_VAR, "").strip()
    if from_env:
        # Resolve full path so the detached subprocess doesn't depend on $PATH
        resolved = shutil.which(from_env)
        return resolved or from_env

    path = shutil.which(_CLI_COMMAND_DEFAULT)
    return path or _CLI_COMMAND_DEFAULT


async def _delayed_shutdown() -> None:
    """Wait briefly then send SIGTERM to trigger a graceful shutdown."""
    await asyncio.sleep(SWARM_RESTART_SHUTDOWN_DELAY_SECONDS)
    logger.info(SWARM_RESTART_LOG_SIGTERM)
    os.kill(os.getpid(), signal.SIGTERM)


@router.post(SWARM_DAEMON_API_PATH_RESTART)
async def restart_daemon() -> dict:
    """Trigger a graceful self-restart of the swarm daemon.

    Spawns a detached ``/bin/sh`` subprocess that waits for the current process
    to exit, then runs ``oak swarm restart -n <swarm_id>`` to bring the daemon
    back up.  This routes through ``SwarmDaemonManager.restart()`` which
    properly manages the PID file and process lifecycle (stop → start).
    """
    swarm_id = os.environ.get(SWARM_ENV_VAR_ID, "")
    if not swarm_id:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=SWARM_RESTART_ERROR_NO_SWARM_ID,
        )

    cli_command = _resolve_cli_command()
    cli_restart = f"{shlex.quote(cli_command)} swarm restart -n {shlex.quote(swarm_id)}"

    # Build a shell one-liner: sleep (so the current process can finish
    # shutting down), then restart via the CLI which manages the full lifecycle.
    restart_cmd = f"sleep {SWARM_RESTART_SUBPROCESS_DELAY_SECONDS} && {cli_restart}"

    detach_kwargs = get_process_detach_kwargs()
    logger.info(SWARM_RESTART_LOG_SPAWNING, cli_restart)
    try:
        subprocess.Popen(
            [_SHELL, "-c", restart_cmd],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            **detach_kwargs,
        )
    except OSError as exc:
        logger.error(SWARM_RESTART_LOG_SPAWN_FAILED, exc)
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=SWARM_RESTART_ERROR_SPAWN_DETAIL.format(error=exc),
        ) from exc

    # Schedule graceful shutdown
    logger.info(
        SWARM_RESTART_LOG_SCHEDULING_SHUTDOWN.format(delay=SWARM_RESTART_SHUTDOWN_DELAY_SECONDS)
    )
    asyncio.create_task(_delayed_shutdown(), name="swarm_self_restart_shutdown")

    return {SWARM_RESPONSE_KEY_STATUS: SWARM_RESTART_STATUS_RESTARTING}
