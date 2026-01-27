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
from open_agent_kit.features.codebase_intelligence.daemon.models import MemoryType

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.store.core import ActivityStore

logger = logging.getLogger(__name__)


def create_session(
    store: ActivityStore,
    session_id: str,
    agent: str,
    project_root: str,
    parent_session_id: str | None = None,
    parent_session_reason: str | None = None,
) -> Session:
    """Create a new session record.

    Args:
        store: The ActivityStore instance.
        session_id: Unique session identifier.
        agent: Agent name (claude, cursor, etc.).
        project_root: Project root directory.
        parent_session_id: Optional parent session ID (for session linking).
        parent_session_reason: Why linked: 'clear', 'compact', 'inferred'.

    Returns:
        Created Session object.
    """
    # Import here to avoid circular imports
    from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
        get_machine_identifier,
    )

    session = Session(
        id=session_id,
        agent=agent,
        project_root=project_root,
        started_at=datetime.now(),
        parent_session_id=parent_session_id,
        parent_session_reason=parent_session_reason,
        source_machine_id=get_machine_identifier(),
    )

    with store._transaction() as conn:
        row = session.to_row()
        conn.execute(
            """
            INSERT INTO sessions (id, agent, project_root, started_at, status,
                                  prompt_count, tool_count, processed, summary, created_at_epoch,
                                  parent_session_id, parent_session_reason, source_machine_id)
            VALUES (:id, :agent, :project_root, :started_at, :status,
                    :prompt_count, :tool_count, :processed, :summary, :created_at_epoch,
                    :parent_session_id, :parent_session_reason, :source_machine_id)
            """,
            row,
        )

    if parent_session_id:
        logger.debug(
            f"Created session {session_id} for agent {agent} "
            f"(parent={parent_session_id[:8]}..., reason={parent_session_reason})"
        )
    else:
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


def update_session_summary(store: ActivityStore, session_id: str, summary: str) -> None:
    """Update the session summary.

    Args:
        store: The ActivityStore instance.
        session_id: Session to update.
        summary: LLM-generated session summary.
    """
    with store._transaction() as conn:
        conn.execute(
            "UPDATE sessions SET summary = ? WHERE id = ?",
            (summary, session_id),
        )
    logger.debug(f"Updated session {session_id} summary: {summary[:50]}...")


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
    sort: str = "last_activity",
) -> list[Session]:
    """Get recent sessions with pagination support.

    Args:
        store: The ActivityStore instance.
        limit: Maximum sessions to return.
        offset: Number of sessions to skip (for pagination).
        status: Optional status filter (e.g., 'active', 'completed').
        sort: Sort order - 'last_activity' (default), 'created', or 'status'.

    Returns:
        List of recent Session objects.
    """
    conn = store._get_connection()
    params: list[Any] = []

    if sort == "last_activity":
        # Sort by most recent activity, falling back to session start time
        # This ensures resumed sessions appear at the top
        query = """
            SELECT s.*, COALESCE(MAX(a.timestamp_epoch), s.created_at_epoch) as sort_key
            FROM sessions s
            LEFT JOIN activities a ON s.id = a.session_id
        """
        if status:
            query += " WHERE s.status = ?"
            params.append(status)
        query += " GROUP BY s.id ORDER BY sort_key DESC LIMIT ? OFFSET ?"
    elif sort == "status":
        # Active sessions first, then by creation time
        query = "SELECT * FROM sessions"
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY CASE WHEN status = 'active' THEN 0 ELSE 1 END, created_at_epoch DESC LIMIT ? OFFSET ?"
    else:
        # Default: sort by created_at_epoch (session start time)
        query = "SELECT * FROM sessions"
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


