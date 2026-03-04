"""OAK data tools for agents.

This module provides MCP tools that expose Team data
to agents running via the claude-agent-sdk. These tools allow agents to:
- Search code and memories semantically
- Access session history and summaries
- Get project statistics

The tools delegate to shared ToolOperations for actual implementation,
wrapped with the SDK's @tool decorator for registration.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from open_agent_kit.features.agent_runtime.constants import (
    OAK_MCP_SERVER_NAME,
    OAK_MCP_SERVER_VERSION,
    OAK_TOOL_ARCHIVE,
    OAK_TOOL_MEMORIES,
    OAK_TOOL_PROJECT_STATS,
    OAK_TOOL_QUERY,
    OAK_TOOL_REMEMBER,
    OAK_TOOL_RESOLVE,
    OAK_TOOL_SEARCH,
    OAK_TOOL_SESSIONS,
)

if TYPE_CHECKING:
    from claude_agent_sdk.types import McpSdkServerConfig

    from open_agent_kit.features.agent_runtime.models import AgentToolAccess
    from open_agent_kit.features.team.activity.store import ActivityStore
    from open_agent_kit.features.team.memory.store import VectorStore
    from open_agent_kit.features.team.retrieval.engine import RetrievalEngine

logger = logging.getLogger(__name__)


def build_oak_tools_from_access(tool_access: AgentToolAccess) -> set[str] | None:
    """Map ``AgentToolAccess`` flags to an enabled-tools set.

    Returns ``None`` when no OAK access is requested (the caller should
    skip MCP server creation entirely in that case).

    Args:
        tool_access: Access flags from an agent definition.

    Returns:
        Set of OAK tool name strings, or ``None`` if nothing is enabled.
    """
    has_any = (
        tool_access.code_search
        or tool_access.memory_search
        or tool_access.session_history
        or tool_access.project_stats
        or tool_access.sql_query
        or tool_access.memory_write
    )
    if not has_any:
        return None

    enabled: set[str] = set()
    if tool_access.code_search:
        enabled.add(OAK_TOOL_SEARCH)
    if tool_access.memory_search:
        enabled.add(OAK_TOOL_MEMORIES)
    if tool_access.session_history:
        enabled.add(OAK_TOOL_SESSIONS)
    if tool_access.project_stats:
        enabled.add(OAK_TOOL_PROJECT_STATS)
    if tool_access.sql_query:
        enabled.add(OAK_TOOL_QUERY)
    if tool_access.memory_write:
        enabled.add(OAK_TOOL_REMEMBER)
        enabled.add(OAK_TOOL_RESOLVE)
        enabled.add(OAK_TOOL_ARCHIVE)

    return enabled


def create_oak_tools(
    retrieval_engine: RetrievalEngine,
    activity_store: ActivityStore | None,
    vector_store: VectorStore | None,
    enabled_tools: set[str] | None = None,
) -> list[Any]:
    """Create OAK data tools for use with claude-agent-sdk.

    These tools are implemented as decorated functions that can be passed
    to create_sdk_mcp_server(). They delegate to shared ToolOperations
    for the actual implementation.

    Args:
        retrieval_engine: RetrievalEngine instance for search operations.
        activity_store: ActivityStore instance for session data (optional).
        vector_store: VectorStore instance for stats (optional).
        enabled_tools: Optional set of tool names to include. If None, all
            standard tools are included (oak_query requires explicit opt-in).

    Returns:
        List of tool functions decorated with @tool.
    """
    try:
        from claude_agent_sdk import tool
    except ImportError:
        logger.warning("claude-agent-sdk not installed, OAK tools unavailable")
        return []

    from open_agent_kit.features.team.tools import ToolOperations

    # Create shared operations instance
    ops = ToolOperations(retrieval_engine, activity_store, vector_store)

    # Default enabled tools (oak_query excluded by default — requires explicit opt-in)
    default_tools = {
        OAK_TOOL_SEARCH,
        OAK_TOOL_MEMORIES,
        OAK_TOOL_SESSIONS,
        OAK_TOOL_PROJECT_STATS,
    }
    active_tools = enabled_tools if enabled_tools is not None else default_tools

    tools = []

    # Tool: oak_search - Semantic search over code, memories, and plans
    if OAK_TOOL_SEARCH in active_tools:

        @tool(
            OAK_TOOL_SEARCH,
            "Search the codebase, project memories, and plans using semantic similarity. "
            "Use search_type='plans' to find implementation plans (SDDs) that explain design intent. "
            "Returns ranked results with relevance scores.",
            {
                "query": str,  # Natural language search query
                "search_type": str,  # 'all', 'code', 'memory', or 'plans'
                "limit": int,  # Maximum results (1-50)
                "include_resolved": bool,  # Include resolved/superseded memories
            },
        )
        async def oak_search(args: dict[str, Any]) -> dict[str, Any]:
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
                logger.error(f"OAK search failed: {e}")
                return {
                    "content": [{"type": "text", "text": f"Search error: {e}"}],
                    "is_error": True,
                }

        tools.append(oak_search)

    # Tool: oak_memories - List and filter memories
    if OAK_TOOL_MEMORIES in active_tools:

        @tool(
            OAK_TOOL_MEMORIES,
            "List project memories with optional filtering. "
            "Memories include discoveries, gotchas, decisions, and bug fixes.",
            {
                "memory_type": str,  # Filter by type (optional)
                "limit": int,  # Maximum results (1-100)
                "status": str,  # Filter by status: 'active', 'resolved', 'superseded'
                "include_resolved": bool,  # Include all statuses
            },
        )
        async def oak_memories(args: dict[str, Any]) -> dict[str, Any]:
            """List memories with filtering."""
            try:
                result = ops.list_memories(args)
                return {"content": [{"type": "text", "text": result}]}
            except (OSError, ValueError, RuntimeError) as e:
                logger.error(f"OAK memories failed: {e}")
                return {
                    "content": [{"type": "text", "text": f"Error listing memories: {e}"}],
                    "is_error": True,
                }

        tools.append(oak_memories)

    # Tool: oak_sessions - Access session history
    if OAK_TOOL_SESSIONS in active_tools:

        @tool(
            OAK_TOOL_SESSIONS,
            "List recent coding sessions with summaries. "
            "Useful for understanding project history and past work.",
            {
                "limit": int,  # Maximum sessions (1-20)
                "include_summary": bool,  # Include session summaries
            },
        )
        async def oak_sessions(args: dict[str, Any]) -> dict[str, Any]:
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
                logger.error(f"OAK sessions failed: {e}")
                return {
                    "content": [{"type": "text", "text": f"Error listing sessions: {e}"}],
                    "is_error": True,
                }

        tools.append(oak_sessions)

    # Tool: oak_project_stats - Get project statistics
    if OAK_TOOL_PROJECT_STATS in active_tools:

        @tool(
            OAK_TOOL_PROJECT_STATS,
            "Get statistics about the indexed codebase and memories. "
            "Useful for understanding project scope and OAK data coverage.",
            {},
        )
        async def oak_project_stats(args: dict[str, Any]) -> dict[str, Any]:
            """Get project statistics."""
            try:
                result = ops.get_stats(args)
                return {"content": [{"type": "text", "text": result}]}
            except (OSError, ValueError, RuntimeError, AttributeError) as e:
                logger.error(f"OAK project stats failed: {e}")
                return {
                    "content": [{"type": "text", "text": f"Error getting stats: {e}"}],
                    "is_error": True,
                }

        tools.append(oak_project_stats)

    # Tool: oak_query - Read-only SQL queries (opt-in only)
    if OAK_TOOL_QUERY in active_tools:

        @tool(
            OAK_TOOL_QUERY,
            "Execute a read-only SQL query against the activities database. "
            "Only SELECT, WITH, and EXPLAIN statements are allowed. "
            "Returns results as a formatted markdown table. "
            "Use datetime(col, 'unixepoch', 'localtime') to format epoch timestamps.",
            {
                "sql": str,  # SQL query (SELECT/WITH/EXPLAIN only)
                "limit": int,  # Maximum rows to return (1-500, default 100)
            },
        )
        async def oak_query(args: dict[str, Any]) -> dict[str, Any]:
            """Execute read-only SQL query."""
            try:
                result = ops.execute_query(args)
                return {"content": [{"type": "text", "text": result}]}
            except ValueError as e:
                return {
                    "content": [{"type": "text", "text": f"Query validation error: {e}"}],
                    "is_error": True,
                }
            except (OSError, RuntimeError) as e:
                logger.error(f"OAK query failed: {e}")
                return {
                    "content": [
                        {"type": "text", "text": f"SQL error: {e}\n\nFix your query and retry."}
                    ],
                    "is_error": True,
                }

        tools.append(oak_query)

    # Tool: oak_remember - Create a new observation (opt-in via memory_write)
    if OAK_TOOL_REMEMBER in active_tools:

        @tool(
            OAK_TOOL_REMEMBER,
            "Create a new observation/memory. Use this to record discoveries, "
            "gotchas, decisions, bug fixes, or trade-offs for future reference.",
            {
                "observation": str,  # The observation text (required)
                "memory_type": str,  # 'discovery', 'gotcha', 'bug_fix', 'decision', 'trade_off'
                "context": str,  # Related file path or additional context
            },
        )
        async def oak_remember(args: dict[str, Any]) -> dict[str, Any]:
            """Create a new observation."""
            try:
                result = ops.remember(args)
                return {"content": [{"type": "text", "text": result}]}
            except (ValueError, TypeError) as e:
                return {
                    "content": [{"type": "text", "text": f"Error: {e}"}],
                    "is_error": True,
                }
            except (OSError, RuntimeError) as e:
                logger.error(f"OAK remember failed: {e}")
                return {
                    "content": [{"type": "text", "text": f"Remember error: {e}"}],
                    "is_error": True,
                }

        tools.append(oak_remember)

    # Tool: oak_resolve - Mark observation as resolved/superseded (opt-in via memory_write)
    if OAK_TOOL_RESOLVE in active_tools:

        @tool(
            OAK_TOOL_RESOLVE,
            "Mark an observation as resolved or superseded. Use after fixing a bug, "
            "addressing a gotcha, or when a newer observation replaces an older one.",
            {
                "id": str,  # Observation UUID (required)
                "status": str,  # 'resolved' or 'superseded'
                "reason": str,  # Optional reason for resolution
            },
        )
        async def oak_resolve(args: dict[str, Any]) -> dict[str, Any]:
            """Resolve an observation."""
            try:
                result = ops.resolve_memory(args)
                return {"content": [{"type": "text", "text": result}]}
            except ValueError as e:
                return {
                    "content": [{"type": "text", "text": f"Error: {e}"}],
                    "is_error": True,
                }
            except (OSError, RuntimeError) as e:
                logger.error(f"OAK resolve failed: {e}")
                return {
                    "content": [{"type": "text", "text": f"Resolve error: {e}"}],
                    "is_error": True,
                }

        tools.append(oak_resolve)

    # Tool: oak_archive - Remove observations from search index (opt-in via memory_write)
    if OAK_TOOL_ARCHIVE in active_tools:

        @tool(
            OAK_TOOL_ARCHIVE,
            "Archive observations from the ChromaDB search index. Archived observations "
            "remain in SQLite for historical queries but stop polluting vector search results. "
            "Provide specific IDs or use status_filter + older_than_days to bulk archive.",
            {
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
                        "description": "Archive by status: 'resolved', 'superseded', or 'both'",
                    },
                    "older_than_days": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Only archive observations older than this many days",
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "If true, return count without actually archiving",
                    },
                },
            },
        )
        async def oak_archive(args: dict[str, Any]) -> dict[str, Any]:
            """Archive observations from search index."""
            try:
                result = ops.archive_memories(args)
                return {"content": [{"type": "text", "text": result}]}
            except ValueError as e:
                return {
                    "content": [{"type": "text", "text": f"Error: {e}"}],
                    "is_error": True,
                }
            except (OSError, RuntimeError) as e:
                logger.error(f"OAK archive failed: {e}")
                return {
                    "content": [{"type": "text", "text": f"Archive error: {e}"}],
                    "is_error": True,
                }

        tools.append(oak_archive)

    return tools


def create_oak_mcp_server(
    retrieval_engine: RetrievalEngine,
    activity_store: ActivityStore | None = None,
    vector_store: VectorStore | None = None,
    enabled_tools: set[str] | None = None,
) -> McpSdkServerConfig | None:
    """Create an in-process MCP server with OAK tools.

    This server can be passed to ClaudeCodeOptions.mcp_servers to make
    OAK tools available to agents.

    Args:
        retrieval_engine: RetrievalEngine instance for search operations.
        activity_store: ActivityStore instance for session data (optional).
        vector_store: VectorStore instance for stats (optional).
        enabled_tools: Optional set of tool names to include. If None, all
            standard tools are included (oak_query requires explicit opt-in).

    Returns:
        McpSdkServerConfig instance, or None if SDK not available.
    """
    try:
        from claude_agent_sdk import create_sdk_mcp_server
    except ImportError:
        logger.warning("claude-agent-sdk not installed, cannot create MCP server")
        return None

    tools = create_oak_tools(retrieval_engine, activity_store, vector_store, enabled_tools)
    if not tools:
        return None

    return create_sdk_mcp_server(
        name=OAK_MCP_SERVER_NAME,
        version=OAK_MCP_SERVER_VERSION,
        tools=tools,
    )


# =============================================================================
# Backward Compatibility Aliases (deprecated — use oak_* names)
# =============================================================================

build_ci_tools_from_access = build_oak_tools_from_access
create_ci_tools = create_oak_tools
create_ci_mcp_server = create_oak_mcp_server
