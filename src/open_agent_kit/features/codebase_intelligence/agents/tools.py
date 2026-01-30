"""CI data tools for agents.

This module provides MCP tools that expose Codebase Intelligence data
to agents running via the claude-code-sdk. These tools allow agents to:
- Search code and memories semantically
- Access session history and summaries
- Get project statistics

The tools delegate to shared ToolOperations for actual implementation,
wrapped with the SDK's @tool decorator for registration.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from open_agent_kit.features.codebase_intelligence.constants import (
    CI_MCP_SERVER_NAME,
    CI_MCP_SERVER_VERSION,
    CI_TOOL_MEMORIES,
    CI_TOOL_PROJECT_STATS,
    CI_TOOL_SEARCH,
    CI_TOOL_SESSIONS,
)

if TYPE_CHECKING:
    from claude_code_sdk.types import McpSdkServerConfig

    from open_agent_kit.features.codebase_intelligence.activity.store import ActivityStore
    from open_agent_kit.features.codebase_intelligence.memory.store import VectorStore
    from open_agent_kit.features.codebase_intelligence.retrieval.engine import RetrievalEngine

logger = logging.getLogger(__name__)


def create_ci_tools(
    retrieval_engine: RetrievalEngine,
    activity_store: ActivityStore | None,
    vector_store: VectorStore | None,
) -> list[Any]:
    """Create CI data tools for use with claude-code-sdk.

    These tools are implemented as decorated functions that can be passed
    to create_sdk_mcp_server(). They delegate to shared ToolOperations
    for the actual implementation.

    Args:
        retrieval_engine: RetrievalEngine instance for search operations.
        activity_store: ActivityStore instance for session data (optional).
        vector_store: VectorStore instance for stats (optional).

    Returns:
        List of tool functions decorated with @tool.
    """
    try:
        from claude_code_sdk import tool
    except ImportError:
        logger.warning("claude-code-sdk not installed, CI tools unavailable")
        return []

    from open_agent_kit.features.codebase_intelligence.tools import ToolOperations

    # Create shared operations instance
    ops = ToolOperations(retrieval_engine, activity_store, vector_store)

    tools = []

    # Tool: ci_search - Semantic search over code, memories, and plans
    @tool(
        CI_TOOL_SEARCH,
        "Search the codebase, project memories, and plans using semantic similarity. "
        "Use search_type='plans' to find implementation plans (SDDs) that explain design intent. "
        "Returns ranked results with relevance scores.",
        {
            "query": str,  # Natural language search query
            "search_type": str,  # 'all', 'code', 'memory', or 'plans'
            "limit": int,  # Maximum results (1-50)
        },
    )
    async def ci_search(args: dict[str, Any]) -> dict[str, Any]:
        """Search code, memories, and plans."""
        try:
            result = ops.search(args)
            return {"content": [{"type": "text", "text": result}]}
        except ValueError as e:
            return {
                "content": [{"type": "text", "text": f"Error: {e}"}],
                "is_error": True,
            }
        except (OSError, RuntimeError) as e:
            logger.error(f"CI search failed: {e}")
            return {
                "content": [{"type": "text", "text": f"Search error: {e}"}],
                "is_error": True,
            }

    tools.append(ci_search)

    # Tool: ci_memories - List and filter memories
    @tool(
        CI_TOOL_MEMORIES,
        "List project memories with optional filtering. "
        "Memories include discoveries, gotchas, decisions, and bug fixes.",
        {
            "memory_type": str,  # Filter by type (optional)
            "limit": int,  # Maximum results (1-100)
        },
    )
    async def ci_memories(args: dict[str, Any]) -> dict[str, Any]:
        """List memories with filtering."""
        try:
            result = ops.list_memories(args)
            return {"content": [{"type": "text", "text": result}]}
        except (OSError, ValueError, RuntimeError) as e:
            logger.error(f"CI memories failed: {e}")
            return {
                "content": [{"type": "text", "text": f"Error listing memories: {e}"}],
                "is_error": True,
            }

    tools.append(ci_memories)

    # Tool: ci_sessions - Access session history
    @tool(
        CI_TOOL_SESSIONS,
        "List recent coding sessions with summaries. "
        "Useful for understanding project history and past work.",
        {
            "limit": int,  # Maximum sessions (1-20)
            "include_summary": bool,  # Include session summaries
        },
    )
    async def ci_sessions(args: dict[str, Any]) -> dict[str, Any]:
        """List recent sessions."""
        try:
            result = ops.list_sessions(args)
            return {"content": [{"type": "text", "text": result}]}
        except ValueError as e:
            return {
                "content": [{"type": "text", "text": str(e)}],
                "is_error": True,
            }
        except (OSError, RuntimeError, AttributeError) as e:
            logger.error(f"CI sessions failed: {e}")
            return {
                "content": [{"type": "text", "text": f"Error listing sessions: {e}"}],
                "is_error": True,
            }

    tools.append(ci_sessions)

    # Tool: ci_project_stats - Get project statistics
    @tool(
        CI_TOOL_PROJECT_STATS,
        "Get statistics about the indexed codebase and memories. "
        "Useful for understanding project scope and CI data coverage.",
        {},
    )
    async def ci_project_stats(args: dict[str, Any]) -> dict[str, Any]:
        """Get project statistics."""
        try:
            result = ops.get_stats(args)
            return {"content": [{"type": "text", "text": result}]}
        except (OSError, ValueError, RuntimeError, AttributeError) as e:
            logger.error(f"CI project stats failed: {e}")
            return {
                "content": [{"type": "text", "text": f"Error getting stats: {e}"}],
                "is_error": True,
            }

    tools.append(ci_project_stats)

    return tools


def create_ci_mcp_server(
    retrieval_engine: RetrievalEngine,
    activity_store: ActivityStore | None = None,
    vector_store: VectorStore | None = None,
) -> McpSdkServerConfig | None:
    """Create an in-process MCP server with CI tools.

    This server can be passed to ClaudeCodeOptions.mcp_servers to make
    CI tools available to agents.

    Args:
        retrieval_engine: RetrievalEngine instance for search operations.
        activity_store: ActivityStore instance for session data (optional).
        vector_store: VectorStore instance for stats (optional).

    Returns:
        McpSdkServerConfig instance, or None if SDK not available.
    """
    try:
        from claude_code_sdk import create_sdk_mcp_server
    except ImportError:
        logger.warning("claude-code-sdk not installed, cannot create MCP server")
        return None

    tools = create_ci_tools(retrieval_engine, activity_store, vector_store)
    if not tools:
        return None

    return create_sdk_mcp_server(
        name=CI_MCP_SERVER_NAME,
        version=CI_MCP_SERVER_VERSION,
        tools=tools,
    )
