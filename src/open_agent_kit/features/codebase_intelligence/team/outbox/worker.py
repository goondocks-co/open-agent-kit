"""Background worker that flushes the team outbox to the team server.

Uses a daemon thread with a timer loop, following the same pattern as
cloud_relay/client.py for background work with reconnect/backoff.
"""

import json
import logging
import threading
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol

from open_agent_kit.features.codebase_intelligence.constants.team import (
    TEAM_LOG_SYNC_ERROR,
    TEAM_LOG_SYNC_FLUSH,
    TEAM_LOG_SYNC_STARTED,
    TEAM_LOG_SYNC_STOPPED,
    TEAM_OUTBOX_BATCH_SIZE,
    TEAM_OUTBOX_MAX_RETRY_COUNT,
    TEAM_OUTBOX_PRUNE_AGE_HOURS,
    TEAM_OUTBOX_STATUS_FAILED,
    TEAM_OUTBOX_STATUS_PENDING,
    TEAM_OUTBOX_STATUS_SENT,
)
from open_agent_kit.features.codebase_intelligence.team.protocol import (
    TeamEvent,
    TeamEventBatch,
    TeamSyncStatus,
)

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.store.core import ActivityStore
    from open_agent_kit.features.codebase_intelligence.config.team import TeamConfig

logger = logging.getLogger(__name__)


class TeamTransport(Protocol):
    """Protocol for team transport implementations.

    Defined here as a protocol so the worker can be built and tested
    independently of the Phase 2 transport module.
    """

    def push_events(self, batch: TeamEventBatch) -> int:
        """Push a batch of events to the team server.

        Args:
            batch: Events to push.

        Returns:
            Number of events accepted by the server.

        Raises:
            Exception: On transport failure.
        """
        ...


