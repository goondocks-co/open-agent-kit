"""Self-restart route for the swarm daemon.

Spawns a detached subprocess that re-launches the uvicorn server after the
current process exits, then sends SIGTERM to trigger graceful shutdown.

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
import sys
from http import HTTPStatus

from fastapi import APIRouter, HTTPException, Request

from open_agent_kit.features.swarm.constants import (
    SWARM_DAEMON_API_PATH_RESTART,
    SWARM_DAEMON_DEFAULT_PORT,
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

# /bin/sh is guaranteed to exist on all POSIX systems.
_SHELL = "/bin/sh"


def _build_uvicorn_command(port: int) -> str:
    """Build the uvicorn command string to re-launch this daemon.

    Re-uses ``sys.executable`` to ensure the same Python is used.  The port
    is taken from the currently running server so it binds to the same address.
    """
    python = shlex.quote(sys.executable)
    return (
        f"{python} -m uvicorn"
        " open_agent_kit.features.swarm.daemon.server:create_app"
        " --factory"
        " --host 127.0.0.1"
        f" --port {port}"
        " --log-level warning"
        " --no-access-log"
    )


async def _delayed_shutdown() -> None:
    """Wait briefly then send SIGTERM to trigger a graceful shutdown."""
    await asyncio.sleep(SWARM_RESTART_SHUTDOWN_DELAY_SECONDS)
    logger.info(SWARM_RESTART_LOG_SIGTERM)
    os.kill(os.getpid(), signal.SIGTERM)


@router.post(SWARM_DAEMON_API_PATH_RESTART)
async def restart_daemon(request: Request) -> dict:
    """Trigger a graceful self-restart of the swarm daemon.

    Spawns a detached ``/bin/sh`` subprocess that waits for the current process
    to exit, then re-launches the uvicorn server with the same environment
    variables.  After spawning, schedules a SIGTERM to shut down the current
    process.
    """
    swarm_id = os.environ.get("OAK_SWARM_ID", "")
    if not swarm_id:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=SWARM_RESTART_ERROR_NO_SWARM_ID,
        )

    # Determine the port the server is currently listening on.
    port = request.url.port or SWARM_DAEMON_DEFAULT_PORT

    uvicorn_cmd = _build_uvicorn_command(port)

    # Build a shell one-liner: sleep (so the current process can finish
    # shutting down), then re-launch uvicorn with the same env vars.
    restart_cmd = f"sleep {SWARM_RESTART_SUBPROCESS_DELAY_SECONDS} && {uvicorn_cmd}"

    # Pass through swarm env vars so the new process inherits them.
    env = os.environ.copy()

    detach_kwargs = get_process_detach_kwargs()
    logger.info(SWARM_RESTART_LOG_SPAWNING, uvicorn_cmd)
    try:
        subprocess.Popen(
            [_SHELL, "-c", restart_cmd],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            env=env,
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
