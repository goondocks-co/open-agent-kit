"""Session summary generation.

Creates high-level summaries of completed sessions using LLM.
"""

import logging
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.prompts import (
        PromptTemplateConfig,
    )
    from open_agent_kit.features.codebase_intelligence.activity.store import (
        ActivityStore,
    )
    from open_agent_kit.features.codebase_intelligence.memory.store import VectorStore

logger = logging.getLogger(__name__)


def process_session_summary(
    session_id: str,
    activity_store: "ActivityStore",
    vector_store: "VectorStore",
    prompt_config: "PromptTemplateConfig",
    call_llm: Callable[[str], dict[str, Any]],
    generate_title: Callable[[str], str | None],
) -> str | None:
    """Generate and store a session summary and title.

    Called at session end to create a high-level summary of what was accomplished.
    Stored as a session_summary memory for injection into future sessions.
    Also generates a short title for the session if one doesn't exist.

    Args:
        session_id: Session ID to summarize.
        activity_store: Activity store for fetching session data.
        vector_store: Vector store for storing summary.
        prompt_config: Prompt template configuration.
        call_llm: Function to call LLM.
        generate_title: Function to generate session title.

    Returns:
        Summary text if generated, None otherwise.
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
        return None

    # Get prompt batches for this session
    batches = activity_store.get_session_prompt_batches(session_id, limit=100)
    if not batches:
        logger.debug(f"No prompt batches for session {session_id}, skipping summary")
        return None

    # Check for existing session summary (handles resumed sessions)
    # Only summarize batches created after the last summary
    existing_summary = activity_store.get_latest_session_summary(session_id)
    if existing_summary:
        # Filter to only include batches newer than the existing summary
        summary_time = existing_summary.created_at
        new_batches = [b for b in batches if b.started_at and b.started_at > summary_time]
        if not new_batches:
            logger.debug(
                f"Session {session_id} already summarized at {summary_time}, "
                "no new batches since then"
            )
            return None
        logger.info(
            f"Session {session_id} resumed: summarizing {len(new_batches)} new batches "
            f"(of {len(batches)} total) since last summary"
        )
        batches = new_batches

    # Get session stats
    stats = activity_store.get_session_stats(session_id)

    # Check if session has enough substance to summarize
    tool_calls = stats.get("total_activities", 0)
    if tool_calls < 3:
        logger.debug(f"Session {session_id} too short ({tool_calls} tools), skipping summary")
        return None

    # Get summary template
    summary_template = prompt_config.get_template("session-summary")
    if not summary_template:
        logger.warning("No session-summary prompt template found")
        return None

    # Calculate duration
    duration_minutes = 0.0
    if session.started_at and session.ended_at:
        duration_minutes = (session.ended_at - session.started_at).total_seconds() / 60

    # Format prompt batches for context
    batch_lines = []
    for i, batch in enumerate(batches[:20], 1):  # Limit to 20 batches
        classification = batch.classification or "unknown"
        user_prompt = batch.user_prompt or "(no prompt captured)"
        # Truncate long prompts
        if len(user_prompt) > 150:
            user_prompt = user_prompt[:147] + "..."
        batch_lines.append(f"{i}. [{classification}] {user_prompt}")

    prompt_batches_text = "\n".join(batch_lines) if batch_lines else "(no batches)"

    # Build prompt
    prompt = summary_template.prompt
    prompt = prompt.replace("{{session_duration}}", f"{duration_minutes:.1f}")
    prompt = prompt.replace("{{prompt_batch_count}}", str(len(batches)))
    prompt = prompt.replace("{{files_read_count}}", str(len(stats.get("files_read", []))))
    prompt = prompt.replace("{{files_modified_count}}", str(len(stats.get("files_modified", []))))
    prompt = prompt.replace("{{files_created_count}}", str(len(stats.get("files_created", []))))
    prompt = prompt.replace("{{tool_calls}}", str(tool_calls))
    prompt = prompt.replace("{{prompt_batches}}", prompt_batches_text)

    # Call LLM
    result = call_llm(prompt)

    if not result.get("success"):
        logger.warning(f"Session summary LLM call failed: {result.get('error')}")
        return None

    # Extract summary text (raw response, not JSON)
    raw_response = result.get("raw_response", "")
    summary: str = str(raw_response).strip() if raw_response else ""
    if not summary or len(summary) < 10:
        logger.debug("Session summary too short or empty")
        return None

    # Clean up common LLM artifacts
    if summary.startswith('"') and summary.endswith('"'):
        summary = summary[1:-1]

    # Store as session_summary memory using dual-write: SQLite + ChromaDB
    obs_id = str(uuid4())
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
        return None

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

    # Generate title if session doesn't have one yet
    if session and not session.title:
        generate_title(session_id)

    return summary