class TeamSyncWorker:
    """Background worker that flushes outbox events to the team server.

    Lifecycle:
        1. start() spawns a daemon thread running _run_loop().
        2. _run_loop() sleeps for the configured interval, then calls _flush_outbox().
        3. stop() signals the thread to exit gracefully.

    The transport is injected via set_transport(). If no transport is available,
    flush is a no-op (events accumulate in the outbox until transport is set).
    """

    def __init__(
        self,
        store: "ActivityStore",
        config: "TeamConfig",
        project_id: str,
    ) -> None:
        self._store = store
        self._config = config
        self._project_id = project_id
        self._transport: TeamTransport | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        # Status tracking (thread-safe via lock)
        self._lock = threading.Lock()
        self._last_sync: str | None = None
        self._last_error: str | None = None
        self._events_sent_total: int = 0

    def set_transport(self, transport: TeamTransport) -> None:
        """Set or replace the transport used for pushing events.

        Args:
            transport: Transport implementation for pushing events.
        """
        self._transport = transport

    def start(self) -> None:
        """Start the background flush timer."""
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="team-sync-worker",
            daemon=True,
        )
        self._thread.start()
        logger.info(TEAM_LOG_SYNC_STARTED.format(interval=self._config.sync_interval_seconds))

    def stop(self) -> None:
        """Stop the worker gracefully."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
        logger.info(TEAM_LOG_SYNC_STOPPED)

    def _run_loop(self) -> None:
        """Timer loop: sleep(interval), flush, repeat."""
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=self._config.sync_interval_seconds)
            if self._stop_event.is_set():
                break
            try:
                flushed = self._flush_outbox()
                if flushed > 0:
                    logger.info(TEAM_LOG_SYNC_FLUSH.format(count=flushed))
            except Exception as exc:
                logger.error(TEAM_LOG_SYNC_ERROR.format(error=exc))
                with self._lock:
                    self._last_error = str(exc)

    def _flush_outbox(self) -> int:
        """Flush pending outbox events to the team server.

        SELECT pending events -> build TeamEventBatch -> push via transport
        -> UPDATE status to sent. On failure: increment retry_count, set
        error_message. Prune sent events older than the configured age.

        Returns:
            Number of events flushed successfully.
        """
        if self._transport is None:
            return 0

        conn = self._store._get_connection()

        # Select pending events that haven't exceeded retry limit
        cursor = conn.execute(
            """
            SELECT id, event_type, payload, source_machine_id, content_hash,
                   schema_version, created_at
            FROM team_outbox
            WHERE status = ? AND retry_count < ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (TEAM_OUTBOX_STATUS_PENDING, TEAM_OUTBOX_MAX_RETRY_COUNT, TEAM_OUTBOX_BATCH_SIZE),
        )
        rows = cursor.fetchall()
        if not rows:
            self._prune_sent_events(conn)
            return 0

        # Build batch
        events: list[TeamEvent] = []
        row_ids: list[int] = []
        for row in rows:
            row_ids.append(row[0])
            payload = json.loads(row[2]) if isinstance(row[2], str) else row[2]
            events.append(
                TeamEvent(
                    event_type=row[1],
                    payload=payload,
                    source_machine_id=row[3],
                    content_hash=row[4],
                    schema_version=row[5],
                    timestamp=row[6],
                    project_id=self._project_id,
                )
            )

        batch = TeamEventBatch(events=events)

        # Push via transport
        try:
            accepted = self._transport.push_events(batch)
        except Exception as exc:
            # Mark all rows as retry-incremented
            self._mark_retry(conn, row_ids, str(exc))
            raise

        # Mark accepted events as sent
        if accepted > 0:
            sent_ids = row_ids[:accepted]
            self._mark_sent(conn, sent_ids)

        # Mark remaining (rejected) as retry
        if accepted < len(row_ids):
            rejected_ids = row_ids[accepted:]
            self._mark_retry(conn, rejected_ids, "rejected by server")

        with self._lock:
            self._events_sent_total += accepted
            self._last_sync = datetime.now(UTC).isoformat()
            self._last_error = None

        self._prune_sent_events(conn)
        return accepted

    def _mark_sent(self, conn: Any, row_ids: list[int]) -> None:
        """Mark outbox rows as sent."""
        if not row_ids:
            return
        placeholders = ",".join("?" * len(row_ids))
        with self._store._transaction() as tx:
            tx.execute(
                f"UPDATE team_outbox SET status = ? WHERE id IN ({placeholders})",
                [TEAM_OUTBOX_STATUS_SENT, *row_ids],
            )

    def _mark_retry(self, conn: Any, row_ids: list[int], error: str) -> None:
        """Increment retry count and record error for outbox rows."""
        if not row_ids:
            return
        placeholders = ",".join("?" * len(row_ids))
        with self._store._transaction() as tx:
            tx.execute(
                f"""
                UPDATE team_outbox
                SET retry_count = retry_count + 1,
                    error_message = ?,
                    status = CASE
                        WHEN retry_count + 1 >= ? THEN ?
                        ELSE status
                    END
                WHERE id IN ({placeholders})
                """,
                [error, TEAM_OUTBOX_MAX_RETRY_COUNT, TEAM_OUTBOX_STATUS_FAILED, *row_ids],
            )

    def _prune_sent_events(self, conn: Any) -> None:
        """Delete sent events older than the configured prune age."""
        from datetime import timedelta

        cutoff = (datetime.now(UTC) - timedelta(hours=TEAM_OUTBOX_PRUNE_AGE_HOURS)).isoformat()
        with self._store._transaction() as tx:
            tx.execute(
                "DELETE FROM team_outbox WHERE status = ? AND created_at < ?",
                (TEAM_OUTBOX_STATUS_SENT, cutoff),
            )

    def get_status(self) -> TeamSyncStatus:
        """Return current sync status.

        Returns:
            TeamSyncStatus with queue depth and sync state.
        """
        # Get queue depth from database
        try:
            conn = self._store._get_connection()
            cursor = conn.execute(
                "SELECT COUNT(*) FROM team_outbox WHERE status = ?",
                (TEAM_OUTBOX_STATUS_PENDING,),
            )
            result = cursor.fetchone()
            queue_depth = int(result[0]) if result else 0
        except Exception:
            queue_depth = 0

        with self._lock:
            return TeamSyncStatus(
                enabled=True,
                queue_depth=queue_depth,
                last_sync=self._last_sync,
                last_error=self._last_error,
                events_sent_total=self._events_sent_total,
            )
