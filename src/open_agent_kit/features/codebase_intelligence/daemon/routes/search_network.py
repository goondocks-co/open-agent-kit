"""Federated network search route for the CI daemon.

Provides the POST /api/search/network endpoint that fans out search
queries to peer nodes via the cloud relay.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from open_agent_kit.features.codebase_intelligence.constants import (
    CLOUD_RELAY_FEDERATED_SEARCH_DEFAULT_LIMIT,
    SEARCH_TYPE_CODE,
)
from open_agent_kit.features.codebase_intelligence.daemon.state import get_state

logger = logging.getLogger(__name__)

router = APIRouter(tags=["search"])


@router.post("/api/search/network")
async def search_network(request: Request) -> dict[str, Any]:
    """Perform a federated search across connected relay nodes.

    Sends the query to the cloud relay which fans it out to peer nodes.
    Code searches are rejected because code is project-specific and
    not meaningful across different projects.

    Returns:
        Dict with results list and optional sources metadata.
    """
    state = get_state()

    if state.cloud_relay_client is None:
        raise HTTPException(status_code=503, detail="Cloud relay not connected")

    relay_status = state.cloud_relay_client.get_status()
    if not relay_status.connected:
        raise HTTPException(status_code=503, detail="Cloud relay not connected")

    body = await request.json()
    query = body.get("query", "")
    search_type = body.get("search_type", "all")
    limit = body.get("limit", CLOUD_RELAY_FEDERATED_SEARCH_DEFAULT_LIMIT)

    if not query:
        raise HTTPException(status_code=400, detail="query is required")

    if search_type == SEARCH_TYPE_CODE:
        raise HTTPException(
            status_code=400,
            detail="Code search is project-specific and cannot be shared across the network",
        )

    result = await state.cloud_relay_client.search_network(
        query=query,
        search_type=search_type,
        limit=limit,
    )

    return result
