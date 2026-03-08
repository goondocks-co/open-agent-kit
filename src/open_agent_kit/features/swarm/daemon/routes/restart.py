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
from open_agent_kit.utils.daemon_lifecycle import delayed_shutdown
from open_agent_kit.utils.platform import get_process_detach_kwargs
from open_agent_kit.utils.release_channel import SHELL, resolve_swarm_cli_command

logger = logging.getLogger(__name__)

router = APIRouter(tags=[SWARM_RESTART_ROUTE_TAG])


def _resolve_cli_command() -> str:
    """Resolve the CLI command for the restart subprocess."""
    return resolve_swarm_cli_command(SWARM_CLI_COMMAND_ENV_VAR)


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
            [SHELL, "-c", restart_cmd],
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
    asyncio.create_task(
        delayed_shutdown(
            SWARM_RESTART_SHUTDOWN_DELAY_SECONDS, log_message=SWARM_RESTART_LOG_SIGTERM
        ),
        name="swarm_self_restart_shutdown",
    )

    return {SWARM_RESPONSE_KEY_STATUS: SWARM_RESTART_STATUS_RESTARTING}
