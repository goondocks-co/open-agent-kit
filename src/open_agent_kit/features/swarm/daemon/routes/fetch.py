"""Fetch detail route for the swarm daemon."""

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from open_agent_kit.features.swarm.constants import (
    MCP_TOOL_FETCH,
    SWARM_DAEMON_API_PATH_FETCH,
    SWARM_DEFAULT_FETCH_TIMEOUT_SECONDS,
    SWARM_ERROR_NOT_CONNECTED,
    SWARM_RESPONSE_KEY_ERROR,
    SWARM_ROUTE_TAG,
)
from open_agent_kit.features.swarm.daemon.state import (
    get_swarm_state,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=[SWARM_ROUTE_TAG])


class FetchRequest(BaseModel):
    """Swarm fetch request body."""

    ids: list[str]
    project_slug: str


@router.post(SWARM_DAEMON_API_PATH_FETCH)
async def swarm_fetch(body: FetchRequest) -> dict:
    """Fetch full content for chunk IDs from a specific project."""
    state = get_swarm_state()
    if not state.http_client:
        return {SWARM_RESPONSE_KEY_ERROR: SWARM_ERROR_NOT_CONNECTED}
    try:
        return await state.http_client.call(
            tool_name=MCP_TOOL_FETCH,
            arguments={"ids": body.ids},
            target_project=body.project_slug,
            timeout=SWARM_DEFAULT_FETCH_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        logger.error("Swarm fetch failed: %s", exc)
        return {SWARM_RESPONSE_KEY_ERROR: str(exc)}
