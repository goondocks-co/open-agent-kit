"""Nodes route for the swarm daemon."""

import logging

from fastapi import APIRouter

from open_agent_kit.features.swarm.constants import (
    SWARM_DAEMON_API_PATH_NODES,
    SWARM_ERROR_NOT_CONNECTED,
    SWARM_RESPONSE_KEY_ERROR,
    SWARM_RESPONSE_KEY_TEAMS,
    SWARM_ROUTE_TAG,
)
from open_agent_kit.features.swarm.daemon.state import (
    get_swarm_state,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=[SWARM_ROUTE_TAG])


@router.get(SWARM_DAEMON_API_PATH_NODES)
async def swarm_nodes() -> dict:
    """List all nodes in the swarm."""
    state = get_swarm_state()
    if not state.http_client:
        return {SWARM_RESPONSE_KEY_ERROR: SWARM_ERROR_NOT_CONNECTED, SWARM_RESPONSE_KEY_TEAMS: []}
    try:
        return await state.http_client.nodes()
    except Exception as exc:
        logger.error("Swarm nodes request failed: %s", exc)
        return {SWARM_RESPONSE_KEY_ERROR: str(exc), SWARM_RESPONSE_KEY_TEAMS: []}
