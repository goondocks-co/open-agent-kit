"""Observation operations for activity store.

Functions for storing and managing memory observations in SQLite.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from open_agent_kit.features.codebase_intelligence.activity.store.models import StoredObservation
from open_agent_kit.features.codebase_intelligence.daemon.models import MemoryType

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.store.core import ActivityStore

logger = logging.getLogger(__name__)


def store_observation(store: ActivityStore, observation: StoredObservation) -> str:
    """Store a memory observation in SQLite.

    This is the source of truth. ChromaDB embedding happens separately.

    Args:
        store: The ActivityStore instance.
        observation: The observation to store.

    Returns:
        The observation ID.
    """
    # Set source_machine_id if not already set (imported observations preserve original)
    if observation.source_machine_id is None:
        observation.source_machine_id = store.machine_id

    with store._transaction() as conn:
        row = observation.to_row()
        conn.execute(
            """
            INSERT OR REPLACE INTO memory_observations
            (id, session_id, prompt_batch_id, observation, memory_type,
             context, tags, importance, file_path, created_at, created_at_epoch, embedded,
             source_machine_id, content_hash)
            VALUES (:id, :session_id, :prompt_batch_id, :observation, :memory_type,
                    :context, :tags, :importance, :file_path, :created_at,
                    :created_at_epoch, :embedded, :source_machine_id, :content_hash)
            """,
            row,
        )

    logger.debug(f"Stored observation {observation.id} for session {observation.session_id}")
    return observation.id


def get_observation(store: ActivityStore, observation_id: str) -> StoredObservation | None:
    """Get an observation by ID.

    Args:
        store: The ActivityStore instance.
        observation_id: The observation ID.

    Returns:
        The observation or None if not found.
    """
    conn = store._get_connection()
    cursor = conn.execute(
        "SELECT * FROM memory_observations WHERE id = ?",
        (observation_id,),
    )
    row = cursor.fetchone()
    return StoredObservation.from_row(row) if row else None


def get_latest_session_summary(store: ActivityStore, session_id: str) -> StoredObservation | None:
    """Get the most recent session_summary observation for a session.

    Used to check if a session has already been summarized, and when,
    so we can avoid duplicate summaries on session resume.

    Args:
        store: The ActivityStore instance.
        session_id: The session ID.

    Returns:
        The most recent session_summary observation or None if none exists.
    """
    conn = store._get_connection()
    cursor = conn.execute(
        """
        SELECT * FROM memory_observations
        WHERE session_id = ? AND memory_type = 'session_summary'
        ORDER BY created_at_epoch DESC
        LIMIT 1
        """,
        (session_id,),
    )
    row = cursor.fetchone()
    return StoredObservation.from_row(row) if row else None


def get_unembedded_observations(store: ActivityStore, limit: int = 100) -> list[StoredObservation]:
    """Get observations that haven't been added to ChromaDB.

    Used for rebuilding the ChromaDB index from SQLite.

    Args:
        store: The ActivityStore instance.
        limit: Maximum observations to return.

    Returns:
        List of unembedded observations.
    """
    conn = store._get_connection()
    cursor = conn.execute(
        """
        SELECT * FROM memory_observations
        WHERE embedded = FALSE
        ORDER BY created_at_epoch
        LIMIT ?
        """,
        (limit,),
    )
    return [StoredObservation.from_row(row) for row in cursor.fetchall()]


def mark_observation_embedded(store: ActivityStore, observation_id: str) -> None:
    """Mark an observation as embedded in ChromaDB.

    Args:
        store: The ActivityStore instance.
        observation_id: The observation ID.
    """
    with store._transaction() as conn:
        conn.execute(
            "UPDATE memory_observations SET embedded = TRUE WHERE id = ?",
            (observation_id,),
        )


def mark_observations_embedded(store: ActivityStore, observation_ids: list[str]) -> None:
    """Mark multiple observations as embedded in ChromaDB.

    Args:
        store: The ActivityStore instance.
        observation_ids: List of observation IDs.
    """
    if not observation_ids:
        return

    with store._transaction() as conn:
        placeholders = ",".join("?" * len(observation_ids))
        conn.execute(
            f"UPDATE memory_observations SET embedded = TRUE WHERE id IN ({placeholders})",
            observation_ids,
        )


def mark_all_observations_unembedded(store: ActivityStore) -> int:
    """Mark all observations as not embedded (for full ChromaDB rebuild).

    Args:
        store: The ActivityStore instance.

    Returns:
        Number of observations marked.
    """
    with store._transaction() as conn:
        cursor = conn.execute(
            "UPDATE memory_observations SET embedded = FALSE WHERE embedded = TRUE"
        )
        count = cursor.rowcount

    logger.info(f"Marked {count} observations as unembedded for rebuild")
    return count


def count_observations(store: ActivityStore) -> int:
    """Count total observations in SQLite.

    Args:
        store: The ActivityStore instance.

    Returns:
        Total observation count.
    """
    conn = store._get_connection()
    cursor = conn.execute("SELECT COUNT(*) FROM memory_observations")
    result = cursor.fetchone()
    return int(result[0]) if result else 0


def count_embedded_observations(store: ActivityStore) -> int:
    """Count observations that are in ChromaDB.

    Args:
        store: The ActivityStore instance.

    Returns:
        Embedded observation count.
    """
    conn = store._get_connection()
    cursor = conn.execute("SELECT COUNT(*) FROM memory_observations WHERE embedded = TRUE")
    result = cursor.fetchone()
    return int(result[0]) if result else 0


def count_unembedded_observations(store: ActivityStore) -> int:
    """Count observations not yet in ChromaDB.

    Args:
        store: The ActivityStore instance.

    Returns:
        Unembedded observation count.
    """
    conn = store._get_connection()
    cursor = conn.execute("SELECT COUNT(*) FROM memory_observations WHERE embedded = FALSE")
    result = cursor.fetchone()
    return int(result[0]) if result else 0


def list_session_summaries(store: ActivityStore, limit: int = 10) -> list[StoredObservation]:
    """List recent session_summary observations from SQLite.

    Args:
        store: The ActivityStore instance.
        limit: Maximum number of session summaries to return.

    Returns:
        List of StoredObservation entries, most recent first.
    """
    conn = store._get_connection()
    cursor = conn.execute(
        """
        SELECT * FROM memory_observations
        WHERE memory_type = ?
        ORDER BY created_at_epoch DESC
        LIMIT ?
        """,
        (MemoryType.SESSION_SUMMARY.value, limit),
    )
    return [StoredObservation.from_row(row) for row in cursor.fetchall()]


def count_observations_by_type(store: ActivityStore, memory_type: str) -> int:
    """Count observations by memory_type in SQLite.

    Args:
        store: The ActivityStore instance.
        memory_type: Memory type value to count.

    Returns:
        Count of observations matching the type.
    """
    conn = store._get_connection()
    cursor = conn.execute(
        "SELECT COUNT(*) FROM memory_observations WHERE memory_type = ?",
        (memory_type,),
    )
    result = cursor.fetchone()
    return int(result[0]) if result else 0
