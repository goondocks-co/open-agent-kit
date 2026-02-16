"""Context injection helpers for AI agent hooks.

This module provides formatting functions for injecting relevant context
(memories, code snippets, session summaries) into AI agent conversations.
Extracted from hooks.py for maintainability.
"""

import logging
from typing import TYPE_CHECKING, Any

from open_agent_kit.features.codebase_intelligence.constants import (
    AGENT_CURSOR,
    AGENTS_HOOK_SPECIFIC_OUTPUT,
    DEFAULT_PREVIEW_LENGTH,
    DEFAULT_RELATED_QUERY_LENGTH,
    INJECTION_MAX_CODE_CHUNKS,
    INJECTION_MAX_LINES_PER_CHUNK,
    INJECTION_MAX_MEMORIES,
    INJECTION_MAX_SESSION_SUMMARIES,
    INJECTION_SESSION_START_REMINDER_BLOCK,
    INJECTION_SESSION_SUMMARIES_TITLE,
    MEMORY_EMBED_LABEL_CONTEXT,
    MEMORY_EMBED_LABEL_FILE,
    MEMORY_EMBED_LABEL_SEPARATOR,
    MEMORY_EMBED_LABEL_TEMPLATE,
    MEMORY_EMBED_LINE_SEPARATOR,
)
from open_agent_kit.features.codebase_intelligence.daemon.models import MemoryType

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

        mem_id = mem.get("id", "")
        line = f"- {emoji} **{mem_type}**: {obs}"
        if ctx:
            line += f" _(context: {ctx})_"
        if mem_id:
            line += f" `[id: {mem_id}]`"
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

    lines = [INJECTION_SESSION_SUMMARIES_TITLE]
    for i, summary in enumerate(summaries[:max_items], 1):
        obs = summary.get("observation", "")
        tags = summary.get("tags", [])

        # Extract agent from tags (filter out system tags)
        system_tags = {"session-summary", "session", "llm-summarized", "auto-extracted"}
        agent = next((t for t in tags if t not in system_tags), "unknown")

        # Truncate long summaries
        if len(obs) > 200:
            obs = obs[:197] + "..."

        lines.append(f"**Session {i}** ({agent}): {obs}")

    return MEMORY_EMBED_LINE_SEPARATOR.join(lines)


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
    normalized_path: str,
    tool_output: str | None = None,
    user_prompt: str | None = None,
) -> str:
    """Build search query from file path + context for richer semantic matching.

    Combines file path with relevant excerpts from tool output and user prompt
    to create a more semantically meaningful search query than file path alone.

    Args:
        normalized_path: The project-relative path being operated on.
        tool_output: Optional tool output (will filter noise patterns).
        user_prompt: Optional user prompt excerpt.

    Returns:
        Combined search query string.
    """
    file_name = normalized_path.rsplit("/", 1)[-1]
    parts = [
        MEMORY_EMBED_LABEL_TEMPLATE.format(
            label=MEMORY_EMBED_LABEL_FILE,
            separator=MEMORY_EMBED_LABEL_SEPARATOR,
            value=file_name,
        ),
        MEMORY_EMBED_LABEL_TEMPLATE.format(
            label=MEMORY_EMBED_LABEL_CONTEXT,
            separator=MEMORY_EMBED_LABEL_SEPARATOR,
            value=normalized_path,
        ),
    ]

    # Add tool output excerpt (skip noise patterns like file content dumps)
    # Ensure tool_output is actually a string before processing
    if tool_output and isinstance(tool_output, str):
        noise_prefixes = ("Read ", "1\u2192", "{", "[", "     1\u2192")
        if not any(tool_output.strip().startswith(p) for p in noise_prefixes):
            excerpt = tool_output[:DEFAULT_PREVIEW_LENGTH].strip()
            if excerpt:
                parts.append(excerpt)

    # Add user prompt excerpt (ensure it's a string, not a mock or other type)
    # Use DEFAULT_RELATED_QUERY_LENGTH for meaningful semantic matching
    if user_prompt and isinstance(user_prompt, str):
        parts.append(user_prompt[:DEFAULT_RELATED_QUERY_LENGTH].strip())

    return MEMORY_EMBED_LINE_SEPARATOR.join(parts)


