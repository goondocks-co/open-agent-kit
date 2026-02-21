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

    Only returns active observations — resolved/superseded observations are
    preserved during reprocessing so their content hashes continue to block
    re-extraction of already-addressed content.

    Args:
        store: The ActivityStore instance.
        batch_id: Prompt batch ID to query.

    Returns:
        List of active observation IDs linked to this batch.
    """
    conn = store._get_connection()
    cursor = conn.execute(
        "SELECT id FROM memory_observations WHERE prompt_batch_id = ? "
        "AND COALESCE(status, 'active') = 'active' "
        "AND COALESCE(origin_type, 'auto_extracted') != 'agent_created'",
        (batch_id,),
    )
    return [row[0] for row in cursor.fetchall()]


def delete_batch_observations(store: ActivityStore, batch_id: int) -> list[str]:
    """Delete active observations for a prompt batch from SQLite.

    Used before reprocessing a batch to prevent duplicate observations.
    Only deletes active observations — resolved/superseded observations are
    preserved so their content hashes block re-extraction during reprocessing.
    Returns the deleted IDs so the caller can also clean ChromaDB.

    Args:
        store: The ActivityStore instance.
        batch_id: Prompt batch ID whose active observations should be deleted.

    Returns:
        List of deleted observation IDs (for ChromaDB cleanup).
    """
    # Get active IDs first (for ChromaDB cleanup by caller)
    obs_ids = get_batch_observation_ids(store, batch_id)
    if not obs_ids:
        return []

    with store._transaction() as conn:
        placeholders = ",".join("?" * len(obs_ids))
        conn.execute(
            f"DELETE FROM memory_observations WHERE id IN ({placeholders})",
            obs_ids,
        )

    logger.info(
        f"Deleted {len(obs_ids)} active observations for batch {batch_id} (pre-reprocessing)"
    )
    return obs_ids


def delete_observations_for_batches(
    store: ActivityStore,
    batch_ids: list[int],
    machine_id: str,
) -> list[str]:
    """Delete active observations for multiple batches and reset batch flags atomically.

    Only deletes active observations — resolved/superseded observations are
    preserved so their content hashes block re-extraction during reprocessing.

    Collects observation IDs, deletes them from SQLite, and resets the
    processed/classification flags on the batches — all in a single transaction.
    Returns the deleted observation IDs so the caller can clean ChromaDB.

    Args:
        store: The ActivityStore instance.
        batch_ids: Prompt batch IDs whose active observations should be deleted.
        machine_id: Only delete observations from this machine.

    Returns:
        List of deleted observation IDs (for ChromaDB cleanup).
    """
    if not batch_ids:
        return []

    conn = store._get_connection()
    batch_placeholders = ",".join("?" * len(batch_ids))

    # Collect active, auto-extracted IDs before deleting (for ChromaDB cleanup by caller).
    # Agent-created observations are preserved — they were created by the maintenance
    # agent and should not be destroyed by devtools reprocessing.
    cursor = conn.execute(
        f"""
        SELECT id FROM memory_observations
        WHERE prompt_batch_id IN ({batch_placeholders})
          AND source_machine_id = ?
          AND COALESCE(status, 'active') = 'active'
          AND COALESCE(origin_type, 'auto_extracted') != 'agent_created'
        """,
        (*batch_ids, machine_id),
    )
    obs_ids = [row[0] for row in cursor.fetchall()]

    with store._transaction() as tx_conn:
        # Delete active observations only
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
        f"Deleted {len(obs_ids)} active observations and reset {len(batch_ids)} batches "
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


def delete_records_by_machine(
    store: ActivityStore,
    machine_id: str,
    vector_store: Any | None = None,
) -> dict[str, int]:
    """Delete all records originating from a specific machine.

    Used by replace-mode restore to clear stale data before importing a fresh
    backup snapshot.  Follows FK cascade order to avoid constraint violations.

    Children are deleted by FK reference to the parent IDs being removed — not
    solely by ``source_machine_id`` — because prior additive imports can create
    cross-machine FK references (e.g. an activity from machine A that points to
    a prompt_batch from machine B).  The self-referential
    ``prompt_batches.source_plan_batch_id`` FK is NULLed out before the batch
    rows themselves are deleted.

    Skips ``agent_schedules`` (personal preferences, already filtered during import).

    Args:
        store: The ActivityStore instance.
        machine_id: The ``source_machine_id`` value identifying the remote machine.
        vector_store: Optional vector store for ChromaDB cleanup.

    Returns:
        Dictionary with per-table deleted counts.
    """
    conn = store._get_connection()
    counts: dict[str, int] = {
        "session_link_events": 0,
        "session_relationships": 0,
        "activities": 0,
        "memory_observations": 0,
        "resolution_events": 0,
        "governance_audit_events": 0,
        "prompt_batches": 0,
        "sessions": 0,
        "agent_runs": 0,
    }

    # Pre-collect parent IDs so children can be deleted by FK reference
    cursor = conn.execute(
        "SELECT id FROM prompt_batches WHERE source_machine_id = ?",
        (machine_id,),
    )
    batch_ids = [row[0] for row in cursor.fetchall()]

    cursor = conn.execute(
        "SELECT id FROM sessions WHERE source_machine_id = ?",
        (machine_id,),
    )
    session_ids = [row[0] for row in cursor.fetchall()]

    # Collect observation IDs for ChromaDB cleanup *before* deleting.
    # Must capture three sources of observations:
    #   1. Same-machine: source_machine_id matches
    #   2. Batch-FK: prompt_batch_id references a batch from this machine
    #   3. Session-FK: session_id references a session from this machine but
    #      source_machine_id differs (created by background processing on
    #      another machine after an additive import)
    observation_ids: list[str] = []
    if vector_store:
        parts = ["SELECT id FROM memory_observations WHERE source_machine_id = ?"]
        params: list[Any] = [machine_id]
        if batch_ids:
            bp = ",".join("?" * len(batch_ids))
            parts.append(f"SELECT id FROM memory_observations WHERE prompt_batch_id IN ({bp})")
            params.extend(batch_ids)
        if session_ids:
            sp = ",".join("?" * len(session_ids))
            parts.append(f"SELECT id FROM memory_observations WHERE session_id IN ({sp})")
            params.extend(session_ids)
        cursor = conn.execute(" UNION ".join(parts), params)
        observation_ids = [row[0] for row in cursor.fetchall()]

    with store._transaction() as tx:
        # 1-2. Junction tables (no source_machine_id column, keyed by session_id)
        if session_ids:
            sp = ",".join("?" * len(session_ids))

            cursor = tx.execute(
                f"DELETE FROM session_link_events WHERE session_id IN ({sp})",
                session_ids,
            )
            counts["session_link_events"] = cursor.rowcount

            cursor = tx.execute(
                f"DELETE FROM session_relationships "
                f"WHERE session_a_id IN ({sp}) OR session_b_id IN ({sp})",
                [*session_ids, *session_ids],
            )
            counts["session_relationships"] = cursor.rowcount

        # 3. Activities — delete by FK reference to batches being removed,
        #    then mop up any remaining by source_machine_id (e.g. NULL batch ref).
        if batch_ids:
            bp = ",".join("?" * len(batch_ids))
            cursor = tx.execute(
                f"DELETE FROM activities WHERE prompt_batch_id IN ({bp})",
                batch_ids,
            )
            counts["activities"] = cursor.rowcount
        cursor = tx.execute("DELETE FROM activities WHERE source_machine_id = ?", (machine_id,))
        counts["activities"] += cursor.rowcount

        # 4. Memory observations — same FK-first approach.
        if batch_ids:
            cursor = tx.execute(
                f"DELETE FROM memory_observations WHERE prompt_batch_id IN ({bp})",
                batch_ids,
            )
            counts["memory_observations"] = cursor.rowcount
        cursor = tx.execute(
            "DELETE FROM memory_observations WHERE source_machine_id = ?",
            (machine_id,),
        )
        counts["memory_observations"] += cursor.rowcount

        # 4.5 Resolution events — delete by source_machine_id and by observation_id
        cursor = tx.execute(
            "DELETE FROM resolution_events WHERE source_machine_id = ?",
            (machine_id,),
        )
        counts["resolution_events"] = cursor.rowcount
        if observation_ids:
            op = ",".join("?" * len(observation_ids))
            cursor = tx.execute(
                f"DELETE FROM resolution_events WHERE observation_id IN ({op})",
                observation_ids,
            )
            counts["resolution_events"] += cursor.rowcount

        # 4.6 Governance audit events — leaf table, FK to sessions only
        if session_ids:
            cursor = tx.execute(
                f"DELETE FROM governance_audit_events WHERE session_id IN ({sp})",
                session_ids,
            )
            counts["governance_audit_events"] = cursor.rowcount
        cursor = tx.execute(
            "DELETE FROM governance_audit_events WHERE source_machine_id = ?",
            (machine_id,),
        )
        counts["governance_audit_events"] += cursor.rowcount

        # 5. Prompt batches — clear self-referential FK first, then delete.
        if batch_ids:
            tx.execute(
                f"UPDATE prompt_batches SET source_plan_batch_id = NULL "
                f"WHERE source_plan_batch_id IN ({bp})",
                batch_ids,
            )
        cursor = tx.execute("DELETE FROM prompt_batches WHERE source_machine_id = ?", (machine_id,))
        counts["prompt_batches"] = cursor.rowcount

        # 5.5 Cross-machine cascade sweep — clean up remaining child records
        # from OTHER machines that reference sessions owned by this machine.
        # This handles records created by background processing on machine B
        # after an additive import of machine A's sessions (the observations
        # get source_machine_id=B but session_id pointing to machine A).
        if session_ids:
            sp = ",".join("?" * len(session_ids))
            cursor = tx.execute(
                f"DELETE FROM activities WHERE session_id IN ({sp})",
                session_ids,
            )
            counts["activities"] += cursor.rowcount

            cursor = tx.execute(
                f"DELETE FROM memory_observations WHERE session_id IN ({sp})",
                session_ids,
            )
            counts["memory_observations"] += cursor.rowcount

            # Prompt batches — nullify self-referential FK for remaining, then delete
            remaining = tx.execute(
                f"SELECT id FROM prompt_batches WHERE session_id IN ({sp})",
                session_ids,
            ).fetchall()
            remaining_ids = [r[0] for r in remaining]
            if remaining_ids:
                rp = ",".join("?" * len(remaining_ids))
                tx.execute(
                    f"UPDATE prompt_batches SET source_plan_batch_id = NULL "
                    f"WHERE source_plan_batch_id IN ({rp})",
                    remaining_ids,
                )
            cursor = tx.execute(
                f"DELETE FROM prompt_batches WHERE session_id IN ({sp})",
                session_ids,
            )
            counts["prompt_batches"] += cursor.rowcount

        # 6. Sessions
        cursor = tx.execute("DELETE FROM sessions WHERE source_machine_id = ?", (machine_id,))
        counts["sessions"] = cursor.rowcount

        # 7. Agent runs
        cursor = tx.execute("DELETE FROM agent_runs WHERE source_machine_id = ?", (machine_id,))
        counts["agent_runs"] = cursor.rowcount

    # ChromaDB cleanup (after SQLite commit)
    if vector_store and observation_ids:
        try:
            vector_store.delete_memories(observation_ids)
            logger.debug(
                f"Cleaned up {len(observation_ids)} ChromaDB embeddings for machine {machine_id}"
            )
        except (ValueError, RuntimeError) as e:
            logger.warning(f"Failed to clean up ChromaDB embeddings for machine {machine_id}: {e}")

    total = sum(counts.values())
    logger.info(
        f"Deleted {total} records for machine {machine_id}: "
        + ", ".join(f"{k}={v}" for k, v in counts.items() if v > 0)
    )
    return counts


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
        # Delete junction tables first (session_relationships has FK to sessions)
        conn.execute(
            "DELETE FROM session_relationships WHERE session_a_id = ? OR session_b_id = ?",
            (session_id, session_id),
        )
        conn.execute(
            "DELETE FROM session_link_events WHERE session_id = ?",
            (session_id,),
        )

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

        # Delete prompt batches — nullify self-referential FK first
        batch_ids = [
            r[0]
            for r in conn.execute(
                "SELECT id FROM prompt_batches WHERE session_id = ?",
                (session_id,),
            ).fetchall()
        ]
        if batch_ids:
            bp = ",".join("?" * len(batch_ids))
            conn.execute(
                f"UPDATE prompt_batches SET source_plan_batch_id = NULL "
                f"WHERE source_plan_batch_id IN ({bp})",
                batch_ids,
            )
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
