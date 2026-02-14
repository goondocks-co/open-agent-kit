"""Automatic resolution of superseded observations.

When a new observation is stored, searches for semantically similar active
observations on the same topic/file and marks them as superseded.
This keeps the observation graph clean without manual agent intervention.
"""

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from open_agent_kit.features.codebase_intelligence.constants import (
    AUTO_RESOLVE_SEARCH_LIMIT,
    AUTO_RESOLVE_SIMILARITY_THRESHOLD,
    AUTO_RESOLVE_SIMILARITY_THRESHOLD_NO_CONTEXT,
    AUTO_RESOLVE_SKIP_TYPES,
    OBSERVATION_STATUS_ACTIVE,
    OBSERVATION_STATUS_SUPERSEDED,
)

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.store import (
        ActivityStore,
    )
    from open_agent_kit.features.codebase_intelligence.config import AutoResolveConfig
    from open_agent_kit.features.codebase_intelligence.memory.store import VectorStore

logger = logging.getLogger(__name__)


def auto_resolve_superseded(
    new_obs_id: str,
    obs_text: str,
    memory_type: str,
    context: str | None,
    session_id: str,
    vector_store: "VectorStore",
    activity_store: "ActivityStore",
    auto_resolve_config: "AutoResolveConfig | None" = None,
) -> list[str]:
    """Search for similar active observations and supersede them.

    Called after a new observation is stored. Finds older observations that
    are semantically equivalent and marks them as superseded by the new one.

    Uses a higher similarity threshold when observations lack shared context
    (file path) to avoid false positives.

    Args:
        new_obs_id: ID of the newly stored observation.
        obs_text: Text of the new observation.
        memory_type: Type of the new observation (gotcha, bug_fix, etc.).
        context: File path or context string of the new observation.
        session_id: Session that created the new observation.
        vector_store: ChromaDB vector store for similarity search.
        activity_store: SQLite activity store for status updates.
        auto_resolve_config: Optional config overriding default thresholds.

    Returns:
        List of observation IDs that were superseded.
    """
    if auto_resolve_config is not None and not auto_resolve_config.enabled:
        return []

    if memory_type in AUTO_RESOLVE_SKIP_TYPES:
        return []

    # Read thresholds from config or fall back to constants
    threshold_same_ctx = (
        auto_resolve_config.similarity_threshold
        if auto_resolve_config
        else AUTO_RESOLVE_SIMILARITY_THRESHOLD
    )
    threshold_no_ctx = (
        auto_resolve_config.similarity_threshold_no_context
        if auto_resolve_config
        else AUTO_RESOLVE_SIMILARITY_THRESHOLD_NO_CONTEXT
    )
    search_limit = (
        auto_resolve_config.search_limit if auto_resolve_config else AUTO_RESOLVE_SEARCH_LIMIT
    )

    try:
        results = vector_store.search_memory(
            query=obs_text,
            limit=search_limit,
            memory_types=[memory_type],
            metadata_filters={"status": OBSERVATION_STATUS_ACTIVE},
        )
    except (OSError, ValueError, RuntimeError, AttributeError) as e:
        logger.debug(f"Auto-resolve search failed: {e}")
        return []

    superseded_ids: list[str] = []
    resolved_at = datetime.now(UTC).isoformat()

    for result in results:
        result_id = result.get("id", "")
        if result_id == new_obs_id:
            continue

        similarity = result.get("relevance", 0.0)

        # Choose threshold based on context overlap
        result_context = result.get("context", "")
        if context and result_context and context == result_context:
            threshold = threshold_same_ctx
        else:
            threshold = threshold_no_ctx

        if similarity < threshold:
            continue

        # Supersede the old observation in both stores
        try:
            activity_store.update_observation_status(
                observation_id=result_id,
                status=OBSERVATION_STATUS_SUPERSEDED,
                resolved_by_session_id=session_id,
                resolved_at=resolved_at,
                superseded_by=new_obs_id,
            )
            vector_store.update_memory_status(result_id, OBSERVATION_STATUS_SUPERSEDED)
            superseded_ids.append(result_id)
            logger.info(
                f"Auto-superseded observation {result_id[:12]}... "
                f"(similarity={similarity:.3f}) by {new_obs_id[:12]}..."
            )
        except (OSError, ValueError, TypeError, AttributeError) as e:
            logger.warning(f"Failed to auto-supersede {result_id}: {e}")

    return superseded_ids
