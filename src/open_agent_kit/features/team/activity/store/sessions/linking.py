"""Session linking operations.

Parent-child session linking, lineage traversal, and cycle detection.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from open_agent_kit.features.team.activity.store.models import Session
from open_agent_kit.features.team.constants import (
    LINK_EVENT_AUTO_LINKED,
    LINK_EVENT_MANUAL_LINKED,
    LINK_EVENT_SUGGESTION_ACCEPTED,
    LINK_EVENT_UNLINKED,
    SESSION_LINK_REASON_MANUAL,
    SESSION_LINK_REASON_SUGGESTION,
    SESSION_STATUS_ACTIVE,
    SESSION_STATUS_COMPLETED,
)

if TYPE_CHECKING:
    from open_agent_kit.features.team.activity.store.core import ActivityStore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal tier helpers for find_linkable_parent_session
# ---------------------------------------------------------------------------


def _find_immediate_parent(
    store: ActivityStore,
    exclude_session_id: str,
    agent: str,
    project_root: str,
    new_session_started_at: datetime,
    max_gap_seconds: int,
) -> tuple[str, str] | None:
    """Tier 1: Find a session that JUST ended (within max_gap_seconds).

    Handles normal "clear context and proceed" flow.
    Most transitions: 0.04-0.12 seconds.

    Returns:
        Tuple of (parent_session_id, reason) if found, None otherwise.
    """
    from open_agent_kit.features.team.constants import (
        SESSION_LINK_REASON_CLEAR,
    )

    conn = store._get_connection()
    # Order by ended_at DESC to find the most recently ENDED session,
    # not the most recently created one (they can differ when multiple
    # sessions overlap).
    cursor = conn.execute(
        f"""
        SELECT id, ended_at
        FROM sessions
        WHERE id != ?
          AND agent = ?
          AND project_root = ?
          AND ended_at IS NOT NULL
          AND status = '{SESSION_STATUS_COMPLETED}'
        ORDER BY ended_at DESC
        LIMIT 1
        """,
        (exclude_session_id, agent, project_root),
    )
    candidate = cursor.fetchone()

    if candidate:
        parent_id: str = candidate[0]
        ended_at_str: str | None = candidate[1]
        if ended_at_str:
            try:
                ended_at = datetime.fromisoformat(ended_at_str)
                gap_seconds = (new_session_started_at - ended_at).total_seconds()

                if 0 <= gap_seconds <= max_gap_seconds:
                    logger.debug(
                        f"[Tier 1] Found just-ended session {parent_id[:8]}... "
                        f"(gap={gap_seconds:.2f}s)"
                    )
                    return (parent_id, SESSION_LINK_REASON_CLEAR)
                else:
                    logger.debug(
                        f"[Tier 1] Candidate {parent_id[:8]}... gap={gap_seconds:.2f}s "
                        f"exceeds {max_gap_seconds}s, trying fallbacks"
                    )
            except (ValueError, TypeError) as e:
                logger.debug(f"[Tier 1] Could not parse ended_at: {e}")

    return None


def _find_active_parent(
    store: ActivityStore,
    exclude_session_id: str,
    agent: str,
    project_root: str,
) -> tuple[str, str] | None:
    """Tier 2: Find an ACTIVE session (race condition - SessionEnd not processed yet).

    Only matches if session has prompt activity (not an empty concurrent session).

    Returns:
        Tuple of (parent_session_id, reason) if found, None otherwise.
    """
    from open_agent_kit.features.team.constants import (
        SESSION_LINK_REASON_CLEAR_ACTIVE,
    )

    conn = store._get_connection()
    cursor = conn.execute(
        f"""
        SELECT id, created_at_epoch
        FROM sessions
        WHERE id != ?
          AND agent = ?
          AND project_root = ?
          AND status = '{SESSION_STATUS_ACTIVE}'
          AND prompt_count > 0
        ORDER BY created_at_epoch DESC
        LIMIT 1
        """,
        (exclude_session_id, agent, project_root),
    )
    active_candidate = cursor.fetchone()

    if active_candidate:
        active_parent_id: str = active_candidate[0]
        logger.info(
            f"[Tier 2] Found active session {active_parent_id[:8]}... "
            "(SessionEnd may not have been processed yet)"
        )
        return (active_parent_id, SESSION_LINK_REASON_CLEAR_ACTIVE)

    return None


def _find_stale_parent(
    store: ActivityStore,
    exclude_session_id: str,
    agent: str,
    project_root: str,
    new_session_started_at: datetime,
    fallback_max_hours: int,
) -> tuple[str, str] | None:
    """Tier 3: Find a recently completed session within fallback window.

    Handles the "next day resume" scenario where planning session went stale.
    Uses ended_at DESC ordering to find the most recently ended session.

    Returns:
        Tuple of (parent_session_id, reason) if found, None otherwise.
    """
    from open_agent_kit.features.team.constants import (
        SESSION_LINK_REASON_INFERRED,
    )

    conn = store._get_connection()
    now_epoch = new_session_started_at.timestamp()
    cursor = conn.execute(
        f"""
        SELECT id, created_at_epoch
        FROM sessions
        WHERE id != ?
          AND agent = ?
          AND project_root = ?
          AND ended_at IS NOT NULL
          AND status = '{SESSION_STATUS_COMPLETED}'
        ORDER BY ended_at DESC
        LIMIT 1
        """,
        (exclude_session_id, agent, project_root),
    )
    fallback_candidate = cursor.fetchone()

    if fallback_candidate:
        fallback_parent_id: str = fallback_candidate[0]
        created_at_epoch = fallback_candidate[1]
        hours_since_created = (now_epoch - created_at_epoch) / 3600

        if hours_since_created <= fallback_max_hours:
            logger.info(
                f"[Tier 3] Linking to recent session {fallback_parent_id[:8]}... "
                f"(created {hours_since_created:.1f}h ago, "
                f"reason={SESSION_LINK_REASON_INFERRED})"
            )
            return (fallback_parent_id, SESSION_LINK_REASON_INFERRED)
        else:
            logger.debug(
                f"[Tier 3] Session {fallback_parent_id[:8]}... too old "
                f"({hours_since_created:.1f}h > {fallback_max_hours}h)"
            )

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def find_just_ended_session(
    store: ActivityStore,
    agent: str,
    project_root: str,
    exclude_session_id: str,
    new_session_started_at: datetime,
    max_gap_seconds: int = 5,
) -> str | None:
    """Find a session that just ended, suitable for parent linking.

    Wrapper for find_linkable_parent_session that returns only the session ID
    for backward compatibility. Use find_linkable_parent_session directly
    if you need the linking reason.

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
    result = find_linkable_parent_session(
        store=store,
        agent=agent,
        project_root=project_root,
        exclude_session_id=exclude_session_id,
        new_session_started_at=new_session_started_at,
        max_gap_seconds=max_gap_seconds,
    )
    return result[0] if result else None


