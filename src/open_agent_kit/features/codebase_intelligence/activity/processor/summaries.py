"""Session summary generation.

Creates high-level summaries of completed sessions using LLM.
"""

import logging
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any

from open_agent_kit.features.codebase_intelligence.constants import (
    RECOVERY_BATCH_PROMPT,
    SESSION_SUMMARY_OBS_ID_PREFIX,
    SUMMARY_MAX_PLAN_CONTEXT_LENGTH,
)

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.prompts import (
        PromptTemplateConfig,
    )
    from open_agent_kit.features.codebase_intelligence.activity.store import (
        ActivityStore,
    )
    from open_agent_kit.features.codebase_intelligence.memory.store import VectorStore

logger = logging.getLogger(__name__)


def _is_recovery_prompt(prompt: str | None) -> bool:
    """Check if a prompt is a continuation placeholder (from session transitions)."""
    if not prompt:
        return False
    return prompt.startswith("[Recovery batch") or prompt == RECOVERY_BATCH_PROMPT


def _get_plan_context_for_summary(batches: list) -> str:
    """Get plan content to include in summary prompt.

    If the session contains a plan, include a truncated version so the summary
    accurately reflects what the session was about.

    Args:
        batches: List of PromptBatch objects for this session.

    Returns:
        Formatted plan context string, or empty string if no plan.
    """
    for batch in batches:
        if batch.source_type == "plan" and batch.plan_content:
            plan_content = batch.plan_content
            # Truncate if too long
            if len(plan_content) > SUMMARY_MAX_PLAN_CONTEXT_LENGTH:
                plan_content = plan_content[:SUMMARY_MAX_PLAN_CONTEXT_LENGTH] + "\n... (truncated)"

            return f"\n\n## Session Plan\n\nThis session created or implemented the following plan:\n\n{plan_content}\n"

    return ""


def _get_parent_context_for_summary(
    session_id: str,
    activity_store: "ActivityStore",
) -> str:
    """Get parent session context to include in summary prompt.

    Args:
        session_id: Current session ID.
        activity_store: Activity store.

    Returns:
        Formatted parent context string, or empty string if no parent.
    """
    try:
        session = activity_store.get_session(session_id)
        if not session or not session.parent_session_id:
            return ""

        parent = activity_store.get_session(session.parent_session_id)
        if not parent:
            return ""

        # Get parent's summary from observations if available
        parent_summary = None
        summary_obs = activity_store.get_latest_session_summary(session.parent_session_id)
        if summary_obs:
            parent_summary = summary_obs.observation

        if not parent.title and not parent_summary:
            return ""

        context = "\n\n## Parent Session Context\n"
        context += "This session is a continuation of a previous session.\n"
        if parent.title:
            context += f"Parent title: {parent.title}\n"
        if parent_summary:
            # Truncate long summaries
            preview = parent_summary[:400] if len(parent_summary) > 400 else parent_summary
            context += f"Parent summary: {preview}\n"

        return context
    except (OSError, ValueError, AttributeError):
        return ""


