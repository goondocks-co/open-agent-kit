"""Fetch detail route for the swarm daemon.

Uses the same ``/api/swarm/fetch`` path on the swarm DO that the MCP
``swarm_fetch`` tool uses, ensuring a single code-path for fetch operations.
"""

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from open_agent_kit.features.swarm.constants import (
    SWARM_DAEMON_API_PATH_FETCH,
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
    """Fetch full content for chunk IDs via the swarm DO.

    Calls ``/api/swarm/fetch`` on the swarm worker directly — the same
    endpoint that the MCP ``swarm_fetch`` tool uses.  This avoids the
    broadcast/federate-tool indirection that previously caused empty results.
    """
    state = get_swarm_state()
    if not state.http_client:
        logger.warning("Fetch request dropped: not connected to swarm worker")
        return {SWARM_RESPONSE_KEY_ERROR: SWARM_ERROR_NOT_CONNECTED}

    logger.info(
        "Swarm fetch: %d chunk IDs from project=%s",
        len(body.ids),
        body.project_slug,
    )
    logger.debug(
        "Swarm fetch IDs: %s",
        body.ids[:10] if len(body.ids) > 10 else body.ids,
    )

    try:
        result = await state.http_client.fetch(
            ids=body.ids,
            project_slug=body.project_slug,
        )
        results = result.get("results", [])
        logger.info("Swarm fetch complete: %d chunks returned", len(results))
        return result
    except Exception as exc:
        logger.error("Swarm fetch failed: %s", exc)
        return {SWARM_RESPONSE_KEY_ERROR: str(exc)}
