"""Delete operations for activity store.

Functions for cascade delete operations on sessions, batches, and activities.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

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


def delete_batch_observations(store: ActivityStore, batch_id: int) -> list[str]:
    """Delete all observations for a prompt batch from SQLite.

    Used before reprocessing a batch to prevent duplicate observations.
    Returns the deleted IDs so the caller can also clean ChromaDB.

    Args:
        store: The ActivityStore instance.
        batch_id: Prompt batch ID whose observations should be deleted.

    Returns:
        List of deleted observation IDs (for ChromaDB cleanup).
    """
    # Get IDs first (for ChromaDB cleanup by caller)
    obs_ids = get_batch_observation_ids(store, batch_id)
    if not obs_ids:
        return []

    with store._transaction() as conn:
        placeholders = ",".join("?" * len(obs_ids))
        conn.execute(
            f"DELETE FROM memory_observations WHERE id IN ({placeholders})",
            obs_ids,
        )

    logger.info(f"Deleted {len(obs_ids)} observations for batch {batch_id} (pre-reprocessing)")
    return obs_ids


def delete_observations_for_batches(
    store: ActivityStore,
    batch_ids: list[int],
    machine_id: str,
) -> list[str]:
    """Delete observations for multiple batches and reset batch flags atomically.

    Collects observation IDs, deletes them from SQLite, and resets the
    processed/classification flags on the batches — all in a single transaction.
    Returns the deleted observation IDs so the caller can clean ChromaDB.

    Args:
        store: The ActivityStore instance.
        batch_ids: Prompt batch IDs whose observations should be deleted.
        machine_id: Only delete observations from this machine.

    Returns:
        List of deleted observation IDs (for ChromaDB cleanup).
    """
    if not batch_ids:
        return []

    conn = store._get_connection()
    batch_placeholders = ",".join("?" * len(batch_ids))

    # Collect IDs before deleting (for ChromaDB cleanup by caller)
    cursor = conn.execute(
        f"""
        SELECT id FROM memory_observations
        WHERE prompt_batch_id IN ({batch_placeholders})
          AND source_machine_id = ?
        """,
        (*batch_ids, machine_id),
    )
    obs_ids = [row[0] for row in cursor.fetchall()]

    with store._transaction() as tx_conn:
        # Delete observations
        if obs_ids:
            obs_placeholders = ",".join("?" * len(obs_ids))
            tx_conn.execute(
                f"DELETE FROM memory_observations WHERE id IN ({obs_placeholders})",
                obs_ids,
            )

        # Reset processed flag on batches so background processor re-extracts
        tx_conn.execute(
            f"""
            UPDATE prompt_batches
            SET processed = FALSE, classification = NULL
            WHERE id IN ({batch_placeholders})
            """,
            batch_ids,
        )

    logger.info(
        f"Deleted {len(obs_ids)} observations and reset {len(batch_ids)} batches "
        f"for reprocessing (machine={machine_id})"
    )
    return obs_ids


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


def delete_session(
    store: ActivityStore,
    session_id: str,
    vector_store: Any | None = None,
) -> dict[str, int]:
    """Delete a session and all related data.

    Cascade deletes:
    - All prompt batches for this session
    - All activities for this session
    - All memory observations for this session
    - ChromaDB embeddings if vector_store is provided

    Args:
        store: The ActivityStore instance.
        session_id: The session ID to delete.
        vector_store: Optional vector store for ChromaDB cleanup.

    Returns:
        Dictionary with counts: batches_deleted, activities_deleted, observations_deleted
    """
    result = {"batches_deleted": 0, "activities_deleted": 0, "observations_deleted": 0}

    # Get observation IDs before deleting (for ChromaDB cleanup)
    observation_ids = get_session_observation_ids(store, session_id) if vector_store else []

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

    # Clean up ChromaDB embeddings if vector_store provided
    # This handles both memory observations and session summaries
    if vector_store and observation_ids:
        try:
            vector_store.delete_memories(observation_ids)
            logger.debug(
                f"Cleaned up {len(observation_ids)} ChromaDB embeddings for session {session_id}"
            )
        except (ValueError, RuntimeError) as e:
            # Log but don't fail - SQLite cleanup already succeeded
            logger.warning(f"Failed to clean up ChromaDB embeddings for session {session_id}: {e}")

    logger.info(
        f"Deleted session {session_id}: "
        f"{result['batches_deleted']} batches, "
        f"{result['activities_deleted']} activities, "
        f"{result['observations_deleted']} observations"
    )
    return result
