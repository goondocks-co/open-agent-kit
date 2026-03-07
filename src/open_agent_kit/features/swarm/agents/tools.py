"""Swarm tools for agents.

This module provides MCP tools that expose swarm operations to agents
running via the claude-agent-sdk. These tools allow agents to:
- Search across all connected swarm nodes
- List connected nodes
- Call tools on specific nodes
- Broadcast tool calls to all nodes
- Check swarm connectivity status

The tools delegate to the SwarmWorkerClient for HTTP communication
with the swarm worker, wrapped with the SDK's @tool decorator.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from open_agent_kit.features.swarm.constants import (
    SWARM_TOOL_HEALTH_CHECK,
    SWARM_TOOL_NODES,
    SWARM_TOOL_SEARCH,
    SWARM_TOOL_STATUS,
)
from open_agent_kit.features.swarm.tool_schema import SWARM_TOOL_DEFS_BY_NAME

if TYPE_CHECKING:
    from open_agent_kit.features.swarm.daemon.client import (
        SwarmWorkerClient,
    )

logger = logging.getLogger(__name__)


def _format_result(result: Any) -> str:
    """Serialize *result* to JSON, prepending any ``warning`` field."""
    warning = result.get("warning", "") if isinstance(result, dict) else ""
    text = json.dumps(result, indent=2)
    if warning:
        text = f"Warning: {warning}\n\n{text}"
    return text


def create_swarm_tools(
    client: SwarmWorkerClient,
    enabled_tools: set[str] | None = None,
) -> list[Any]:
    """Create swarm tools for use with claude-agent-sdk.

    These tools are implemented as decorated functions that can be passed
    to create_sdk_mcp_server(). They delegate to the SwarmWorkerClient
    for HTTP communication with the swarm worker.

    Args:
        client: SwarmWorkerClient instance for swarm operations.
        enabled_tools: Optional set of tool names to include. If None,
            all swarm tools are included.

    Returns:
        List of tool functions decorated with @tool.
    """
    try:
        from claude_agent_sdk import tool
    except ImportError:
        logger.warning("claude-agent-sdk not installed, swarm tools unavailable")
        return []

    default_tools = {
        SWARM_TOOL_SEARCH,
        SWARM_TOOL_NODES,
        SWARM_TOOL_STATUS,
        SWARM_TOOL_HEALTH_CHECK,
    }
    active_tools = enabled_tools if enabled_tools is not None else default_tools

    tools = []

    # Tool: swarm_search - Search across all connected swarm nodes
    if SWARM_TOOL_SEARCH in active_tools:

        @tool(
            SWARM_TOOL_SEARCH,
            SWARM_TOOL_DEFS_BY_NAME[SWARM_TOOL_SEARCH].description,
            {
                "query": str,  # Natural language search query
                "search_type": str,  # 'all', 'code', 'memory', or 'plans'
                "limit": int,  # Maximum results per node (1-50)
            },
        )
        async def swarm_search(args: dict[str, Any]) -> dict[str, Any]:
            """Search across swarm nodes."""
            query = args.get("query", "")
            if not query:
                return {
                    "content": [{"type": "text", "text": "Error: query is required"}],
                    "is_error": True,
                }
            try:
                result = await client.search(
                    query=query,
                    search_type=args.get("search_type", "all"),
                    limit=args.get("limit", 10),
                )
                return {"content": [{"type": "text", "text": _format_result(result)}]}
            except Exception as e:
                logger.error("Swarm search failed: %s", e)
                return {
                    "content": [{"type": "text", "text": f"Swarm search error: {e}"}],
                    "is_error": True,
                }

        tools.append(swarm_search)

    # Tool: swarm_nodes - List all connected nodes in the swarm
    if SWARM_TOOL_NODES in active_tools:

        @tool(
            SWARM_TOOL_NODES,
            SWARM_TOOL_DEFS_BY_NAME[SWARM_TOOL_NODES].description,
            {},
        )
        async def swarm_nodes(args: dict[str, Any]) -> dict[str, Any]:
            """List connected swarm nodes."""
            try:
                result = await client.nodes()
                return {"content": [{"type": "text", "text": _format_result(result)}]}
            except Exception as e:
                logger.error("Swarm nodes failed: %s", e)
                return {
                    "content": [{"type": "text", "text": f"Swarm nodes error: {e}"}],
                    "is_error": True,
                }

        tools.append(swarm_nodes)

    # Tool: swarm_status - Check swarm connectivity status
    if SWARM_TOOL_STATUS in active_tools:

        @tool(
            SWARM_TOOL_STATUS,
            SWARM_TOOL_DEFS_BY_NAME[SWARM_TOOL_STATUS].description,
            {},
        )
        async def swarm_status(args: dict[str, Any]) -> dict[str, Any]:
            """Check swarm connectivity status."""
            try:
                nodes_result = await client.nodes()
                teams = nodes_result.get("teams", [])
                status_info = {
                    "connected": True,
                    "swarm_id": nodes_result.get("swarm_id", "unknown"),
                    "node_count": len(teams),
                    "nodes": [
                        {
                            "project_slug": t.get("project_slug", "unknown"),
                            "status": t.get("status", "unknown"),
                        }
                        for t in teams
                    ],
                }
                return {"content": [{"type": "text", "text": json.dumps(status_info, indent=2)}]}
            except Exception as e:
                logger.error("Swarm status check failed: %s", e)
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps({"connected": False, "error": str(e)}, indent=2),
                        }
                    ],
                }

        tools.append(swarm_status)

    # Tool: swarm_health_check - Check health of a specific team
    if SWARM_TOOL_HEALTH_CHECK in active_tools:

        @tool(
            SWARM_TOOL_HEALTH_CHECK,
            SWARM_TOOL_DEFS_BY_NAME[SWARM_TOOL_HEALTH_CHECK].description,
            {
                "team_slug": str,  # Project slug of the team to check
            },
        )
        async def swarm_health_check(args: dict[str, Any]) -> dict[str, Any]:
            """Check health of a swarm team."""
            team_slug = args.get("team_slug", "")
            if not team_slug:
                return {
                    "content": [{"type": "text", "text": "Error: team_slug is required"}],
                    "is_error": True,
                }
            try:
                result = await client.health_check(team_slug=team_slug)
                return {"content": [{"type": "text", "text": _format_result(result)}]}
            except Exception as e:
                error_msg = str(e)
                if hasattr(e, "response"):
                    try:
                        detail = e.response.json()
                        if "team_capabilities" in detail:
                            error_msg = (
                                f"{detail.get('error', error_msg)}\n"
                                f"Available capabilities: {detail['team_capabilities']}"
                            )
                        else:
                            error_msg = detail.get("error", error_msg)
                    except Exception:
                        pass
                logger.error("Swarm health check failed: %s", error_msg)
                return {
                    "content": [{"type": "text", "text": f"Swarm health check error: {error_msg}"}],
                    "is_error": True,
                }

        tools.append(swarm_health_check)

    return tools


def create_swarm_mcp_server(
    client: SwarmWorkerClient,
    enabled_tools: set[str] | None = None,
) -> Any | None:
    """Create an in-process MCP server with swarm tools.

    This server can be passed to ClaudeCodeOptions.mcp_servers to make
    swarm tools available to agents.

    Args:
        client: SwarmWorkerClient instance for swarm operations.
        enabled_tools: Optional set of tool names to include. If None,
            all swarm tools are included.

    Returns:
        McpSdkServerConfig instance, or None if SDK not available.
    """
    try:
        from claude_agent_sdk import create_sdk_mcp_server
    except ImportError:
        logger.warning("claude-agent-sdk not installed, cannot create swarm MCP server")
        return None

    tools = create_swarm_tools(client, enabled_tools)
    if not tools:
        return None

    return create_sdk_mcp_server(
        name="oak-swarm",
        version="0.1.0",
        tools=tools,
    )
