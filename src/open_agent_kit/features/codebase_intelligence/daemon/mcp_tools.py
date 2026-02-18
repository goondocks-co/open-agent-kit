"""MCP tool handlers for Codebase Intelligence.

Exposes tools that AI agents can call via MCP protocol:
- oak_search: Search code and memories semantically
- oak_remember: Store observations for future retrieval
- oak_context: Get relevant context for current task
- oak_resolve_memory: Mark observations as resolved or superseded

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
            "Search the codebase, project memories, and past implementation plans using "
            "semantic similarity. Use this to find relevant code implementations, past "
            "decisions, gotchas, learnings, and plans. Returns ranked results with "
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
                    "enum": ["all", "code", "memory", "plans"],
                    "default": "all",
                    "description": "Search code, memories, plans, or all",
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

        self.ops = ToolOperations(retrieval_engine)

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
