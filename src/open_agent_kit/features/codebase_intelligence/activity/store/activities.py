"""Activity operations for activity store.

Functions for adding, retrieving, and searching activities.
"""

from __future__ import annotations

import logging
import sqlite3
from typing import TYPE_CHECKING, Any

from open_agent_kit.features.codebase_intelligence.activity.store.models import Activity

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.store.core import ActivityStore

logger = logging.getLogger(__name__)


def add_activity(store: ActivityStore, activity: Activity) -> int:
    """Add a tool execution activity.

    Args:
        store: The ActivityStore instance.
        activity: Activity to store.

    Returns:
        ID of inserted activity.
    """
    # Set source_machine_id if not already set
    if activity.source_machine_id is None:
        activity.source_machine_id = store.machine_id

    with store._transaction() as conn:
        row = activity.to_row()
        cursor = conn.execute(
            """
            INSERT INTO activities (session_id, prompt_batch_id, tool_name, tool_input, tool_output_summary,
                                   file_path, files_affected, duration_ms, success,
                                   error_message, timestamp, timestamp_epoch, processed, observation_id,
                                   source_machine_id, content_hash)
            VALUES (:session_id, :prompt_batch_id, :tool_name, :tool_input, :tool_output_summary,
                    :file_path, :files_affected, :duration_ms, :success,
                    :error_message, :timestamp, :timestamp_epoch, :processed, :observation_id,
                    :source_machine_id, :content_hash)
            """,
            row,
        )
        # Update session tool count
        conn.execute(
            "UPDATE sessions SET tool_count = tool_count + 1 WHERE id = ?",
            (activity.session_id,),
        )
        # Update prompt batch activity count if linked
        if activity.prompt_batch_id:
            conn.execute(
                "UPDATE prompt_batches SET activity_count = activity_count + 1 WHERE id = ?",
                (activity.prompt_batch_id,),
            )
        # Invalidate cache for this session
        store._invalidate_stats_cache(activity.session_id)
        return cursor.lastrowid or 0


def flush_activity_buffer(store: ActivityStore) -> list[int]:
    """Flush any buffered activities to the database.

    Args:
        store: The ActivityStore instance.

    Returns:
        List of inserted activity IDs.
    """
    with store._buffer_lock:
        if not store._activity_buffer:
            return []
        activities = store._activity_buffer[:]
        store._activity_buffer.clear()

    if activities:
        count = len(activities)
        ids = add_activities(store, activities)
        logger.debug(f"Flushed {count} buffered activities (bulk insert)")
        return ids
    return []


def add_activity_buffered(
    store: ActivityStore, activity: Activity, force_flush: bool = False
) -> int | None:
    """Add an activity with automatic batching.

    Activities are buffered and flushed when the buffer reaches _buffer_size.
    This provides better performance for rapid tool execution while maintaining
    low latency for debugging.

    Args:
        store: The ActivityStore instance.
        activity: Activity to add.
        force_flush: If True, flush buffer immediately after adding.

    Returns:
        Activity ID if flushed immediately, None if buffered.
    """
    with store._buffer_lock:
        store._activity_buffer.append(activity)
        should_flush = len(store._activity_buffer) >= store._buffer_size or force_flush

        if should_flush:
            activities = store._activity_buffer[:]
            store._activity_buffer.clear()
        else:
            activities = None

    if activities:
        count = len(activities)
        ids = add_activities(store, activities)
        logger.debug(f"Bulk inserted {count} activities (buffer auto-flush)")
        # Return the ID of the activity we just added (last in batch)
        return ids[-1] if ids else None
    return None


