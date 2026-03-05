"""Nodes route for the swarm daemon."""

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from open_agent_kit.features.swarm.constants import (
    SWARM_DAEMON_API_PATH_NODE_REMOVE,
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


class _RemoveNodeRequest(BaseModel):
    team_id: str


def _enrich_team(team: dict) -> dict:
    """Map swarm worker team fields to the shape the UI expects."""
    stale = team.get("stale", True)
    return {
        **team,
        "status": "stale" if stale else "connected",
        "last_seen": team.get("last_heartbeat"),
    }


@router.get(SWARM_DAEMON_API_PATH_NODES)
async def swarm_nodes() -> dict:
    """List all nodes in the swarm."""
    state = get_swarm_state()
    if not state.http_client:
        return {SWARM_RESPONSE_KEY_ERROR: SWARM_ERROR_NOT_CONNECTED, SWARM_RESPONSE_KEY_TEAMS: []}
    try:
        data = await state.http_client.nodes()
        # Enrich teams with status/last_seen fields for the UI
        if SWARM_RESPONSE_KEY_TEAMS in data:
            data[SWARM_RESPONSE_KEY_TEAMS] = [
                _enrich_team(t) for t in data[SWARM_RESPONSE_KEY_TEAMS]
            ]
        node_count = len(data.get(SWARM_RESPONSE_KEY_TEAMS, []))
        logger.debug("Nodes list: %d nodes", node_count)
        return data
    except Exception as exc:
        logger.error("Swarm nodes request failed: %s", exc)
        return {SWARM_RESPONSE_KEY_ERROR: str(exc), SWARM_RESPONSE_KEY_TEAMS: []}


@router.post(SWARM_DAEMON_API_PATH_NODE_REMOVE)
async def remove_node(request: _RemoveNodeRequest) -> dict:
    """Remove a node from the swarm."""
    state = get_swarm_state()
    if not state.http_client:
        return {SWARM_RESPONSE_KEY_ERROR: SWARM_ERROR_NOT_CONNECTED}
    logger.info("Removing node: team_id=%s", request.team_id)
    try:
        result = await state.http_client.unregister(request.team_id)
        logger.info("Node removed: team_id=%s", request.team_id)
        return {"success": True, **result}
    except Exception as exc:
        logger.error("Swarm node remove failed: team_id=%s error=%s", request.team_id, exc)
        return {SWARM_RESPONSE_KEY_ERROR: str(exc)}
