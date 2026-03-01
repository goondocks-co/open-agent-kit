"""TeamBackfillService: bulk-enqueue historical local data as team events."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from open_agent_kit.features.codebase_intelligence.constants.team import (
    TEAM_BACKFILL_CHUNK_SIZE,
    TEAM_BACKFILL_STATE_KEY_COMPLETED_AT,
    TEAM_BACKFILL_STATE_KEY_COUNTS,
    TEAM_BACKFILL_STATE_KEY_SCHEMA_VERSION,
    TEAM_EVENT_ACTIVITY_UPSERT,
    TEAM_EVENT_OBSERVATION_RESOLVED,
    TEAM_EVENT_OBSERVATION_UPSERT,
    TEAM_EVENT_PROMPT_BATCH_RESPONSE_UPDATE,
    TEAM_EVENT_PROMPT_BATCH_UPSERT,
    TEAM_EVENT_SESSION_UPSERT,
)
from open_agent_kit.features.codebase_intelligence.team.outbox.writer import enqueue_team_event

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.store.core import ActivityStore

logger = logging.getLogger(__name__)


@dataclass
class BackfillResult:
    sessions: int = 0
    batches: int = 0
    observations: int = 0
    activities: int = 0
    resolution_events: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return (
            self.sessions
            + self.batches
            + self.observations
            + self.activities
            + self.resolution_events
        )


class TeamBackfillService:
    """Bulk-enqueues all historical local data into the team outbox.

    Uses the same content_hashes as normal emission, so server dedup
    makes repeated runs idempotent.
    """

    CHUNK_SIZE = TEAM_BACKFILL_CHUNK_SIZE

    def needs_backfill(self, store: ActivityStore) -> bool:
        """Return True if no completed backfill exists at the current schema version."""
        conn = store._get_connection()
        schema_version = store.get_schema_version()
        row = conn.execute(
            "SELECT value FROM team_sync_state WHERE key = ?",
            (TEAM_BACKFILL_STATE_KEY_SCHEMA_VERSION,),
        ).fetchone()
        if not row:
            return True
        try:
            return int(row["value"]) != schema_version
        except (ValueError, TypeError):
            return True

    def run(self, store: ActivityStore) -> BackfillResult:
        """Bulk-enqueue all local rows as team events.

        Order: sessions -> prompt_batches -> observations -> activities -> resolution_events.
        Processes in chunks to avoid long outbox lock times.
        """
        result = BackfillResult()
        machine_id = store.machine_id or "unknown"
        schema_version = store.get_schema_version()

        try:
            self._backfill_sessions(store, machine_id, schema_version, result)
            self._backfill_batches(store, machine_id, schema_version, result)
            self._backfill_observations(store, machine_id, schema_version, result)
            self._backfill_activities(store, machine_id, schema_version, result)
            self._backfill_resolution_events(store, machine_id, schema_version, result)
            self._mark_complete(store, schema_version, result)
            logger.info(
                "Team backfill complete: %d sessions, %d batches, %d observations, "
                "%d activities, %d resolution_events",
                result.sessions,
                result.batches,
                result.observations,
                result.activities,
                result.resolution_events,
            )
        except Exception as exc:
            logger.exception("Team backfill failed")
            result.errors.append(str(exc))

        return result

    async def run_async(self, store: ActivityStore) -> BackfillResult:
        """Async wrapper -- runs run() in a thread executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.run, store)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _backfill_sessions(
        self,
        store: ActivityStore,
        machine_id: str,
        schema_version: int,
        result: BackfillResult,
    ) -> None:
        conn = store._get_connection()
        offset = 0
        while True:
            rows = conn.execute(
                "SELECT * FROM sessions WHERE source_machine_id = ? "
                "ORDER BY created_at_epoch ASC LIMIT ? OFFSET ?",
                (machine_id, self.CHUNK_SIZE, offset),
            ).fetchall()
            if not rows:
                break
            with store._transaction() as wconn:
                for row in rows:
                    d = dict(row)
                    # Hash includes mutable session fields so that updates
                    # (summary, title, status, ended_at) produce a new
                    # content_hash and bypass outbox/server deduplication.
                    _mutable = {
                        k: d.get(k)
                        for k in (
                            "status",
                            "ended_at",
                            "summary",
                            "summary_updated_at",
                            "title",
                            "title_manually_edited",
                            "prompt_count",
                            "tool_count",
                        )
                    }
                    _state_hash = hashlib.sha256(
                        json.dumps(_mutable, sort_keys=True).encode()
                    ).hexdigest()[:12]
                    ch = f"session:{d['id']}:{_state_hash}"
                    enqueue_team_event(
                        conn=wconn,
                        event_type=TEAM_EVENT_SESSION_UPSERT,
                        payload=d,
                        source_machine_id=machine_id,
                        content_hash=ch,
                        schema_version=schema_version,
                    )
                    result.sessions += 1
            offset += len(rows)
            if len(rows) < self.CHUNK_SIZE:
                break

    def _backfill_batches(
        self,
        store: ActivityStore,
        machine_id: str,
        schema_version: int,
        result: BackfillResult,
    ) -> None:
        conn = store._get_connection()
        offset = 0
        while True:
            rows = conn.execute(
                "SELECT * FROM prompt_batches WHERE source_machine_id = ? "
                "ORDER BY created_at_epoch ASC LIMIT ? OFFSET ?",
                (machine_id, self.CHUNK_SIZE, offset),
            ).fetchall()
            if not rows:
                break
            with store._transaction() as wconn:
                for row in rows:
                    d = dict(row)
                    ch = d.get("content_hash") or f"{d['session_id']}:prompt:{d['prompt_number']}"
                    enqueue_team_event(
                        conn=wconn,
                        event_type=TEAM_EVENT_PROMPT_BATCH_UPSERT,
                        payload=d,
                        source_machine_id=machine_id,
                        content_hash=ch,
                        schema_version=schema_version,
                    )
                    result.batches += 1
                    # If batch has a response, also emit a response update
                    if d.get("response_summary") or d.get("status") == "completed":
                        enqueue_team_event(
                            conn=wconn,
                            event_type=TEAM_EVENT_PROMPT_BATCH_RESPONSE_UPDATE,
                            payload={
                                "batch_content_hash": ch,
                                "session_id": d["session_id"],
                                "prompt_number": d["prompt_number"],
                                "response_summary": d.get("response_summary"),
                                "status": d.get("status"),
                                "ended_at": d.get("ended_at"),
                                "classification": d.get("classification"),
                                "processed": d.get("processed"),
                                "source_machine_id": machine_id,
                            },
                            source_machine_id=machine_id,
                            content_hash=f"batch_response_backfill:{ch}",
                            schema_version=schema_version,
                        )
            offset += len(rows)
            if len(rows) < self.CHUNK_SIZE:
                break

    def _backfill_observations(
        self,
        store: ActivityStore,
        machine_id: str,
        schema_version: int,
        result: BackfillResult,
    ) -> None:
        conn = store._get_connection()
        offset = 0
        while True:
            rows = conn.execute(
                "SELECT * FROM memory_observations WHERE source_machine_id = ? "
                "ORDER BY created_at_epoch ASC LIMIT ? OFFSET ?",
                (machine_id, self.CHUNK_SIZE, offset),
            ).fetchall()
            if not rows:
                break
            with store._transaction() as wconn:
                for row in rows:
                    d = dict(row)
                    ch = d.get("content_hash") or f"obs:{d['id']}"
                    enqueue_team_event(
                        conn=wconn,
                        event_type=TEAM_EVENT_OBSERVATION_UPSERT,
                        payload=d,
                        source_machine_id=machine_id,
                        content_hash=ch,
                        schema_version=schema_version,
                    )
                    result.observations += 1
            offset += len(rows)
            if len(rows) < self.CHUNK_SIZE:
                break

    def _backfill_activities(
        self,
        store: ActivityStore,
        machine_id: str,
        schema_version: int,
        result: BackfillResult,
    ) -> None:
        conn = store._get_connection()
        offset = 0
        while True:
            rows = conn.execute(
                """
                SELECT a.*, pb.prompt_number AS batch_prompt_number
                FROM activities a
                LEFT JOIN prompt_batches pb ON a.prompt_batch_id = pb.id
                WHERE a.source_machine_id = ?
                ORDER BY a.timestamp_epoch ASC
                LIMIT ? OFFSET ?
                """,
                (machine_id, self.CHUNK_SIZE, offset),
            ).fetchall()
            if not rows:
                break
            with store._transaction() as wconn:
                for row in rows:
                    d = dict(row)
                    ch = d.get("content_hash") or f"activity:{d['id']}"
                    enqueue_team_event(
                        conn=wconn,
                        event_type=TEAM_EVENT_ACTIVITY_UPSERT,
                        payload=d,
                        source_machine_id=machine_id,
                        content_hash=ch,
                        schema_version=schema_version,
                    )
                    result.activities += 1
            offset += len(rows)
            if len(rows) < self.CHUNK_SIZE:
                break

    def _backfill_resolution_events(
        self,
        store: ActivityStore,
        machine_id: str,
        schema_version: int,
        result: BackfillResult,
    ) -> None:
        conn = store._get_connection()
        offset = 0
        while True:
            rows = conn.execute(
                "SELECT * FROM resolution_events WHERE source_machine_id = ? "
                "ORDER BY created_at_epoch ASC LIMIT ? OFFSET ?",
                (machine_id, self.CHUNK_SIZE, offset),
            ).fetchall()
            if not rows:
                break
            with store._transaction() as wconn:
                for row in rows:
                    d = dict(row)
                    ch = d.get("content_hash") or f"res:{d['id']}"
                    enqueue_team_event(
                        conn=wconn,
                        event_type=TEAM_EVENT_OBSERVATION_RESOLVED,
                        payload=d,
                        source_machine_id=machine_id,
                        content_hash=ch,
                        schema_version=schema_version,
                    )
                    result.resolution_events += 1
            offset += len(rows)
            if len(rows) < self.CHUNK_SIZE:
                break

    def _mark_complete(
        self,
        store: ActivityStore,
        schema_version: int,
        result: BackfillResult,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        with store._transaction() as conn:
            for key, value in [
                (TEAM_BACKFILL_STATE_KEY_COMPLETED_AT, now),
                (TEAM_BACKFILL_STATE_KEY_SCHEMA_VERSION, str(schema_version)),
                (
                    TEAM_BACKFILL_STATE_KEY_COUNTS,
                    json.dumps(
                        {
                            "sessions": result.sessions,
                            "batches": result.batches,
                            "observations": result.observations,
                            "activities": result.activities,
                            "resolution_events": result.resolution_events,
                        }
                    ),
                ),
            ]:
                conn.execute(
                    "INSERT OR REPLACE INTO team_sync_state (key, value, updated_at) "
                    "VALUES (?, ?, ?)",
                    (key, value, now),
                )
