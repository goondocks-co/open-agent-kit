"""Restart route for the swarm daemon."""

import logging
import os
import signal

from fastapi import APIRouter, BackgroundTasks

from open_agent_kit.features.swarm.constants import (
    SWARM_DAEMON_API_PATH_RESTART,
    SWARM_ROUTE_TAG,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=[SWARM_ROUTE_TAG])


def _schedule_shutdown() -> None:
    """Send SIGTERM to self after a short delay to allow response to complete."""
    import time

    time.sleep(0.5)
    os.kill(os.getpid(), signal.SIGTERM)


@router.post(SWARM_DAEMON_API_PATH_RESTART)
async def restart_daemon(background_tasks: BackgroundTasks) -> dict:
    """Schedule a daemon restart after the response is sent."""
    logger.info("Restart requested via API")
    background_tasks.add_task(_schedule_shutdown)
    return {"status": "restarting"}
