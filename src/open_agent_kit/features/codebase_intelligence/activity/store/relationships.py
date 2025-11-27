"""Session relationship operations for activity store.

Functions for creating, retrieving, and managing many-to-many semantic
relationships between sessions. This complements the parent-child model
(designed for temporal continuity) with relationships that can span any time gap.

Use cases:
- Working on a feature a month ago and iterating on it now
- Related sessions working on the same component/concept
- User-driven linking of sessions that work on similar topics
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from open_agent_kit.features.codebase_intelligence.constants import (
    RELATIONSHIP_CREATED_BY_MANUAL,
    RELATIONSHIP_CREATED_BY_SUGGESTION,
    RELATIONSHIP_TYPE_RELATED,
)

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.store.core import ActivityStore

logger = logging.getLogger(__name__)


@dataclass
class SessionRelationship:
    """A relationship between two sessions."""

    id: int
    session_a_id: str
    session_b_id: str
    relationship_type: str
    similarity_score: float | None
    created_at: datetime
    created_at_epoch: int
    created_by: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> SessionRelationship:
        """Create a SessionRelationship from a database row."""
        return cls(
            id=row["id"],
            session_a_id=row["session_a_id"],
            session_b_id=row["session_b_id"],
            relationship_type=row["relationship_type"],
            similarity_score=row["similarity_score"],
            created_at=datetime.fromisoformat(row["created_at"]),
            created_at_epoch=row["created_at_epoch"],
            created_by=row["created_by"],
        )


def get_related_sessions(
    store: ActivityStore,
    session_id: str,
) -> list[tuple[str, SessionRelationship]]:
    """Get all sessions related to a given session.

    Relationships are bidirectional: if A is related to B, then B is related to A.
    This function returns both directions.

    Args:
        store: The ActivityStore instance.
        session_id: Session to get related sessions for.

    Returns:
        List of (related_session_id, relationship) tuples.
        The related_session_id is the OTHER session in the relationship.
    """
    conn = store._get_connection()

    # Find relationships where this session is either session_a or session_b
    cursor = conn.execute(
        """
        SELECT * FROM session_relationships
        WHERE session_a_id = ? OR session_b_id = ?
        ORDER BY created_at_epoch DESC
        """,
        (session_id, session_id),
    )

    results: list[tuple[str, SessionRelationship]] = []
    for row in cursor.fetchall():
        relationship = SessionRelationship.from_row(row)
        # Return the OTHER session in the relationship
        other_session_id = (
            relationship.session_b_id
            if relationship.session_a_id == session_id
            else relationship.session_a_id
        )
        results.append((other_session_id, relationship))

    return results


def get_relationship(
    store: ActivityStore,
    session_a_id: str,
    session_b_id: str,
) -> SessionRelationship | None:
    """Get the relationship between two sessions, if it exists.

    Checks both directions (a->b and b->a).

    Args:
        store: The ActivityStore instance.
        session_a_id: First session ID.
        session_b_id: Second session ID.

    Returns:
        SessionRelationship if found, None otherwise.
    """
    conn = store._get_connection()
    cursor = conn.execute(
        """
        SELECT * FROM session_relationships
        WHERE (session_a_id = ? AND session_b_id = ?)
           OR (session_a_id = ? AND session_b_id = ?)
        LIMIT 1
        """,
        (session_a_id, session_b_id, session_b_id, session_a_id),
    )
    row = cursor.fetchone()
    return SessionRelationship.from_row(row) if row else None


def add_relationship(
    store: ActivityStore,
    session_a_id: str,
    session_b_id: str,
    similarity_score: float | None = None,
    created_by: str = RELATIONSHIP_CREATED_BY_MANUAL,
    relationship_type: str = RELATIONSHIP_TYPE_RELATED,
) -> SessionRelationship | None:
    """Add a relationship between two sessions.

    Relationships are stored with a canonical ordering (session_a_id < session_b_id
    alphabetically) to prevent duplicate entries in both directions.

    Args:
        store: The ActivityStore instance.
        session_a_id: First session ID.
        session_b_id: Second session ID.
        similarity_score: Vector similarity when relationship was created.
        created_by: Who created: 'suggestion' or 'manual'.
        relationship_type: Type of relationship (currently only 'related').

    Returns:
        Created SessionRelationship, or None if already exists or error.
    """
    # Validate created_by
    if created_by not in (RELATIONSHIP_CREATED_BY_SUGGESTION, RELATIONSHIP_CREATED_BY_MANUAL):
        logger.warning(f"Invalid created_by value: {created_by}, using 'manual'")
        created_by = RELATIONSHIP_CREATED_BY_MANUAL

    # Don't allow self-relationships
    if session_a_id == session_b_id:
        logger.warning(f"Cannot create self-relationship for session {session_a_id}")
        return None

    # Check if relationship already exists
    existing = get_relationship(store, session_a_id, session_b_id)
    if existing:
        logger.debug(
            f"Relationship already exists between {session_a_id[:8]} and {session_b_id[:8]}"
        )
        return existing

    # Use canonical ordering to prevent duplicates
    # Always store with session_a_id < session_b_id alphabetically
    if session_a_id > session_b_id:
        session_a_id, session_b_id = session_b_id, session_a_id

    now = datetime.now()
    try:
        with store._transaction() as conn:
            cursor = conn.execute(
                """
                INSERT INTO session_relationships (
                    session_a_id, session_b_id, relationship_type,
                    similarity_score, created_at, created_at_epoch, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_a_id,
                    session_b_id,
                    relationship_type,
                    similarity_score,
                    now.isoformat(),
                    int(now.timestamp()),
                    created_by,
                ),
            )
            relationship_id = cursor.lastrowid

        logger.info(
            f"Added {relationship_type} relationship between "
            f"{session_a_id[:8]} and {session_b_id[:8]} "
            f"(created_by={created_by}, similarity={similarity_score:.2f if similarity_score else 'N/A'})"
        )

        return SessionRelationship(
            id=relationship_id or 0,
            session_a_id=session_a_id,
            session_b_id=session_b_id,
            relationship_type=relationship_type,
            similarity_score=similarity_score,
            created_at=now,
            created_at_epoch=int(now.timestamp()),
            created_by=created_by,
        )

    except sqlite3.IntegrityError as e:
        # Relationship already exists (race condition)
        logger.debug(f"Relationship already exists (integrity error): {e}")
        return get_relationship(store, session_a_id, session_b_id)
    except (OSError, ValueError, RuntimeError) as e:
        logger.error(f"Failed to add relationship: {e}")
        return None


