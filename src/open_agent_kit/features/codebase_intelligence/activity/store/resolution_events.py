"""Resolution event operations for activity store.

Functions for storing and managing resolution events that propagate
observation status changes across machines via the backup pipeline.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from open_agent_kit.features.codebase_intelligence.activity.store.models import (
    ResolutionEvent,
)
from open_agent_kit.features.codebase_intelligence.constants import (
    OBSERVATION_STATUS_ACTIVE,
    OBSERVATION_STATUS_RESOLVED,
    OBSERVATION_STATUS_SUPERSEDED,
    RESOLUTION_EVENT_ACTION_REACTIVATED,
)

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.store.core import ActivityStore

logger = logging.getLogger(__name__)


def store_resolution_event(
    store: ActivityStore,
    observation_id: str,
    action: str,
    resolved_by_session_id: str | None = None,
    superseded_by: str | None = None,
    reason: str | None = None,
    created_at: datetime | None = None,
    source_machine_id: str | None = None,
    applied: bool = True,
) -> str:
    """Create and store a resolution event.

    Auto-sets source_machine_id from the store and computes content_hash.

    Args:
        store: The ActivityStore instance.
        observation_id: Target observation being resolved/superseded/reactivated.
        action: One of 'resolved', 'superseded', 'reactivated'.
        resolved_by_session_id: Session that performed the resolution.
        superseded_by: New observation ID (for 'superseded' action).
        reason: Optional reason for the resolution.
        created_at: Timestamp (defaults to now).
        source_machine_id: Machine that performed the resolution (defaults to store.machine_id).
        applied: Whether this event has been applied locally (default True for locally-created).

    Returns:
        The resolution event ID.
    """
    now = created_at or datetime.now()
    event = ResolutionEvent(
        id=str(uuid.uuid4()),
        observation_id=observation_id,
        action=action,
        resolved_by_session_id=resolved_by_session_id,
        superseded_by=superseded_by,
        reason=reason,
        created_at=now,
        source_machine_id=source_machine_id or store.machine_id,
        applied=applied,
    )

    with store._transaction() as conn:
        row = event.to_row()
        conn.execute(
            """
            INSERT OR IGNORE INTO resolution_events
            (id, observation_id, action, resolved_by_session_id, superseded_by,
             reason, created_at, created_at_epoch, source_machine_id, content_hash, applied)
            VALUES (:id, :observation_id, :action, :resolved_by_session_id, :superseded_by,
                    :reason, :created_at, :created_at_epoch, :source_machine_id,
                    :content_hash, :applied)
            """,
            row,
        )

    logger.debug(f"Stored resolution event {event.id}: {action} on observation {observation_id}")
    return event.id


def replay_unapplied_events(
    store: ActivityStore,
    vector_store: Any | None = None,
) -> int:
    """Find and apply unapplied resolution events.

    Processes events in chronological order (oldest first).  For each event:
    1. Check if the target observation exists locally (defer if not).
    2. Compare timestamps — last-writer-wins.
    3. Update observation status via update_observation_status().
    4. Update ChromaDB if vector_store provided.
    5. Mark the event as applied.

    Does NOT create new resolution events (prevents infinite feedback loops).

    Args:
        store: The ActivityStore instance.
        vector_store: Optional vector store for ChromaDB updates.

    Returns:
        Number of events successfully applied.
    """
    from open_agent_kit.features.codebase_intelligence.activity.store.observations import (
        get_observation,
        update_observation_status,
    )

    conn = store._get_connection()
    cursor = conn.execute(
        """
        SELECT * FROM resolution_events
        WHERE applied = FALSE
        ORDER BY created_at_epoch ASC
        """,
    )
    events = [ResolutionEvent.from_row(row) for row in cursor.fetchall()]

    if not events:
        return 0

    applied_count = 0
    for event in events:
        obs = get_observation(store, event.observation_id)
        if obs is None:
            # Observation not yet imported — leave unapplied for next replay
            logger.debug(
                f"Deferring resolution event {event.id}: "
                f"observation {event.observation_id} not found locally"
            )
            continue

        # Last-writer-wins: only apply if this event is newer than the current resolution
        if obs.resolved_at and int(obs.resolved_at.timestamp()) >= int(
            event.created_at.timestamp()
        ):
            # Current state is newer or equal — mark applied but skip update
            _mark_event_applied(store, event.id)
            applied_count += 1
            logger.debug(
                f"Skipping stale resolution event {event.id}: "
                f"observation already has newer resolution"
            )
            continue

        # Determine new status and resolution fields based on action
        if event.action == RESOLUTION_EVENT_ACTION_REACTIVATED:
            new_status = OBSERVATION_STATUS_ACTIVE
            resolved_at_str = None
            resolved_by = None
            superseded_by = None
        else:
            new_status = event.action  # 'resolved' or 'superseded'
            resolved_at_str = event.created_at.isoformat()
            resolved_by = event.resolved_by_session_id
            superseded_by = event.superseded_by

        # Update observation status in SQLite
        updated = update_observation_status(
            store,
            event.observation_id,
            new_status,
            resolved_by_session_id=resolved_by,
            resolved_at=resolved_at_str,
            superseded_by=superseded_by,
        )

        if not updated:
            logger.warning(
                f"Failed to apply resolution event {event.id}: "
                f"observation {event.observation_id} update returned False"
            )
            continue

        # Update ChromaDB if available
        if vector_store and obs.embedded:
            try:
                metadata_update: dict[str, Any] = {"status": new_status}
                if superseded_by:
                    metadata_update["superseded_by"] = superseded_by
                vector_store.update_memory_status(event.observation_id, new_status)
            except (ValueError, RuntimeError) as e:
                logger.warning(f"Failed to update ChromaDB for resolution event {event.id}: {e}")

        _mark_event_applied(store, event.id)
        applied_count += 1
        logger.debug(
            f"Applied resolution event {event.id}: {event.action} on {event.observation_id}"
        )

    if applied_count:
        logger.info(f"Replayed {applied_count}/{len(events)} resolution events")
    return applied_count


def _mark_event_applied(store: ActivityStore, event_id: str) -> None:
    """Mark a resolution event as applied."""
    with store._transaction() as conn:
        conn.execute(
            "UPDATE resolution_events SET applied = TRUE WHERE id = ?",
            (event_id,),
        )


def get_all_resolution_event_hashes(store: ActivityStore) -> set[str]:
    """Get all resolution event content_hash values for dedup checking.

    Args:
        store: The ActivityStore instance.

    Returns:
        Set of content hash strings.
    """
    conn = store._get_connection()
    cursor = conn.execute(
        "SELECT content_hash FROM resolution_events WHERE content_hash IS NOT NULL"
    )
    return {row[0] for row in cursor.fetchall()}


def count_unapplied_events(store: ActivityStore) -> int:
    """Count resolution events that haven't been applied yet.

    Args:
        store: The ActivityStore instance.

    Returns:
        Number of unapplied resolution events.
    """
    conn = store._get_connection()
    cursor = conn.execute("SELECT COUNT(*) FROM resolution_events WHERE applied = FALSE")
    result = cursor.fetchone()
    return int(result[0]) if result else 0


def backfill_resolution_events(store: ActivityStore) -> int:
    """Backfill resolution events for existing resolved/superseded observations.

    Each machine only backfills events for resolutions it performed, determined
    by joining resolved_by_session_id to sessions.source_machine_id.

    Idempotent: skips observations that already have a resolution event.

    Args:
        store: The ActivityStore instance.

    Returns:
        Number of resolution events created.
    """
    conn = store._get_connection()
    cursor = conn.execute(
        """
        SELECT mo.id, mo.status, mo.resolved_by_session_id, mo.superseded_by,
               mo.resolved_at
        FROM memory_observations mo
        JOIN sessions s ON mo.resolved_by_session_id = s.id
        WHERE mo.status IN (?, ?)
          AND s.source_machine_id = ?
          AND mo.id NOT IN (SELECT observation_id FROM resolution_events)
        """,
        (OBSERVATION_STATUS_RESOLVED, OBSERVATION_STATUS_SUPERSEDED, store.machine_id),
    )
    rows = cursor.fetchall()

    if not rows:
        return 0

    count = 0
    for row in rows:
        obs_id = row["id"]
        status = row["status"]
        resolved_by = row["resolved_by_session_id"]
        superseded_by = row["superseded_by"]
        resolved_at_str = row["resolved_at"]

        created_at = datetime.fromisoformat(resolved_at_str) if resolved_at_str else datetime.now()

        store_resolution_event(
            store,
            observation_id=obs_id,
            action=status,
            resolved_by_session_id=resolved_by,
            superseded_by=superseded_by,
            created_at=created_at,
            applied=True,  # Local observation already in correct state
        )
        count += 1

    if count:
        logger.info(f"Backfilled {count} resolution events from existing resolutions")
    return count
