"""CI data tools for agents.

This module provides MCP tools that expose Codebase Intelligence data
to agents running via the claude-code-sdk. These tools allow agents to:
- Search code and memories semantically
- Access session history and summaries
- Get project statistics

The tools use the existing RetrievalEngine and ActivityStore for data access.
"""

import logging
from typing import TYPE_CHECKING, Any

from open_agent_kit.features.codebase_intelligence.constants import (
    CI_MCP_SERVER_NAME,
    CI_MCP_SERVER_VERSION,
    CI_TOOL_MEMORIES,
    CI_TOOL_PROJECT_STATS,
    CI_TOOL_SEARCH,
    CI_TOOL_SESSIONS,
    DEFAULT_SEARCH_LIMIT,
    SEARCH_TYPE_ALL,
    SEARCH_TYPE_CODE,
    SEARCH_TYPE_MEMORY,
)

if TYPE_CHECKING:
    from claude_agent_sdk import SDKMCPServer

    from open_agent_kit.features.codebase_intelligence.activity.store import ActivityStore
    from open_agent_kit.features.codebase_intelligence.memory.store import VectorStore
    from open_agent_kit.features.codebase_intelligence.retrieval.engine import RetrievalEngine

logger = logging.getLogger(__name__)


def _format_code_results(results: list[dict[str, Any]], max_preview: int = 200) -> str:
    """Format code search results for agent consumption.

    Args:
        results: Code search results from RetrievalEngine.
        max_preview: Maximum characters for content preview.

    Returns:
        Formatted string with code results.
    """
    if not results:
        return "No code results found."

    lines = [f"Found {len(results)} code chunks:\n"]
    for i, r in enumerate(results, 1):
        filepath = r.get("filepath", "unknown")
        chunk_type = r.get("chunk_type", "unknown")
        name = r.get("name", "")
        start_line = r.get("start_line", 0)
        end_line = r.get("end_line", 0)
        confidence = r.get("confidence", "medium")
        content = r.get("content", "")

        header = f"{i}. {filepath}:{start_line}-{end_line}"
        if name:
            header += f" ({chunk_type}: {name})"
        header += f" [{confidence}]"

        lines.append(header)
        if content:
            preview = content[:max_preview]
            if len(content) > max_preview:
                preview += "..."
            lines.append(f"   {preview}\n")

    return "\n".join(lines)


def _format_memory_results(results: list[dict[str, Any]]) -> str:
    """Format memory search results for agent consumption.

    Args:
        results: Memory search results from RetrievalEngine.

    Returns:
        Formatted string with memory results.
    """
    if not results:
        return "No memories found."

    lines = [f"Found {len(results)} memories:\n"]
    for i, r in enumerate(results, 1):
        memory_type = r.get("memory_type", "discovery")
        observation = r.get("observation", r.get("summary", ""))
        confidence = r.get("confidence", "medium")

        lines.append(f"{i}. [{memory_type}] ({confidence})")
        lines.append(f"   {observation}\n")

    return "\n".join(lines)


def _format_session_results(sessions: list[dict[str, Any]]) -> str:
    """Format session list for agent consumption.

    Args:
        sessions: Session records from ActivityStore.

    Returns:
        Formatted string with session summaries.
    """
    if not sessions:
        return "No sessions found."

    lines = [f"Found {len(sessions)} sessions:\n"]
    for i, s in enumerate(sessions, 1):
        session_id = s.get("id", "unknown")
        title = s.get("title") or s.get("first_prompt_preview", "Untitled")
        if title and len(title) > 80:
            title = title[:77] + "..."
        status = s.get("status", "unknown")
        started_at = s.get("started_at", "")
        summary = s.get("summary", "")

        lines.append(f"{i}. {title}")
        lines.append(f"   ID: {session_id} | Status: {status} | Started: {started_at}")
        if summary:
            preview = summary[:200] + "..." if len(summary) > 200 else summary
            lines.append(f"   Summary: {preview}")
        lines.append("")

    return "\n".join(lines)


