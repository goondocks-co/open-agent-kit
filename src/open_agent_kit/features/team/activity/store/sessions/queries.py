"""Session query operations.

Functions for listing, counting, and filtering sessions.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from open_agent_kit.features.team.activity.store.models import Session
from open_agent_kit.features.team.constants import (
    MIN_SESSION_ACTIVITIES,
    SESSION_STATUS_ACTIVE,
    SESSION_STATUS_COMPLETED,
)

if TYPE_CHECKING:
    from open_agent_kit.features.team.activity.store.core import ActivityStore

logger = logging.getLogger(__name__)


def get_unprocessed_sessions(store: ActivityStore, limit: int = 10) -> list[Session]:
    """Get sessions that haven't been processed yet.

    Only returns sessions owned by this machine to prevent background processing
    from generating summaries/titles for another machine's imported sessions.

    Args:
        store: The ActivityStore instance.
        limit: Maximum sessions to return.

    Returns:
        List of unprocessed Session objects.
    """
    conn = store._get_connection()
    cursor = conn.execute(
        f"""
        SELECT * FROM sessions
        WHERE processed = FALSE AND status = '{SESSION_STATUS_COMPLETED}'
          AND source_machine_id = ?
        ORDER BY created_at_epoch DESC
        LIMIT ?
        """,
        (store.machine_id, limit),
    )
    return [Session.from_row(row) for row in cursor.fetchall()]


def mark_session_processed(store: ActivityStore, session_id: str) -> None:
    """Mark session as processed by background worker."""
    with store._transaction() as conn:
        conn.execute(
            "UPDATE sessions SET processed = TRUE WHERE id = ?",
            (session_id,),
        )


def get_session_members(store: ActivityStore) -> list[str]:
    """Get distinct source_machine_id values from sessions.

    Returns:
        List of unique source_machine_id strings, ordered alphabetically.
    """
    conn = store._get_connection()
    cursor = conn.execute(
        "SELECT DISTINCT source_machine_id FROM sessions "
        "WHERE source_machine_id IS NOT NULL "
        "ORDER BY source_machine_id"
    )
    return [row[0] for row in cursor.fetchall()]


def count_sessions(
    store: ActivityStore,
    status: str | None = None,
    agent: str | None = None,
    member: str | None = None,
) -> int:
    """Count total sessions with optional status filter.

    Args:
        store: The ActivityStore instance.
        status: Optional status filter (e.g., 'active', 'completed').
        agent: Optional agent filter. Matches exact and model-agent labels
            containing the agent (e.g., ``gpt-5.3-codex`` matches ``codex``).
        member: Optional team member username filter. Matches all machine IDs
            for that username by extracting the username portion (everything
            before the last 7 characters: ``_`` + 6-char hash).

    Returns:
        Total number of sessions matching the filter.
    """
    conn = store._get_connection()
    conditions: list[str] = []
    params: list[Any] = []

    if status:
        conditions.append("status = ?")
        params.append(status)

    if agent:
        normalized_agent = agent.strip().lower()
        conditions.append("(LOWER(agent) = ? OR LOWER(agent) LIKE ?)")
        params.extend([normalized_agent, f"%{normalized_agent}%"])

    if member:
        conditions.append(
            "source_machine_id IS NOT NULL "
            "AND SUBSTR(source_machine_id, 1, LENGTH(source_machine_id) - 7) = ?"
        )
        params.append(member)

    query = "SELECT COUNT(*) FROM sessions"
    if conditions:
        query += f" WHERE {' AND '.join(conditions)}"

    cursor = conn.execute(query, params)
    row = cursor.fetchone()
    return row[0] if row else 0


def get_recent_sessions(
    store: ActivityStore,
    limit: int = 10,
    offset: int = 0,
    status: str | None = None,
    agent: str | None = None,
    sort: str = "last_activity",
    member: str | None = None,
) -> list[Session]:
    """Get recent sessions with pagination support.

    Args:
        store: The ActivityStore instance.
        limit: Maximum sessions to return.
        offset: Number of sessions to skip (for pagination).
        status: Optional status filter (e.g., 'active', 'completed').
        agent: Optional agent filter. Matches exact and model-agent labels
            containing the agent (e.g., ``gpt-5.3-codex`` matches ``codex``).
        sort: Sort order - 'last_activity' (default), 'created', or 'status'.
        member: Optional team member username filter. Matches all machine IDs
            for that username by extracting the username portion (everything
            before the last 7 characters: ``_`` + 6-char hash).

    Returns:
        List of recent Session objects.
    """
    conn = store._get_connection()
    params: list[Any] = []
    conditions: list[str] = []
    if status:
        conditions.append("s.status = ?")
        params.append(status)
    if agent:
        normalized_agent = agent.strip().lower()
        conditions.append("(LOWER(s.agent) = ? OR LOWER(s.agent) LIKE ?)")
        params.extend([normalized_agent, f"%{normalized_agent}%"])
    if member:
        conditions.append(
            "s.source_machine_id IS NOT NULL "
            "AND SUBSTR(s.source_machine_id, 1, LENGTH(s.source_machine_id) - 7) = ?"
        )
        params.append(member)

    if sort == "last_activity":
        # Sort by most recent activity, falling back to session start time
        # This ensures resumed sessions appear at the top
        query = """
            SELECT s.*, COALESCE(MAX(a.timestamp_epoch), s.created_at_epoch) as sort_key
            FROM sessions s
            LEFT JOIN activities a ON s.id = a.session_id
        """
        if conditions:
            query += f" WHERE {' AND '.join(conditions)}"
        query += " GROUP BY s.id ORDER BY sort_key DESC LIMIT ? OFFSET ?"
    elif sort == "status":
        # Active sessions first, then by creation time
        query = "SELECT * FROM sessions s"
        if conditions:
            query += f" WHERE {' AND '.join(conditions)}"
        query += f" ORDER BY CASE WHEN status = '{SESSION_STATUS_ACTIVE}' THEN 0 ELSE 1 END, created_at_epoch DESC LIMIT ? OFFSET ?"
    else:
        # Default: sort by created_at_epoch (session start time)
        query = "SELECT * FROM sessions s"
        if conditions:
            query += f" WHERE {' AND '.join(conditions)}"
        query += " ORDER BY created_at_epoch DESC LIMIT ? OFFSET ?"

    params.extend([limit, offset])
    cursor = conn.execute(query, params)
    return [Session.from_row(row) for row in cursor.fetchall()]


def get_sessions_needing_titles(store: ActivityStore, limit: int = 10) -> list[Session]:
    """Get sessions that need titles generated.

    Returns sessions that:
    - Don't have a title yet
    - Have at least one prompt batch (so we can generate a title)
    - Are either completed or have been active for at least 5 minutes

    Args:
        store: The ActivityStore instance.
        limit: Maximum sessions to return.

    Returns:
        List of Session objects needing titles.
    """
    conn = store._get_connection()

    # Get sessions without titles that have prompt batches
    # Only process sessions that are either completed OR have been active 5+ minutes
    five_minutes_ago = int(time.time()) - 300
    cursor = conn.execute(
        f"""
        SELECT s.* FROM sessions s
        WHERE s.title IS NULL
        AND (s.title_manually_edited IS NULL OR s.title_manually_edited = FALSE)
        AND s.source_machine_id = ?
        AND EXISTS (SELECT 1 FROM prompt_batches pb WHERE pb.session_id = s.id)
        AND (s.status = '{SESSION_STATUS_COMPLETED}' OR s.created_at_epoch < ?)
        ORDER BY s.created_at_epoch DESC
        LIMIT ?
        """,
        (store.machine_id, five_minutes_ago, limit),
    )
    return [Session.from_row(row) for row in cursor.fetchall()]


def get_sessions_missing_summaries(
    store: ActivityStore, limit: int = 10, min_activities: int | None = None
) -> list[Session]:
    """Get completed sessions missing a summary.

    Only returns sessions that meet the quality threshold (>= min_activities),
    since low-quality sessions will never be summarized and would otherwise
    cause an infinite retry loop every background tick.

    Args:
        store: The ActivityStore instance.
        limit: Maximum sessions to return.
        min_activities: Minimum activities threshold. Defaults to MIN_SESSION_ACTIVITIES.

    Returns:
        List of Session objects missing summaries.
    """
    if min_activities is None:
        min_activities = MIN_SESSION_ACTIVITIES

    conn = store._get_connection()
    cursor = conn.execute(
        f"""
        SELECT s.* FROM sessions s
        WHERE s.status = '{SESSION_STATUS_COMPLETED}'
        AND s.source_machine_id = ?
        AND s.summary IS NULL
        AND (SELECT COUNT(*) FROM activities a WHERE a.session_id = s.id) >= ?
        ORDER BY s.created_at_epoch DESC
        LIMIT ?
        """,
        (store.machine_id, min_activities, limit),
    )
    return [Session.from_row(row) for row in cursor.fetchall()]


def get_completed_sessions(
    store: ActivityStore,
    *,
    min_activities: int | None = None,
    limit: int = 500,
) -> list[Session]:
    """Get completed sessions, optionally filtered by minimum activity count.

    Unlike ``get_sessions_missing_summaries``, this returns ALL completed
    sessions regardless of whether they already have summaries. Used by
    the devtools regenerate-summaries endpoint in force mode.

    Args:
        store: The ActivityStore instance.
        limit: Maximum sessions to return.
        min_activities: If provided, only return sessions with at least
            this many activities.

    Returns:
        List of completed Session objects, newest first.
    """
    conn = store._get_connection()

    if min_activities is not None:
        cursor = conn.execute(
            f"""
            SELECT s.* FROM sessions s
            WHERE s.status = '{SESSION_STATUS_COMPLETED}'
            AND s.source_machine_id = ?
            AND (SELECT COUNT(*) FROM activities a WHERE a.session_id = s.id) >= ?
            ORDER BY s.created_at_epoch DESC
            LIMIT ?
            """,
            (store.machine_id, min_activities, limit),
        )
    else:
        cursor = conn.execute(
            f"""
            SELECT s.* FROM sessions s
            WHERE s.status = '{SESSION_STATUS_COMPLETED}'
            AND s.source_machine_id = ?
            ORDER BY s.created_at_epoch DESC
            LIMIT ?
            """,
            (store.machine_id, limit),
        )

    return [Session.from_row(row) for row in cursor.fetchall()]


def count_session_activities(store: ActivityStore, session_id: str) -> int:
    """Count total activities for a session.

    Args:
        store: The ActivityStore instance.
        session_id: Session to count activities for.

    Returns:
        Number of activities in the session.
    """
    conn = store._get_connection()
    cursor = conn.execute(
        "SELECT COUNT(*) FROM activities WHERE session_id = ?",
        (session_id,),
    )
    row = cursor.fetchone()
    return row[0] if row else 0


def is_session_sufficient(
    store: ActivityStore,
    session_id: str,
    min_activities: int | None = None,
) -> bool:
    """Check if a session meets the quality threshold for summarization.

    Sessions that don't meet this threshold will not be titled, summarized,
    or embedded. They will be cleaned up after the stale timeout.

    Args:
        store: The ActivityStore instance.
        session_id: Session ID to check.
        min_activities: Minimum activities threshold. Defaults to MIN_SESSION_ACTIVITIES.
            Pass a configured value from session_quality.min_activities if available.

    Returns:
        True if session has >= min_activities tool calls.
    """
    if min_activities is None:
        min_activities = MIN_SESSION_ACTIVITIES

    conn = store._get_connection()
    cursor = conn.execute(
        "SELECT COUNT(*) FROM activities WHERE session_id = ?",
        (session_id,),
    )
    row = cursor.fetchone()
    activity_count = row[0] if row else 0
    return activity_count >= min_activities


def count_sessions_with_summaries(store: ActivityStore) -> int:
    """Count sessions that have a summary.

    Used to report how many sessions will be re-embedded.

    Args:
        store: The ActivityStore instance.

    Returns:
        Number of sessions with a non-NULL summary.
    """
    conn = store._get_connection()
    cursor = conn.execute("SELECT COUNT(*) FROM sessions WHERE summary IS NOT NULL")
    result = cursor.fetchone()
    return result[0] or 0 if result else 0


def list_sessions_with_summaries(
    store: ActivityStore, limit: int = 5, source_machine_id: str | None = None
) -> list[Session]:
    """List recent sessions that have a non-NULL summary.

    Used by context injection to provide recent session summaries to agents.

    Args:
        store: The ActivityStore instance.
        limit: Maximum sessions to return.
        source_machine_id: Optional machine filter. Defaults to store.machine_id.

    Returns:
        List of Session objects with summaries, most recent first.
    """
    machine_id = source_machine_id or store.machine_id
    conn = store._get_connection()
    cursor = conn.execute(
        """
        SELECT * FROM sessions
        WHERE summary IS NOT NULL
          AND source_machine_id = ?
        ORDER BY summary_updated_at DESC, created_at_epoch DESC
        LIMIT ?
        """,
        (machine_id, limit),
    )
    return [Session.from_row(row) for row in cursor.fetchall()]
