"""Context injection helpers for AI agent hooks.

This module provides formatting functions for injecting relevant context
(memories, code snippets, session summaries) into AI agent conversations.
Extracted from hooks.py for maintainability.
"""

import logging
from typing import TYPE_CHECKING

from open_agent_kit.features.codebase_intelligence.constants import (
    INJECTION_MAX_CODE_CHUNKS,
    INJECTION_MAX_LINES_PER_CHUNK,
    INJECTION_MAX_MEMORIES,
    INJECTION_MAX_SESSION_SUMMARIES,
)
from open_agent_kit.features.codebase_intelligence.retrieval.engine import RetrievalEngine

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.daemon.state import DaemonState

logger = logging.getLogger(__name__)

# Language detection map (file extension -> code fence language)
LANG_MAP: dict[str, str] = {
    "py": "python",
    "ts": "typescript",
    "tsx": "typescript",
    "js": "javascript",
    "jsx": "javascript",
    "rb": "ruby",
    "go": "go",
    "rs": "rust",
    "java": "java",
    "kt": "kotlin",
    "swift": "swift",
    "c": "c",
    "cpp": "cpp",
    "h": "c",
    "hpp": "cpp",
    "cs": "csharp",
    "sh": "bash",
    "yaml": "yaml",
    "yml": "yaml",
    "json": "json",
    "md": "markdown",
    "sql": "sql",
}


# =============================================================================
# Memory Formatting
# =============================================================================


def format_memories_for_injection(
    memories: list[dict], max_items: int = INJECTION_MAX_MEMORIES
) -> str:
    """Format memories as a concise string for context injection.

    Args:
        memories: List of memory dicts with observation, memory_type, context.
        max_items: Maximum number of items to include.

    Returns:
        Formatted string for Claude's context.
    """
    if not memories:
        return ""

    emoji_map = {
        "gotcha": "!",
        "bug_fix": "[fix]",
        "decision": "[decision]",
        "discovery": "[discovery]",
        "trade_off": "[trade-off]",
    }

    lines = ["## Recent Project Memories\n"]
    for mem in memories[:max_items]:
        mem_type = mem.get("memory_type", "note")
        emoji = emoji_map.get(mem_type, "[note]")
        obs = mem.get("observation", "")
        ctx = mem.get("context", "")

        line = f"- {emoji} **{mem_type}**: {obs}"
        if ctx:
            line += f" _(context: {ctx})_"
        lines.append(line)

    return "\n".join(lines)


def format_session_summaries(
    summaries: list[dict], max_items: int = INJECTION_MAX_SESSION_SUMMARIES
) -> str:
    """Format session summaries for context injection.

    Args:
        summaries: List of session summary memory dicts.
        max_items: Maximum number of summaries to include.

    Returns:
        Formatted string with recent session context.
    """
    if not summaries:
        return ""

    lines = ["## Recent Session History\n"]
    for i, summary in enumerate(summaries[:max_items], 1):
        obs = summary.get("observation", "")
        tags = summary.get("tags", [])

        # Extract agent from tags (filter out system tags)
        system_tags = {"session-summary", "session", "llm-summarized", "auto-extracted"}
        agent = next((t for t in tags if t not in system_tags), "unknown")

        # Truncate long summaries
        if len(obs) > 200:
            obs = obs[:197] + "..."

        lines.append(f"**Session {i}** ({agent}): {obs}\n")

    return "\n".join(lines)


# =============================================================================
# Code Formatting
# =============================================================================


def format_code_for_injection(
    code_chunks: list[dict],
    max_chunks: int = INJECTION_MAX_CODE_CHUNKS,
    max_lines_per_chunk: int = INJECTION_MAX_LINES_PER_CHUNK,
) -> str:
    """Format code chunks as markdown for context injection.

    Args:
        code_chunks: List of code chunk dicts with filepath, start_line, end_line, name, content.
        max_chunks: Maximum number of chunks to include.
        max_lines_per_chunk: Maximum lines per chunk before truncation.

    Returns:
        Formatted markdown string with code blocks.
    """
    if not code_chunks:
        return ""

    parts = ["## Relevant Code\n"]
    for chunk in code_chunks[:max_chunks]:
        filepath = chunk.get("filepath", "unknown")
        start_line = chunk.get("start_line", 1)
        end_line = chunk.get("end_line", start_line)
        name = chunk.get("name", "")
        content = chunk.get("content", "")

        # Truncate long chunks
        lines = content.split("\n")
        if len(lines) > max_lines_per_chunk:
            content = (
                "\n".join(lines[:max_lines_per_chunk])
                + f"\n... ({len(lines) - max_lines_per_chunk} more lines)"
            )

        # Detect language from extension
        ext = filepath.rsplit(".", 1)[-1] if "." in filepath else ""
        lang = LANG_MAP.get(ext, ext)

        header = f"**{filepath}** (L{start_line}-{end_line})"
        if name:
            header += f" - `{name}`"
        parts.append(f"{header}\n```{lang}\n{content}\n```\n")

    return "\n".join(parts)


