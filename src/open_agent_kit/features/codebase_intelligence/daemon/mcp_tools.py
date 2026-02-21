"""MCP tool handlers for Codebase Intelligence.

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

These tools delegate to shared ToolOperations for actual implementation.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.retrieval.engine import RetrievalEngine

logger = logging.getLogger(__name__)


# Tool Definitions (for MCP registration)
# These follow the MCP tool specification schema

MCP_TOOLS = [
    {
        "name": "oak_search",
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
            },
            "required": ["query"],
        },
    },
    {
        "name": "oak_remember",
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
        "name": "oak_context",
        "description": (
            "Get relevant context for your current task. Call this when starting "
            "work on something to retrieve related code, past decisions, and "
            "applicable project guidelines. Returns a curated set of context "
            "optimized for the task at hand."
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
            },
            "required": ["task"],
        },
    },
    {
        "name": "oak_resolve_memory",
        "description": (
            "Mark a memory observation as resolved or superseded. "
            "Use this after completing work that addresses a gotcha, fixing a bug that "
            "was tracked as an observation, or when a newer observation replaces an older one."
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
            },
            "required": ["id"],
        },
    },
    {
        "name": "oak_sessions",
        "description": (
            "List recent coding sessions with their status and summaries. "
            "Use this to understand what work has been done recently and find "
            "session IDs for deeper investigation with oak_activity."
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
            },
        },
    },
    {
        "name": "oak_memories",
        "description": (
            "Browse stored memories and observations. Use this to review what "
            "the system has learned about the codebase, including gotchas, "
            "bug fixes, decisions, discoveries, and trade-offs."
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
            },
        },
    },
    {
        "name": "oak_stats",
        "description": (
            "Get project intelligence statistics including indexed code chunks, "
            "unique files, memory count, and observation status breakdown. "
            "Use this for a quick health check of the codebase intelligence system."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "oak_activity",
        "description": (
            "View tool execution history for a specific session. Shows what tools "
            "were used, which files were affected, success/failure status, and "
            "output summaries. Use oak_sessions first to find session IDs."
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
            },
            "required": ["session_id"],
        },
    },
    {
        "name": "oak_archive_memories",
        "description": (
            "Archive observations from the ChromaDB search index. Archived observations "
            "remain in SQLite for historical queries but stop appearing in vector search "
            "results. Provide specific IDs or use status_filter + older_than_days to "
            "bulk archive stale resolved/superseded observations."
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
            },
        },
    },
]


class MCPToolHandler:
    """Handler for MCP tool calls.

    Delegates to shared ToolOperations for actual implementation.
    """

    def __init__(self, retrieval_engine: RetrievalEngine) -> None:
        """Initialize handler.

        Args:
            retrieval_engine: RetrievalEngine instance for all operations.
        """
        from open_agent_kit.features.codebase_intelligence.tools import ToolOperations

        self.ops = ToolOperations(
            retrieval_engine,
            activity_store=getattr(retrieval_engine, "activity_store", None),
            vector_store=getattr(retrieval_engine, "store", None),
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
            "oak_search": self.ops.search,
            "oak_remember": self.ops.remember,
            "oak_context": self.ops.get_context,
            "oak_resolve_memory": self.ops.resolve_memory,
            "oak_sessions": self.ops.list_sessions,
            "oak_memories": self.ops.list_memories,
            "oak_stats": lambda args: self.ops.get_stats(args),
            "oak_activity": self.ops.list_activities,
            "oak_archive_memories": self.ops.archive_memories,
        }

        handler = handlers.get(tool_name)
        if not handler:
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
