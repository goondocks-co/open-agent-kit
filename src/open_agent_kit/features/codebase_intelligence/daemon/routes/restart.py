"""Self-restart route for the CI daemon."""

import asyncio
import logging
import os
import signal
import subprocess
import sys
import textwrap
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
)
from open_agent_kit.features.codebase_intelligence.daemon.state import get_state
from open_agent_kit.utils.platform import get_process_detach_kwargs

logger = logging.getLogger(__name__)

router = APIRouter(tags=[CI_RESTART_ROUTE_TAG])


@router.post(CI_RESTART_API_PATH)
async def self_restart() -> dict:
    """Trigger a graceful self-restart of the CI daemon.

    Spawns a detached subprocess that waits for the current process to exit,
    then runs ``<cli_command> ci restart`` to bring the daemon back up.
    """
    state = get_state()
    if not state.project_root:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=CI_RESTART_ERROR_NO_PROJECT_ROOT,
        )

    project_root = str(state.project_root)

    # Resolve CLI command from config
    cli_command = resolve_ci_cli_command(state.project_root)

    # Spawn detached restarter subprocess
    restarter_code = textwrap.dedent(f"""\
        import time, subprocess
        time.sleep({CI_RESTART_SUBPROCESS_DELAY_SECONDS})
        subprocess.run(["{cli_command}", "ci", "restart"], cwd="{project_root}")
    """)

    detach_kwargs = get_process_detach_kwargs()
    logger.info(CI_RESTART_LOG_SPAWNING.format(command=f"{cli_command} ci restart"))
    subprocess.Popen(
        [sys.executable, "-c", restarter_code],
        cwd=project_root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        **detach_kwargs,
    )

    # Schedule graceful shutdown
    async def _delayed_shutdown() -> None:
        await asyncio.sleep(CI_RESTART_SHUTDOWN_DELAY_SECONDS)
        logger.info("Self-restart: sending SIGTERM")
        os.kill(os.getpid(), signal.SIGTERM)

    logger.info(CI_RESTART_LOG_SCHEDULING_SHUTDOWN.format(delay=CI_RESTART_SHUTDOWN_DELAY_SECONDS))
    asyncio.create_task(_delayed_shutdown(), name="self_restart_shutdown")

    return {"status": CI_RESTART_STATUS_RESTARTING}