def find_linkable_parent_session(
    store: ActivityStore,
    agent: str,
    project_root: str,
    exclude_session_id: str,
    new_session_started_at: datetime,
    max_gap_seconds: int | None = None,
    fallback_max_hours: int | None = None,
) -> tuple[str, str] | None:
    """Find a session suitable for parent linking with multi-tier fallback.

    Used when source="clear" to link the new session to the previous session.
    Uses a tiered approach to handle different scenarios:

    1. **Tier 1 (immediate)**: Session ended within max_gap_seconds
       - Handles normal "clear context and proceed" flow
       - Most transitions: 0.04-0.12 seconds

    2. **Tier 2 (race condition)**: Most recent ACTIVE session for same agent/project
       - Handles race condition where SessionEnd hasn't been processed yet
       - Only matches if session has prompt activity (not empty)

    3. **Tier 3 (stale/next-day)**: Most recent COMPLETED session within fallback window
       - Handles case where planning session went stale and user returns later
       - Uses created_at_epoch ordering (not ended_at which reflects recovery time)

    Args:
        store: The ActivityStore instance.
        agent: Agent name to match.
        project_root: Project root to match.
        exclude_session_id: Session ID to exclude (the new session).
        new_session_started_at: When the new session started.
        max_gap_seconds: Maximum gap for tier 1 (default from constants).
        fallback_max_hours: Maximum hours for tier 3 fallback (default from constants).

    Returns:
        Tuple of (parent_session_id, reason) if found, None otherwise.
        Reason is one of the SESSION_LINK_REASON_* constants.
    """
    from open_agent_kit.features.team.constants import (
        SESSION_LINK_FALLBACK_MAX_HOURS,
        SESSION_LINK_IMMEDIATE_GAP_SECONDS,
    )

    # Apply defaults from constants
    if max_gap_seconds is None:
        max_gap_seconds = SESSION_LINK_IMMEDIATE_GAP_SECONDS
    if fallback_max_hours is None:
        fallback_max_hours = SESSION_LINK_FALLBACK_MAX_HOURS

    # Tier 1: Look for session that JUST ended (within max_gap_seconds)
    result = _find_immediate_parent(
        store,
        exclude_session_id,
        agent,
        project_root,
        new_session_started_at,
        max_gap_seconds,
    )
    if result:
        return result

    # Tier 2: Look for ACTIVE session (race condition - SessionEnd not processed yet)
    result = _find_active_parent(
        store,
        exclude_session_id,
        agent,
        project_root,
    )
    if result:
        return result

    # Tier 3: Fallback to most recent completed session within fallback window
    result = _find_stale_parent(
        store,
        exclude_session_id,
        agent,
        project_root,
        new_session_started_at,
        fallback_max_hours,
    )
    if result:
        return result

    logger.debug("No suitable parent session found for linking")
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
    from open_agent_kit.features.team.activity.store.sessions.crud import (
        get_session,
    )

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


