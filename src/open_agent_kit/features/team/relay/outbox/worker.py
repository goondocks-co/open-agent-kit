"""Background worker that flushes observation events from the team outbox
to the cloud relay.

Uses a daemon thread with a timer loop and exponential backoff on failure.
The relay client (CloudRelayClient) is injected via set_relay_client().
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from open_agent_kit.features.team.constants.team import (
    TEAM_LOG_SYNC_ERROR,
    TEAM_LOG_SYNC_FLUSH,
    TEAM_LOG_SYNC_STARTED,
    TEAM_LOG_SYNC_STOPPED,
    TEAM_OUTBOX_BATCH_SIZE,
    TEAM_OUTBOX_BATCH_SIZE_BURST,
    TEAM_OUTBOX_BURST_THRESHOLD,
    TEAM_OUTBOX_FAILED_PRUNE_AGE_HOURS,
    TEAM_OUTBOX_MAX_RETRY_COUNT,
    TEAM_OUTBOX_PRUNE_AGE_HOURS,
    TEAM_OUTBOX_STATUS_FAILED,
    TEAM_OUTBOX_STATUS_PENDING,
    TEAM_OUTBOX_STATUS_SENT,
    TEAM_SYNC_MAX_BACKOFF_SECONDS,
)
from open_agent_kit.features.team.relay.protocol import (
    TeamSyncStatus,
)

if TYPE_CHECKING:
    from open_agent_kit.features.team.activity.store.core import ActivityStore
    from open_agent_kit.features.team.config.team import TeamConfig

logger = logging.getLogger(__name__)


@runtime_checkable
class RelayClientProtocol(Protocol):
    """Protocol for relay clients used by ObsFlushWorker."""

    async def push_observations(self, observations: list[dict]) -> None: ...


class ObsFlushWorker:
    """Background worker that flushes outbox observation events to the cloud relay.

    Lifecycle:
        1. start() spawns a daemon thread running _run_loop().
        2. _run_loop() sleeps for the configured interval, then calls _flush_outbox().
        3. stop() signals the thread to exit gracefully.

    The relay client is injected via set_relay_client(). If no relay client is
    available, flush is a no-op (events accumulate in the outbox until the
    client is set).
    """

    def __init__(
        self,
        store: ActivityStore,
        config: TeamConfig,
        project_id: str,
    ) -> None:
        self._store = store
        self._config = config
        self._project_id = project_id
        self._relay_client: RelayClientProtocol | None = None
        self._event_loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        # Status tracking (thread-safe via lock)
        self._lock = threading.Lock()
        self._last_sync: str | None = None
        self._last_error: str | None = None
        self._events_sent_total: int = 0

    def set_relay_client(self, relay_client: RelayClientProtocol) -> None:
        """Set or replace the relay client used for pushing observations.

        Captures the running event loop so the worker thread can schedule
        async relay calls via ``asyncio.run_coroutine_threadsafe``.

        Args:
            relay_client: CloudRelayClient instance (or compatible).
        """
        self._relay_client = relay_client
        try:
            self._event_loop = asyncio.get_running_loop()
        except RuntimeError:
            self._event_loop = None

    def start(self) -> None:
        """Start the background flush timer."""
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="obs-flush-worker",
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
        """Timer loop: sleep(interval), flush, repeat.

        Uses exponential backoff on consecutive failures to avoid
        hammering a downed relay. Resets to the base interval on success.
        """
        consecutive_failures = 0
        while not self._stop_event.is_set():
            backoff = min(
                self._config.sync_interval_seconds * (2 ** min(consecutive_failures, 6)),
                TEAM_SYNC_MAX_BACKOFF_SECONDS,
            )
            self._stop_event.wait(timeout=backoff)
            if self._stop_event.is_set():
                break
            try:
                flushed = self._flush_outbox()
                consecutive_failures = 0
                if flushed > 0:
                    logger.info(TEAM_LOG_SYNC_FLUSH.format(count=flushed))
            except Exception as exc:
                consecutive_failures += 1
                logger.error(TEAM_LOG_SYNC_ERROR.format(error=exc))
                with self._lock:
                    self._last_error = str(exc)

    def flush(self) -> int:
        """Public entry point for on-demand outbox flush.

        Returns:
            Number of events flushed successfully.
        """
        return self._flush_outbox()

    def _flush_outbox(self) -> int:
        """Flush pending outbox events to the cloud relay.

        SELECT pending events -> extract observation payloads ->
        push via relay_client -> UPDATE status to sent.
        On failure: increment retry_count.
        Prune sent events older than the configured age.

        Returns:
            Number of events flushed successfully.
        """
        if self._relay_client is None:
            return 0

        conn = self._store._get_connection()

        # Choose batch size: use burst limit when the queue is deep
        depth_row = conn.execute(
            "SELECT COUNT(*) FROM team_outbox WHERE status = ?",
            (TEAM_OUTBOX_STATUS_PENDING,),
        ).fetchone()
        pending_count = depth_row[0] if depth_row else 0
        batch_limit = (
            TEAM_OUTBOX_BATCH_SIZE_BURST
            if pending_count >= TEAM_OUTBOX_BURST_THRESHOLD
            else TEAM_OUTBOX_BATCH_SIZE
        )

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
            (TEAM_OUTBOX_STATUS_PENDING, TEAM_OUTBOX_MAX_RETRY_COUNT, batch_limit),
        )
        rows = cursor.fetchall()
        if not rows:
            self._prune_sent_events()
            return 0

        # Build observation list for relay
        obs_list: list[dict[str, Any]] = []
        row_ids: list[int] = []
        for row in rows:
            row_ids.append(row[0])
            payload = json.loads(row[2]) if isinstance(row[2], str) else row[2]
            obs_list.append(
                {
                    "event_type": row[1],
                    "payload": payload,
                    "source_machine_id": row[3],
                    "content_hash": row[4],
                    "schema_version": row[5],
                    "timestamp": row[6],
                    "project_id": self._project_id,
                }
            )

        # Push via relay client (async method — schedule from this thread)
        try:
            coro = self._relay_client.push_observations(obs_list)
            if self._event_loop is not None and self._event_loop.is_running():
                future = asyncio.run_coroutine_threadsafe(coro, self._event_loop)
                future.result(timeout=30)
            else:
                raise RuntimeError("No event loop available for obs push")
            accepted = len(obs_list)
        except Exception as exc:
            self._mark_retry(row_ids, str(exc))
            raise

        # Mark all events as sent
        if accepted > 0:
            self._mark_sent(row_ids[:accepted])

        with self._lock:
            self._events_sent_total += accepted
            self._last_sync = datetime.now(UTC).isoformat()
            self._last_error = None

        self._prune_sent_events()
        return accepted

    def _mark_sent(self, row_ids: list[int]) -> None:
        """Mark outbox rows as sent."""
        if not row_ids:
            return
        placeholders = ",".join("?" * len(row_ids))
        with self._store._transaction() as tx:
            tx.execute(
                f"UPDATE team_outbox SET status = ? WHERE id IN ({placeholders})",
                [TEAM_OUTBOX_STATUS_SENT, *row_ids],
            )

    def _mark_retry(self, row_ids: list[int], error: str) -> None:
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

    def _prune_sent_events(self) -> None:
        """Delete sent and permanently-failed events older than the configured prune ages."""
        from datetime import timedelta

        sent_cutoff = (datetime.now(UTC) - timedelta(hours=TEAM_OUTBOX_PRUNE_AGE_HOURS)).isoformat()
        failed_cutoff = (
            datetime.now(UTC) - timedelta(hours=TEAM_OUTBOX_FAILED_PRUNE_AGE_HOURS)
        ).isoformat()
        with self._store._transaction() as tx:
            tx.execute(
                "DELETE FROM team_outbox WHERE status = ? AND created_at < ?",
                (TEAM_OUTBOX_STATUS_SENT, sent_cutoff),
            )
            tx.execute(
                "DELETE FROM team_outbox WHERE status = ? AND created_at < ?",
                (TEAM_OUTBOX_STATUS_FAILED, failed_cutoff),
            )

    def get_status(self) -> TeamSyncStatus:
        """Return current sync status.

        Returns:
            TeamSyncStatus with queue depth and sync state.
        """
        try:
            conn = self._store._get_connection()
            cursor = conn.execute(
                "SELECT COUNT(*) FROM team_outbox WHERE status = ?",
                (TEAM_OUTBOX_STATUS_PENDING,),
            )
            result = cursor.fetchone()
            queue_depth = int(result[0]) if result else 0
        except Exception:
            logger.warning("Failed to query outbox queue depth", exc_info=True)
            queue_depth = -1

        with self._lock:
            return TeamSyncStatus(
                enabled=True,
                queue_depth=queue_depth,
                last_sync=self._last_sync,
                last_error=self._last_error,
                events_sent_total=self._events_sent_total,
            )
