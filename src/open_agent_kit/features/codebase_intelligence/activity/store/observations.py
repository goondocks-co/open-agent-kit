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
             source_machine_id, content_hash,
             status, resolved_by_session_id, resolved_at, superseded_by, session_origin_type)
            VALUES (:id, :session_id, :prompt_batch_id, :observation, :memory_type,
                    :context, :tags, :importance, :file_path, :created_at,
                    :created_at_epoch, :embedded, :source_machine_id, :content_hash,
                    :status, :resolved_by_session_id, :resolved_at, :superseded_by, :session_origin_type)
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


def count_observations_for_batches(
    store: ActivityStore,
    batch_ids: list[int],
    machine_id: str,
) -> int:
    """Count observations linked to specific batches from a given machine.

    Args:
        store: The ActivityStore instance.
        batch_ids: Prompt batch IDs to count observations for.
        machine_id: Only count observations from this machine.

    Returns:
        Observation count.
    """
    if not batch_ids:
        return 0

    conn = store._get_connection()
    placeholders = ",".join("?" * len(batch_ids))
    cursor = conn.execute(
        f"""
        SELECT COUNT(*) FROM memory_observations
        WHERE prompt_batch_id IN ({placeholders})
          AND source_machine_id = ?
        """,
        (*batch_ids, machine_id),
    )
    result = cursor.fetchone()
    return int(result[0]) if result else 0


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


def get_embedded_observation_ids(store: ActivityStore) -> list[str]:
    """Get all observation IDs that are embedded in ChromaDB.

    Used by orphan cleanup to diff against ChromaDB IDs.

    Args:
        store: The ActivityStore instance.

    Returns:
        List of embedded observation IDs.
    """
    conn = store._get_connection()
    cursor = conn.execute("SELECT id FROM memory_observations WHERE embedded = TRUE")
    return [row[0] for row in cursor.fetchall()]


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


def update_observation_status(
    store: ActivityStore,
    observation_id: str,
    status: str,
    resolved_by_session_id: str | None = None,
    resolved_at: str | None = None,
    superseded_by: str | None = None,
) -> bool:
    """Update the lifecycle status of an observation.

    Args:
        store: The ActivityStore instance.
        observation_id: The observation ID.
        status: New status (active, resolved, superseded).
        resolved_by_session_id: Session that resolved this observation.
        resolved_at: ISO timestamp of resolution.
        superseded_by: Observation ID that supersedes this one.

    Returns:
        True if the observation was found and updated.
    """
    with store._transaction() as conn:
        cursor = conn.execute(
            """
            UPDATE memory_observations
            SET status = ?,
                resolved_by_session_id = COALESCE(?, resolved_by_session_id),
                resolved_at = COALESCE(?, resolved_at),
                superseded_by = COALESCE(?, superseded_by)
            WHERE id = ?
            """,
            (status, resolved_by_session_id, resolved_at, superseded_by, observation_id),
        )
        updated = cursor.rowcount > 0

    if updated:
        logger.debug(f"Updated observation {observation_id} status to {status}")
    else:
        logger.warning(f"Observation {observation_id} not found for status update")
    return updated


def get_observations_by_session(
    store: ActivityStore,
    session_id: str,
    status: str | None = None,
) -> list[StoredObservation]:
    """Get all observations for a session, optionally filtered by status.

    Args:
        store: The ActivityStore instance.
        session_id: The session ID.
        status: Filter by status (active, resolved, superseded). None for all.

    Returns:
        List of observations for the session.
    """
    conn = store._get_connection()
    if status:
        cursor = conn.execute(
            "SELECT * FROM memory_observations WHERE session_id = ? AND status = ? "
            "ORDER BY created_at_epoch",
            (session_id, status),
        )
    else:
        cursor = conn.execute(
            "SELECT * FROM memory_observations WHERE session_id = ? " "ORDER BY created_at_epoch",
            (session_id,),
        )
    return [StoredObservation.from_row(row) for row in cursor.fetchall()]


def count_observations_by_status(store: ActivityStore) -> dict[str, int]:
    """Count observations grouped by lifecycle status.

    Args:
        store: The ActivityStore instance.

    Returns:
        Dictionary mapping status to count, e.g. {"active": 42, "resolved": 10}.
    """
    conn = store._get_connection()
    cursor = conn.execute(
        "SELECT COALESCE(status, 'active') as status, COUNT(*) as count "
        "FROM memory_observations GROUP BY COALESCE(status, 'active')"
    )
    return {row[0]: row[1] for row in cursor.fetchall()}


def get_active_observations(
    store: ActivityStore,
    limit: int = 100,
) -> list[StoredObservation]:
    """Get active observations ordered oldest-first.

    Used by staleness detection to find observations that may have been
    addressed in later sessions.

    Args:
        store: The ActivityStore instance.
        limit: Maximum observations to return.

    Returns:
        List of active StoredObservation entries, oldest first.
    """
    conn = store._get_connection()
    cursor = conn.execute(
        """
        SELECT * FROM memory_observations
        WHERE COALESCE(status, 'active') = 'active'
        ORDER BY created_at_epoch ASC
        LIMIT ?
        """,
        (limit,),
    )
    return [StoredObservation.from_row(row) for row in cursor.fetchall()]


def find_later_edit_session(
    store: ActivityStore,
    file_path: str,
    after_epoch: float,
    exclude_session_id: str,
) -> str | None:
    """Check if a file was edited in a later session.

    Used by staleness heuristics to detect when an observation's context
    file has been modified by subsequent work.

    Args:
        store: The ActivityStore instance.
        file_path: File path to check for later edits.
        after_epoch: Only consider edits after this Unix timestamp.
        exclude_session_id: Session to exclude (the observation's own session).

    Returns:
        Session ID that edited the file, or None if no later edits found.
    """
    conn = store._get_connection()
    cursor = conn.execute(
        """
        SELECT DISTINCT a.session_id
        FROM activities a
        WHERE a.file_path = ?
          AND a.timestamp_epoch > ?
          AND a.session_id != ?
          AND a.tool_name IN ('Edit', 'MultiEdit', 'Write')
        LIMIT 1
        """,
        (file_path, after_epoch, exclude_session_id),
    )
    row = cursor.fetchone()
    return row[0] if row else None
