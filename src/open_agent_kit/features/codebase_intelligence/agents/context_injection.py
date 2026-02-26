"""Context injection helpers for interactive ACP sessions.

Provides functions for building session context, searching prompt context,
and formatting task awareness blocks for the system prompt.  Extracted from
``InteractiveSessionManager`` to keep it focused on session lifecycle.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from open_agent_kit.features.codebase_intelligence.constants import (
    INJECTION_MAX_SESSION_SUMMARIES,
    INJECTION_SESSION_START_REMINDER_BLOCK,
)

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.store import ActivityStore
    from open_agent_kit.features.codebase_intelligence.agents.registry import AgentRegistry
    from open_agent_kit.features.codebase_intelligence.memory.store import VectorStore
    from open_agent_kit.features.codebase_intelligence.retrieval.engine import RetrievalEngine

logger = logging.getLogger(__name__)


def build_session_context(
    session_id: str,
    vector_store: VectorStore | None,
    activity_store: ActivityStore | None,
) -> str:
    """Build context string for session-start injection.

    Args:
        session_id: Current session ID for tool call linking.
        vector_store: VectorStore for CI stats.
        activity_store: ActivityStore for session summaries.

    Returns:
        Formatted context string (may be empty).
    """
    parts: list[str] = []

    try:
        if vector_store:
            stats = vector_store.get_stats()
            code_chunks = stats.get("code_chunks", 0)
            memory_count = stats.get("memory_observations", 0)

            if code_chunks > 0 or memory_count > 0:
                parts.append(
                    f"**Codebase Intelligence Active**: {code_chunks} code chunks indexed, "
                    f"{memory_count} memories stored."
                )

                reminder = INJECTION_SESSION_START_REMINDER_BLOCK
                reminder += f"\n- Current session: `session_id={session_id}`"
                parts.append(reminder)

                if activity_store:
                    try:
                        from open_agent_kit.features.codebase_intelligence.daemon.routes.injection import (
                            format_session_summaries,
                        )

                        recent_sessions = activity_store.list_sessions_with_summaries(
                            limit=INJECTION_MAX_SESSION_SUMMARIES
                        )
                        if recent_sessions:
                            session_summaries = [
                                {
                                    "observation": s.summary,
                                    "tags": [s.agent],
                                }
                                for s in recent_sessions
                            ]
                            session_text = format_session_summaries(session_summaries)
                            if session_text:
                                parts.append(session_text)
                    except (OSError, ValueError, RuntimeError, AttributeError) as e:
                        logger.debug(f"Failed to fetch session summaries for ACP injection: {e}")
    except (OSError, ValueError, RuntimeError, AttributeError) as e:
        logger.debug(f"Failed to build session context: {e}")

    return "\n\n".join(parts) if parts else ""


def search_prompt_context(
    user_text: str,
    retrieval_engine: RetrievalEngine | None,
) -> str | None:
    """Search for relevant code and memories based on user prompt.

    Args:
        user_text: The user's prompt text.
        retrieval_engine: RetrievalEngine for searching.

    Returns:
        Formatted context string, or None if nothing relevant found.
    """
    if not retrieval_engine:
        return None

    try:
        from open_agent_kit.features.codebase_intelligence.daemon.routes.injection import (
            format_code_for_injection,
            format_memories_for_injection,
        )
        from open_agent_kit.features.codebase_intelligence.retrieval.engine import (
            RetrievalEngine as RE,
        )

        search_res = retrieval_engine.search(
            query=user_text,
            search_type="all",
            limit=10,
        )

        parts: list[str] = []

        if search_res.code:
            confident_code = RE.filter_by_combined_score(search_res.code, min_combined="high")
            if confident_code:
                code_text = format_code_for_injection(confident_code[:3])
                if code_text:
                    parts.append(code_text)

        if search_res.memory:
            confident_memories = RE.filter_by_combined_score(search_res.memory, min_combined="high")
            if confident_memories:
                mem_text = format_memories_for_injection(confident_memories[:5])
                if mem_text:
                    parts.append(mem_text)

        if parts:
            return "\n\n".join(parts)

    except (OSError, ValueError, RuntimeError, AttributeError) as e:
        logger.debug(f"Failed to search prompt context: {e}")

    return None


def build_task_context(
    focus: str,
    agent_registry: AgentRegistry | None,
) -> str:
    """Build a task-awareness section for the system prompt.

    When a non-default focus is active, finds all tasks that use that
    template and produces a concise reference the agent can use.

    Args:
        focus: Current agent focus (template name).
        agent_registry: AgentRegistry for loading task definitions.

    Returns:
        Markdown block describing available tasks, or empty string.
    """
    if agent_registry is None:
        return ""

    tasks = [t for t in agent_registry.list_tasks() if t.agent_type == focus]
    if not tasks:
        return ""

    lines = [
        "## Available Tasks",
        "",
        (
            "The following pre-configured tasks exist for this focus. When the "
            "user's request aligns with a task, follow its conventions — maintained "
            "files, style, and output requirements."
        ),
        "",
    ]

    for task in tasks:
        lines.append(f"### {task.display_name} (`{task.name}`)")
        if task.description:
            lines.append(f"{task.description.strip()}")
        lines.append("")

        if task.maintained_files:
            lines.append("**Maintained files:**")
            for mf in task.maintained_files:
                path = mf.path.replace("{project_root}/", "")
                purpose = f" — {mf.purpose}" if mf.purpose else ""
                lines.append(f"- `{path}`{purpose}")
            lines.append("")

        if task.output_requirements:
            sections = task.output_requirements.get("required_sections", [])
            if sections:
                lines.append("**Required sections:**")
                for section in sections:
                    if isinstance(section, dict):
                        name = section.get("name", "")
                        desc = section.get("description", "")
                        lines.append(f"- {name}: {desc}" if desc else f"- {name}")
                lines.append("")

        if task.style:
            conventions = task.style.get("conventions", [])
            if conventions:
                lines.append("**Conventions:**")
                for conv in conventions:
                    lines.append(f"- {conv}")
                lines.append("")

    return "\n".join(lines)
