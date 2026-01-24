"""Observation storage logic.

Dual-write pattern: SQLite (source of truth) + ChromaDB (search index).
"""

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.store import (
        ActivityStore,
    )
    from open_agent_kit.features.codebase_intelligence.memory.store import VectorStore

logger = logging.getLogger(__name__)


def store_observation(
    session_id: str,
    observation: dict[str, Any],
    activity_store: "ActivityStore",
    vector_store: "VectorStore",
    classification: str | None = None,
    prompt_batch_id: int | None = None,
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

    # Build tags
    tags = ["auto-extracted", f"importance:{importance_str}"]
    if classification:
        tags.append(f"session:{classification}")

    obs_id = str(uuid4())
    created_at = datetime.now()

    # Step 1: Store to SQLite (source of truth) - MUST succeed
    stored_obs = StoredObservation(
        id=obs_id,
        session_id=session_id,
        prompt_batch_id=prompt_batch_id,
        observation=obs_text,
        memory_type=memory_type.value,
        context=observation.get("context"),
        tags=tags,
        importance=importance_int,
        created_at=created_at,
        embedded=False,  # Not yet in ChromaDB
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
        context=observation.get("context"),
        tags=tags,
        created_at=created_at,
    )

    try:
        vector_store.add_memory(memory)
        # Step 3: Mark as embedded in SQLite
        activity_store.mark_observation_embedded(obs_id)
        logger.debug(f"Stored observation to ChromaDB [{obs_type}]: {obs_text[:50]}...")
        return obs_id
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as e:
        # ChromaDB failed, but SQLite has the data - it can be retried later
        logger.warning(f"Failed to embed observation in ChromaDB (will retry later): {e}")
        # Return the ID anyway - SQLite storage succeeded
        return obs_id
