"""Session title generation.

Generates short, descriptive titles for sessions using LLM.
"""

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.prompts import (
        PromptTemplateConfig,
    )
    from open_agent_kit.features.codebase_intelligence.activity.store import (
        ActivityStore,
    )

logger = logging.getLogger(__name__)


def generate_session_title(
    session_id: str,
    activity_store: "ActivityStore",
    prompt_config: "PromptTemplateConfig",
    call_llm: Callable[[str], dict[str, Any]],
) -> str | None:
    """Generate a short title for a session based on its prompts.

    Args:
        session_id: Session ID to generate title for.
        activity_store: Activity store for fetching batches.
        prompt_config: Prompt template configuration.
        call_llm: Function to call LLM.

    Returns:
        Title text if generated, None otherwise.
    """
    # Get prompt batches for this session
    batches = activity_store.get_session_prompt_batches(session_id, limit=10)
    if not batches:
        logger.debug(f"No prompt batches for session {session_id}, skipping title")
        return None

    # Get title template
    title_template = prompt_config.get_template("session-title")
    if not title_template:
        logger.debug("No session-title prompt template found, skipping title")
        return None

    # Format prompt batches for context
    batch_lines = []
    for i, batch in enumerate(batches[:10], 1):
        user_prompt = batch.user_prompt or "(no prompt captured)"
        # Truncate long prompts
        if len(user_prompt) > 200:
            user_prompt = user_prompt[:197] + "..."
        batch_lines.append(f"{i}. {user_prompt}")

    prompt_batches_text = "\n".join(batch_lines) if batch_lines else "(no batches)"

    # Build prompt
    prompt = title_template.prompt
    prompt = prompt.replace("{{prompt_batches}}", prompt_batches_text)

    # Call LLM
    result = call_llm(prompt)

    if not result.get("success"):
        logger.warning(f"Session title LLM call failed: {result.get('error')}")
        return None

    # Extract title text
    raw_response = result.get("raw_response", "")
    title: str = str(raw_response).strip() if raw_response else ""
    if not title or len(title) < 3:
        logger.debug("Session title too short or empty")
        return None

    # Clean up common LLM artifacts (quotes around the title)
    if title.startswith('"') and title.endswith('"'):
        title = title[1:-1]
    # Remove trailing punctuation
    title = title.rstrip(".")

    # Truncate if too long (should be 5-10 words)
    if len(title) > 80:
        title = title[:77] + "..."

    # Store title in session
    try:
        activity_store.update_session_title(session_id, title)
        logger.info(f"Generated title for session {session_id}: {title}")
        return title
    except (OSError, ValueError, TypeError) as e:
        logger.error(f"Failed to store session title: {e}", exc_info=True)
        return None


def generate_pending_titles(
    activity_store: "ActivityStore",
    prompt_config: "PromptTemplateConfig",
    call_llm: Callable[[str], dict[str, Any]],
    limit: int = 5,
) -> int:
    """Generate titles for sessions that don't have them.

    Called periodically by background processing to ensure all sessions
    get titles, even if they were created before the title feature was added.

    Args:
        activity_store: Activity store for fetching sessions.
        prompt_config: Prompt template configuration.
        call_llm: Function to call LLM.
        limit: Maximum sessions to process per call.

    Returns:
        Number of titles generated.
    """
    sessions = activity_store.get_sessions_needing_titles(limit=limit)

    if not sessions:
        return 0

    generated = 0
    for session in sessions:
        try:
            title = generate_session_title(
                session.id,
                activity_store,
                prompt_config,
                call_llm,
            )
            if title:
                generated += 1
        except (OSError, ValueError, TypeError, RuntimeError) as e:
            logger.warning(f"Failed to generate title for session {session.id[:8]}: {e}")

    return generated
