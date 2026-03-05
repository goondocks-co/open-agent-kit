"""Tool call and broadcast routes for the swarm daemon."""

import logging
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from open_agent_kit.features.swarm.constants import (
    SWARM_DAEMON_API_PATH_BROADCAST,
    SWARM_DAEMON_API_PATH_TOOL_CALL,
    SWARM_DEFAULT_TOOL_TIMEOUT_SECONDS,
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


class ToolCallRequest(BaseModel):
    """Swarm tool call request body."""

    tool_name: str
    arguments: dict[str, Any] = {}
    target_project: str


class BroadcastRequest(BaseModel):
    """Swarm broadcast request body."""

    tool_name: str
    arguments: dict[str, Any] = {}


@router.post(SWARM_DAEMON_API_PATH_TOOL_CALL)
async def swarm_tool_call(body: ToolCallRequest) -> dict:
    """Call a tool on a specific project in the swarm."""
    state = get_swarm_state()
    if not state.http_client:
        logger.warning("Tool call dropped: not connected to swarm worker")
        return {SWARM_RESPONSE_KEY_ERROR: SWARM_ERROR_NOT_CONNECTED}
    logger.info("Swarm tool call: tool=%s target=%s", body.tool_name, body.target_project)
    logger.debug("Swarm tool call arguments: %s", body.arguments)
    try:
        result = await state.http_client.call(
            tool_name=body.tool_name,
            arguments=body.arguments,
            target_project=body.target_project,
            timeout=SWARM_DEFAULT_TOOL_TIMEOUT_SECONDS,
        )
        logger.info(
            "Swarm tool call complete: tool=%s target=%s", body.tool_name, body.target_project
        )
        logger.debug(
            "Swarm tool call result keys: %s",
            list(result.keys()) if isinstance(result, dict) else type(result).__name__,
        )
        return result
    except Exception as exc:
        logger.error(
            "Swarm tool call failed: tool=%s target=%s error=%s",
            body.tool_name,
            body.target_project,
            exc,
        )
        return {SWARM_RESPONSE_KEY_ERROR: str(exc)}


@router.post(SWARM_DAEMON_API_PATH_BROADCAST)
async def swarm_broadcast(body: BroadcastRequest) -> dict:
    """Broadcast a tool call to all projects in the swarm."""
    state = get_swarm_state()
    if not state.http_client:
        logger.warning("Broadcast dropped: not connected to swarm worker")
        return {SWARM_RESPONSE_KEY_ERROR: SWARM_ERROR_NOT_CONNECTED, SWARM_RESPONSE_KEY_RESULTS: []}
    logger.info("Swarm broadcast: tool=%s", body.tool_name)
    logger.debug("Swarm broadcast arguments: %s", body.arguments)
    try:
        result = await state.http_client.broadcast(
            tool_name=body.tool_name,
            arguments=body.arguments,
            timeout=SWARM_DEFAULT_TOOL_TIMEOUT_SECONDS,
        )
        result_count = len(result.get(SWARM_RESPONSE_KEY_RESULTS, []))
        logger.info("Swarm broadcast complete: tool=%s responses=%d", body.tool_name, result_count)
        for entry in result.get(SWARM_RESPONSE_KEY_RESULTS, []):
            slug = entry.get("project_slug", "unknown")
            has_error = bool(entry.get("error"))
            logger.debug("  broadcast response: project=%s error=%s", slug, has_error)
        return result
    except Exception as exc:
        logger.error("Swarm broadcast failed: tool=%s error=%s", body.tool_name, exc)
        return {SWARM_RESPONSE_KEY_ERROR: str(exc), SWARM_RESPONSE_KEY_RESULTS: []}
