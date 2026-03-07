"""MCP tool handlers for Team.

Exposes tools that AI agents can call via MCP protocol:
- oak_search: Search code, memories, plans, and sessions semantically
- oak_remember: Store observations for future retrieval
- oak_context: Get relevant context for current task
- oak_resolve_memory: Mark observations as resolved or superseded
- oak_sessions: List recent coding sessions
- oak_memories: Browse stored memories/observations
- oak_stats: Get project intelligence statistics
- oak_activity: View tool execution history for a session
- oak_archive_memories: Archive observations from search index
- swarm_search: Search across all projects in the swarm
- swarm_nodes: List all teams in the swarm
- swarm_status: Get swarm connection status

These tools delegate to shared ToolOperations for actual implementation.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from open_agent_kit.features.swarm.constants import (
    SWARM_TOOL_NODES,
    SWARM_TOOL_SEARCH,
    SWARM_TOOL_STATUS,
)
from open_agent_kit.features.swarm.tool_schema import SWARM_TOOL_DEFS_BY_NAME
from open_agent_kit.features.team.constants import (
    MCP_TOOL_ACTIVITY,
    MCP_TOOL_ARCHIVE_MEMORIES,
    MCP_TOOL_CONTEXT,
    MCP_TOOL_FETCH,
    MCP_TOOL_MEMORIES,
    MCP_TOOL_NODES,
    MCP_TOOL_REMEMBER,
    MCP_TOOL_RESOLVE_MEMORY,
    MCP_TOOL_SEARCH,
    MCP_TOOL_SESSIONS,
    MCP_TOOL_STATS,
)

if TYPE_CHECKING:
    from open_agent_kit.features.team.cloud_relay.base import PolicyAccessor
    from open_agent_kit.features.team.retrieval.engine import RetrievalEngine

logger = logging.getLogger(__name__)


# Tool Definitions (for MCP registration)
# These follow the MCP tool specification schema

MCP_TOOLS = [
    {
        "name": MCP_TOOL_SEARCH,
        "description": (
            "Search the codebase, project memories, sessions, and past implementation plans using "
            "semantic similarity. Use this to find relevant code implementations, past "
            "decisions, gotchas, learnings, plans, and session history. Returns ranked results with "
            "relevance scores. Use search_type='plans' to find past implementation plans."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Natural language search query "
                        "(e.g., 'authentication middleware', 'database connection handling')"
                    ),
                },
                "search_type": {
                    "type": "string",
                    "enum": ["all", "code", "memory", "plans", "sessions"],
                    "default": "all",
                    "description": "Search code, memories, plans, sessions, or all",
                },
                "limit": {
                    "type": "integer",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 50,
                    "description": "Maximum results to return",
                },
                "include_resolved": {
                    "type": "boolean",
                    "default": False,
                    "description": "If True, include resolved/superseded memories in results",
                },
                "include_network": {
                    "type": "boolean",
                    "default": False,
                    "description": (
                        "If True, also search across connected team network nodes "
                        "via the cloud relay. Not available for code searches."
                    ),
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": MCP_TOOL_REMEMBER,
        "description": (
            "Store an observation, decision, or learning for future sessions. "
            "Use this when you discover something important about the codebase "
            "that would help in future work. Types: gotcha (pitfalls), bug_fix "
            "(how issues were resolved), decision (architecture choices), "
            "discovery (learned facts), trade_off (compromises made)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "observation": {
                    "type": "string",
                    "description": "The observation or learning to store",
                },
                "memory_type": {
                    "type": "string",
                    "enum": ["gotcha", "bug_fix", "decision", "discovery", "trade_off"],
                    "default": "discovery",
                    "description": "Type of observation",
                },
                "context": {
                    "type": "string",
                    "description": "Related file path or additional context",
                },
            },
            "required": ["observation"],
        },
    },
    {
        "name": MCP_TOOL_CONTEXT,
        "description": (
            "Get relevant context for your current task. Call this when starting "
            "work on something to retrieve related code, past decisions, and "
            "applicable project guidelines. Returns a curated set of context "
            "optimized for the task at hand. Set include_network=true to also "
            "fetch memories from connected team nodes (code context stays local)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Description of what you're working on",
                },
                "current_files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Files currently being viewed/edited",
                },
                "max_tokens": {
                    "type": "integer",
                    "default": 2000,
                    "description": "Maximum tokens of context to return",
                },
                "include_network": {
                    "type": "boolean",
                    "default": False,
                    "description": (
                        "If True, also fetch memories from connected team network nodes. "
                        "Code context stays local-only (branch/worktree differences)."
                    ),
                },
            },
            "required": ["task"],
        },
    },
    {
        "name": MCP_TOOL_RESOLVE_MEMORY,
        "description": (
            "Mark a memory observation as resolved or superseded. "
            "Use this after completing work that addresses a gotcha, fixing a bug that "
            "was tracked as an observation, or when a newer observation replaces an older one. "
            "Set node_id to target a specific remote node (use oak_nodes to discover nodes)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "description": (
                        "The observation UUID to resolve. Use oak_search to find the ID first "
                        '(returned in each result\'s "id" field, '
                        'e.g. "8430042a-1b01-4c86-8026-6ede46cd93d9").'
                    ),
                },
                "status": {
                    "type": "string",
                    "enum": ["resolved", "superseded"],
                    "default": "resolved",
                    "description": "New status - 'resolved' (default) or 'superseded'.",
                },
                "reason": {
                    "type": "string",
                    "description": "Optional reason for resolution.",
                },
                "node_id": {
                    "type": "string",
                    "description": (
                        "Target a specific node. Use oak_nodes to discover available nodes."
                    ),
                },
            },
            "required": ["id"],
        },
    },
    {
        "name": MCP_TOOL_SESSIONS,
        "description": (
            "List recent coding sessions with their status and summaries. "
            "Use this to understand what work has been done recently and find "
            "session IDs for deeper investigation with oak_activity. "
            "Set include_network=true to also fetch sessions from connected team nodes."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 20,
                    "description": "Maximum number of sessions to return",
                },
                "include_summary": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include session summaries in output",
                },
                "include_network": {
                    "type": "boolean",
                    "default": False,
                    "description": (
                        "If True, also fetch sessions from connected team network nodes."
                    ),
                },
            },
        },
    },
    {
        "name": MCP_TOOL_MEMORIES,
        "description": (
            "Browse stored memories and observations. Use this to review what "
            "the system has learned about the codebase, including gotchas, "
            "bug fixes, decisions, discoveries, and trade-offs. "
            "Set include_network=true to also fetch memories from connected team nodes."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "memory_type": {
                    "type": "string",
                    "enum": ["gotcha", "bug_fix", "decision", "discovery", "trade_off"],
                    "description": "Filter by memory type (optional)",
                },
                "limit": {
                    "type": "integer",
                    "default": 20,
                    "minimum": 1,
                    "maximum": 100,
                    "description": "Maximum number of memories to return",
                },
                "status": {
                    "type": "string",
                    "enum": ["active", "resolved", "superseded"],
                    "default": "active",
                    "description": "Filter by observation status",
                },
                "include_resolved": {
                    "type": "boolean",
                    "default": False,
                    "description": "If True, include all statuses regardless of status filter",
                },
                "include_network": {
                    "type": "boolean",
                    "default": False,
                    "description": (
                        "If True, also fetch memories from connected team network nodes."
                    ),
                },
            },
        },
    },
    {
        "name": MCP_TOOL_STATS,
        "description": (
            "Get project intelligence statistics including indexed code chunks, "
            "unique files, memory count, and observation status breakdown. "
            "Use this for a quick health check of the team system. "
            "Set include_network=true to also fetch stats from connected team nodes."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "include_network": {
                    "type": "boolean",
                    "default": False,
                    "description": ("If True, also fetch stats from connected team network nodes."),
                },
            },
        },
    },
    {
        "name": MCP_TOOL_ACTIVITY,
        "description": (
            "View tool execution history for a specific session. Shows what tools "
            "were used, which files were affected, success/failure status, and "
            "output summaries. Use oak_sessions first to find session IDs. "
            "Set node_id to query a specific remote node (use oak_nodes to discover nodes)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "The session ID to get activities for",
                },
                "tool_name": {
                    "type": "string",
                    "description": "Filter activities by tool name (optional)",
                },
                "limit": {
                    "type": "integer",
                    "default": 50,
                    "minimum": 1,
                    "maximum": 200,
                    "description": "Maximum number of activities to return",
                },
                "node_id": {
                    "type": "string",
                    "description": (
                        "Target a specific node. Use oak_nodes to discover available nodes."
                    ),
                },
            },
            "required": ["session_id"],
        },
    },
    {
        "name": MCP_TOOL_ARCHIVE_MEMORIES,
        "description": (
            "Archive observations from the ChromaDB search index. Archived observations "
            "remain in SQLite for historical queries but stop appearing in vector search "
            "results. Provide specific IDs or use status_filter + older_than_days to "
            "bulk archive stale resolved/superseded observations. "
            "Set node_id to target a specific remote node (use oak_nodes to discover nodes)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific observation IDs to archive",
                },
                "status_filter": {
                    "type": "string",
                    "enum": ["resolved", "superseded", "both"],
                    "description": (
                        "Archive observations by status: 'resolved', 'superseded', or 'both'"
                    ),
                },
                "older_than_days": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Only archive observations older than this many days",
                },
                "dry_run": {
                    "type": "boolean",
                    "default": False,
                    "description": "If True, return count without actually archiving",
                },
                "node_id": {
                    "type": "string",
                    "description": (
                        "Target a specific node. Use oak_nodes to discover available nodes."
                    ),
                },
            },
        },
    },
    {
        "name": MCP_TOOL_FETCH,
        "description": (
            "Fetch full content for one or more chunk IDs returned by oak_search. "
            "Use this to expand truncated previews into complete documents."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of chunk IDs to fetch full content for",
                },
            },
            "required": ["ids"],
        },
    },
    {
        "name": MCP_TOOL_NODES,
        "description": (
            "List connected team relay nodes. Shows machine IDs, online status, "
            "OAK version, and capabilities for each node. Use this to discover "
            "available nodes before targeting them with node_id in other tools."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    # ------------------------------------------------------------------
    # Swarm tools (cross-project federation)
    # ------------------------------------------------------------------
    {
        "name": SWARM_TOOL_SEARCH,
        "description": SWARM_TOOL_DEFS_BY_NAME[SWARM_TOOL_SEARCH].description,
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language search query",
                },
                "search_type": {
                    "type": "string",
                    "enum": ["all", "code", "memory"],
                    "default": "all",
                    "description": "Search scope: 'all', 'code', or 'memory'",
                },
                "limit": {
                    "type": "integer",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 50,
                    "description": "Maximum results to return",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": SWARM_TOOL_NODES,
        "description": SWARM_TOOL_DEFS_BY_NAME[SWARM_TOOL_NODES].description,
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": SWARM_TOOL_STATUS,
        "description": SWARM_TOOL_DEFS_BY_NAME[SWARM_TOOL_STATUS].description,
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]


class MCPToolHandler:
    """Handler for MCP tool calls.

    Delegates to shared ToolOperations for actual implementation.
    """

    def __init__(
        self,
        retrieval_engine: RetrievalEngine,
        relay_client: Any | None = None,
        policy_accessor: PolicyAccessor | None = None,
    ) -> None:
        """Initialize handler.

        Args:
            retrieval_engine: RetrievalEngine instance for all operations.
            relay_client: Optional RelayClient for network search.
            policy_accessor: Optional callable returning DataCollectionPolicy.
        """
        from open_agent_kit.features.team.tools import ToolOperations

        self.ops = ToolOperations(
            retrieval_engine,
            activity_store=getattr(retrieval_engine, "activity_store", None),
            vector_store=getattr(retrieval_engine, "store", None),
            relay_client=relay_client,
            policy_accessor=policy_accessor,
        )

    def handle_tool_call(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Handle an MCP tool call.

        Args:
            tool_name: Name of the tool being called.
            arguments: Tool arguments.

        Returns:
            Tool result in MCP format.
        """
        handlers = {
            MCP_TOOL_SEARCH: self.ops.search,
            MCP_TOOL_REMEMBER: self.ops.remember,
            MCP_TOOL_CONTEXT: self.ops.get_context,
            MCP_TOOL_RESOLVE_MEMORY: self.ops.resolve_memory,
            MCP_TOOL_SESSIONS: self.ops.list_sessions,
            MCP_TOOL_MEMORIES: self.ops.list_memories,
            MCP_TOOL_STATS: lambda args: self.ops.get_stats(args),
            MCP_TOOL_ACTIVITY: self.ops.list_activities,
            MCP_TOOL_ARCHIVE_MEMORIES: self.ops.archive_memories,
            MCP_TOOL_FETCH: self.ops.fetch,
            MCP_TOOL_NODES: lambda args: self.ops.list_nodes(args),
            # Swarm tools
            SWARM_TOOL_SEARCH: self.ops.swarm_search,
            SWARM_TOOL_NODES: lambda args: self.ops.swarm_nodes(),
            SWARM_TOOL_STATUS: lambda args: self.ops.swarm_status(),
        }

        handler = handlers.get(tool_name)
        if not handler:
            logger.warning("Unknown tool '%s' — available: %s", tool_name, list(handlers.keys()))
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}],
            }

        try:
            result = handler(arguments)
            return {
                "content": [{"type": "text", "text": result}],
            }
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            logger.exception(f"Tool {tool_name} failed: {e}")
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"Tool error: {e!s}"}],
            }

    @staticmethod
    def get_tool_definitions() -> list[dict]:
        """Get MCP tool definitions for registration.

        Returns:
            List of tool definitions in MCP format.
        """
        return MCP_TOOLS