def enrich_sessions_with_lineage(
    store: ActivityStore,
    sessions: list[dict],
) -> None:
    """Enrich session search results with parent_session_id and chain_position.

    Adds lineage metadata from SQLite so agents can navigate multi-session
    feature chains. chain_position is like "1 of 5" (root) or "3 of 5".
    Only set when the session belongs to a chain of 2+ sessions.

    Operates in-place on the session dicts.

    Args:
        store: The ActivityStore instance.
        sessions: List of session result dicts (must have 'id' key).
    """
    if not sessions:
        return

    conn = store._get_connection()
    session_ids = [s["id"] for s in sessions]

    # Batch-fetch parent_session_id for all result sessions
    placeholders = ",".join("?" * len(session_ids))
    cursor = conn.execute(
        f"SELECT id, parent_session_id FROM sessions WHERE id IN ({placeholders})",  # noqa: S608
        session_ids,
    )
    parent_map: dict[str, str | None] = {row[0]: row[1] for row in cursor.fetchall()}

    # For each session, walk up to find root and count ancestors
    root_for: dict[str, str] = {}
    ancestors_for: dict[str, int] = {}

    for sid in session_ids:
        ancestors = 0
        current = sid
        seen: set[str] = {sid}
        while parent_map.get(current):
            parent = parent_map[current]
            if parent is None or parent in seen:
                break
            seen.add(parent)
            ancestors += 1
            # Fetch parent's parent if not already known
            if parent not in parent_map:
                row = conn.execute(
                    "SELECT parent_session_id FROM sessions WHERE id = ?",
                    (parent,),
                ).fetchone()
                parent_map[parent] = row[0] if row else None
            current = parent
        root_for[sid] = current
        ancestors_for[sid] = ancestors

    # Count chain size per unique root (one recursive CTE each, cached)
    chain_size_cache: dict[str, int] = {}
    for root_id in set(root_for.values()):
        if root_id in chain_size_cache:
            continue
        cursor = conn.execute(
            """
            WITH RECURSIVE chain AS (
                SELECT id FROM sessions WHERE id = ?
                UNION ALL
                SELECT s.id FROM sessions s
                JOIN chain c ON s.parent_session_id = c.id
            )
            SELECT COUNT(*) FROM chain
            """,
            (root_id,),
        )
        chain_size_cache[root_id] = cursor.fetchone()[0]

    # Write enrichment back into session dicts
    for s in sessions:
        sid = s["id"]
        s["parent_session_id"] = parent_map.get(sid)
        root_id = root_for[sid]
        total = chain_size_cache[root_id]
        position = ancestors_for[sid] + 1
        s["chain_position"] = f"{position} of {total}" if total > 1 else None


