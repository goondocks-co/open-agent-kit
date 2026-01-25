"""Session operations for activity store.

Functions for creating, retrieving, and managing sessions.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any

from open_agent_kit.features.codebase_intelligence.activity.store.models import Session

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.store.core import ActivityStore

logger = logging.getLogger(__name__)


def create_session(store: ActivityStore, session_id: str, agent: str, project_root: str) -> Session:
    """Create a new session record.

    Args:
        store: The ActivityStore instance.
        session_id: Unique session identifier.
        agent: Agent name (claude, cursor, etc.).
        project_root: Project root directory.

    Returns:
        Created Session object.
    """
    session = Session(
        id=session_id,
        agent=agent,
        project_root=project_root,
        started_at=datetime.now(),
    )

    with store._transaction() as conn:
        row = session.to_row()
        conn.execute(
            """
            INSERT INTO sessions (id, agent, project_root, started_at, status,
                                  prompt_count, tool_count, processed, summary, created_at_epoch)
            VALUES (:id, :agent, :project_root, :started_at, :status,
                    :prompt_count, :tool_count, :processed, :summary, :created_at_epoch)
            """,
            row,
        )

    logger.debug(f"Created session {session_id} for agent {agent}")
    return session


def get_session(store: ActivityStore, session_id: str) -> Session | None:
    """Get session by ID."""
    conn = store._get_connection()
    cursor = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
    row = cursor.fetchone()
    return Session.from_row(row) if row else None


def get_or_create_session(
    store: ActivityStore, session_id: str, agent: str, project_root: str
) -> tuple[Session, bool]:
    """Get existing session or create new one.

    Handles session resumption gracefully - if session exists, returns it.
    If it was previously ended, reactivates it.
    Idempotent: handles duplicate hook calls and race conditions safely.

    Args:
        store: The ActivityStore instance.
        session_id: Unique session identifier.
        agent: Agent name (claude, cursor, etc.).
        project_root: Project root directory.

    Returns:
        Tuple of (Session, created) where created is True if new session.
    """
    existing = get_session(store, session_id)
    if existing:
        # Reactivate if previously ended
        if existing.status == "completed":
            with store._transaction() as conn:
                conn.execute(
                    """
                    UPDATE sessions
                    SET status = 'active', ended_at = NULL
                    WHERE id = ?
                    """,
                    (session_id,),
                )
            existing.status = "active"
            existing.ended_at = None
            logger.debug(f"Reactivated session {session_id}")
        return existing, False

    # Create new session - handle race condition if another hook created it concurrently
    try:
        session = create_session(store, session_id, agent, project_root)
        return session, True
    except sqlite3.IntegrityError:
        # Race condition: another hook created the session between our check and insert
        # This is safe - just return the existing session
        logger.debug(
            f"Race condition detected: session {session_id} was created concurrently. "
            "Returning existing session."
        )
        existing = get_session(store, session_id)
        if existing:
            return existing, False
        # If we still can't find it, something went wrong - re-raise
        raise


def end_session(store: ActivityStore, session_id: str, summary: str | None = None) -> None:
    """Mark session as completed.

    Args:
        store: The ActivityStore instance.
        session_id: Session to end.
        summary: Optional session summary.
    """
    with store._transaction() as conn:
        conn.execute(
            """
            UPDATE sessions
            SET ended_at = ?, status = 'completed', summary = ?
            WHERE id = ?
            """,
            (datetime.now().isoformat(), summary, session_id),
        )
    logger.debug(f"Ended session {session_id}")


def update_session_title(store: ActivityStore, session_id: str, title: str) -> None:
    """Update the session title.

    Args:
        store: The ActivityStore instance.
        session_id: Session to update.
        title: LLM-generated short title for the session.
    """
    with store._transaction() as conn:
        conn.execute(
            "UPDATE sessions SET title = ? WHERE id = ?",
            (title, session_id),
        )
    logger.debug(f"Updated session {session_id} title: {title[:50]}...")


def reactivate_session_if_needed(store: ActivityStore, session_id: str) -> bool:
    """Reactivate a session if it's currently completed.

    Called when new activity arrives for a session that may have been
    auto-closed by stale session recovery. This enables sessions to
    seamlessly resume when Claude Code sends new prompts after a gap.

    This is performant: the UPDATE only affects completed sessions and
    uses the primary key index. For active sessions, it's a no-op.

    Args:
        store: The ActivityStore instance.
        session_id: Session to potentially reactivate.

    Returns:
        True if session was reactivated, False if already active or not found.
    """
    with store._transaction() as conn:
        cursor = conn.execute(
            """
            UPDATE sessions
            SET status = 'active', ended_at = NULL
            WHERE id = ? AND status = 'completed'
            """,
            (session_id,),
        )
        reactivated = cursor.rowcount > 0

    if reactivated:
        logger.info(f"Reactivated completed session {session_id} for new activity")

    return reactivated


def ensure_session_exists(store: ActivityStore, session_id: str, agent: str) -> bool:
    """Create session if it doesn't exist (for deleted session recovery).

    Called when a prompt arrives for a session that was previously deleted
    (e.g., empty abandoned session cleaned up by recover_stale_sessions).

    Args:
        store: The ActivityStore instance.
        session_id: Session ID to check/create.
        agent: Agent name for session creation.

    Returns:
        True if session was created, False if already existed.
    """
    conn = store._get_connection()
    cursor = conn.execute("SELECT id FROM sessions WHERE id = ?", (session_id,))
    if cursor.fetchone():
        return False

    # Session was deleted - recreate with minimal info
    # project_root derived from db_path: .oak/ci/activities.db -> project root
    project_root = str(store.db_path.parent.parent.parent)
    create_session(store, session_id, agent, project_root)
    logger.info(f"Recreated deleted session {session_id} for new prompt (agent={agent})")
    return True


def increment_prompt_count(store: ActivityStore, session_id: str) -> None:
    """Increment the prompt count for a session."""
    with store._transaction() as conn:
        conn.execute(
            "UPDATE sessions SET prompt_count = prompt_count + 1 WHERE id = ?",
            (session_id,),
        )


def get_unprocessed_sessions(store: ActivityStore, limit: int = 10) -> list[Session]:
    """Get sessions that haven't been processed yet.

    Args:
        store: The ActivityStore instance.
        limit: Maximum sessions to return.

    Returns:
        List of unprocessed Session objects.
    """
    conn = store._get_connection()
    cursor = conn.execute(
        """
        SELECT * FROM sessions
        WHERE processed = FALSE AND status = 'completed'
        ORDER BY created_at_epoch DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [Session.from_row(row) for row in cursor.fetchall()]


