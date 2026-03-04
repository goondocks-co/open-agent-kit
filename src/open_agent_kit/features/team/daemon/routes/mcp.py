"""MCP tool routes for the CI daemon.

These routes expose MCP tool functionality via HTTP for external callers.
The actual tool handlers use RetrievalEngine directly (same process).
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException, Query, Request

from open_agent_kit.features.team.daemon.state import (
    get_data_collection_policy,
    get_state,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["mcp"])


@router.get("/api/mcp/tools")
async def list_mcp_tools() -> dict:
    """List available MCP tools."""
    from open_agent_kit.features.team.daemon.mcp_tools import MCP_TOOLS

    return {"tools": MCP_TOOLS}


@router.post("/api/mcp/call")
async def call_mcp_tool(
    request: Request,
    tool_name: str = Query(...),
) -> dict:
    """Call an MCP tool.

    The handler uses RetrievalEngine directly (same process, no HTTP overhead).

    handle_tool_call() is synchronous but may internally schedule async relay
    coroutines via run_coroutine_threadsafe (for federated/network calls).
    Running it on the event loop thread would deadlock those coroutines, so
    we dispatch to a thread pool and set the event loop reference so
    _run_relay_coro can schedule work back onto the main loop.
    """
    from open_agent_kit.features.team.daemon.mcp_tools import MCPToolHandler

    state = get_state()

    if not state.retrieval_engine:
        raise HTTPException(status_code=503, detail="Retrieval engine not initialized")

    try:
        arguments = await request.json()
    except (ValueError, json.JSONDecodeError):
        logger.debug("Failed to parse JSON arguments")
        arguments = {}

    # Create handler with retrieval engine (direct access, no HTTP)
    handler = MCPToolHandler(
        retrieval_engine=state.retrieval_engine,
        relay_client=state.cloud_relay_client,
        policy_accessor=get_data_collection_policy,
    )

    # Run in a thread pool so the event loop stays free for relay coroutines
    # scheduled by _run_relay_coro() during federated/network tool calls.
    loop = asyncio.get_running_loop()

    def _execute() -> dict:
        # Make the main event loop visible to this thread so
        # asyncio.get_event_loop() in _run_relay_coro returns it.
        asyncio.set_event_loop(loop)
        return handler.handle_tool_call(tool_name, arguments)

    return await loop.run_in_executor(None, _execute)
