"""Prompt batch query operations.

Read-only queries for listing, filtering, and aggregating prompt batches.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from open_agent_kit.features.team.activity.store.models import (
    Activity,
    PromptBatch,
)

if TYPE_CHECKING:
    from open_agent_kit.features.team.activity.store.core import ActivityStore

logger = logging.getLogger(__name__)


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
    sort: str = "created",
) -> tuple[list[PromptBatch], int]:
    """Get plan batches from prompt_batches table.

    Plans are prompt batches with source_type='plan' and plan_content populated.

    Args:
        store: The ActivityStore instance.
        limit: Maximum plans to return.
        offset: Number of plans to skip.
        session_id: Optional session ID to filter by.
        deduplicate: If True, deduplicate plans by file path (keeps latest).
            The same plan file may appear across sessions when a plan is
            created in one session and refined in another. Within a single
            session, plan iterations are consolidated at detection time
            (update-in-place), so dedup here handles the cross-session case.
        sort: Sort order - 'created' (newest first, default) or 'created_asc' (oldest first).

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

    # Determine sort direction
    sort_order = "ASC" if sort == "created_asc" else "DESC"

    if deduplicate:
        # Deduplicate by plan_file_path, keeping the most recent version.
        # Within a session, plan iterations are already consolidated at
        # detection time (update-in-place). This handles the cross-session
        # case where the same file appears in parent/child sessions.
        # Plans without a file path (e.g., derived plans) are never deduped.
        count_query = f"""
            SELECT COUNT(*) FROM (
                SELECT id FROM prompt_batches
                WHERE {where_clause} AND plan_file_path IS NULL
                UNION ALL
                SELECT MAX(id) FROM prompt_batches
                WHERE {where_clause} AND plan_file_path IS NOT NULL
                GROUP BY plan_file_path
            )
        """
        cursor = conn.execute(count_query, base_params + base_params)
        total = cursor.fetchone()[0]

        # Use CTE with ROW_NUMBER to keep the latest per file path.
        # Plans without a file path pass through without dedup.
        query = f"""
            WITH unique_plans AS (
                SELECT *,
                       ROW_NUMBER() OVER (
                           PARTITION BY COALESCE(plan_file_path, 'null-' || id)
                           ORDER BY created_at_epoch DESC, id DESC
                       ) as rn
                FROM prompt_batches
                WHERE {where_clause}
            )
            SELECT id, session_id, prompt_number, user_prompt, started_at, ended_at,
                   status, activity_count, processed, classification, source_type,
                   plan_file_path, plan_content, created_at_epoch, plan_embedded
            FROM unique_plans
            WHERE rn = 1
            ORDER BY created_at_epoch {sort_order}
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
            ORDER BY created_at_epoch {sort_order}
            LIMIT ? OFFSET ?
        """
        params = base_params + [limit, offset]

    cursor = conn.execute(query, params)
    plans = [PromptBatch.from_row(row) for row in cursor.fetchall()]

    return plans, total


