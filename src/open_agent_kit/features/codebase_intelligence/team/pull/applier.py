"""Applies team events received from the server to the local store.

Uses direct SQL (not store_observation) to avoid triggering outbox hooks
on imported data, which would cause infinite sync loops.
"""

import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from open_agent_kit.features.codebase_intelligence.constants.team import (
    TEAM_EVENT_OBSERVATION_RESOLVED,
    TEAM_EVENT_OBSERVATION_UPSERT,
    TEAM_EVENT_SESSION_SUMMARY_UPDATE,
    TEAM_EVENT_SESSION_UPSERT,
)

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.store.core import ActivityStore
    from open_agent_kit.features.codebase_intelligence.team.protocol import TeamEvent

logger = logging.getLogger(__name__)


@dataclass
class ApplyResult:
    """Result of applying a batch of team events."""

    applied: int = 0
    skipped: int = 0  # Already exists (dedup)
    errors: int = 0


class TeamEventApplier:
    """Applies team events to the local activity store.

    Events are deduplicated by content_hash before insertion.
    Imported records are marked for re-embedding (embedded=False,
    summary_embedded=0, applied=False) so that ChromaDB picks them up.
    """

    def __init__(self, store: "ActivityStore") -> None:
        self._store = store

    def apply_batch(self, events: list["TeamEvent"]) -> ApplyResult:
        """Apply a batch of team events to the local store.

        Args:
            events: List of TeamEvent objects from the server.

        Returns:
            ApplyResult with counts of applied, skipped, and errored events.
        """
        result = ApplyResult()
        for event in events:
            try:
                applied = self._apply_event(event)
                if applied:
                    result.applied += 1
                else:
                    result.skipped += 1
            except Exception:
                logger.exception("Failed to apply team event")
                result.errors += 1
        return result

    def _apply_event(self, event: "TeamEvent") -> bool:
        """Apply a single event. Returns True if applied, False if skipped (dedup)."""
        payload = event.payload if isinstance(event.payload, dict) else json.loads(event.payload)

        if event.event_type == TEAM_EVENT_OBSERVATION_UPSERT:
            return self._apply_observation_upsert(payload)
        elif event.event_type == TEAM_EVENT_OBSERVATION_RESOLVED:
            return self._apply_observation_resolved(payload)
        elif event.event_type == TEAM_EVENT_SESSION_UPSERT:
            return self._apply_session_upsert(payload)
        elif event.event_type == TEAM_EVENT_SESSION_SUMMARY_UPDATE:
            return self._apply_session_summary_update(payload)
        else:
            logger.warning("Unknown team event type: %s", event.event_type)
            return False

    def _apply_observation_upsert(self, payload: dict) -> bool:
        """Apply an observation upsert. Dedup by content_hash.

        Imported observations are marked embedded=False so ChromaDB
        will re-embed them on the next background processing cycle.
        """
        content_hash = payload.get("content_hash")
        if content_hash:
            from open_agent_kit.features.codebase_intelligence.activity.store.observations import (
                has_observation_with_hash,
            )

            if has_observation_with_hash(self._store, content_hash):
                return False

        with self._store._transaction() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO memory_observations
                (id, session_id, prompt_batch_id, observation, memory_type,
                 context, tags, importance, file_path, created_at, created_at_epoch,
                 embedded, source_machine_id, content_hash, status,
                 resolved_by_session_id, resolved_at, superseded_by,
                 session_origin_type, origin_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.get("id"),
                    payload.get("session_id"),
                    payload.get("prompt_batch_id"),
                    payload.get("observation"),
                    payload.get("memory_type"),
                    payload.get("context"),
                    payload.get("tags"),
                    payload.get("importance", 5),
                    payload.get("file_path"),
                    payload.get("created_at"),
                    payload.get("created_at_epoch"),
                    False,  # embedded=False -- needs ChromaDB re-embedding
                    payload.get("source_machine_id"),
                    content_hash,
                    payload.get("status", "active"),
                    payload.get("resolved_by_session_id"),
                    payload.get("resolved_at"),
                    payload.get("superseded_by"),
                    payload.get("session_origin_type"),
                    payload.get("origin_type", "auto_extracted"),
                ),
            )
        return True

    def _apply_observation_resolved(self, payload: dict) -> bool:
        """Apply an observation resolution event. Dedup by content_hash."""
        content_hash = payload.get("content_hash")
        if content_hash:
            conn = self._store._get_connection()
            existing = conn.execute(
                "SELECT 1 FROM resolution_events WHERE content_hash = ? LIMIT 1",
                (content_hash,),
            ).fetchone()
            if existing:
                return False

        with self._store._transaction() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO resolution_events
                (id, observation_id, action, resolved_by_session_id, superseded_by,
                 reason, created_at, created_at_epoch, source_machine_id, content_hash, applied)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.get("id"),
                    payload.get("observation_id"),
                    payload.get("action"),
                    payload.get("resolved_by_session_id"),
                    payload.get("superseded_by"),
                    payload.get("reason"),
                    payload.get("created_at"),
                    payload.get("created_at_epoch"),
                    payload.get("source_machine_id"),
                    content_hash,
                    False,  # applied=False for imported events
                ),
            )

            # Also update the observation status
            observation_id = payload.get("observation_id")
            action = payload.get("action")
            if observation_id and action:
                if action == "resolved":
                    conn.execute(
                        "UPDATE memory_observations SET status = 'resolved', "
                        "resolved_at = ? WHERE id = ?",
                        (payload.get("created_at"), observation_id),
                    )
                elif action == "superseded":
                    conn.execute(
                        "UPDATE memory_observations SET status = 'superseded', "
                        "superseded_by = ? WHERE id = ?",
                        (payload.get("superseded_by"), observation_id),
                    )
        return True

    def _apply_session_upsert(self, payload: dict) -> bool:
        """Apply a session upsert. Last-write-wins by session ID."""
        session_id = payload.get("id")
        if not session_id:
            return False

        with self._store._transaction() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO sessions
                (id, agent, project_root, started_at, ended_at, status,
                 prompt_count, tool_count, processed, summary, title,
                 title_manually_edited, created_at_epoch, parent_session_id,
                 parent_session_reason, source_machine_id, transcript_path,
                 summary_updated_at, summary_embedded)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    payload.get("agent", "unknown"),
                    payload.get("project_root", ""),
                    payload.get("started_at"),
                    payload.get("ended_at"),
                    payload.get("status", "active"),
                    payload.get("prompt_count", 0),
                    payload.get("tool_count", 0),
                    payload.get("processed", False),
                    payload.get("summary"),
                    payload.get("title"),
                    payload.get("title_manually_edited", False),
                    payload.get("created_at_epoch", 0),
                    payload.get("parent_session_id"),
                    payload.get("parent_session_reason"),
                    payload.get("source_machine_id"),
                    payload.get("transcript_path"),
                    payload.get("summary_updated_at"),
                    0,  # summary_embedded=0 -- needs re-embedding
                ),
            )
        return True

    def _apply_session_summary_update(self, payload: dict) -> bool:
        """Apply a session summary update. Last-write-wins."""
        session_id = payload.get("session_id")
        summary = payload.get("summary")
        if not session_id or summary is None:
            return False

        with self._store._transaction() as conn:
            conn.execute(
                "UPDATE sessions SET summary = ?, summary_updated_at = ?, "
                "summary_embedded = 0 WHERE id = ?",
                (summary, payload.get("summary_updated_at"), session_id),
            )
        return True
