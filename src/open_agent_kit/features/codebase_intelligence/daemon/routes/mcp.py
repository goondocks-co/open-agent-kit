"""MCP tool routes for the CI daemon."""

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
    """Call an MCP tool."""
    from open_agent_kit.features.codebase_intelligence.daemon.mcp_tools import MCPToolHandler

    state = get_state()

    if not state.vector_store or not state.embedding_chain:
        raise HTTPException(status_code=503, detail="Vector store not initialized")

    try:
        arguments = await request.json()
    except (ValueError, json.JSONDecodeError):
        logger.debug("Failed to parse JSON arguments")
        arguments = {}

    handler = MCPToolHandler(
        vector_store=state.vector_store,
        embedding_chain=state.embedding_chain,
    )

    return handler.handle_tool_call(tool_name, arguments)
