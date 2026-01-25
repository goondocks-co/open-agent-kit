"""Delete operations for activity store.

Functions for cascade delete operations on sessions, batches, and activities.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.store.core import ActivityStore

logger = logging.getLogger(__name__)


def get_session_observation_ids(store: ActivityStore, session_id: str) -> list[str]:
    """Get all observation IDs for a session (for ChromaDB cleanup).

    Args:
        store: The ActivityStore instance.
        session_id: Session to query.

    Returns:
        List of observation IDs linked to this session.
    """
    conn = store._get_connection()
    cursor = conn.execute(
        "SELECT id FROM memory_observations WHERE session_id = ?",
        (session_id,),
    )
    return [row[0] for row in cursor.fetchall()]


def get_batch_observation_ids(store: ActivityStore, batch_id: int) -> list[str]:
    """Get all observation IDs for a prompt batch (for ChromaDB cleanup).

    Args:
        store: The ActivityStore instance.
        batch_id: Prompt batch ID to query.

    Returns:
        List of observation IDs linked to this batch.
    """
    conn = store._get_connection()
    cursor = conn.execute(
        "SELECT id FROM memory_observations WHERE prompt_batch_id = ?",
        (batch_id,),
    )
    return [row[0] for row in cursor.fetchall()]


def delete_observation(store: ActivityStore, observation_id: str) -> bool:
    """Delete an observation from SQLite.

    Args:
        store: The ActivityStore instance.
        observation_id: The observation ID to delete.

    Returns:
        True if deleted, False if not found.
    """
    with store._transaction() as conn:
        cursor = conn.execute(
            "DELETE FROM memory_observations WHERE id = ?",
            (observation_id,),
        )
        deleted = cursor.rowcount > 0

    if deleted:
        logger.info(f"Deleted observation {observation_id}")
    return deleted


def delete_activity(store: ActivityStore, activity_id: int) -> str | None:
    """Delete a single activity.

    Args:
        store: The ActivityStore instance.
        activity_id: The activity ID to delete.

    Returns:
        The linked observation_id if any (for ChromaDB cleanup), None otherwise.
    """
    conn = store._get_connection()

    # Get the observation_id before deleting (if any)
    cursor = conn.execute(
        "SELECT observation_id FROM activities WHERE id = ?",
        (activity_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None

    observation_id: str | None = row[0]

    with store._transaction() as conn:
        conn.execute("DELETE FROM activities WHERE id = ?", (activity_id,))

    logger.info(f"Deleted activity {activity_id}")
    return observation_id


def delete_prompt_batch(store: ActivityStore, batch_id: int) -> dict[str, int]:
    """Delete a prompt batch and all related data.

    Cascade deletes:
    - Activities linked to this batch
    - Memory observations linked to this batch

    Args:
        store: The ActivityStore instance.
        batch_id: The prompt batch ID to delete.

    Returns:
        Dictionary with counts: activities_deleted, observations_deleted
    """
    result = {"activities_deleted": 0, "observations_deleted": 0}

    with store._transaction() as conn:
        # Delete activities for this batch
        cursor = conn.execute(
            "DELETE FROM activities WHERE prompt_batch_id = ?",
            (batch_id,),
        )
        result["activities_deleted"] = cursor.rowcount

        # Delete observations for this batch
        cursor = conn.execute(
            "DELETE FROM memory_observations WHERE prompt_batch_id = ?",
            (batch_id,),
        )
        result["observations_deleted"] = cursor.rowcount

        # Delete the batch itself
        conn.execute("DELETE FROM prompt_batches WHERE id = ?", (batch_id,))

    logger.info(
        f"Deleted prompt batch {batch_id}: "
        f"{result['activities_deleted']} activities, "
        f"{result['observations_deleted']} observations"
    )
    return result


def delete_session(store: ActivityStore, session_id: str) -> dict[str, int]:
    """Delete a session and all related data.

    Cascade deletes:
    - All prompt batches for this session
    - All activities for this session
    - All memory observations for this session

    Args:
        store: The ActivityStore instance.
        session_id: The session ID to delete.

    Returns:
        Dictionary with counts: batches_deleted, activities_deleted, observations_deleted
    """
    result = {"batches_deleted": 0, "activities_deleted": 0, "observations_deleted": 0}

    with store._transaction() as conn:
        # Delete activities for this session
        cursor = conn.execute(
            "DELETE FROM activities WHERE session_id = ?",
            (session_id,),
        )
        result["activities_deleted"] = cursor.rowcount

        # Delete observations for this session
        cursor = conn.execute(
            "DELETE FROM memory_observations WHERE session_id = ?",
            (session_id,),
        )
        result["observations_deleted"] = cursor.rowcount

        # Delete prompt batches for this session
        cursor = conn.execute(
            "DELETE FROM prompt_batches WHERE session_id = ?",
            (session_id,),
        )
        result["batches_deleted"] = cursor.rowcount

        # Delete the session itself
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

    logger.info(
        f"Deleted session {session_id}: "
        f"{result['batches_deleted']} batches, "
        f"{result['activities_deleted']} activities, "
        f"{result['observations_deleted']} observations"
    )
    return result
