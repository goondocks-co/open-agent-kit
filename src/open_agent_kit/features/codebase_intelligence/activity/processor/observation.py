"""Observation storage logic.

Dual-write pattern: SQLite (source of truth) + ChromaDB (search index).
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
    compute_observation_hash,
)
from open_agent_kit.features.codebase_intelligence.constants import (
    ORIGIN_TYPE_AUTO_EXTRACTED,
)
from open_agent_kit.utils.file_utils import get_relative_path

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.store import (
        ActivityStore,
    )
    from open_agent_kit.features.codebase_intelligence.config import AutoResolveConfig
    from open_agent_kit.features.codebase_intelligence.memory.store import VectorStore

logger = logging.getLogger(__name__)


def _normalize_context_path(
    context: str | None,
    project_root: str | None,
) -> str | None:
    """Normalize context paths to project-relative when possible."""
    if not context:
        return context
    if not project_root:
        return context

    root_path = Path(project_root)
    context_path = Path(context)

    try:
        if not context_path.is_absolute():
            context_path = root_path / context_path
        context_path = context_path.resolve()
        root_path = root_path.resolve()
        if context_path == root_path or root_path in context_path.parents:
            return get_relative_path(context_path, root_path).as_posix()
    except (OSError, RuntimeError, ValueError):
        return context

    return context


def store_observation(
    session_id: str,
    observation: dict[str, Any],
    activity_store: "ActivityStore",
    vector_store: "VectorStore",
    classification: str | None = None,
    prompt_batch_id: int | None = None,
    project_root: str | None = None,
    session_origin_type: str | None = None,
    auto_resolve_config: "AutoResolveConfig | None" = None,
) -> str | None:
    """Store an observation using dual-write: SQLite (source of truth) + ChromaDB (search index).

    SQLite is the authoritative storage. ChromaDB can be rebuilt from SQLite if needed.

    Args:
        session_id: Source session ID.
        observation: Observation data from LLM.
        activity_store: SQLite activity store.
        vector_store: ChromaDB vector store.
        classification: Session classification for tagging.
        prompt_batch_id: Optional prompt batch ID for linking.

    Returns:
        Observation ID if stored, None otherwise.
    """
    from open_agent_kit.features.codebase_intelligence.activity.store import (
        StoredObservation,
    )
    from open_agent_kit.features.codebase_intelligence.daemon.models import MemoryType
    from open_agent_kit.features.codebase_intelligence.memory.store import (
        MemoryObservation,
    )

    obs_text = observation.get("observation", "")
    if not obs_text:
        return None

    # Content-hash dedup guard: skip if identical observation already exists (any status)
    obs_type_raw = observation.get("type", "discovery")
    context_raw = observation.get("context")
    content_hash = compute_observation_hash(obs_text, obs_type_raw, context_raw)
    if activity_store.has_observation_with_hash(content_hash):
        logger.debug(
            f"Skipping duplicate observation (hash={content_hash[:8]}): {obs_text[:50]}..."
        )
        return None

    # Map observation type
    type_map = {
        "gotcha": MemoryType.GOTCHA,
        "bug_fix": MemoryType.BUG_FIX,
        "decision": MemoryType.DECISION,
        "discovery": MemoryType.DISCOVERY,
    }
    obs_type = observation.get("type", "discovery")
    memory_type = type_map.get(obs_type, MemoryType.DISCOVERY)

    # Map importance string to integer (1-10 scale)
    importance_str = observation.get("importance", "medium")
    importance_map = {"low": 3, "medium": 5, "high": 8, "critical": 10}
    importance_int = importance_map.get(importance_str, 5)

    # Cap importance for planning/investigation sessions
    from open_agent_kit.features.codebase_intelligence.constants import (
        SESSION_ORIGIN_INVESTIGATION,
        SESSION_ORIGIN_PLANNING,
        SESSION_ORIGIN_PLANNING_IMPORTANCE_CAP,
    )

    if session_origin_type in (SESSION_ORIGIN_PLANNING, SESSION_ORIGIN_INVESTIGATION):
        importance_int = min(importance_int, SESSION_ORIGIN_PLANNING_IMPORTANCE_CAP)

    # Build tags
    tags = ["auto-extracted", f"importance:{importance_str}"]
    if classification:
        tags.append(f"session:{classification}")
    if session_origin_type:
        tags.append(f"origin:{session_origin_type}")

    context = _normalize_context_path(observation.get("context"), project_root)
    obs_id = str(uuid4())
    created_at = datetime.now()

    # Step 1: Store to SQLite (source of truth) - MUST succeed
    stored_obs = StoredObservation(
        id=obs_id,
        session_id=session_id,
        prompt_batch_id=prompt_batch_id,
        observation=obs_text,
        memory_type=memory_type.value,
        context=context,
        tags=tags,
        importance=importance_int,
        created_at=created_at,
        embedded=False,  # Not yet in ChromaDB
        session_origin_type=session_origin_type,
        origin_type=ORIGIN_TYPE_AUTO_EXTRACTED,
    )

    try:
        activity_store.store_observation(stored_obs)
        logger.debug(f"Stored observation to SQLite [{obs_type}]: {obs_text[:50]}...")
    except (OSError, ValueError, TypeError) as e:
        logger.error(f"Failed to store observation to SQLite: {e}", exc_info=True)
        return None

    # Step 2: Embed and store in ChromaDB (search index)
    memory = MemoryObservation(
        id=obs_id,
        observation=obs_text,
        memory_type=memory_type.value,
        context=context,
        tags=tags,
        created_at=created_at,
        importance=importance_int,
        session_origin_type=session_origin_type,
    )

    try:
        vector_store.add_memory(memory)
        # Step 3: Mark as embedded in SQLite
        activity_store.mark_observation_embedded(obs_id)
        logger.debug(f"Stored observation to ChromaDB [{obs_type}]: {obs_text[:50]}...")
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as e:
        # ChromaDB failed, but SQLite has the data - it can be retried later
        logger.warning(f"Failed to embed observation in ChromaDB (will retry later): {e}")
        # Return the ID anyway - SQLite storage succeeded
        return obs_id

    # Step 4: Auto-resolve older observations superseded by this one
    from open_agent_kit.features.codebase_intelligence.activity.processor.auto_resolve import (
        auto_resolve_superseded,
    )

    superseded = auto_resolve_superseded(
        new_obs_id=obs_id,
        obs_text=obs_text,
        memory_type=memory_type.value,
        context=context,
        session_id=session_id,
        vector_store=vector_store,
        activity_store=activity_store,
        auto_resolve_config=auto_resolve_config,
    )
    if superseded:
        logger.info(
            f"Observation {obs_id[:12]}... superseded {len(superseded)} older observation(s)"
        )

    return obs_id


def truncate_observations(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Truncate observations to the per-batch maximum, keeping highest importance first.

    The extraction prompts ask for "at most 5" (soft limit); this function
    enforces a hard cap defined by MAX_OBSERVATIONS_PER_BATCH.

    Args:
        observations: Raw observation dicts from LLM response.

    Returns:
        Truncated list sorted by importance (high > medium > low).
    """
    from open_agent_kit.features.codebase_intelligence.constants import (
        MAX_OBSERVATIONS_PER_BATCH,
    )

    if len(observations) <= MAX_OBSERVATIONS_PER_BATCH:
        return observations

    importance_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    sorted_obs = sorted(
        observations,
        key=lambda o: importance_order.get(o.get("importance", "medium"), 2),
    )

    logger.info(
        f"Truncating {len(observations)} observations to {MAX_OBSERVATIONS_PER_BATCH} "
        f"(dropped {len(observations) - MAX_OBSERVATIONS_PER_BATCH} lowest-importance)"
    )
    return sorted_obs[:MAX_OBSERVATIONS_PER_BATCH]
