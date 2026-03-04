"""Health route for the swarm daemon."""

from fastapi import APIRouter

from open_agent_kit.features.swarm.constants import (
    SWARM_DAEMON_API_PATH_HEALTH,
    SWARM_HEALTH_STATUS_OK,
    SWARM_RESPONSE_KEY_STATUS,
    SWARM_RESTART_ROUTE_TAG,
)

router = APIRouter(tags=[SWARM_RESTART_ROUTE_TAG])


@router.get(SWARM_DAEMON_API_PATH_HEALTH)
async def health() -> dict:
    """Basic health check."""
    return {SWARM_RESPONSE_KEY_STATUS: SWARM_HEALTH_STATUS_OK}
