"""Result formatting functions for CI tools.

These functions convert raw search/retrieval results into human-readable
markdown text suitable for LLM consumption.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.retrieval.engine import SearchResult


def format_code_results(results: list[dict[str, Any]], max_preview: int = 200) -> str:
    """Format code search results for agent consumption.

    Args:
        results: Code search results from RetrievalEngine.
        max_preview: Maximum characters for content preview.

    Returns:
        Formatted markdown string with code results.
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
        relevance = r.get("relevance")
        content = r.get("content", "")

        # Build header with location and metadata
        header = f"{i}. **{filepath}:{start_line}-{end_line}**"
        if name:
            header += f" ({chunk_type}: {name})"
        if relevance is not None:
            header += f" [relevance: {round(relevance, 2)}]"
        elif confidence:
            header += f" [{confidence}]"

        lines.append(header)
        if content:
            preview = content[:max_preview]
            if len(content) > max_preview:
                preview += "..."
            lines.append(f"```\n{preview}\n```\n")

    return "\n".join(lines)


def format_memory_results(results: list[dict[str, Any]]) -> str:
    """Format memory search results for agent consumption.

    Args:
        results: Memory search results from RetrievalEngine.

    Returns:
        Formatted markdown string with memory results.
    """
    if not results:
        return "No memories found."

    # Emoji mapping for memory types
    emoji_map = {
        "gotcha": "⚠️",
        "bug_fix": "🐛",
        "decision": "📋",
        "discovery": "💡",
        "trade_off": "⚖️",
    }

    lines = [f"Found {len(results)} memories:\n"]
    for i, r in enumerate(results, 1):
        memory_type = r.get("memory_type", "discovery")
        observation = r.get("observation", r.get("summary", ""))
        confidence = r.get("confidence", "medium")
        context = r.get("context", "")
        emoji = emoji_map.get(memory_type, "📝")

        header = f"{i}. {emoji} [{memory_type}]"
        if confidence != "medium":
            header += f" ({confidence})"

        lines.append(header)
        lines.append(f"   {observation}")
        if context:
            lines.append(f"   (context: {context})")
        lines.append("")

    return "\n".join(lines)


def format_plan_results(results: list[dict[str, Any]]) -> str:
    """Format plan search results for agent consumption.

    Plans are Software Design Documents (SDDs) that capture design intent,
    requirements, and implementation approach for features.

    Args:
        results: Plan search results from RetrievalEngine.

    Returns:
        Formatted markdown string with plan results.
    """
    if not results:
        return "No plans found."

    lines = [f"Found {len(results)} plans:\n"]
    for i, r in enumerate(results, 1):
        title = r.get("title", "Untitled Plan")
        confidence = r.get("confidence", "medium")
        preview = r.get("preview", "")
        created_at = r.get("created_at", "")
        plan_id = r.get("id", "unknown")

        lines.append(f"{i}. **{title}** [{confidence}]")
        if created_at:
            lines.append(f"   Created: {created_at}")
        lines.append(f"   ID: {plan_id}")
        if preview:
            # Indent preview lines (first 5 lines max)
            preview_lines = preview.split("\n")[:5]
            for line in preview_lines:
                lines.append(f"   {line}")
            if len(preview.split("\n")) > 5:
                lines.append("   ...")
        lines.append("")

    return "\n".join(lines)