def mark_session_processed(store: ActivityStore, session_id: str) -> None:
    """Mark session as processed by background worker."""
    with store._transaction() as conn:
        conn.execute(
            "UPDATE sessions SET processed = TRUE WHERE id = ?",
            (session_id,),
        )


def get_recent_sessions(
    store: ActivityStore,
    limit: int = 10,
    offset: int = 0,
    status: str | None = None,
) -> list[Session]:
    """Get recent sessions with pagination support.

    Args:
        store: The ActivityStore instance.
        limit: Maximum sessions to return.
        offset: Number of sessions to skip (for pagination).
        status: Optional status filter (e.g., 'active', 'completed').

    Returns:
        List of recent Session objects.
    """
    conn = store._get_connection()

    query = "SELECT * FROM sessions"
    params: list[Any] = []

    if status:
        query += " WHERE status = ?"
        params.append(status)

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
        """
        SELECT s.* FROM sessions s
        WHERE s.title IS NULL
        AND EXISTS (SELECT 1 FROM prompt_batches pb WHERE pb.session_id = s.id)
        AND (s.status = 'completed' OR s.created_at_epoch < ?)
        ORDER BY s.created_at_epoch DESC
        LIMIT ?
        """,
        (five_minutes_ago, limit),
    )
    return [Session.from_row(row) for row in cursor.fetchall()]


def recover_stale_sessions(
    store: ActivityStore, timeout_seconds: int = 3600
) -> tuple[list[str], list[str]]:
    """Auto-end or delete sessions that have been inactive for too long.

    This handles cases where the SessionEnd hook didn't fire (crash, network
    disconnect, user closed terminal without proper exit).

    A session is considered stale if:
    - It has activities and the most recent activity is older than timeout_seconds
    - It has NO activities and was created more than timeout_seconds ago

    Sessions with prompt batches are marked as 'completed'.
    Empty sessions (no prompt batches) are deleted entirely to avoid clutter.

    Args:
        store: The ActivityStore instance.
        timeout_seconds: Sessions inactive longer than this are auto-ended.

    Returns:
        Tuple of (recovered_ids, deleted_ids) for state synchronization.
        - recovered_ids: Sessions marked as 'completed' (had prompt batches)
        - deleted_ids: Sessions deleted (were empty)
    """
    # Import here to avoid circular imports
    from open_agent_kit.features.codebase_intelligence.activity.store.delete import (
        delete_session,
    )

    cutoff_epoch = time.time() - timeout_seconds

    # Find active sessions with no recent activity, including their prompt count
    # IMPORTANT: For sessions with no activities, check created_at_epoch
    # to avoid marking brand new sessions as stale
    conn = store._get_connection()
    cursor = conn.execute(
        """
        SELECT s.id, MAX(a.timestamp_epoch) as last_activity, s.created_at_epoch,
               s.prompt_count
        FROM sessions s
        LEFT JOIN activities a ON s.id = a.session_id
        WHERE s.status = 'active'
        GROUP BY s.id
        HAVING (last_activity IS NOT NULL AND last_activity < ?)
            OR (last_activity IS NULL AND s.created_at_epoch < ?)
        """,
        (cutoff_epoch, cutoff_epoch),
    )
    stale_sessions = [(row[0], row[1], row[2], row[3] or 0) for row in cursor.fetchall()]

    if not stale_sessions:
        return [], []

    recovered_ids = []
    deleted_ids = []
    for session_id, _last_activity, _created_at, prompt_count in stale_sessions:
        if prompt_count == 0:
            # Empty session - delete it entirely
            delete_session(store, session_id)
            deleted_ids.append(session_id)
        else:
            # Non-empty session - mark as completed
            with store._transaction() as conn:
                conn.execute(
                    """
                    UPDATE sessions
                    SET status = 'completed', ended_at = ?
                    WHERE id = ? AND status = 'active'
                    """,
                    (datetime.now().isoformat(), session_id),
                )
            recovered_ids.append(session_id)

    if recovered_ids:
        logger.info(
            f"Recovered {len(recovered_ids)} stale sessions "
            f"(inactive > {timeout_seconds}s): {[s[:8] for s in recovered_ids]}"
        )
    if deleted_ids:
        logger.info(
            f"Deleted {len(deleted_ids)} empty stale sessions "
            f"(inactive > {timeout_seconds}s): {[s[:8] for s in deleted_ids]}"
        )

    return recovered_ids, deleted_ids
