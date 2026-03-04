"""TeamBackfillService: bulk-enqueue historical local data as team events."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from open_agent_kit.features.team.constants.team import (
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
from open_agent_kit.features.team.relay.outbox.writer import enqueue_team_event

if TYPE_CHECKING:
    from open_agent_kit.features.team.activity.store.core import ActivityStore

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
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.run, store)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _backfill_table(
        self,
        store: ActivityStore,
        machine_id: str,
        schema_version: int,
        query: str,
        cursor_column: str,
        event_type: str,
        hash_fn: Callable[[dict[str, Any]], str],
        row_callback: Callable[[dict[str, Any], Any, str, int], None] | None = None,
    ) -> int:
        """Generic keyset-paginated backfill for a single table.

        Args:
            store: Activity store instance.
            machine_id: Source machine identifier.
            schema_version: Current schema version.
            query: SQL query with ``{cursor_clause}`` placeholder for the
                keyset WHERE clause. Must ORDER BY the cursor column ASC.
            cursor_column: Column name used for keyset pagination.
            event_type: Team event type constant.
            hash_fn: Function that derives a content_hash from a row dict.
            row_callback: Optional callback invoked per-row with
                ``(row_dict, write_conn, machine_id, schema_version)``
                for emitting additional events (e.g. batch response updates).

        Returns:
            Number of rows processed.
        """
        conn = store._get_connection()
        cursor_value: int | str = -1
        count = 0

        while True:
            sql = query.format(cursor_clause=f"AND {cursor_column} > ?")
            rows = conn.execute(sql, (machine_id, cursor_value, self.CHUNK_SIZE)).fetchall()
            if not rows:
                break
            with store._transaction() as wconn:
                for row in rows:
                    d = dict(row)
                    ch = hash_fn(d)
                    enqueue_team_event(
                        conn=wconn,
                        event_type=event_type,
                        payload=d,
                        source_machine_id=machine_id,
                        content_hash=ch,
                        schema_version=schema_version,
                    )
                    count += 1
                    if row_callback is not None:
                        row_callback(d, wconn, machine_id, schema_version)
            cursor_value = rows[-1][cursor_column]
            if len(rows) < self.CHUNK_SIZE:
                break

        return count

    def _backfill_sessions(
        self,
        store: ActivityStore,
        machine_id: str,
        schema_version: int,
        result: BackfillResult,
    ) -> None:
        def _session_hash(d: dict[str, Any]) -> str:
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
            _state_hash = hashlib.sha256(json.dumps(_mutable, sort_keys=True).encode()).hexdigest()[
                :12
            ]
            return f"session:{d['id']}:{_state_hash}"

        result.sessions = self._backfill_table(
            store,
            machine_id,
            schema_version,
            query=(
                "SELECT * FROM sessions WHERE source_machine_id = ? "
                "{cursor_clause} ORDER BY created_at_epoch ASC LIMIT ?"
            ),
            cursor_column="created_at_epoch",
            event_type=TEAM_EVENT_SESSION_UPSERT,
            hash_fn=_session_hash,
        )

    def _backfill_batches(
        self,
        store: ActivityStore,
        machine_id: str,
        schema_version: int,
        result: BackfillResult,
    ) -> None:
        def _batch_hash(d: dict[str, Any]) -> str:
            return d.get("content_hash") or f"{d['session_id']}:prompt:{d['prompt_number']}"

        def _emit_response(
            d: dict[str, Any],
            wconn: Any,
            mid: str,
            sv: int,
        ) -> None:
            if d.get("response_summary") or d.get("status") == "completed":
                ch = _batch_hash(d)
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
                        "source_machine_id": mid,
                    },
                    source_machine_id=mid,
                    content_hash=f"batch_response_backfill:{ch}",
                    schema_version=sv,
                )

        result.batches = self._backfill_table(
            store,
            machine_id,
            schema_version,
            query=(
                "SELECT * FROM prompt_batches WHERE source_machine_id = ? "
                "{cursor_clause} ORDER BY created_at_epoch ASC LIMIT ?"
            ),
            cursor_column="created_at_epoch",
            event_type=TEAM_EVENT_PROMPT_BATCH_UPSERT,
            hash_fn=_batch_hash,
            row_callback=_emit_response,
        )

    def _backfill_observations(
        self,
        store: ActivityStore,
        machine_id: str,
        schema_version: int,
        result: BackfillResult,
    ) -> None:
        result.observations = self._backfill_table(
            store,
            machine_id,
            schema_version,
            query=(
                "SELECT * FROM memory_observations WHERE source_machine_id = ? "
                "{cursor_clause} ORDER BY created_at_epoch ASC LIMIT ?"
            ),
            cursor_column="created_at_epoch",
            event_type=TEAM_EVENT_OBSERVATION_UPSERT,
            hash_fn=lambda d: d.get("content_hash") or f"obs:{d['id']}",
        )

    def _backfill_activities(
        self,
        store: ActivityStore,
        machine_id: str,
        schema_version: int,
        result: BackfillResult,
    ) -> None:
        result.activities = self._backfill_table(
            store,
            machine_id,
            schema_version,
            query=(
                "SELECT a.*, pb.prompt_number AS batch_prompt_number "
                "FROM activities a "
                "LEFT JOIN prompt_batches pb ON a.prompt_batch_id = pb.id "
                "WHERE a.source_machine_id = ? "
                "{cursor_clause} ORDER BY a.timestamp_epoch ASC LIMIT ?"
            ),
            cursor_column="timestamp_epoch",
            event_type=TEAM_EVENT_ACTIVITY_UPSERT,
            hash_fn=lambda d: d.get("content_hash") or f"activity:{d['id']}",
        )

    def _backfill_resolution_events(
        self,
        store: ActivityStore,
        machine_id: str,
        schema_version: int,
        result: BackfillResult,
    ) -> None:
        result.resolution_events = self._backfill_table(
            store,
            machine_id,
            schema_version,
            query=(
                "SELECT * FROM resolution_events WHERE source_machine_id = ? "
                "{cursor_clause} ORDER BY created_at_epoch ASC LIMIT ?"
            ),
            cursor_column="created_at_epoch",
            event_type=TEAM_EVENT_OBSERVATION_RESOLVED,
            hash_fn=lambda d: d.get("content_hash") or f"res:{d['id']}",
        )

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