def format_session_results(sessions: list[dict[str, Any]]) -> str:
    """Format session list for agent consumption.

    Args:
        sessions: Session records from ActivityStore.

    Returns:
        Formatted markdown string with session summaries.
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


def format_session_search_results(sessions: list[dict[str, Any]]) -> str:
    """Format session search results for agent consumption.

    Sessions are searched via embedded summaries in ChromaDB.

    Args:
        sessions: Session search results from RetrievalEngine.

    Returns:
        Formatted markdown string with session results.
    """
    if not sessions:
        return "No sessions found."

    lines = [f"Found {len(sessions)} sessions:\n"]
    for i, s in enumerate(sessions, 1):
        session_id = s.get("id", "unknown")
        title = s.get("title") or "Untitled"
        if title and len(title) > 80:
            title = title[:77] + "..."
        confidence = s.get("confidence", "medium")
        preview = s.get("preview", "")

        lines.append(f"{i}. **{title}** [{confidence}]")
        lines.append(f"   ID: {session_id}")
        if preview:
            # Truncate and indent preview
            preview_text = preview[:200] + "..." if len(preview) > 200 else preview
            lines.append(f"   {preview_text}")
        lines.append("")

    return "\n".join(lines)


def format_search_results(result: SearchResult, query: str | None = None) -> str:
    """Format combined search results from RetrievalEngine.

    Args:
        result: SearchResult from RetrievalEngine.search().
        query: Optional query string for header.

    Returns:
        Formatted markdown string with all result types.
    """
    output_parts = []

    if query:
        output_parts.append(f"Search results for: {query}\n")

    if result.code:
        output_parts.append("## Code Results\n")
        output_parts.append(format_code_results(result.code))

    if result.memory:
        output_parts.append("\n## Memory Results\n")
        output_parts.append(format_memory_results(result.memory))

    if hasattr(result, "plans") and result.plans:
        output_parts.append("\n## Plan Results\n")
        output_parts.append(format_plan_results(result.plans))

    if hasattr(result, "sessions") and result.sessions:
        output_parts.append("\n## Session Results\n")
        output_parts.append(format_session_search_results(result.sessions))

    if not output_parts or (query and len(output_parts) == 1):
        output_parts.append("No results found for your query.")

    return "\n".join(output_parts)


def format_context_results(
    code: list[dict[str, Any]] | None = None,
    memories: list[dict[str, Any]] | None = None,
) -> str:
    """Format task context results.

    Args:
        code: Relevant code chunks.
        memories: Related memories.

    Returns:
        Formatted markdown string with context.
    """
    parts = []

    if code:
        parts.append("## Relevant Code\n")
        for r in code:
            file_path = r.get("file_path", r.get("filepath", "unknown"))
            chunk_type = r.get("chunk_type", "code")
            name = r.get("name", "")
            start_line = r.get("start_line", 0)
            relevance = r.get("relevance", 0)

            parts.append(
                f"### {file_path} ({chunk_type}: {name})\n"
                f"Line {start_line} (relevance: {round(relevance, 2)})\n"
            )

    if memories:
        parts.append("## Related Memories\n")
        parts.append(format_memory_results(memories))

    if not parts:
        parts.append(
            "No specific context found for this task. " "This may be a new area of the codebase."
        )

    return "\n".join(parts)


def format_stats_results(
    code_chunks: int = 0,
    unique_files: int = 0,
    memory_count: int = 0,
    observation_count: int = 0,
    status_breakdown: dict[str, int] | None = None,
) -> str:
    """Format project statistics.

    Args:
        code_chunks: Number of indexed code chunks.
        unique_files: Number of unique files indexed.
        memory_count: Number of memories stored.
        observation_count: Number of observations in activity store.
        status_breakdown: Observation counts by status (e.g. {"active": 42, "resolved": 10}).

    Returns:
        Formatted markdown string with stats.
    """
    lines = ["## Project Statistics\n"]

    lines.append("### Code Index")
    lines.append(f"- Indexed chunks: {code_chunks}")
    lines.append(f"- Unique files: {unique_files}")
    lines.append(f"- Total memories: {memory_count}")
    lines.append("")

    if observation_count > 0:
        lines.append("### Activity History")
        lines.append(f"- Total observations: {observation_count}")
        if status_breakdown:
            lines.append("- Status breakdown:")
            for status, count in sorted(status_breakdown.items()):
                lines.append(f"  - {status}: {count}")

    return "\n".join(lines)