def get_batch_ids_for_reprocessing(
    store: ActivityStore,
    machine_id: str,
    *,
    mode: str = "all",
    session_id: str | None = None,
    start_epoch: float | None = None,
    end_epoch: float | None = None,
    importance_threshold: int | None = None,
) -> list[int]:
    """Get batch IDs eligible for reprocessing, filtered by source machine.

    Only returns batches where source_machine_id matches the given machine_id
    to prevent accidentally modifying teammates' imported data.

    Args:
        store: The ActivityStore instance.
        machine_id: Current machine identifier (only process own data).
        mode: Reprocessing mode - 'all', 'date_range', 'session', 'low_importance'.
        session_id: Required for 'session' mode.
        start_epoch: Required for 'date_range' mode.
        end_epoch: Required for 'date_range' mode.
        importance_threshold: For 'low_importance' mode (reprocess below this).

    Returns:
        List of prompt batch IDs eligible for reprocessing.

    Raises:
        ValueError: If required parameters are missing for the chosen mode,
            or if an invalid mode is specified.
        KeyError: If the specified session is not found or not owned by this machine.
    """
    conn = store._get_connection()

    if mode == "all":
        cursor = conn.execute(
            """
            SELECT id FROM prompt_batches
            WHERE source_machine_id = ?
              AND status = 'completed'
              AND source_type = 'user'
            ORDER BY created_at_epoch ASC
            """,
            (machine_id,),
        )
        return [row[0] for row in cursor.fetchall()]

    if mode == "date_range":
        if start_epoch is None or end_epoch is None:
            raise ValueError("date_range mode requires start_epoch and end_epoch")
        cursor = conn.execute(
            """
            SELECT id FROM prompt_batches
            WHERE source_machine_id = ?
              AND status = 'completed'
              AND created_at_epoch >= ?
              AND created_at_epoch <= ?
            ORDER BY created_at_epoch ASC
            """,
            (machine_id, start_epoch, end_epoch),
        )
        return [row[0] for row in cursor.fetchall()]

    if mode == "session":
        if not session_id:
            raise ValueError("session mode requires session_id")
        # Check session belongs to this machine
        cursor = conn.execute(
            "SELECT id FROM sessions WHERE id = ? AND source_machine_id = ?",
            (session_id, machine_id),
        )
        if not cursor.fetchone():
            raise KeyError(f"Session not found or not owned by this machine: {session_id}")
        cursor = conn.execute(
            """
            SELECT id FROM prompt_batches
            WHERE session_id = ?
              AND source_machine_id = ?
              AND status = 'completed'
            ORDER BY created_at_epoch ASC
            """,
            (session_id, machine_id),
        )
        return [row[0] for row in cursor.fetchall()]

    if mode == "low_importance":
        threshold = importance_threshold or 4
        cursor = conn.execute(
            """
            SELECT DISTINCT pb.id
            FROM prompt_batches pb
            JOIN memory_observations mo ON mo.prompt_batch_id = pb.id
            WHERE pb.source_machine_id = ?
              AND pb.status = 'completed'
              AND mo.importance < ?
            ORDER BY pb.created_at_epoch ASC
            """,
            (machine_id, threshold),
        )
        return [row[0] for row in cursor.fetchall()]

    valid_modes = "all, date_range, session, low_importance"
    raise ValueError(f"Invalid mode: {mode}. Use: {valid_modes}")


def get_unprocessed_prompt_batches(store: ActivityStore, limit: int = 10) -> list[PromptBatch]:
    """Get prompt batches that haven't been processed yet.

    Only returns batches owned by this machine to prevent background processing
    from creating cross-machine FK references (observations with this machine's
    source_machine_id referencing another machine's sessions).

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
          AND source_machine_id = ?
        ORDER BY created_at_epoch ASC
        LIMIT ?
        """,
        (store.machine_id, limit),
    )
    return [PromptBatch.from_row(row) for row in cursor.fetchall()]


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


def get_bulk_plan_counts(store: ActivityStore, session_ids: list[str]) -> dict[str, int]:
    """Count plan batches for multiple sessions in a single query.

    Args:
        store: The ActivityStore instance.
        session_ids: List of session IDs to count plans for.

    Returns:
        Dictionary mapping session_id -> plan count (only includes non-zero counts).
    """
    if not session_ids:
        return {}

    conn = store._get_connection()
    placeholders = ",".join("?" * len(session_ids))
    cursor = conn.execute(
        f"SELECT session_id, COUNT(*) as cnt "
        f"FROM prompt_batches "
        f"WHERE session_id IN ({placeholders}) "
        f"AND source_type = 'plan' AND plan_content IS NOT NULL "
        f"GROUP BY session_id",
        session_ids,
    )
    return {row["session_id"]: row["cnt"] for row in cursor.fetchall()}