def process_session_summary(
    session_id: str,
    activity_store: "ActivityStore",
    vector_store: "VectorStore",
    prompt_config: "PromptTemplateConfig",
    call_llm: Callable[[str], dict[str, Any]],
    generate_title: Callable[[str], str | None],
    regenerate_title: bool = False,
    generate_title_from_summary: Callable[[str, str], str | None] | None = None,
) -> tuple[str | None, str | None]:
    """Generate and store a session summary and optionally regenerate title.

    Called at session end to create a high-level summary of what was accomplished.
    Stored as a session_summary memory for injection into future sessions.
    Also generates a short title for the session if one doesn't exist,
    or regenerates from the summary when explicitly requested.

    Args:
        session_id: Session ID to summarize.
        activity_store: Activity store for fetching session data.
        vector_store: Vector store for storing summary.
        prompt_config: Prompt template configuration.
        call_llm: Function to call LLM.
        generate_title: Function to generate session title from prompt batches.
        regenerate_title: If True, regenerate title even if one exists.
        generate_title_from_summary: Optional function to generate title from summary text.

    Returns:
        Tuple of (summary text, title text) if generated, (None, None) otherwise.
    """
    from open_agent_kit.features.codebase_intelligence.activity.store import (
        StoredObservation,
    )
    from open_agent_kit.features.codebase_intelligence.daemon.models import MemoryType
    from open_agent_kit.features.codebase_intelligence.memory.store import (
        MemoryObservation,
    )

    # Get session from activity store
    session = activity_store.get_session(session_id)
    if not session:
        logger.warning(f"Session {session_id} not found for summary")
        return None, None

    # Get prompt batches for this session
    batches = activity_store.get_session_prompt_batches(session_id, limit=100)
    if not batches:
        logger.debug(f"No prompt batches for session {session_id}, skipping summary")
        return None, None

    # Check for existing session summary (handles resumed sessions)
    # Only re-summarize if there are new batches since last summary,
    # unless we're explicitly regenerating (regenerate_title implies force regeneration)
    existing_summary = activity_store.get_latest_session_summary(session_id)
    if existing_summary and not regenerate_title:
        summary_time = existing_summary.created_at
        new_batches = [b for b in batches if b.started_at and b.started_at > summary_time]
        if not new_batches:
            logger.debug(
                f"Session {session_id} already summarized at {summary_time}, "
                "no new batches since then"
            )
            return None, None
        # Note: We summarize ALL batches (not just new ones) so the replacement
        # summary has full session context. The deterministic ID ensures upsert.
        logger.info(
            f"Session {session_id} resumed: re-summarizing all {len(batches)} batches "
            f"({len(new_batches)} new since last summary)"
        )
    elif regenerate_title and existing_summary:
        logger.info(f"Force regenerating summary and title for session {session_id}")

    # Get session stats
    stats = activity_store.get_session_stats(session_id)

    # Check if session has enough substance to summarize
    tool_calls = stats.get("activity_count", 0)
    if tool_calls < 3:
        logger.debug(f"Session {session_id} too short ({tool_calls} tools), skipping summary")
        return None, None

    # Get summary template
    summary_template = prompt_config.get_template("session-summary")
    if not summary_template:
        logger.warning("No session-summary prompt template found")
        return None, None

    # Calculate duration
    duration_minutes = 0.0
    if session.started_at and session.ended_at:
        duration_minutes = (session.ended_at - session.started_at).total_seconds() / 60

    # Format prompt batches for context, filtering out continuation placeholders
    batch_lines = []
    for i, batch in enumerate(batches[:20], 1):  # Limit to 20 batches
        classification = batch.classification or "unknown"
        user_prompt = batch.user_prompt or "(no prompt captured)"

        # Skip continuation placeholders - they don't add meaningful context
        if _is_recovery_prompt(user_prompt):
            continue

        # Truncate long prompts
        if len(user_prompt) > 150:
            user_prompt = user_prompt[:147] + "..."
        batch_lines.append(f"{i}. [{classification}] {user_prompt}")

    # Include parent session context for continuation sessions
    parent_context = _get_parent_context_for_summary(session_id, activity_store)

    # Include plan content if this session has a plan
    plan_context = _get_plan_context_for_summary(batches)

    prompt_batches_text = "\n".join(batch_lines) if batch_lines else "(no user prompts captured)"
    if parent_context:
        prompt_batches_text += parent_context

    # Build prompt
    prompt = summary_template.prompt
    prompt = prompt.replace("{{session_duration}}", f"{duration_minutes:.1f}")
    prompt = prompt.replace("{{prompt_batch_count}}", str(len(batches)))
    prompt = prompt.replace("{{files_read_count}}", str(stats.get("reads", 0)))
    prompt = prompt.replace("{{files_modified_count}}", str(stats.get("edits", 0)))
    prompt = prompt.replace("{{files_created_count}}", str(stats.get("writes", 0)))
    prompt = prompt.replace("{{tool_calls}}", str(tool_calls))
    prompt = prompt.replace("{{prompt_batches}}", prompt_batches_text)
    prompt = prompt.replace("{{plan_context}}", plan_context)

    # Call LLM
    result = call_llm(prompt)

    if not result.get("success"):
        logger.warning(f"Session summary LLM call failed: {result.get('error')}")
        return None, None

    # Extract summary text (raw response, not JSON)
    raw_response = result.get("raw_response", "")
    summary: str = str(raw_response).strip() if raw_response else ""
    if not summary or len(summary) < 10:
        logger.debug("Session summary too short or empty")
        return None, None

    # Clean up common LLM artifacts
    if summary.startswith('"') and summary.endswith('"'):
        summary = summary[1:-1]

    # Store as session_summary memory using dual-write: SQLite + ChromaDB
    # Use deterministic ID so session reopens replace existing summary (upsert)
    obs_id = f"{SESSION_SUMMARY_OBS_ID_PREFIX}{session_id}"
    created_at = datetime.now()
    tags = ["session-summary", session.agent or "unknown"]

    # Step 1: Store to SQLite (source of truth)
    stored_obs = StoredObservation(
        id=obs_id,
        session_id=session_id,
        observation=summary,
        memory_type=MemoryType.SESSION_SUMMARY.value,
        context=f"session:{session_id}",
        tags=tags,
        importance=7,  # Session summaries are moderately important
        created_at=created_at,
        embedded=False,
    )

    try:
        activity_store.store_observation(stored_obs)
    except (OSError, ValueError, TypeError) as e:
        logger.error(f"Failed to store session summary to SQLite: {e}", exc_info=True)
        return None, None

    # Step 2: Embed and store in ChromaDB
    memory = MemoryObservation(
        id=obs_id,
        observation=summary,
        memory_type=MemoryType.SESSION_SUMMARY.value,
        context=f"session:{session_id}",
        tags=tags,
        created_at=created_at,
    )

    try:
        vector_store.add_memory(memory)
        activity_store.mark_observation_embedded(obs_id)
        logger.info(f"Stored session summary for {session_id}: {summary[:80]}...")
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as e:
        # ChromaDB failed but SQLite has the data - can retry later
        logger.warning(f"Failed to embed session summary in ChromaDB: {e}")

    # Step 3: Embed to session summaries collection for similarity search
    # This enables the user-driven session linking suggestion system
    from open_agent_kit.features.codebase_intelligence.activity.processor.session_index import (
        embed_session_summary,
    )

    embed_session_summary(
        vector_store=vector_store,
        session_id=session_id,
        title=session.title,
        summary=summary,
        agent=session.agent or "unknown",
        project_root=session.project_root or "",
        created_at_epoch=int(created_at.timestamp()),
    )

    # Generate or regenerate title from the summary (more accurate than prompt-based)
    # Since we just generated a summary, we have good context to create a descriptive title
    title: str | None = None

    if generate_title_from_summary:
        # Prefer title from summary - it's more accurate than prompt-based
        title = generate_title_from_summary(session_id, summary)

    if not title:
        # Fallback to prompt-based title generation if summary-based failed
        # or if generate_title_from_summary wasn't provided
        if regenerate_title or not session.title:
            title = generate_title(session_id)

    if title:
        action = "Regenerated" if session.title else "Generated"
        logger.info(f"{action} title for session {session_id}: {title}")

    return summary, title
