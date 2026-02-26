"""Session lifecycle operations.

Recovery, cleanup, and session finding for stale/ended sessions.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from open_agent_kit.features.codebase_intelligence.constants import (
    MIN_SESSION_ACTIVITIES,
    SESSION_STATUS_ACTIVE,
    SESSION_STATUS_COMPLETED,
)

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.store.core import ActivityStore

logger = logging.getLogger(__name__)


def recover_stale_sessions(
    store: ActivityStore,
    timeout_seconds: int = 3600,
    min_activities: int | None = None,
    vector_store: Any | None = None,
) -> tuple[list[str], list[str]]:
    """Auto-end or delete sessions that have been inactive for too long.

    This handles cases where the SessionEnd hook didn't fire (crash, network
    disconnect, user closed terminal without proper exit).

    A session is considered stale if:
    - It has activities and the most recent activity is older than timeout_seconds
    - It has NO activities and was created more than timeout_seconds ago

    Sessions that meet the quality threshold (>= min_activities) are
    marked as 'completed' for later summarization and embedding.

    Sessions below the quality threshold are deleted entirely - they will never
    be summarized or embedded anyway, so keeping them just creates clutter.

    Args:
        store: The ActivityStore instance.
        timeout_seconds: Sessions inactive longer than this are auto-ended.
            Pass session_quality.stale_timeout_seconds if available.
        min_activities: Minimum activities threshold. Defaults to MIN_SESSION_ACTIVITIES.
            Pass session_quality.min_activities if available.
        vector_store: Optional vector store for ChromaDB cleanup on deletion.

    Returns:
        Tuple of (recovered_ids, deleted_ids) for state synchronization.
        - recovered_ids: Sessions marked as 'completed' (met quality threshold)
        - deleted_ids: Sessions deleted (below quality threshold)
    """
    # Import here to avoid circular imports
    from open_agent_kit.features.codebase_intelligence.activity.store.delete import (
        delete_session,
    )
    from open_agent_kit.features.codebase_intelligence.activity.store.sessions.queries import (
        count_session_activities,
        mark_session_processed,
    )

    if min_activities is None:
        min_activities = MIN_SESSION_ACTIVITIES

    cutoff_epoch = time.time() - timeout_seconds

    # Find active sessions with no recent activity, including their activity count
    # IMPORTANT: Consider multiple signals to avoid false positives:
    # 1. Last activity timestamp (tool calls)
    # 2. Session creation timestamp (for sessions with no activities)
    # 3. Active prompt batches (session was just resumed but no tool calls yet)
    # 4. Most recent prompt batch creation (user sent a new prompt)
    conn = store._get_connection()
    cursor = conn.execute(
        f"""
        SELECT s.id, MAX(a.timestamp_epoch) as last_activity, s.created_at_epoch,
               COUNT(a.id) as activity_count,
               (SELECT MAX(pb.created_at_epoch) FROM prompt_batches pb WHERE pb.session_id = s.id) as last_batch_epoch,
               (SELECT COUNT(*) FROM prompt_batches pb WHERE pb.session_id = s.id AND pb.status = 'active') as active_batches
        FROM sessions s
        LEFT JOIN activities a ON s.id = a.session_id
        WHERE s.status = '{SESSION_STATUS_ACTIVE}'
          AND s.source_machine_id = ?
        GROUP BY s.id
        HAVING
            -- Skip sessions with active prompt batches (currently being worked on)
            active_batches = 0
            -- Check staleness: use the most recent of activity, batch creation, or session creation
            AND COALESCE(last_activity, last_batch_epoch, s.created_at_epoch) < ?
        """,
        (store.machine_id, cutoff_epoch),
    )
    stale_sessions = [(row[0], row[1], row[2], row[3] or 0) for row in cursor.fetchall()]

    if not stale_sessions:
        return [], []

    recovered_ids = []
    deleted_ids = []
    for session_id, _last_activity, _created_at, activity_count in stale_sessions:
        # Use unified quality threshold: sessions below min_activities
        # will never be summarized or embedded, so delete them
        if activity_count < min_activities:
            # Low-quality session - delete it entirely
            delete_session(store, session_id, vector_store=vector_store)
            deleted_ids.append(session_id)
        else:
            # Quality session - mark as completed for summarization
            with store._transaction() as conn:
                conn.execute(
                    f"""
                    UPDATE sessions
                    SET status = '{SESSION_STATUS_COMPLETED}', ended_at = ?
                    WHERE id = ? AND status = '{SESSION_STATUS_ACTIVE}'
                    """,
                    (datetime.now().isoformat(), session_id),
                )
            # If the session has zero unprocessed activities, mark it
            # processed immediately to prevent it becoming a zombie that
            # the background processor re-visits every tick.
            if count_session_activities(store, session_id) == 0:
                mark_session_processed(store, session_id)
            recovered_ids.append(session_id)

    if recovered_ids:
        logger.info(
            f"Recovered {len(recovered_ids)} stale sessions "
            f"(inactive > {timeout_seconds}s): {[s[:8] for s in recovered_ids]}"
        )
    if deleted_ids:
        logger.info(
            f"Deleted {len(deleted_ids)} low-quality stale sessions "
            f"(< {min_activities} activities, inactive > {timeout_seconds}s): "
            f"{[s[:8] for s in deleted_ids]}"
        )

    return recovered_ids, deleted_ids


def cleanup_low_quality_sessions(
    store: ActivityStore,
    vector_store: Any | None = None,
    min_activities: int | None = None,
) -> list[str]:
    """Delete completed sessions that don't meet the quality threshold.

    Removes sessions that will never be summarized or embedded
    (< min_activities tool calls). Called automatically by the background
    processing loop and also available via the devtools API.

    Only deletes COMPLETED sessions to avoid touching active work.
    Uses bulk SQL deletes in a single transaction for efficiency.

    Args:
        store: The ActivityStore instance.
        vector_store: Optional vector store for ChromaDB cleanup.
        min_activities: Minimum activities threshold. Defaults to MIN_SESSION_ACTIVITIES.
            Pass a configured value from session_quality.min_activities if available.

    Returns:
        List of deleted session IDs.
    """
    if min_activities is None:
        min_activities = MIN_SESSION_ACTIVITIES

    conn = store._get_connection()

    # Find completed sessions with fewer than min_activities activities
    cursor = conn.execute(
        f"""
        SELECT s.id, COUNT(a.id) as activity_count
        FROM sessions s
        LEFT JOIN activities a ON s.id = a.session_id
        WHERE s.status = '{SESSION_STATUS_COMPLETED}'
        GROUP BY s.id
        HAVING activity_count < ?
        """,
        (min_activities,),
    )
    low_quality_sessions = [row[0] for row in cursor.fetchall()]

    if not low_quality_sessions:
        return []

    # Collect non-agent ChromaDB observation IDs before SQL deletion
    # (agent-created observations are preserved even when their session is cleaned up)
    all_observation_ids: list[str] = []
    placeholders = ",".join("?" * len(low_quality_sessions))
    if vector_store:
        obs_cursor = conn.execute(
            f"SELECT id FROM memory_observations "
            f"WHERE session_id IN ({placeholders}) "
            f"AND COALESCE(origin_type, 'auto_extracted') != 'agent_created'",
            low_quality_sessions,
        )
        all_observation_ids = [row[0] for row in obs_cursor.fetchall()]

    # Bulk delete all related data in a single transaction.
    # Agent-created observations are preserved — they were created by the
    # maintenance agent and should survive low-quality session cleanup.
    # Order: leaf tables first (FK references), then parent tables.
    with store._transaction() as tx_conn:
        # Junction/leaf tables with FK to sessions
        tx_conn.execute(
            f"DELETE FROM governance_audit_events WHERE session_id IN ({placeholders})",
            low_quality_sessions,
        )
        tx_conn.execute(
            f"DELETE FROM session_link_events WHERE session_id IN ({placeholders})",
            low_quality_sessions,
        )
        tx_conn.execute(
            f"DELETE FROM session_relationships "
            f"WHERE session_a_id IN ({placeholders}) OR session_b_id IN ({placeholders})",
            low_quality_sessions + low_quality_sessions,
        )
        # Core child tables
        tx_conn.execute(
            f"DELETE FROM activities WHERE session_id IN ({placeholders})",
            low_quality_sessions,
        )
        tx_conn.execute(
            f"DELETE FROM memory_observations WHERE session_id IN ({placeholders}) "
            f"AND COALESCE(origin_type, 'auto_extracted') != 'agent_created'",
            low_quality_sessions,
        )
        tx_conn.execute(
            f"DELETE FROM prompt_batches WHERE session_id IN ({placeholders})",
            low_quality_sessions,
        )
        tx_conn.execute(
            f"DELETE FROM sessions WHERE id IN ({placeholders})",
            low_quality_sessions,
        )

    # Batch ChromaDB cleanup (best-effort, SQLite already committed)
    if vector_store and all_observation_ids:
        try:
            vector_store.delete_memories(all_observation_ids)
        except (ValueError, RuntimeError) as e:
            logger.warning(f"Failed to clean up ChromaDB embeddings for low-quality sessions: {e}")

    logger.info(
        f"Cleaned up {len(low_quality_sessions)} low-quality sessions "
        f"(< {min_activities} activities): {[s[:8] for s in low_quality_sessions]}"
    )

    return low_quality_sessions


def find_active_parent_for_subagent(
    store: ActivityStore,
    subagent_session_id: str,
    agent: str,
    recency_seconds: int = 30,
) -> str | None:
    """Find the most likely parent session for a subagent.

    Used when an agent (e.g. VS Code Copilot) gives each subagent its own
    session_id.  The parent is the active session of the *same* agent type
    that most likely spawned this subagent.

    Strategy (handles concurrent sessions and race conditions):
      1. Find the active session of the same agent with the most recent
         tool activity within ``recency_seconds``, using epoch timestamps
         for correct comparison.
      2. Fall back to the most recently *created* active session of the
         same agent.  This handles the common race condition where
         SubagentStart fires before PostToolUse stores the parent's
         ``runSubagent`` activity.

    Args:
        store: The ActivityStore instance.
        subagent_session_id: Session ID of the new subagent (excluded from results).
        agent: Agent name to match (e.g. ``vscode-copilot``).
        recency_seconds: How far back to look for recent tool activity.

    Returns:
        Parent session ID if found, None otherwise.
    """
    conn = store._get_connection()

    # Compute cutoff as epoch (avoids datetime('now') UTC vs local-time bug)
    cutoff_epoch = int(time.time()) - recency_seconds

    # Primary: active session with recent tool activity (epoch-based)
    cursor = conn.execute(
        f"""
        SELECT s.id FROM sessions s
        INNER JOIN activities a ON a.session_id = s.id
        WHERE s.status = '{SESSION_STATUS_ACTIVE}'
          AND s.id != ?
          AND s.agent = ?
          AND a.timestamp_epoch > ?
        ORDER BY a.timestamp_epoch DESC
        LIMIT 1
        """,
        (subagent_session_id, agent, cutoff_epoch),
    )
    row = cursor.fetchone()
    if row:
        return cast(str, row[0])

    # Fallback: most recently created active session of same agent.
    # Handles the race condition where SubagentStart fires before
    # PostToolUse stores the parent's runSubagent activity.
    cursor = conn.execute(
        f"""
        SELECT id FROM sessions
        WHERE status = '{SESSION_STATUS_ACTIVE}' AND id != ? AND agent = ?
        ORDER BY created_at_epoch DESC LIMIT 1
        """,
        (subagent_session_id, agent),
    )
    row = cursor.fetchone()
    return cast(str, row[0]) if row else None