def log_link_event(
    store: ActivityStore,
    session_id: str,
    event_type: str,
    old_parent_id: str | None = None,
    new_parent_id: str | None = None,
    suggested_parent_id: str | None = None,
    suggestion_confidence: float | None = None,
    link_reason: str | None = None,
) -> None:
    """Log a session link event for analytics.

    Args:
        store: The ActivityStore instance.
        session_id: Session that was linked/unlinked.
        event_type: One of LINK_EVENT_* constants.
        old_parent_id: Previous parent (for unlink/change events).
        new_parent_id: New parent (for link events).
        suggested_parent_id: What was suggested (if applicable).
        suggestion_confidence: Confidence score of suggestion.
        link_reason: Why linked (one of SESSION_LINK_REASON_* constants).
    """
    now = datetime.now()
    with store._transaction() as conn:
        conn.execute(
            """
            INSERT INTO session_link_events (
                session_id, event_type, old_parent_id, new_parent_id,
                suggested_parent_id, suggestion_confidence, link_reason,
                created_at, created_at_epoch
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                event_type,
                old_parent_id,
                new_parent_id,
                suggested_parent_id,
                suggestion_confidence,
                link_reason,
                now.isoformat(),
                int(now.timestamp()),
            ),
        )
    logger.debug(
        f"Logged link event: {event_type} for session {session_id[:8]}... "
        f"(old={old_parent_id[:8] if old_parent_id else None}... "
        f"new={new_parent_id[:8] if new_parent_id else None}...)"
    )


def update_session_parent(
    store: ActivityStore,
    session_id: str,
    parent_session_id: str,
    reason: str,
    suggested_parent_id: str | None = None,
    suggestion_confidence: float | None = None,
) -> None:
    """Update the parent session link for a session.

    Args:
        store: The ActivityStore instance.
        session_id: Session to update.
        parent_session_id: Parent session ID.
        reason: Why linked: 'clear', 'compact', 'inferred', 'manual', 'suggestion'.
        suggested_parent_id: For analytics - what was the suggestion if any.
        suggestion_confidence: Confidence score of the suggestion.
    """
    # Get current parent for event logging
    conn = store._get_connection()
    cursor = conn.execute("SELECT parent_session_id FROM sessions WHERE id = ?", (session_id,))
    row = cursor.fetchone()
    old_parent_id = row[0] if row else None

    with store._transaction() as conn:
        conn.execute(
            """
            UPDATE sessions
            SET parent_session_id = ?, parent_session_reason = ?
            WHERE id = ?
            """,
            (parent_session_id, reason, session_id),
        )

    # Determine event type based on reason
    if reason == SESSION_LINK_REASON_SUGGESTION:
        event_type = LINK_EVENT_SUGGESTION_ACCEPTED
    elif reason == SESSION_LINK_REASON_MANUAL:
        event_type = LINK_EVENT_MANUAL_LINKED
    else:
        # Auto-linking (clear, clear_active, inferred, compact)
        event_type = LINK_EVENT_AUTO_LINKED

    # Log the link event
    log_link_event(
        store=store,
        session_id=session_id,
        event_type=event_type,
        old_parent_id=old_parent_id,
        new_parent_id=parent_session_id,
        suggested_parent_id=suggested_parent_id,
        suggestion_confidence=suggestion_confidence,
        link_reason=reason,
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
        # Log the unlink event
        log_link_event(
            store=store,
            session_id=session_id,
            event_type=LINK_EVENT_UNLINKED,
            old_parent_id=previous_parent,
        )
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


def get_bulk_child_session_counts(store: ActivityStore, session_ids: list[str]) -> dict[str, int]:
    """Count child sessions for multiple parent sessions in a single query.

    Args:
        store: The ActivityStore instance.
        session_ids: List of session IDs to check for children.

    Returns:
        Dictionary mapping session_id -> child count (only includes non-zero counts).
    """
    if not session_ids:
        return {}

    conn = store._get_connection()
    placeholders = ",".join("?" * len(session_ids))
    cursor = conn.execute(
        f"SELECT parent_session_id, COUNT(*) as cnt "
        f"FROM sessions WHERE parent_session_id IN ({placeholders}) "
        f"GROUP BY parent_session_id",
        session_ids,
    )
    return {row["parent_session_id"]: row["cnt"] for row in cursor.fetchall()}


def would_create_cycle(
    store: ActivityStore,
    session_id: str,
    proposed_parent_id: str,
    max_depth: int = 100,
) -> bool:
    """Check if linking session_id to proposed_parent_id would create a cycle.

    A cycle would occur if session_id appears in the ancestry chain of
    proposed_parent_id.  Uses a recursive CTE to detect this in a single
    query instead of multiple round trips.

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

    # Walk the ancestry chain of proposed_parent_id via recursive CTE.
    # If session_id appears anywhere in that chain, linking would create a cycle.
    conn = store._get_connection()
    cursor = conn.execute(
        """
        WITH RECURSIVE ancestors(id, depth) AS (
            SELECT parent_session_id, 1
            FROM sessions WHERE id = ?
            UNION ALL
            SELECT s.parent_session_id, a.depth + 1
            FROM sessions s
            JOIN ancestors a ON s.id = a.id
            WHERE a.id IS NOT NULL AND a.depth < ?
        )
        SELECT 1 FROM ancestors WHERE id = ? LIMIT 1
        """,
        (proposed_parent_id, max_depth, session_id),
    )
    return cursor.fetchone() is not None


def is_suggestion_dismissed(store: ActivityStore, session_id: str) -> bool:
    """Check whether the suggested-parent suggestion was dismissed for a session.

    Args:
        store: The ActivityStore instance.
        session_id: Session to check.

    Returns:
        True if the suggestion was dismissed by the user.
    """
    conn = store._get_connection()
    cursor = conn.execute(
        "SELECT suggested_parent_dismissed FROM sessions WHERE id = ?",
        (session_id,),
    )
    row = cursor.fetchone()
    return bool(row and row[0]) if row else False
