"""Session CRUD operations.

Create, read, update, and delete operations for session records.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from datetime import datetime
from typing import TYPE_CHECKING

from open_agent_kit.features.team.activity.store.models import Session
from open_agent_kit.features.team.constants import (
    AGENT_CLAUDE,
    AGENT_UNKNOWN,
    CI_SESSION_COLUMN_TRANSCRIPT_PATH,
    SESSION_STATUS_ACTIVE,
    SESSION_STATUS_COMPLETED,
)

if TYPE_CHECKING:
    from open_agent_kit.features.team.activity.store.core import ActivityStore

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
    session = Session(
        id=session_id,
        agent=agent,
        project_root=project_root,
        started_at=datetime.now(),
        parent_session_id=parent_session_id,
        parent_session_reason=parent_session_reason,
        source_machine_id=store.machine_id,
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
        if existing.status == SESSION_STATUS_COMPLETED:
            with store._transaction() as conn:
                conn.execute(
                    f"""
                    UPDATE sessions
                    SET status = '{SESSION_STATUS_ACTIVE}', ended_at = NULL
                    WHERE id = ?
                    """,
                    (session_id,),
                )
            existing.status = SESSION_STATUS_ACTIVE
            existing.ended_at = None
            logger.debug(f"Reactivated session {session_id}")

        # Update agent label with priority-based logic.
        # Dual-fire scenario: Cursor / VS Code Copilot fire BOTH the Claude
        # cloud hooks (--agent claude) AND their own agent-specific hooks
        # (--agent cursor).  The Claude hooks fire for *every* event, so a
        # naive "last writer wins" would flip-flop between "claude" and the
        # real agent.
        #
        # Priority:  specific agent  >  "claude"  >  "unknown"
        # Once a session is attributed to a specific agent, a generic label
        # ("claude" or "unknown") must not overwrite it.
        if existing.agent != agent:
            _GENERIC_AGENTS = (AGENT_CLAUDE, AGENT_UNKNOWN)
            incoming_is_generic = agent in _GENERIC_AGENTS
            existing_is_specific = existing.agent not in _GENERIC_AGENTS

            if incoming_is_generic and existing_is_specific:
                logger.debug(
                    "Kept session %s agent=%s (incoming %s is generic)",
                    session_id,
                    existing.agent,
                    agent,
                )
            else:
                with store._transaction() as conn:
                    conn.execute(
                        "UPDATE sessions SET agent = ? WHERE id = ?",
                        (agent, session_id),
                    )
                logger.debug(
                    f"Updated session {session_id} agent label: {existing.agent} -> {agent}"
                )
                existing.agent = agent

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
    ended_at = datetime.now().isoformat()
    with store._transaction() as conn:
        conn.execute(
            f"""
            UPDATE sessions
            SET ended_at = ?, status = '{SESSION_STATUS_COMPLETED}', summary = ?
            WHERE id = ?
            """,
            (ended_at, summary, session_id),
        )

    logger.debug(f"Ended session {session_id}")


def update_session_title(
    store: ActivityStore, session_id: str, title: str, manually_edited: bool = False
) -> None:
    """Update the session title.

    Args:
        store: The ActivityStore instance.
        session_id: Session to update.
        title: Short title for the session.
        manually_edited: If True, marks the title as manually edited to protect
            it from being overwritten by LLM-generated titles.
    """
    with store._transaction() as conn:
        conn.execute(
            "UPDATE sessions SET title = ?, title_manually_edited = ? WHERE id = ?",
            (title, manually_edited, session_id),
        )

    logger.debug(f"Updated session {session_id} title: {title[:50]}...")


def update_session_summary(store: ActivityStore, session_id: str, summary: str) -> None:
    """Update the session summary.

    Args:
        store: The ActivityStore instance.
        session_id: Session to update.
        summary: LLM-generated session summary.
    """
    now_epoch = int(time.time())
    with store._transaction() as conn:
        conn.execute(
            "UPDATE sessions SET summary = ?, summary_updated_at = ? WHERE id = ?",
            (summary, now_epoch, session_id),
        )

    logger.debug(f"Updated session {session_id} summary: {summary[:50]}...")


def mark_session_summary_embedded(
    store: ActivityStore, session_id: str, embedded: bool = True
) -> None:
    """Mark whether a session summary has been embedded in ChromaDB.

    Args:
        store: The ActivityStore instance.
        session_id: Session to update.
        embedded: True if embedded, False to clear the flag.
    """
    with store._transaction() as conn:
        conn.execute(
            "UPDATE sessions SET summary_embedded = ? WHERE id = ?",
            (int(embedded), session_id),
        )


def update_session_transcript_path(
    store: ActivityStore, session_id: str, transcript_path: str
) -> None:
    """Store the transcript file path for a session.

    Args:
        store: The ActivityStore instance.
        session_id: Session to update.
        transcript_path: Absolute path to the session's JSONL transcript file.
    """
    with store._transaction() as conn:
        conn.execute(
            f"UPDATE sessions SET {CI_SESSION_COLUMN_TRANSCRIPT_PATH} = ? WHERE id = ?",
            (transcript_path, session_id),
        )

    logger.debug(f"Updated session {session_id} transcript_path: {transcript_path}")


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
            f"""
            UPDATE sessions
            SET status = '{SESSION_STATUS_ACTIVE}', ended_at = NULL
            WHERE id = ? AND status = '{SESSION_STATUS_COMPLETED}'
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
