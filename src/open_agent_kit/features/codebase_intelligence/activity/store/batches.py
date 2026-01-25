"""Prompt batch operations for activity store.

Functions for creating, retrieving, and managing prompt batches and plans.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any

from open_agent_kit.features.codebase_intelligence.activity.store.models import (
    Activity,
    PromptBatch,
)

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.store.core import ActivityStore

logger = logging.getLogger(__name__)


def create_prompt_batch(
    store: ActivityStore,
    session_id: str,
    user_prompt: str | None = None,
    source_type: str = "user",
    plan_file_path: str | None = None,
    plan_content: str | None = None,
    agent: str | None = None,
) -> PromptBatch:
    """Create a new prompt batch (when user submits a prompt).

    Args:
        store: The ActivityStore instance.
        session_id: Parent session ID.
        user_prompt: Full user prompt text (up to 10K chars).
        source_type: Source type (user, agent_notification, plan, system).
        plan_file_path: Path to plan file (for source_type='plan').
        plan_content: Plan content (extracted from prompt or written to file).
        agent: Agent name for session recreation if needed.

    Returns:
        Created PromptBatch with assigned ID.
    """
    # Import here to avoid circular imports
    from open_agent_kit.features.codebase_intelligence.activity.store.sessions import (
        ensure_session_exists,
        reactivate_session_if_needed,
    )

    # Reactivate session if it was completed (e.g., by stale session recovery).
    # This ensures sessions seamlessly resume when new prompts arrive after a gap.
    # Performant: single UPDATE that only affects completed sessions (no-op if active).
    reactivate_session_if_needed(store, session_id)

    # Ensure session exists (handles deleted sessions from empty session cleanup).
    # When an empty session is deleted by recover_stale_sessions and a prompt
    # later arrives, we seamlessly recreate the session.
    if agent:
        ensure_session_exists(store, session_id, agent)

    # Get current prompt count for this session
    conn = store._get_connection()
    cursor = conn.execute(
        "SELECT COUNT(*) as count FROM prompt_batches WHERE session_id = ?",
        (session_id,),
    )
    row = cursor.fetchone()
    prompt_number = (row["count"] or 0) + 1

    batch = PromptBatch(
        session_id=session_id,
        prompt_number=prompt_number,
        user_prompt=user_prompt,
        started_at=datetime.now(),
        source_type=source_type,
        plan_file_path=plan_file_path,
        plan_content=plan_content,
    )

    with store._transaction() as conn:
        row_data = batch.to_row()
        cursor = conn.execute(
            """
            INSERT INTO prompt_batches (session_id, prompt_number, user_prompt,
                                       started_at, status, activity_count, processed,
                                       classification, source_type, plan_file_path,
                                       plan_content, created_at_epoch)
            VALUES (:session_id, :prompt_number, :user_prompt,
                    :started_at, :status, :activity_count, :processed,
                    :classification, :source_type, :plan_file_path,
                    :plan_content, :created_at_epoch)
            """,
            row_data,
        )
        batch.id = cursor.lastrowid

        # Update session prompt count
        conn.execute(
            "UPDATE sessions SET prompt_count = prompt_count + 1 WHERE id = ?",
            (session_id,),
        )

    logger.debug(
        f"Created prompt batch {batch.id} (prompt #{prompt_number}, source={source_type}) "
        f"for session {session_id}"
    )
    return batch


def get_prompt_batch(store: ActivityStore, batch_id: int) -> PromptBatch | None:
    """Get prompt batch by ID."""
    conn = store._get_connection()
    cursor = conn.execute("SELECT * FROM prompt_batches WHERE id = ?", (batch_id,))
    row = cursor.fetchone()
    return PromptBatch.from_row(row) if row else None


def get_active_prompt_batch(store: ActivityStore, session_id: str) -> PromptBatch | None:
    """Get the current active prompt batch for a session.

    Args:
        store: The ActivityStore instance.
        session_id: Session to query.

    Returns:
        Active PromptBatch if one exists, None otherwise.
    """
    conn = store._get_connection()
    cursor = conn.execute(
        """
        SELECT * FROM prompt_batches
        WHERE session_id = ? AND status = 'active'
        ORDER BY prompt_number DESC
        LIMIT 1
        """,
        (session_id,),
    )
    row = cursor.fetchone()
    return PromptBatch.from_row(row) if row else None


def end_prompt_batch(store: ActivityStore, batch_id: int) -> None:
    """Mark a prompt batch as completed (when agent stops responding).

    Args:
        store: The ActivityStore instance.
        batch_id: Prompt batch to end.
    """
    with store._transaction() as conn:
        conn.execute(
            """
            UPDATE prompt_batches
            SET ended_at = ?, status = 'completed'
            WHERE id = ?
            """,
            (datetime.now().isoformat(), batch_id),
        )
    logger.debug(f"Ended prompt batch {batch_id}")


def get_unprocessed_prompt_batches(store: ActivityStore, limit: int = 10) -> list[PromptBatch]:
    """Get prompt batches that haven't been processed yet.

    Args:
        store: The ActivityStore instance.
        limit: Maximum batches to return.

    Returns:
        List of unprocessed PromptBatch objects (completed but not processed).
    """
    conn = store._get_connection()
    cursor = conn.execute(
        """
        SELECT * FROM prompt_batches
        WHERE processed = FALSE AND status = 'completed'
        ORDER BY created_at_epoch ASC
        LIMIT ?
        """,
        (limit,),
    )
    return [PromptBatch.from_row(row) for row in cursor.fetchall()]


def mark_prompt_batch_processed(
    store: ActivityStore,
    batch_id: int,
    classification: str | None = None,
) -> None:
    """Mark prompt batch as processed.

    Args:
        store: The ActivityStore instance.
        batch_id: Batch to mark.
        classification: LLM classification result.
    """
    with store._transaction() as conn:
        conn.execute(
            """
            UPDATE prompt_batches
            SET processed = TRUE, classification = ?
            WHERE id = ?
            """,
            (classification, batch_id),
        )


def update_prompt_batch_source_type(
    store: ActivityStore,
    batch_id: int,
    source_type: str,
    plan_file_path: str | None = None,
    plan_content: str | None = None,
) -> None:
    """Update the source type for a prompt batch.

    Used when plan mode is detected mid-batch (e.g., Write to plans directory).

    Args:
        store: The ActivityStore instance.
        batch_id: Batch to update.
        source_type: New source type (user, agent_notification, plan, system).
        plan_file_path: Path to plan file (for source_type='plan').
        plan_content: Full plan content (for source_type='plan').
    """
    # Truncate plan content to max length
    if plan_content and len(plan_content) > PromptBatch.MAX_PLAN_CONTENT_LENGTH:
        plan_content = plan_content[: PromptBatch.MAX_PLAN_CONTENT_LENGTH]

    with store._transaction() as conn:
        if plan_file_path or plan_content:
            conn.execute(
                """
                UPDATE prompt_batches
                SET source_type = ?, plan_file_path = ?, plan_content = ?
                WHERE id = ?
                """,
                (source_type, plan_file_path, plan_content, batch_id),
            )
        else:
            conn.execute(
                """
                UPDATE prompt_batches
                SET source_type = ?
                WHERE id = ?
                """,
                (source_type, batch_id),
            )
    logger.debug(f"Updated prompt batch {batch_id} source_type to {source_type}")


def get_session_prompt_batches(
    store: ActivityStore,
    session_id: str,
    limit: int | None = None,
) -> list[PromptBatch]:
    """Get all prompt batches for a session.

    Args:
        store: The ActivityStore instance.
        session_id: Session to query.
        limit: Maximum batches to return.

    Returns:
        List of PromptBatch objects in chronological order.
    """
    conn = store._get_connection()

    query = """
        SELECT * FROM prompt_batches
        WHERE session_id = ?
        ORDER BY prompt_number ASC
    """
    params: list[Any] = [session_id]

    if limit:
        query += " LIMIT ?"
        params.append(limit)

    cursor = conn.execute(query, params)
    return [PromptBatch.from_row(row) for row in cursor.fetchall()]


def get_plans(
    store: ActivityStore,
    limit: int = 50,
    offset: int = 0,
    session_id: str | None = None,
    deduplicate: bool = True,
) -> tuple[list[PromptBatch], int]:
    """Get plan batches from prompt_batches table.

    Plans are prompt batches with source_type='plan' and plan_content populated.

    Args:
        store: The ActivityStore instance.
        limit: Maximum plans to return.
        offset: Number of plans to skip.
        session_id: Optional session ID to filter by.
        deduplicate: If True, deduplicate plans by content (keeps earliest).
            The same plan content may appear in multiple sessions when a plan
            is created in one session and later implemented in another.

    Returns:
        Tuple of (list of PromptBatch objects, total count).
    """
    conn = store._get_connection()

    # Build WHERE clause for base plan filtering
    where_parts = ["source_type = 'plan'", "plan_content IS NOT NULL"]
    base_params: list[Any] = []

    if session_id:
        where_parts.append("session_id = ?")
        base_params.append(session_id)

    where_clause = " AND ".join(where_parts)

    # Use first 500 characters as a fingerprint for deduplication.
    # This handles cases where the same plan has minor variations
    # (e.g., slightly different whitespace, updated sections at the end).
    content_fingerprint = "SUBSTR(plan_content, 1, 500)"

    if deduplicate:
        # Use window function to deduplicate by content fingerprint.
        # The same plan may appear in multiple sessions (created in one,
        # implemented in another). We keep only the first occurrence.
        count_query = f"""
            SELECT COUNT(DISTINCT {content_fingerprint})
            FROM prompt_batches
            WHERE {where_clause}
        """
        cursor = conn.execute(count_query, base_params)
        total = cursor.fetchone()[0]

        # Use CTE with ROW_NUMBER to get first occurrence of each unique plan
        query = f"""
            WITH unique_plans AS (
                SELECT *,
                       ROW_NUMBER() OVER (
                           PARTITION BY {content_fingerprint}
                           ORDER BY created_at_epoch ASC
                       ) as rn
                FROM prompt_batches
                WHERE {where_clause}
            )
            SELECT id, session_id, prompt_number, user_prompt, started_at, ended_at,
                   status, activity_count, processed, classification, source_type,
                   plan_file_path, plan_content, created_at_epoch, plan_embedded
            FROM unique_plans
            WHERE rn = 1
            ORDER BY created_at_epoch DESC
            LIMIT ? OFFSET ?
        """
        params = base_params + [limit, offset]
    else:
        # No deduplication - return all plans
        count_query = f"SELECT COUNT(*) FROM prompt_batches WHERE {where_clause}"
        cursor = conn.execute(count_query, base_params)
        total = cursor.fetchone()[0]

        query = f"""
            SELECT * FROM prompt_batches
            WHERE {where_clause}
            ORDER BY created_at_epoch DESC
            LIMIT ? OFFSET ?
        """
        params = base_params + [limit, offset]

    cursor = conn.execute(query, params)
    plans = [PromptBatch.from_row(row) for row in cursor.fetchall()]

    return plans, total


def recover_stuck_batches(store: ActivityStore, timeout_seconds: int = 1800) -> int:
    """Auto-end batches stuck in 'active' status for too long.

    This handles cases where the session ended unexpectedly (crash, network
    disconnect) without calling the stop hook.

    Args:
        store: The ActivityStore instance.
        timeout_seconds: Batches active longer than this are auto-ended.

    Returns:
        Number of batches recovered.
    """
    cutoff_epoch = time.time() - timeout_seconds

    with store._transaction() as conn:
        cursor = conn.execute(
            """
            UPDATE prompt_batches
            SET status = 'completed'
            WHERE status = 'active' AND created_at_epoch < ?
            RETURNING id
            """,
            (cutoff_epoch,),
        )
        recovered_ids = [row[0] for row in cursor.fetchall()]

    if recovered_ids:
        logger.info(
            f"Recovered {len(recovered_ids)} stuck batches "
            f"(active > {timeout_seconds}s): {recovered_ids}"
        )

    return len(recovered_ids)


def recover_orphaned_activities(store: ActivityStore) -> int:
    """Associate orphaned activities (NULL batch) with appropriate batches.

    For each orphaned activity, finds the most recent batch for that session
    and associates the activity with it. If no batch exists, creates a
    recovery batch.

    Args:
        store: The ActivityStore instance.

    Returns:
        Number of activities recovered.
    """
    conn = store._get_connection()

    # Find sessions with orphaned activities
    cursor = conn.execute(
        """
        SELECT DISTINCT session_id, COUNT(*) as orphan_count
        FROM activities
        WHERE prompt_batch_id IS NULL
        GROUP BY session_id
        """
    )
    orphan_sessions = cursor.fetchall()

    if not orphan_sessions:
        return 0

    total_recovered = 0

    for session_id, orphan_count in orphan_sessions:
        # Find the most recent batch for this session
        cursor = conn.execute(
            """
            SELECT id FROM prompt_batches
            WHERE session_id = ?
            ORDER BY created_at_epoch DESC
            LIMIT 1
            """,
            (session_id,),
        )
        batch_row = cursor.fetchone()

        if batch_row:
            batch_id = batch_row[0]
        else:
            # Create a recovery batch for this session
            now = time.time()
            with store._transaction() as tx_conn:
                tx_conn.execute(
                    """
                    INSERT INTO prompt_batches
                    (session_id, prompt_number, user_prompt, started_at, created_at_epoch, status)
                    VALUES (?, 0, '[Recovery batch for orphaned activities]', datetime(?, 'unixepoch'), ?, 'completed')
                    """,
                    (session_id, now, now),
                )
                cursor = tx_conn.execute("SELECT last_insert_rowid()")
                batch_id = cursor.fetchone()[0]
                logger.info(f"Created recovery batch {batch_id} for session {session_id}")

        # Associate orphaned activities with the batch
        with store._transaction() as tx_conn:
            tx_conn.execute(
                """
                UPDATE activities
                SET prompt_batch_id = ?
                WHERE session_id = ? AND prompt_batch_id IS NULL
                """,
                (batch_id, session_id),
            )

        logger.info(
            f"Recovered {orphan_count} orphaned activities for session "
            f"{session_id[:8]}... -> batch {batch_id}"
        )
        total_recovered += orphan_count

    return total_recovered


def get_prompt_batch_activities(
    store: ActivityStore,
    batch_id: int,
    limit: int | None = None,
) -> list[Activity]:
    """Get all activities for a prompt batch.

    Args:
        store: The ActivityStore instance.
        batch_id: Prompt batch ID.
        limit: Maximum activities to return.

    Returns:
        List of Activity objects in chronological order.
    """
    conn = store._get_connection()

    query = "SELECT * FROM activities WHERE prompt_batch_id = ? ORDER BY timestamp_epoch ASC"
    params: list[Any] = [batch_id]

    if limit:
        query += " LIMIT ?"
        params.append(limit)

    cursor = conn.execute(query, params)
    return [Activity.from_row(row) for row in cursor.fetchall()]


def get_prompt_batch_stats(store: ActivityStore, batch_id: int) -> dict[str, Any]:
    """Get statistics for a prompt batch.

    Args:
        store: The ActivityStore instance.
        batch_id: Prompt batch to query.

    Returns:
        Dictionary with batch statistics.
    """
    conn = store._get_connection()

    # Tool counts by name
    cursor = conn.execute(
        """
        SELECT tool_name, COUNT(*) as count
        FROM activities
        WHERE prompt_batch_id = ?
        GROUP BY tool_name
        ORDER BY count DESC
        """,
        (batch_id,),
    )
    tool_counts = {row["tool_name"]: row["count"] for row in cursor.fetchall()}

    # File and error counts
    cursor = conn.execute(
        """
        SELECT
            COUNT(DISTINCT file_path) as files_touched,
            SUM(CASE WHEN tool_name = 'Read' THEN 1 ELSE 0 END) as reads,
            SUM(CASE WHEN tool_name = 'Edit' THEN 1 ELSE 0 END) as edits,
            SUM(CASE WHEN tool_name = 'Write' THEN 1 ELSE 0 END) as writes,
            SUM(CASE WHEN success = FALSE THEN 1 ELSE 0 END) as errors
        FROM activities
        WHERE prompt_batch_id = ?
        """,
        (batch_id,),
    )
    row = cursor.fetchone()

    return {
        "tool_counts": tool_counts,
        "files_touched": row["files_touched"] or 0,
        "reads": row["reads"] or 0,
        "edits": row["edits"] or 0,
        "writes": row["writes"] or 0,
        "errors": row["errors"] or 0,
    }


# ==========================================================================
# Plan Embedding Operations (for semantic search of plans)
# ==========================================================================


def get_unembedded_plans(store: ActivityStore, limit: int = 50) -> list[PromptBatch]:
    """Get plan batches that haven't been embedded in ChromaDB yet.

    Returns batches where:
    - source_type = 'plan'
    - plan_content is not empty
    - plan_embedded = FALSE

    Args:
        store: The ActivityStore instance.
        limit: Maximum batches to return.

    Returns:
        List of PromptBatch objects needing embedding.
    """
    conn = store._get_connection()
    cursor = conn.execute(
        """
        SELECT * FROM prompt_batches
        WHERE source_type = 'plan'
          AND plan_content IS NOT NULL
          AND plan_content != ''
          AND (plan_embedded IS NULL OR plan_embedded = 0)
        ORDER BY created_at_epoch ASC
        LIMIT ?
        """,
        (limit,),
    )
    return [PromptBatch.from_row(row) for row in cursor.fetchall()]


def mark_plan_embedded(store: ActivityStore, batch_id: int) -> None:
    """Mark a plan batch as embedded in ChromaDB.

    Args:
        store: The ActivityStore instance.
        batch_id: The prompt batch ID to mark.
    """
    with store._transaction() as conn:
        conn.execute(
            "UPDATE prompt_batches SET plan_embedded = 1 WHERE id = ?",
            (batch_id,),
        )
    logger.debug(f"Marked plan batch {batch_id} as embedded")


def mark_plan_unembedded(store: ActivityStore, batch_id: int) -> None:
    """Mark a plan batch as not embedded in ChromaDB.

    Used when a plan is deleted from ChromaDB to allow re-indexing.

    Args:
        store: The ActivityStore instance.
        batch_id: The prompt batch ID to mark.
    """
    with store._transaction() as conn:
        conn.execute(
            "UPDATE prompt_batches SET plan_embedded = 0 WHERE id = ?",
            (batch_id,),
        )
    logger.debug(f"Marked plan batch {batch_id} as unembedded")


def count_unembedded_plans(store: ActivityStore) -> int:
    """Count plan batches not yet in ChromaDB.

    Args:
        store: The ActivityStore instance.

    Returns:
        Unembedded plan count.
    """
    conn = store._get_connection()
    cursor = conn.execute(
        """
        SELECT COUNT(*) FROM prompt_batches
        WHERE source_type = 'plan'
          AND plan_content IS NOT NULL
          AND plan_content != ''
          AND (plan_embedded IS NULL OR plan_embedded = 0)
        """
    )
    result = cursor.fetchone()
    return int(result[0]) if result else 0


def mark_all_plans_unembedded(store: ActivityStore) -> int:
    """Mark all plans as not embedded (for full ChromaDB rebuild).

    Args:
        store: The ActivityStore instance.

    Returns:
        Number of plans marked.
    """
    with store._transaction() as conn:
        cursor = conn.execute("UPDATE prompt_batches SET plan_embedded = 0 WHERE plan_embedded = 1")
        count = cursor.rowcount

    logger.info(f"Marked {count} plans as unembedded for rebuild")
    return count