def remove_relationship(
    store: ActivityStore,
    session_a_id: str,
    session_b_id: str,
) -> bool:
    """Remove a relationship between two sessions.

    Checks both directions (a->b and b->a).

    Args:
        store: The ActivityStore instance.
        session_a_id: First session ID.
        session_b_id: Second session ID.

    Returns:
        True if relationship was removed, False if not found.
    """
    try:
        with store._transaction() as conn:
            cursor = conn.execute(
                """
                DELETE FROM session_relationships
                WHERE (session_a_id = ? AND session_b_id = ?)
                   OR (session_a_id = ? AND session_b_id = ?)
                """,
                (session_a_id, session_b_id, session_b_id, session_a_id),
            )
            deleted = cursor.rowcount > 0

        if deleted:
            logger.info(f"Removed relationship between {session_a_id[:8]} and {session_b_id[:8]}")
        else:
            logger.debug(f"No relationship found between {session_a_id[:8]} and {session_b_id[:8]}")

        return deleted

    except (OSError, ValueError, RuntimeError) as e:
        logger.error(f"Failed to remove relationship: {e}")
        return False


def remove_relationship_by_id(
    store: ActivityStore,
    relationship_id: int,
) -> bool:
    """Remove a relationship by its ID.

    Args:
        store: The ActivityStore instance.
        relationship_id: The relationship ID to remove.

    Returns:
        True if relationship was removed, False if not found.
    """
    try:
        with store._transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM session_relationships WHERE id = ?",
                (relationship_id,),
            )
            deleted = cursor.rowcount > 0

        if deleted:
            logger.info(f"Removed relationship {relationship_id}")
        else:
            logger.debug(f"Relationship {relationship_id} not found")

        return deleted

    except (OSError, ValueError, RuntimeError) as e:
        logger.error(f"Failed to remove relationship {relationship_id}: {e}")
        return False


def get_related_session_ids(
    store: ActivityStore,
    session_id: str,
) -> set[str]:
    """Get the IDs of all sessions related to a given session.

    Convenience function that returns just the IDs, useful for filtering.

    Args:
        store: The ActivityStore instance.
        session_id: Session to get related session IDs for.

    Returns:
        Set of related session IDs.
    """
    related = get_related_sessions(store, session_id)
    return {session_id for session_id, _ in related}


def count_relationships(
    store: ActivityStore,
    session_id: str | None = None,
) -> int:
    """Count relationships, optionally filtered by session.

    Args:
        store: The ActivityStore instance.
        session_id: If provided, count only relationships involving this session.

    Returns:
        Number of relationships.
    """
    conn = store._get_connection()

    if session_id:
        cursor = conn.execute(
            """
            SELECT COUNT(*) FROM session_relationships
            WHERE session_a_id = ? OR session_b_id = ?
            """,
            (session_id, session_id),
        )
    else:
        cursor = conn.execute("SELECT COUNT(*) FROM session_relationships")

    row = cursor.fetchone()
    return row[0] if row else 0


def delete_relationships_for_session(
    store: ActivityStore,
    session_id: str,
) -> int:
    """Delete all relationships involving a session.

    Called when a session is deleted to clean up related relationships.

    Args:
        store: The ActivityStore instance.
        session_id: Session whose relationships should be deleted.

    Returns:
        Number of relationships deleted.
    """
    try:
        with store._transaction() as conn:
            cursor = conn.execute(
                """
                DELETE FROM session_relationships
                WHERE session_a_id = ? OR session_b_id = ?
                """,
                (session_id, session_id),
            )
            deleted = cursor.rowcount

        if deleted > 0:
            logger.info(f"Deleted {deleted} relationships for session {session_id[:8]}")

        return deleted

    except (OSError, ValueError, RuntimeError) as e:
        logger.error(f"Failed to delete relationships for session {session_id}: {e}")
        return 0