def add_activities(store: ActivityStore, activities: list[Activity]) -> list[int]:
    """Add multiple activities in a single transaction (bulk insert).

    This method is more efficient than calling add_activity() multiple times
    as it uses a single transaction and batches count updates.

    Args:
        store: The ActivityStore instance.
        activities: List of activities to insert.

    Returns:
        List of inserted activity IDs.
    """
    if not activities:
        return []

    # Set source_machine_id for all activities that don't have it
    machine_id = store.machine_id
    for activity in activities:
        if activity.source_machine_id is None:
            activity.source_machine_id = machine_id

    count = len(activities)
    ids: list[int] = []
    session_updates: dict[str, int] = {}  # session_id -> count delta
    batch_updates: dict[int, int] = {}  # batch_id -> count delta
    affected_sessions: set[str] = set()

    logger.debug(f"Bulk inserting {count} activities in single transaction")

    try:
        ids, session_updates, batch_updates, affected_sessions = _bulk_insert_transaction(
            store, activities
        )
    except sqlite3.IntegrityError:
        # FK constraint failure in batch mode — fall back to individual inserts
        # so one bad activity doesn't block the whole buffer.
        logger.debug("Bulk insert hit IntegrityError, falling back to individual inserts")
        ids, session_updates, batch_updates, affected_sessions = _individual_insert_fallback(
            store, activities
        )

    # Invalidate cache for all affected sessions
    for session_id in affected_sessions:
        store._invalidate_stats_cache(session_id)

    logger.debug(
        f"Bulk insert complete: {len(ids)} activities inserted for {len(affected_sessions)} sessions"
    )
    return ids


_INSERT_SQL = """
    INSERT INTO activities (session_id, prompt_batch_id, tool_name, tool_input, tool_output_summary,
                           file_path, files_affected, duration_ms, success,
                           error_message, timestamp, timestamp_epoch, processed, observation_id,
                           source_machine_id, content_hash)
    VALUES (:session_id, :prompt_batch_id, :tool_name, :tool_input, :tool_output_summary,
            :file_path, :files_affected, :duration_ms, :success,
            :error_message, :timestamp, :timestamp_epoch, :processed, :observation_id,
            :source_machine_id, :content_hash)
"""


def _track_activity(
    activity: Activity,
    cursor_lastrowid: int,
    ids: list[int],
    session_updates: dict[str, int],
    batch_updates: dict[int, int],
    affected_sessions: set[str],
) -> None:
    """Accumulate bookkeeping for a successfully inserted activity."""
    ids.append(cursor_lastrowid or 0)
    session_updates[activity.session_id] = session_updates.get(activity.session_id, 0) + 1
    affected_sessions.add(activity.session_id)
    if activity.prompt_batch_id:
        batch_updates[activity.prompt_batch_id] = batch_updates.get(activity.prompt_batch_id, 0) + 1


def _apply_count_updates(
    conn: sqlite3.Connection,
    session_updates: dict[str, int],
    batch_updates: dict[int, int],
) -> None:
    """Bulk-update session and batch counts inside an open transaction."""
    for session_id, delta in session_updates.items():
        conn.execute(
            "UPDATE sessions SET tool_count = tool_count + ? WHERE id = ?",
            (delta, session_id),
        )
    for batch_id, delta in batch_updates.items():
        conn.execute(
            "UPDATE prompt_batches SET activity_count = activity_count + ? WHERE id = ?",
            (delta, batch_id),
        )


def _bulk_insert_transaction(
    store: ActivityStore,
    activities: list[Activity],
) -> tuple[list[int], dict[str, int], dict[int, int], set[str]]:
    """Insert all activities in one transaction (fast path)."""
    ids: list[int] = []
    session_updates: dict[str, int] = {}
    batch_updates: dict[int, int] = {}
    affected_sessions: set[str] = set()

    with store._transaction() as conn:
        for activity in activities:
            row = activity.to_row()
            cursor = conn.execute(_INSERT_SQL, row)
            _track_activity(
                activity,
                cursor.lastrowid or 0,
                ids,
                session_updates,
                batch_updates,
                affected_sessions,
            )
        _apply_count_updates(conn, session_updates, batch_updates)

    return ids, session_updates, batch_updates, affected_sessions


def _individual_insert_fallback(
    store: ActivityStore,
    activities: list[Activity],
) -> tuple[list[int], dict[str, int], dict[int, int], set[str]]:
    """Insert activities one-by-one, skipping any that violate FK constraints."""
    ids: list[int] = []
    session_updates: dict[str, int] = {}
    batch_updates: dict[int, int] = {}
    affected_sessions: set[str] = set()
    skipped = 0

    for activity in activities:
        try:
            with store._transaction() as conn:
                row = activity.to_row()
                cursor = conn.execute(_INSERT_SQL, row)
                _track_activity(
                    activity,
                    cursor.lastrowid or 0,
                    ids,
                    session_updates,
                    batch_updates,
                    affected_sessions,
                )
        except sqlite3.IntegrityError:
            skipped += 1
            logger.debug(
                f"Skipped activity with FK violation: "
                f"session={activity.session_id} batch={activity.prompt_batch_id} "
                f"tool={activity.tool_name}"
            )

    # Apply count updates for successfully inserted activities
    if session_updates or batch_updates:
        with store._transaction() as conn:
            _apply_count_updates(conn, session_updates, batch_updates)

    if skipped:
        logger.warning(f"Skipped {skipped}/{len(activities)} activities due to FK violations")

    return ids, session_updates, batch_updates, affected_sessions