def create_ci_tools(
    retrieval_engine: "RetrievalEngine",
    activity_store: "ActivityStore | None",
    vector_store: "VectorStore | None",
) -> list[Any]:
    """Create CI data tools for use with claude-code-sdk.

    These tools are implemented as decorated functions that can be passed
    to create_sdk_mcp_server().

    Args:
        retrieval_engine: RetrievalEngine instance for search operations.
        activity_store: ActivityStore instance for session data (optional).
        vector_store: VectorStore instance for stats (optional).

    Returns:
        List of tool functions decorated with @tool.
    """
    try:
        from claude_agent_sdk.tools import tool
    except ImportError:
        logger.warning("claude-code-sdk not installed, CI tools unavailable")
        return []

    tools = []

    # Tool: ci_search - Semantic search over code and memories
    @tool(
        CI_TOOL_SEARCH,
        "Search the codebase and project memories using semantic similarity. "
        "Returns ranked results with relevance scores.",
        {
            "query": str,  # Natural language search query
            "search_type": str,  # 'all', 'code', or 'memory'
            "limit": int,  # Maximum results (1-50)
        },
    )
    async def ci_search(args: dict[str, Any]) -> dict[str, Any]:
        """Search code and memories."""
        query = args.get("query", "")
        search_type = args.get("search_type", SEARCH_TYPE_ALL)
        limit = min(max(args.get("limit", DEFAULT_SEARCH_LIMIT), 1), 50)

        if not query:
            return {
                "content": [{"type": "text", "text": "Error: query is required"}],
                "is_error": True,
            }

        if search_type not in (SEARCH_TYPE_ALL, SEARCH_TYPE_CODE, SEARCH_TYPE_MEMORY):
            search_type = SEARCH_TYPE_ALL

        try:
            result = retrieval_engine.search(
                query=query,
                search_type=search_type,
                limit=limit,
            )

            output_parts = []
            if result.code:
                output_parts.append("## Code Results\n")
                output_parts.append(_format_code_results(result.code))
            if result.memory:
                output_parts.append("\n## Memory Results\n")
                output_parts.append(_format_memory_results(result.memory))

            if not output_parts:
                output_parts.append("No results found for your query.")

            return {"content": [{"type": "text", "text": "\n".join(output_parts)}]}

        except (OSError, ValueError, RuntimeError) as e:
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
        memory_type = args.get("memory_type")
        limit = min(max(args.get("limit", 20), 1), 100)

        try:
            memory_types = [memory_type] if memory_type else None
            memories, total = retrieval_engine.list_memories(
                limit=limit,
                memory_types=memory_types,
            )

            if not memories:
                return {"content": [{"type": "text", "text": "No memories found."}]}

            output = _format_memory_results(memories)
            output += f"\n(Showing {len(memories)} of {total} total memories)"

            return {"content": [{"type": "text", "text": output}]}

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
        limit = min(max(args.get("limit", 10), 1), 20)

        if not activity_store:
            return {
                "content": [{"type": "text", "text": "Session history not available."}],
                "is_error": True,
            }

        try:
            sessions = activity_store.get_recent_sessions(limit=limit, offset=0)

            if not sessions:
                return {"content": [{"type": "text", "text": "No sessions found."}]}

            # Convert to dicts for formatting
            session_dicts = [
                {
                    "id": s.id,
                    "title": s.title,
                    "first_prompt_preview": None,  # Not a direct attribute on Session
                    "status": s.status or "unknown",
                    "started_at": str(s.started_at) if s.started_at else "",
                    "summary": s.summary or "",
                }
                for s in sessions
            ]

            output = _format_session_results(session_dicts)
            output += f"\n(Showing {len(sessions)} sessions)"

            return {"content": [{"type": "text", "text": output}]}

        except (OSError, ValueError, RuntimeError, AttributeError) as e:
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
            stats_parts = ["## Project Statistics\n"]

            # Vector store stats
            if vector_store:
                vs_stats = vector_store.get_stats()
                stats_parts.append("### Code Index")
                stats_parts.append(f"- Indexed chunks: {vs_stats.get('code_chunks', 0)}")
                stats_parts.append(f"- Unique files: {vs_stats.get('unique_files', 0)}")
                stats_parts.append(f"- Total memories: {vs_stats.get('memory_count', 0)}")
                stats_parts.append("")

            # Activity store stats
            if activity_store:
                obs_count = activity_store.count_observations()
                stats_parts.append("### Activity History")
                stats_parts.append(f"- Total observations: {obs_count}")

            return {"content": [{"type": "text", "text": "\n".join(stats_parts)}]}

        except (OSError, ValueError, RuntimeError, AttributeError) as e:
            logger.error(f"CI project stats failed: {e}")
            return {
                "content": [{"type": "text", "text": f"Error getting stats: {e}"}],
                "is_error": True,
            }

    tools.append(ci_project_stats)

    return tools


def create_ci_mcp_server(
    retrieval_engine: "RetrievalEngine",
    activity_store: "ActivityStore | None" = None,
    vector_store: "VectorStore | None" = None,
) -> "SDKMCPServer | None":
    """Create an in-process MCP server with CI tools.

    This server can be passed to ClaudeAgentOptions.mcp_servers to make
    CI tools available to agents.

    Args:
        retrieval_engine: RetrievalEngine instance for search operations.
        activity_store: ActivityStore instance for session data (optional).
        vector_store: VectorStore instance for stats (optional).

    Returns:
        SDKMCPServer instance, or None if SDK not available.
    """
    try:
        from claude_agent_sdk import create_sdk_mcp_server
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
