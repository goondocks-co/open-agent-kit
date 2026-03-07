"""Canonical swarm tool definitions.

Single source of truth for tool names, descriptions, and parameter schemas.
Consumed by:
  - ``daemon/mcp_server.py`` (FastMCP server)
  - ``agents/tools.py`` (claude-agent-sdk tools)
  - Verified against ``worker_template/src/mcp-handler.ts`` via test
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from open_agent_kit.features.swarm.constants import (
    SWARM_TOOL_FETCH,
    SWARM_TOOL_HEALTH_CHECK,
    SWARM_TOOL_NODES,
    SWARM_TOOL_SEARCH,
    SWARM_TOOL_STATUS,
)


@dataclass(frozen=True)
class ToolParam:
    """A single tool parameter."""

    name: str
    type: type
    description: str
    required: bool = True
    default: Any = None


@dataclass(frozen=True)
class SwarmToolDef:
    """Canonical definition of a swarm tool."""

    name: str
    description: str
    params: tuple[ToolParam, ...] = ()


SWARM_TOOL_DEFS: tuple[SwarmToolDef, ...] = (
    SwarmToolDef(
        name=SWARM_TOOL_SEARCH,
        description=(
            "Search across all connected projects in the swarm. "
            "Returns results from multiple codebases with project attribution. "
            "Use search_type to narrow results to code, memories, or plans."
        ),
        params=(
            ToolParam("query", str, "Natural language search query."),
            ToolParam(
                "search_type",
                str,
                "Search scope: 'all', 'code', 'memory'.",
                required=False,
                default="all",
            ),
            ToolParam(
                "limit", int, "Maximum results to return (1-50).", required=False, default=10
            ),
        ),
    ),
    SwarmToolDef(
        name=SWARM_TOOL_FETCH,
        description=(
            "Fetch full details for items found via swarm_search. "
            "Pass the chunk IDs and project slug from search results."
        ),
        params=(
            ToolParam("ids", list, "List of chunk IDs from swarm_search results."),
            ToolParam(
                "project_slug",
                str,
                "Project slug from the search result.",
                required=False,
                default="",
            ),
        ),
    ),
    SwarmToolDef(
        name=SWARM_TOOL_NODES,
        description=(
            "List all projects currently connected to the swarm. "
            "Returns project slugs, connection status, and capabilities."
        ),
    ),
    SwarmToolDef(
        name=SWARM_TOOL_STATUS,
        description=(
            "Check the current swarm connectivity status. "
            "Returns whether this node is connected, the swarm ID, "
            "and the number of peer nodes."
        ),
    ),
    SwarmToolDef(
        name=SWARM_TOOL_HEALTH_CHECK,
        description=(
            "Check the health status of a connected team in the swarm. "
            "Returns version info, capabilities, and connection status for each node. "
            "Requires the team to have swarm_management_v1 capability."
        ),
        params=(ToolParam("team_slug", str, "Project slug of the team to check."),),
    ),
)

SWARM_TOOL_DEFS_BY_NAME: dict[str, SwarmToolDef] = {t.name: t for t in SWARM_TOOL_DEFS}
