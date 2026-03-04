"""Status route for the swarm daemon."""

import logging

from fastapi import APIRouter

from open_agent_kit.features.swarm.constants import (
    SWARM_DAEMON_API_PATH_STATUS,
    SWARM_RESPONSE_KEY_CONNECTED,
    SWARM_RESPONSE_KEY_STATUS,
    SWARM_RESPONSE_KEY_SWARM_ID,
    SWARM_RESPONSE_KEY_SWARM_URL,
    SWARM_ROUTE_TAG,
    SWARM_STATUS_CONNECTED,
    SWARM_STATUS_DISCONNECTED,
)
from open_agent_kit.features.swarm.daemon.state import (
    get_swarm_state,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=[SWARM_ROUTE_TAG])


@router.get(SWARM_DAEMON_API_PATH_STATUS)
async def swarm_status() -> dict:
    """Get swarm daemon connection status."""
    state = get_swarm_state()
    connected = state.http_client is not None
    return {
        SWARM_RESPONSE_KEY_SWARM_ID: state.swarm_id,
        SWARM_RESPONSE_KEY_SWARM_URL: state.swarm_url,
        SWARM_RESPONSE_KEY_CONNECTED: connected,
        SWARM_RESPONSE_KEY_STATUS: (
            SWARM_STATUS_CONNECTED if connected else SWARM_STATUS_DISCONNECTED
        ),
    }