# =============================================================================
# Search Query Building
# =============================================================================


def build_rich_search_query(
    file_path: str,
    tool_output: str | None = None,
    user_prompt: str | None = None,
) -> str:
    """Build search query from file path + context for richer semantic matching.

    Combines file path with relevant excerpts from tool output and user prompt
    to create a more semantically meaningful search query than file path alone.

    Args:
        file_path: The file path being operated on.
        tool_output: Optional tool output (will filter noise patterns).
        user_prompt: Optional user prompt excerpt.

    Returns:
        Combined search query string.
    """
    parts = [file_path]

    # Add tool output excerpt (skip noise patterns like file content dumps)
    # Ensure tool_output is actually a string before processing
    if tool_output and isinstance(tool_output, str):
        noise_prefixes = ("Read ", "1\u2192", "{", "[", "     1\u2192")
        if not any(tool_output.strip().startswith(p) for p in noise_prefixes):
            excerpt = tool_output[:200].strip()
            if excerpt:
                parts.append(excerpt)

    # Add user prompt excerpt (ensure it's a string, not a mock or other type)
    # Use 500 chars (~125 tokens) for meaningful semantic matching
    if user_prompt and isinstance(user_prompt, str):
        parts.append(user_prompt[:500].strip())

    return " ".join(parts)


# =============================================================================
# Session Context Building
# =============================================================================


def build_session_context(state: "DaemonState", include_memories: bool = True) -> str:
    """Build context string for session injection.

    Provides status information and relevant memories for session start.
    Does NOT include CLI command reminders (agents rarely use them).

    Args:
        state: Daemon state object.
        include_memories: Whether to include recent memories.

    Returns:
        Formatted context string for Claude.
    """
    parts = []

    # Add CI status summary (simple, no CLI reminders)
    if state.vector_store:
        stats = state.vector_store.get_stats()
        code_chunks = stats.get("code_chunks", 0)
        memory_count = stats.get("memory_observations", 0)

        if code_chunks > 0 or memory_count > 0:
            parts.append(
                f"**Codebase Intelligence Active**: {code_chunks} code chunks indexed, "
                f"{memory_count} memories stored."
            )

        # Include recent session summaries (provides continuity across sessions)
        if include_memories and state.retrieval_engine:
            try:
                session_summaries, _ = state.retrieval_engine.list_memories(
                    limit=INJECTION_MAX_SESSION_SUMMARIES,
                    memory_types=["session_summary"],
                )
                if session_summaries:
                    session_text = format_session_summaries(session_summaries)
                    if session_text:
                        parts.append(session_text)
            except (OSError, ValueError, RuntimeError, AttributeError) as e:
                logger.debug(f"Failed to fetch session summaries for injection: {e}")

        # Include recent memories (gotchas, decisions, etc.) - excluding session summaries
        if include_memories and memory_count > 0 and state.retrieval_engine:
            try:
                # Search with base threshold, then filter by confidence
                # For session start, include high and medium confidence (broader context)
                result = state.retrieval_engine.search(
                    query="important gotchas decisions bugs",
                    search_type="memory",
                    limit=15,  # Fetch more, filter by confidence
                )
                # Filter to high and medium confidence, exclude session summaries
                confident_memories = RetrievalEngine.filter_by_confidence(
                    result.memory, min_confidence="medium"
                )
                recent = [
                    m for m in confident_memories if m.get("memory_type") != "session_summary"
                ]
                if recent:
                    mem_text = format_memories_for_injection(recent[:INJECTION_MAX_MEMORIES])
                    if mem_text:
                        parts.append(mem_text)
            except (OSError, ValueError, RuntimeError, AttributeError) as e:
                logger.debug(f"Failed to fetch memories for injection: {e}")

    return "\n\n".join(parts) if parts else ""
