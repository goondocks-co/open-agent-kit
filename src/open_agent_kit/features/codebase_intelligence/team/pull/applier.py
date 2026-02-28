"""Applies team events received from the server to the local store.

Uses direct SQL (not store_observation) to avoid triggering outbox hooks
on imported data, which would cause infinite sync loops.
"""

import json
import logging
import sqlite3
from dataclasses import dataclass
from typing import TYPE_CHECKING

from open_agent_kit.features.codebase_intelligence.constants.team import (
    TEAM_BACKFILL_CHUNK_SIZE,
    TEAM_EVENT_ACTIVITY_UPSERT,
    TEAM_EVENT_OBSERVATION_RESOLVED,
    TEAM_EVENT_OBSERVATION_STATUS_UPDATE,
    TEAM_EVENT_OBSERVATION_UPSERT,
    TEAM_EVENT_PROMPT_BATCH_META_UPDATE,
    TEAM_EVENT_PROMPT_BATCH_RESPONSE_UPDATE,
    TEAM_EVENT_PROMPT_BATCH_UPSERT,
    TEAM_EVENT_SESSION_END,
    TEAM_EVENT_SESSION_SUMMARY_UPDATE,
    TEAM_EVENT_SESSION_TITLE_UPDATE,
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

    def reconcile_local(self) -> ApplyResult:
        """Re-apply all team_events to fill any local gaps.

        Used by the server node to ensure its own local store matches the team_events
        table. Safe to call repeatedly: INSERT OR REPLACE + content_hash dedup = no-ops
        for already-present records. Processes in chunks to avoid loading the full
        team_events table into memory.
        """
        from open_agent_kit.features.codebase_intelligence.team.protocol import TeamEvent

        result = ApplyResult()
        conn = self._store._get_connection()
        offset = 0

        while True:
            rows = conn.execute(
                "SELECT event_type, payload, source_machine_id, content_hash "
                "FROM team_events ORDER BY id ASC LIMIT ? OFFSET ?",
                (TEAM_BACKFILL_CHUNK_SIZE, offset),
            ).fetchall()
            if not rows:
                break

            events: list[TeamEvent] = []
            for row in rows:
                payload = row["payload"]
                if isinstance(payload, str):
                    payload = json.loads(payload)
                events.append(
                    TeamEvent(
                        event_type=row["event_type"],
                        payload=payload,
                        source_machine_id=row["source_machine_id"] or "",
                        content_hash=row["content_hash"] or "",
                        schema_version=1,
                        timestamp="",
                        project_id="",
                    )
                )

            chunk = self.apply_batch(events)
            result.applied += chunk.applied
            result.skipped += chunk.skipped
            result.errors += chunk.errors
            offset += len(rows)

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
        elif event.event_type == TEAM_EVENT_SESSION_END:
            return self._apply_session_end(payload)
        elif event.event_type == TEAM_EVENT_SESSION_TITLE_UPDATE:
            return self._apply_session_title_update(payload)
        elif event.event_type == TEAM_EVENT_PROMPT_BATCH_UPSERT:
            return self._apply_prompt_batch_upsert(payload)
        elif event.event_type == TEAM_EVENT_PROMPT_BATCH_RESPONSE_UPDATE:
            return self._apply_prompt_batch_response_update(payload)
        elif event.event_type == TEAM_EVENT_PROMPT_BATCH_META_UPDATE:
            return self._apply_prompt_batch_meta_update(payload)
        elif event.event_type == TEAM_EVENT_ACTIVITY_UPSERT:
            return self._apply_activity_upsert(payload)
        elif event.event_type == TEAM_EVENT_OBSERVATION_STATUS_UPDATE:
            return self._apply_observation_status_update(payload)
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

    def _apply_observation_status_update(self, payload: dict) -> bool:
        """Apply an observation status change (resolve/supersede/reactivate).

        Uses COALESCE so a status-only event doesn't overwrite fields that were
        already set. Identified by observation_id (UUID — cross-machine stable).
        """
        observation_id = payload.get("observation_id")
        status = payload.get("status")
        if not observation_id or not status:
            return False

        with self._store._transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE memory_observations
                SET status = ?,
                    resolved_at = COALESCE(?, resolved_at),
                    resolved_by_session_id = COALESCE(?, resolved_by_session_id),
                    superseded_by = COALESCE(?, superseded_by)
                WHERE id = ?
                """,
                (
                    status,
                    payload.get("resolved_at"),
                    payload.get("resolved_by_session_id"),
                    payload.get("superseded_by"),
                    observation_id,
                ),
            )
            updated = cursor.rowcount > 0
        return updated

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

    def _apply_session_end(self, payload: dict) -> bool:
        """Apply a session end event."""
        session_id = payload.get("session_id")
        if not session_id:
            return False
        with self._store._transaction() as conn:
            conn.execute(
                "UPDATE sessions SET ended_at = ?, status = ?, summary = COALESCE(?, summary) WHERE id = ?",
                (
                    payload.get("ended_at"),
                    payload.get("status", "completed"),
                    payload.get("summary"),
                    session_id,
                ),
            )
        return True

    def _apply_session_title_update(self, payload: dict) -> bool:
        """Apply a session title update. Respects manually_edited flag."""
        session_id = payload.get("session_id")
        title = payload.get("title")
        if not session_id or title is None:
            return False
        manually_edited = payload.get("title_manually_edited", False)
        with self._store._transaction() as conn:
            if manually_edited:
                conn.execute(
                    "UPDATE sessions SET title = ?, title_manually_edited = ? WHERE id = ?",
                    (title, True, session_id),
                )
            else:
                # Only update if not manually edited locally
                conn.execute(
                    "UPDATE sessions SET title = ? WHERE id = ? AND (title_manually_edited IS NULL OR title_manually_edited = 0)",
                    (title, session_id),
                )
        return True

    def _ensure_session_exists(self, conn: sqlite3.Connection, payload: dict) -> None:
        """Create a stub session row if the referenced session doesn't exist yet.

        Events can arrive out of order (activity before its session), so we
        insert a minimal placeholder that will be overwritten when the real
        session_upsert event is applied (INSERT OR REPLACE).
        """
        session_id = payload.get("session_id")
        if not session_id:
            return
        conn.execute(
            """
            INSERT OR IGNORE INTO sessions
            (id, agent, project_root, started_at, status, prompt_count, tool_count,
             processed, created_at_epoch, source_machine_id, summary_embedded)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                payload.get("agent", "unknown"),
                payload.get("project_root", ""),
                payload.get("started_at"),
                "active",
                0,
                0,
                False,
                payload.get("created_at_epoch", 0),
                payload.get("source_machine_id"),
                0,
            ),
        )

    def _apply_prompt_batch_upsert(self, payload: dict) -> bool:
        """Apply a prompt batch upsert. Dedup by content_hash."""
        content_hash = payload.get("content_hash")
        if content_hash:
            conn = self._store._get_connection()
            existing = conn.execute(
                "SELECT 1 FROM prompt_batches WHERE content_hash = ? LIMIT 1",
                (content_hash,),
            ).fetchone()
            if existing:
                return False

        with self._store._transaction() as conn:
            self._ensure_session_exists(conn, payload)
            conn.execute(
                """
                INSERT OR REPLACE INTO prompt_batches
                (session_id, prompt_number, user_prompt, started_at, ended_at,
                 status, activity_count, processed, classification, source_type,
                 plan_file_path, plan_content, created_at_epoch, source_machine_id,
                 content_hash, response_summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.get("session_id"),
                    payload.get("prompt_number", 0),
                    payload.get("user_prompt"),
                    payload.get("started_at"),
                    payload.get("ended_at"),
                    payload.get("status", "active"),
                    payload.get("activity_count", 0),
                    payload.get("processed", False),
                    payload.get("classification"),
                    payload.get("source_type", "user"),
                    payload.get("plan_file_path"),
                    payload.get("plan_content"),
                    payload.get("created_at_epoch", 0),
                    payload.get("source_machine_id"),
                    content_hash,
                    payload.get("response_summary"),
                ),
            )
        return True

    def _apply_prompt_batch_response_update(self, payload: dict) -> bool:
        """Apply a prompt batch response/completion update.

        Updates response_summary, status, and ended_at on an existing batch,
        identified by its cross-machine stable content_hash (hash of
        session_id + prompt_number).  Uses COALESCE so that a response-only
        event doesn't overwrite an already-set status, and vice-versa.
        """
        batch_content_hash = payload.get("batch_content_hash")
        if not batch_content_hash:
            return False

        with self._store._transaction() as conn:
            conn.execute(
                """
                UPDATE prompt_batches
                SET response_summary = COALESCE(?, response_summary),
                    status = COALESCE(?, status),
                    ended_at = COALESCE(?, ended_at),
                    classification = COALESCE(?, classification),
                    processed = COALESCE(?, processed)
                WHERE content_hash = ?
                """,
                (
                    payload.get("response_summary"),
                    payload.get("status"),
                    payload.get("ended_at"),
                    payload.get("classification"),
                    payload.get("processed"),
                    batch_content_hash,
                ),
            )
        return True

    def _apply_prompt_batch_meta_update(self, payload: dict) -> bool:
        """Apply a prompt batch metadata update (source_type, plan fields).

        Uses natural key (session_id + prompt_number) for cross-machine stability.
        COALESCE ensures existing values are not overwritten with NULL.
        """
        session_id = payload.get("session_id")
        prompt_number = payload.get("prompt_number")
        if not session_id or prompt_number is None:
            return False
        with self._store._transaction() as conn:
            cursor = conn.execute(
                """
                UPDATE prompt_batches
                SET source_type = COALESCE(?, source_type),
                    plan_file_path = COALESCE(?, plan_file_path),
                    plan_content = COALESCE(?, plan_content)
                WHERE session_id = ? AND prompt_number = ?
                """,
                (
                    payload.get("source_type"),
                    payload.get("plan_file_path"),
                    payload.get("plan_content"),
                    session_id,
                    prompt_number,
                ),
            )
            updated = cursor.rowcount > 0
        return updated

    def _apply_activity_upsert(self, payload: dict) -> bool:
        """Apply an activity upsert. Dedup by content_hash."""
        content_hash = payload.get("content_hash")
        if content_hash:
            conn = self._store._get_connection()
            existing = conn.execute(
                "SELECT 1 FROM activities WHERE content_hash = ? LIMIT 1",
                (content_hash,),
            ).fetchone()
            if existing:
                return False

        with self._store._transaction() as conn:
            self._ensure_session_exists(conn, payload)

            # Natural-key FK resolution: use (session_id, batch_prompt_number) instead of
            # the sender's integer prompt_batch_id (which is local to the sender's DB).
            session_id = payload.get("session_id")
            batch_prompt_number = payload.get("batch_prompt_number")

            if batch_prompt_number is not None and session_id:
                row = conn.execute(
                    "SELECT id FROM prompt_batches WHERE session_id = ? AND prompt_number = ?",
                    (session_id, batch_prompt_number),
                ).fetchone()
                local_batch_id = row["id"] if row else None
            else:
                # Fallback for events without batch_prompt_number (older format).
                # Use the sender's integer as best-effort; may be None cross-machine.
                local_batch_id = payload.get("prompt_batch_id")

            conn.execute(
                """
                INSERT OR REPLACE INTO activities
                (session_id, prompt_batch_id, tool_name, tool_input, tool_output_summary,
                 file_path, files_affected, duration_ms, success, error_message,
                 timestamp, timestamp_epoch, processed, observation_id,
                 source_machine_id, content_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.get("session_id"),
                    local_batch_id,  # resolved local FK
                    payload.get("tool_name"),
                    payload.get("tool_input"),
                    payload.get("tool_output_summary"),
                    payload.get("file_path"),
                    payload.get("files_affected"),
                    payload.get("duration_ms"),
                    payload.get("success"),
                    payload.get("error_message"),
                    payload.get("timestamp"),
                    payload.get("timestamp_epoch"),
                    payload.get("processed", False),
                    payload.get("observation_id"),
                    payload.get("source_machine_id"),
                    content_hash,
                ),
            )
        return True
