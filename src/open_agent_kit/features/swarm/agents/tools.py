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
    SWARM_DEFAULT_TOOL_TIMEOUT_SECONDS,
    SWARM_TOOL_BROADCAST,
    SWARM_TOOL_CALL,
    SWARM_TOOL_NODES,
    SWARM_TOOL_SEARCH,
    SWARM_TOOL_STATUS,
)

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
        SWARM_TOOL_CALL,
        SWARM_TOOL_BROADCAST,
        SWARM_TOOL_STATUS,
    }
    active_tools = enabled_tools if enabled_tools is not None else default_tools

    tools = []

    # Tool: swarm_search - Search across all connected swarm nodes
    if SWARM_TOOL_SEARCH in active_tools:

        @tool(
            SWARM_TOOL_SEARCH,
            "Search across all connected projects in the swarm. "
            "Returns results from multiple codebases with project attribution. "
            "Use search_type to narrow results to code, memories, or plans.",
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
            "List all projects currently connected to the swarm. "
            "Returns project slugs, connection status, and capabilities.",
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

    # Tool: swarm_call - Call a tool on a specific swarm node
    if SWARM_TOOL_CALL in active_tools:

        @tool(
            SWARM_TOOL_CALL,
            "Call a CI tool on a specific project in the swarm. "
            "Routes the tool call to the target project and returns its result. "
            "Use swarm_nodes first to discover available projects.",
            {
                "tool_name": str,  # CI tool to invoke (e.g. 'ci_search', 'ci_memories')
                "arguments": dict,  # Arguments to pass to the tool
                "target_project": str,  # Project slug to route the call to
            },
        )
        async def swarm_call(args: dict[str, Any]) -> dict[str, Any]:
            """Call a tool on a specific swarm node."""
            tool_name = args.get("tool_name", "")
            target_project = args.get("target_project", "")
            if not tool_name or not target_project:
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": "Error: tool_name and target_project are required",
                        }
                    ],
                    "is_error": True,
                }
            try:
                result = await client.call(
                    tool_name=tool_name,
                    arguments=args.get("arguments", {}),
                    target_project=target_project,
                    timeout=SWARM_DEFAULT_TOOL_TIMEOUT_SECONDS,
                )
                return {"content": [{"type": "text", "text": _format_result(result)}]}
            except Exception as e:
                error_msg = str(e)
                # Surface capability-mismatch details from 422 responses.
                if hasattr(e, "response"):
                    try:
                        detail = e.response.json()
                        if "team_capabilities" in detail:
                            error_msg = (
                                f"{detail.get('error', error_msg)}\n"
                                f"Available capabilities: {detail['team_capabilities']}"
                            )
                    except Exception:
                        pass
                logger.error("Swarm call failed: %s", error_msg)
                return {
                    "content": [{"type": "text", "text": f"Swarm call error: {error_msg}"}],
                    "is_error": True,
                }

        tools.append(swarm_call)

    # Tool: swarm_broadcast - Broadcast a tool call to all swarm nodes
    if SWARM_TOOL_BROADCAST in active_tools:

        @tool(
            SWARM_TOOL_BROADCAST,
            "Broadcast a CI tool call to ALL connected projects in the swarm. "
            "Returns aggregated results from every node. Use sparingly — "
            "prefer swarm_search for discovery and swarm_call for targeted queries.",
            {
                "tool_name": str,  # CI tool to invoke on all nodes
                "arguments": dict,  # Arguments to pass to the tool
            },
        )
        async def swarm_broadcast(args: dict[str, Any]) -> dict[str, Any]:
            """Broadcast a tool call to all swarm nodes."""
            tool_name = args.get("tool_name", "")
            if not tool_name:
                return {
                    "content": [{"type": "text", "text": "Error: tool_name is required"}],
                    "is_error": True,
                }
            try:
                result = await client.broadcast(
                    tool_name=tool_name,
                    arguments=args.get("arguments", {}),
                    timeout=SWARM_DEFAULT_TOOL_TIMEOUT_SECONDS,
                )
                return {"content": [{"type": "text", "text": _format_result(result)}]}
            except Exception as e:
                logger.error("Swarm broadcast failed: %s", e)
                return {
                    "content": [{"type": "text", "text": f"Swarm broadcast error: {e}"}],
                    "is_error": True,
                }

        tools.append(swarm_broadcast)

    # Tool: swarm_status - Check swarm connectivity status
    if SWARM_TOOL_STATUS in active_tools:

        @tool(
            SWARM_TOOL_STATUS,
            "Check the current swarm connectivity status. "
            "Returns whether this node is connected, the swarm ID, "
            "and the number of peer nodes.",
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
