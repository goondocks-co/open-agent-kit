"""Cross-cutting maintenance operations for the activity store.

Contains reset and cleanup logic that spans multiple tables.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.store.core import ActivityStore

logger = logging.getLogger(__name__)


def reset_processing_state(
    store: ActivityStore, *, delete_memories: bool = False
) -> dict[str, int]:
    """Reset processing flags on all completed records.

    Optionally deletes all memory observations from SQLite.
    ChromaDB cleanup (if needed) must be handled by the caller,
    since the store layer doesn't hold the vector store reference.

    Args:
        store: The ActivityStore instance.
        delete_memories: If True, delete all memory observations.

    Returns:
        Dict with counts: {observations_deleted, sessions_reset,
        batches_reset, activities_reset}.
    """
    counts: dict[str, int] = {
        "observations_deleted": 0,
        "sessions_reset": 0,
        "batches_reset": 0,
        "activities_reset": 0,
    }

    with store._transaction() as conn:
        if delete_memories:
            # Preserve agent-created observations — they were created by
            # the maintenance agent and should survive devtools resets.
            cursor = conn.execute(
                "DELETE FROM memory_observations "
                "WHERE source_machine_id = ? "
                "AND COALESCE(origin_type, 'auto_extracted') != 'agent_created'",
                (store.machine_id,),
            )
            counts["observations_deleted"] = cursor.rowcount

        cursor = conn.execute(
            "UPDATE sessions SET processed = FALSE, summary = NULL "
            "WHERE status = 'completed' AND source_machine_id = ?",
            (store.machine_id,),
        )
        counts["sessions_reset"] = cursor.rowcount

        cursor = conn.execute(
            "UPDATE prompt_batches "
            "SET processed = FALSE, classification = NULL "
            "WHERE status = 'completed' AND source_machine_id = ?",
            (store.machine_id,),
        )
        counts["batches_reset"] = cursor.rowcount

        cursor = conn.execute(
            "UPDATE activities SET processed = FALSE WHERE source_machine_id = ?",
            (store.machine_id,),
        )
        counts["activities_reset"] = cursor.rowcount

    logger.info("Reset processing state: %s", counts)
    return counts


def cleanup_cross_machine_pollution(
    store: ActivityStore, vector_store: Any | None = None
) -> dict[str, int]:
    """Remove observations that violate the machine isolation invariant.

    Finds observations where the observation's source_machine_id differs
    from its session's source_machine_id — i.e., a local processor created
    observations referencing another machine's imported sessions.

    This is a one-time cleanup for databases that were polluted before
    machine-scoped filters were added to all background processing paths.
    Idempotent: returns zeros on subsequent runs.

    Args:
        store: The ActivityStore instance.
        vector_store: Optional vector store for ChromaDB cleanup.

    Returns:
        Dict with cleanup counts: {observations_deleted, chromadb_deleted}.
    """
    counts: dict[str, int] = {
        "observations_deleted": 0,
        "chromadb_deleted": 0,
    }

    conn = store._get_connection()

    # Find cross-machine observations: observation created by machine X
    # referencing a session owned by machine Y
    cursor = conn.execute("""
        SELECT mo.id FROM memory_observations mo
        JOIN sessions s ON mo.session_id = s.id
        WHERE mo.source_machine_id != s.source_machine_id
        """)
    polluted_ids = [row[0] for row in cursor.fetchall()]

    if not polluted_ids:
        return counts

    # Delete from ChromaDB first (best-effort)
    if vector_store and polluted_ids:
        try:
            vector_store.delete_memories(polluted_ids)
            counts["chromadb_deleted"] = len(polluted_ids)
        except (ValueError, RuntimeError) as e:
            logger.warning(f"ChromaDB cleanup for cross-machine pollution failed: {e}")

    # Delete from SQLite
    placeholders = ",".join("?" * len(polluted_ids))
    with store._transaction() as tx_conn:
        cursor = tx_conn.execute(
            f"DELETE FROM memory_observations WHERE id IN ({placeholders})",
            polluted_ids,
        )
        counts["observations_deleted"] = cursor.rowcount

    logger.info(
        "Cleaned up cross-machine pollution: %d observations deleted, "
        "%d ChromaDB entries removed",
        counts["observations_deleted"],
        counts["chromadb_deleted"],
    )
    return counts
