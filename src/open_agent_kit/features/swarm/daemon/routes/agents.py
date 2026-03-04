"""Agent session routes for the swarm daemon."""

import logging
from typing import Any

from fastapi import APIRouter

from open_agent_kit.features.swarm.constants import (
    SWARM_DAEMON_API_PATH_AGENTS,
    SWARM_ROUTE_TAG,
)
from open_agent_kit.features.swarm.daemon.state import (
    get_swarm_state,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=[SWARM_ROUTE_TAG])


@router.get(SWARM_DAEMON_API_PATH_AGENTS)
async def list_agent_sessions() -> dict[str, Any]:
    """List active agent sessions connected to this swarm daemon."""
    state = get_swarm_state()
    return {"sessions": state.agent_sessions}