# =============================================================================
# Session Context Building
# =============================================================================


def build_session_context(
    state: "DaemonState",
    include_memories: bool = True,
    session_id: str | None = None,
) -> str:
    """Build context string for session injection.

    Provides status information, MCP tool reminders, and relevant memories
    for session start.

    Args:
        state: Daemon state object.
        include_memories: Whether to include recent memories.
        session_id: Optional session ID to include in context for precise
            tool call linking (e.g., oak_remember session_id parameter).

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

            reminder = INJECTION_SESSION_START_REMINDER_BLOCK
            if session_id:
                reminder += f"\n- Current session: `session_id={session_id}`"
            parts.append(reminder)

            # Include recent session summaries (provides continuity across sessions)
            if include_memories and state.retrieval_engine:
                try:
                    session_summaries, _ = state.retrieval_engine.list_memories(
                        limit=INJECTION_MAX_SESSION_SUMMARIES,
                        memory_types=[MemoryType.SESSION_SUMMARY.value],
                    )
                    if not session_summaries and state.activity_store:
                        sqlite_summaries = state.activity_store.list_session_summaries(
                            limit=INJECTION_MAX_SESSION_SUMMARIES
                        )
                        session_summaries = [
                            {
                                "observation": summary.observation,
                                "tags": summary.tags or [],
                                "memory_type": MemoryType.SESSION_SUMMARY.value,
                            }
                            for summary in sqlite_summaries
                        ]
                    if session_summaries:
                        session_text = format_session_summaries(session_summaries)
                        if session_text:
                            parts.append(session_text)
                except (OSError, ValueError, RuntimeError, AttributeError) as e:
                    logger.debug(f"Failed to fetch session summaries for injection: {e}")

            # Note: Random gotchas/decisions are NOT injected at session start because
            # there's no user prompt to filter relevance. Session summaries provide
            # sufficient context. Use oak_context tool for task-specific memories.

    return "\n\n".join(parts) if parts else ""


# =============================================================================
# Hook Output Formatting
# =============================================================================


def format_hook_output(
    response: dict[str, Any],
    agent: str,
    hook_event_name: str,
) -> dict[str, Any]:
    """Format daemon response into the JSON shape the calling agent expects on stdout.

    Each agent protocol has its own expected output format. This function
    centralises that logic so the CLI can be a thin pipe that extracts
    ``hook_output`` from the daemon response and prints it.

    Args:
        response: The daemon route response dict (may contain ``context.injected_context``
            or top-level ``injected_context``).
        agent: Agent identifier (e.g. ``"claude"``, ``"vscode-copilot"``, ``"cursor"``).
        hook_event_name: The hook event name (e.g. ``"SessionStart"``).

    Returns:
        Dict ready to be serialised as JSON and printed to stdout by the CLI.
    """
    injected = response.get("context", {}).get("injected_context") or response.get(
        "injected_context"
    )

    # Claude Code / VS Code Copilot: hookSpecificOutput format.
    #
    # VS Code Copilot requires hookSpecificOutput in ALL hook responses.
    # Without it, VS Code crashes with:
    #   "Cannot read properties of undefined (reading 'hookSpecificOutput')"
    # This applies to ALL events, including UserPromptSubmit and PreCompact
    # which the docs claim don't support hookSpecificOutput.
    #
    # For --agent claude, hookSpecificOutput is the standard format.
    # For --agent vscode-copilot, hookSpecificOutput is mandatory.
    if agent in AGENTS_HOOK_SPECIFIC_OUTPUT:
        hook_specific: dict[str, Any] = {"hookEventName": hook_event_name}
        if injected:
            hook_specific["additionalContext"] = injected
        return {
            "continue": True,
            "hookSpecificOutput": hook_specific,
        }

    # Cursor: flat additional_context format
    if agent == AGENT_CURSOR:
        if injected:
            return {"additional_context": injected}
        return {}

    # Other agents: no formatting
    return {}
