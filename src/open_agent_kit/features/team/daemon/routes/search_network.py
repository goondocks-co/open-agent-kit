"""Federated network search route for the CI daemon.

Provides the POST /api/search/network endpoint that fans out search
queries to peer nodes via the cloud relay.
"""

import logging
from http import HTTPStatus
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from open_agent_kit.features.team.constants import (
    CLOUD_RELAY_FEDERATED_SEARCH_DEFAULT_LIMIT,
    SEARCH_TYPE_ALL,
    SEARCH_TYPE_CODE,
)
from open_agent_kit.features.team.daemon.routes._utils import (
    handle_route_errors,
)
from open_agent_kit.features.team.daemon.state import get_state

logger = logging.getLogger(__name__)

router = APIRouter(tags=["search"])

# Error messages
_ERR_RELAY_NOT_CONNECTED = "Cloud relay not connected"
_ERR_QUERY_REQUIRED = "query is required"
_ERR_CODE_SEARCH_REJECTED = (
    "Code search is project-specific and cannot be shared across the network"
)


class NetworkSearchRequest(BaseModel):
    """Request body for federated network search."""

    query: str = ""
    search_type: str = SEARCH_TYPE_ALL
    limit: int = CLOUD_RELAY_FEDERATED_SEARCH_DEFAULT_LIMIT


@router.post("/api/search/network")
@handle_route_errors("network search")
async def search_network(body: NetworkSearchRequest) -> dict[str, Any]:
    """Perform a federated search across connected relay nodes.

    Sends the query to the cloud relay which fans it out to peer nodes.
    Code searches are rejected because code is project-specific and
    not meaningful across different projects.

    Returns:
        Dict with results list and optional sources metadata.
    """
    state = get_state()

    if state.cloud_relay_client is None:
        raise HTTPException(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE, detail=_ERR_RELAY_NOT_CONNECTED
        )

    relay_status = state.cloud_relay_client.get_status()
    if not relay_status.connected:
        raise HTTPException(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE, detail=_ERR_RELAY_NOT_CONNECTED
        )

    if not body.query:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=_ERR_QUERY_REQUIRED)

    if body.search_type == SEARCH_TYPE_CODE:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=_ERR_CODE_SEARCH_REJECTED,
        )

    result = await state.cloud_relay_client.search_network(
        query=body.query,
        search_type=body.search_type,
        limit=body.limit,
    )

    return result