def get_session_activities(
    store: ActivityStore,
    session_id: str,
    tool_name: str | None = None,
    limit: int | None = None,
) -> list[Activity]:
    """Get activities for a session.

    Args:
        store: The ActivityStore instance.
        session_id: Session to query.
        tool_name: Optional filter by tool name.
        limit: Maximum activities to return.

    Returns:
        List of Activity objects.
    """
    conn = store._get_connection()

    query = "SELECT * FROM activities WHERE session_id = ?"
    params: list[Any] = [session_id]

    if tool_name:
        query += " AND tool_name = ?"
        params.append(tool_name)

    query += " ORDER BY timestamp_epoch ASC"

    if limit:
        query += " LIMIT ?"
        params.append(limit)

    cursor = conn.execute(query, params)
    return [Activity.from_row(row) for row in cursor.fetchall()]


def get_unprocessed_activities(
    store: ActivityStore,
    session_id: str | None = None,
    limit: int = 100,
) -> list[Activity]:
    """Get activities that haven't been processed yet.

    Only returns activities owned by this machine to prevent background
    processing from touching imported data.

    Args:
        store: The ActivityStore instance.
        session_id: Optional session filter.
        limit: Maximum activities to return.

    Returns:
        List of unprocessed Activity objects.
    """
    conn = store._get_connection()

    if session_id:
        cursor = conn.execute(
            """
            SELECT * FROM activities
            WHERE processed = FALSE AND session_id = ?
              AND source_machine_id = ?
            ORDER BY timestamp_epoch ASC
            LIMIT ?
            """,
            (session_id, store.machine_id, limit),
        )
    else:
        cursor = conn.execute(
            """
            SELECT * FROM activities
            WHERE processed = FALSE
              AND source_machine_id = ?
            ORDER BY timestamp_epoch ASC
            LIMIT ?
            """,
            (store.machine_id, limit),
        )

    return [Activity.from_row(row) for row in cursor.fetchall()]


def mark_activities_processed(
    store: ActivityStore,
    activity_ids: list[int],
    observation_id: str | None = None,
) -> None:
    """Mark activities as processed.

    Args:
        store: The ActivityStore instance.
        activity_ids: Activities to mark.
        observation_id: Optional observation ID to link.
    """
    if not activity_ids:
        return

    with store._transaction() as conn:
        placeholders = ",".join("?" * len(activity_ids))
        params: list[str | int | None] = [observation_id, *activity_ids]
        conn.execute(
            f"""
            UPDATE activities
            SET processed = TRUE, observation_id = ?
            WHERE id IN ({placeholders})
            """,
            params,
        )


def search_activities(
    store: ActivityStore,
    query: str,
    session_id: str | None = None,
    limit: int = 20,
) -> list[Activity]:
    """Full-text search across activities.

    Args:
        store: The ActivityStore instance.
        query: Search query (FTS5 syntax).
        session_id: Optional session filter.
        limit: Maximum results.

    Returns:
        List of matching Activity objects.
    """
    conn = store._get_connection()

    if session_id:
        cursor = conn.execute(
            """
            SELECT a.* FROM activities a
            JOIN activities_fts fts ON a.id = fts.rowid
            WHERE activities_fts MATCH ? AND a.session_id = ?
            ORDER BY rank
            LIMIT ?
            """,
            (query, session_id, limit),
        )
    else:
        cursor = conn.execute(
            """
            SELECT a.* FROM activities a
            JOIN activities_fts fts ON a.id = fts.rowid
            WHERE activities_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (query, limit),
        )

    return [Activity.from_row(row) for row in cursor.fetchall()]
