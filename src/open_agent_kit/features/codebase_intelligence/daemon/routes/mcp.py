"""MCP tool routes for the CI daemon.

These routes expose MCP tool functionality via HTTP for external callers.
The actual tool handlers use RetrievalEngine directly (same process).
"""

import json
import logging

from fastapi import APIRouter, HTTPException, Query, Request

from open_agent_kit.features.codebase_intelligence.daemon.state import get_state

logger = logging.getLogger(__name__)

router = APIRouter(tags=["mcp"])


@router.get("/api/mcp/tools")
async def list_mcp_tools() -> dict:
    """List available MCP tools."""
    from open_agent_kit.features.codebase_intelligence.daemon.mcp_tools import MCP_TOOLS

    return {"tools": MCP_TOOLS}


@router.post("/api/mcp/call")
async def call_mcp_tool(
    request: Request,
    tool_name: str = Query(...),
) -> dict:
    """Call an MCP tool.

    The handler uses RetrievalEngine directly (same process, no HTTP overhead).
    """
    from open_agent_kit.features.codebase_intelligence.daemon.mcp_tools import MCPToolHandler

    state = get_state()

    if not state.retrieval_engine:
        raise HTTPException(status_code=503, detail="Retrieval engine not initialized")

    try:
        arguments = await request.json()
    except (ValueError, json.JSONDecodeError):
        logger.debug("Failed to parse JSON arguments")
        arguments = {}

    # Create handler with retrieval engine (direct access, no HTTP)
    handler = MCPToolHandler(retrieval_engine=state.retrieval_engine)

    return handler.handle_tool_call(tool_name, arguments)
