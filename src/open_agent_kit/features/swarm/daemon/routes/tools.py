"""Health check route for the swarm daemon."""

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from open_agent_kit.features.swarm.constants import (
    SWARM_DAEMON_API_PATH_HEALTH_CHECK,
    SWARM_ERROR_NOT_CONNECTED,
    SWARM_RESPONSE_KEY_ERROR,
    SWARM_ROUTE_TAG,
)
from open_agent_kit.features.swarm.daemon.state import (
    get_swarm_state,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=[SWARM_ROUTE_TAG])


class HealthCheckRequest(BaseModel):
    """Swarm health check request body."""

    team_slug: str


@router.post(SWARM_DAEMON_API_PATH_HEALTH_CHECK)
async def swarm_health_check(body: HealthCheckRequest) -> dict:
    """Request a health check for a specific team in the swarm."""
    state = get_swarm_state()
    if not state.http_client:
        logger.warning("Health check dropped: not connected to swarm worker")
        return {SWARM_RESPONSE_KEY_ERROR: SWARM_ERROR_NOT_CONNECTED}
    logger.info("Swarm health check: team_slug=%s", body.team_slug)
    try:
        result = await state.http_client.health_check(team_slug=body.team_slug)
        logger.info("Swarm health check complete: team_slug=%s", body.team_slug)
        return result
    except Exception as exc:
        logger.error("Swarm health check failed: team_slug=%s error=%s", body.team_slug, exc)
        return {SWARM_RESPONSE_KEY_ERROR: str(exc)}