def get_sessions_missing_summaries(store: ActivityStore, limit: int = 10) -> list[Session]:
    """Get completed sessions missing a session_summary memory.

    Args:
        store: The ActivityStore instance.
        limit: Maximum sessions to return.

    Returns:
        List of Session objects missing summaries.
    """
    conn = store._get_connection()
    cursor = conn.execute(
        """
        SELECT s.* FROM sessions s
        WHERE s.status = 'completed'
        AND NOT EXISTS (
            SELECT 1 FROM memory_observations m
            WHERE m.session_id = s.id AND m.memory_type = ?
        )
        ORDER BY s.created_at_epoch DESC
        LIMIT ?
        """,
        (MemoryType.SESSION_SUMMARY.value, limit),
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


def find_just_ended_session(
    store: ActivityStore,
    agent: str,
    project_root: str,
    exclude_session_id: str,
    new_session_started_at: datetime,
    max_gap_seconds: int = 5,
) -> str | None:
    """Find a session that just ended, suitable for parent linking.

    Used when source="clear" to link the new session to the planning session
    that just ended. Looks for ENDED sessions only to avoid false positives
    from concurrent active sessions.

    The 5-second default is based on data analysis showing:
    - Most transitions: 0.04-0.12 seconds
    - Slowest observed: ~8 seconds
    - No transitions in 10s-5min range

    Args:
        store: The ActivityStore instance.
        agent: Agent name to match.
        project_root: Project root to match.
        exclude_session_id: Session ID to exclude (the new session).
        new_session_started_at: When the new session started.
        max_gap_seconds: Maximum gap between end and start (default 5s).

    Returns:
        Parent session ID if found, None otherwise.
    """
    conn = store._get_connection()

    # Find the most recent session that:
    # - Is NOT the excluded session
    # - Has the same agent and project_root
    # - Has ended_at set (is completed)
    # - Started before the new session
    #
    # We then check if it ended within the gap window of the new session starting.
    cursor = conn.execute(
        """
        SELECT id, ended_at
        FROM sessions
        WHERE id != ?
          AND agent = ?
          AND project_root = ?
          AND ended_at IS NOT NULL
          AND status = 'completed'
        ORDER BY created_at_epoch DESC
        LIMIT 1
        """,
        (exclude_session_id, agent, project_root),
    )
    candidate = cursor.fetchone()

    if not candidate:
        return None

    parent_id: str = candidate[0]
    ended_at_str: str | None = candidate[1]
    if not ended_at_str:
        return None

    try:
        ended_at = datetime.fromisoformat(ended_at_str)
        gap_seconds = (new_session_started_at - ended_at).total_seconds()

        # Only link if the gap is within threshold and positive (ended before started)
        if 0 <= gap_seconds <= max_gap_seconds:
            logger.debug(
                f"Found just-ended session {parent_id[:8]}... "
                f"(gap={gap_seconds:.2f}s, max={max_gap_seconds}s)"
            )
            return parent_id
        else:
            logger.debug(
                f"Candidate session {parent_id[:8]}... gap={gap_seconds:.2f}s "
                f"exceeds max={max_gap_seconds}s, not linking"
            )
            return None
    except (ValueError, TypeError) as e:
        logger.debug(f"Could not parse ended_at for session linking: {e}")
        return None


def get_session_lineage(
    store: ActivityStore,
    session_id: str,
    max_depth: int = 10,
) -> list[Session]:
    """Get session lineage (ancestry chain) from newest to oldest.

    Traces parent_session_id links to build a chain of related sessions.
    Useful for understanding how a session evolved through clear/compact cycles.

    Includes cycle prevention: stops if a session is seen twice.

    Args:
        store: The ActivityStore instance.
        session_id: Starting session ID.
        max_depth: Maximum ancestry depth to traverse (default 10).

    Returns:
        List of Session objects, starting with the given session,
        then its parent, grandparent, etc.
    """
    lineage: list[Session] = []
    seen_ids: set[str] = set()
    current_id: str | None = session_id

    while current_id and len(lineage) < max_depth:
        # Cycle prevention
        if current_id in seen_ids:
            logger.warning(f"Cycle detected in session lineage at {current_id[:8]}...")
            break
        seen_ids.add(current_id)

        session = get_session(store, current_id)
        if not session:
            break

        lineage.append(session)
        current_id = session.parent_session_id

    return lineage


def update_session_parent(
    store: ActivityStore,
    session_id: str,
    parent_session_id: str,
    reason: str,
) -> None:
    """Update the parent session link for a session.

    Args:
        store: The ActivityStore instance.
        session_id: Session to update.
        parent_session_id: Parent session ID.
        reason: Why linked: 'clear', 'compact', 'inferred', 'manual'.
    """
    with store._transaction() as conn:
        conn.execute(
            """
            UPDATE sessions
            SET parent_session_id = ?, parent_session_reason = ?
            WHERE id = ?
            """,
            (parent_session_id, reason, session_id),
        )
    logger.debug(
        f"Updated session {session_id[:8]}... parent to {parent_session_id[:8]}... "
        f"(reason={reason})"
    )


def clear_session_parent(store: ActivityStore, session_id: str) -> str | None:
    """Remove the parent link from a session.

    Args:
        store: The ActivityStore instance.
        session_id: Session to unlink.

    Returns:
        The previous parent session ID if there was one, None otherwise.
    """
    # Get current parent before clearing
    conn = store._get_connection()
    cursor = conn.execute("SELECT parent_session_id FROM sessions WHERE id = ?", (session_id,))
    row = cursor.fetchone()
    previous_parent = row[0] if row else None

    with store._transaction() as conn:
        conn.execute(
            """
            UPDATE sessions
            SET parent_session_id = NULL, parent_session_reason = NULL
            WHERE id = ?
            """,
            (session_id,),
        )

    if previous_parent:
        logger.debug(f"Cleared parent link from session {session_id[:8]}...")
    return previous_parent


def get_child_sessions(store: ActivityStore, session_id: str) -> list[Session]:
    """Get sessions that have this session as their parent.

    Args:
        store: The ActivityStore instance.
        session_id: Parent session ID.

    Returns:
        List of child Session objects, ordered by start time (newest first).
    """
    conn = store._get_connection()
    cursor = conn.execute(
        """
        SELECT * FROM sessions
        WHERE parent_session_id = ?
        ORDER BY created_at_epoch DESC
        """,
        (session_id,),
    )
    return [Session.from_row(row) for row in cursor.fetchall()]


def get_child_session_count(store: ActivityStore, session_id: str) -> int:
    """Count sessions that have this session as their parent.

    Args:
        store: The ActivityStore instance.
        session_id: Parent session ID.

    Returns:
        Number of child sessions.
    """
    conn = store._get_connection()
    cursor = conn.execute(
        "SELECT COUNT(*) FROM sessions WHERE parent_session_id = ?",
        (session_id,),
    )
    row = cursor.fetchone()
    return row[0] if row else 0


def would_create_cycle(
    store: ActivityStore,
    session_id: str,
    proposed_parent_id: str,
    max_depth: int = 100,
) -> bool:
    """Check if linking session_id to proposed_parent_id would create a cycle.

    A cycle would occur if proposed_parent_id is in the ancestry chain of session_id,
    or if session_id is in the ancestry chain of proposed_parent_id.

    Args:
        store: The ActivityStore instance.
        session_id: Session that would become the child.
        proposed_parent_id: Session that would become the parent.
        max_depth: Maximum ancestry depth to check (cycle prevention).

    Returns:
        True if the link would create a cycle, False if safe.
    """
    # Self-link is a cycle
    if session_id == proposed_parent_id:
        return True

    # Check if session_id is an ancestor of proposed_parent_id
    # (i.e., proposed_parent_id is in the descendant chain of session_id)
    # If so, linking would create: session_id -> proposed_parent_id -> ... -> session_id
    current_id: str | None = proposed_parent_id
    seen: set[str] = set()
    depth = 0

    while current_id and depth < max_depth:
        if current_id in seen:
            # Already a cycle in the data
            return True
        if current_id == session_id:
            # session_id is an ancestor of proposed_parent_id
            return True
        seen.add(current_id)

        session = get_session(store, current_id)
        if not session:
            break
        current_id = session.parent_session_id
        depth += 1

    return False
