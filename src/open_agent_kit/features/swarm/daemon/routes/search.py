"""Search route for the swarm daemon."""

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from open_agent_kit.features.swarm.constants import (
    SWARM_DAEMON_API_PATH_SEARCH,
    SWARM_ERROR_NOT_CONNECTED,
    SWARM_RESPONSE_KEY_ERROR,
    SWARM_RESPONSE_KEY_RESULTS,
    SWARM_ROUTE_TAG,
)
from open_agent_kit.features.swarm.daemon.state import (
    get_swarm_state,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=[SWARM_ROUTE_TAG])


class SearchRequest(BaseModel):
    """Swarm search request body."""

    query: str
    search_type: str = "all"
    limit: int = 10


@router.post(SWARM_DAEMON_API_PATH_SEARCH)
async def swarm_search(body: SearchRequest) -> dict:
    """Search across swarm nodes."""
    state = get_swarm_state()
    if not state.http_client:
        return {SWARM_RESPONSE_KEY_ERROR: SWARM_ERROR_NOT_CONNECTED, SWARM_RESPONSE_KEY_RESULTS: []}
    try:
        return await state.http_client.search(body.query, body.search_type, body.limit)
    except Exception as exc:
        logger.error("Swarm search failed: %s", exc)
        return {SWARM_RESPONSE_KEY_ERROR: str(exc), SWARM_RESPONSE_KEY_RESULTS: []}
