"""Background worker that pulls events from the team server.

Uses a daemon thread with a timer loop, following the same pattern as
the outbox TeamSyncWorker for background work with graceful shutdown.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from open_agent_kit.features.codebase_intelligence.constants.team import (
    TEAM_LOG_PULL_APPLIED,
    TEAM_LOG_PULL_ERROR,
    TEAM_LOG_PULL_STARTED,
    TEAM_LOG_PULL_STOPPED,
)
from open_agent_kit.features.codebase_intelligence.team.protocol import (
    TeamPullRequest,
    TeamPullStatus,
)

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.store.core import ActivityStore
    from open_agent_kit.features.codebase_intelligence.config.team import TeamConfig
    from open_agent_kit.features.codebase_intelligence.team.pull.applier import TeamEventApplier
    from open_agent_kit.features.codebase_intelligence.team.transport.base import TeamTransport

logger = logging.getLogger(__name__)


class TeamPullWorker:
    """Background worker that polls the team server for new events.

    Lifecycle:
        1. start() spawns a daemon thread running _run_loop().
        2. _run_loop() sleeps for the configured interval, then calls _pull_and_apply().
        3. stop() signals the thread to exit gracefully.

    The transport is injected via set_transport(). If no transport is available,
    pull is a no-op (events accumulate on the server until transport is set).
    """

    def __init__(
        self,
        store: ActivityStore,
        config: TeamConfig,
        project_id: str,
        machine_id: str,
    ) -> None:
        self._store = store
        self._config = config
        self._project_id = project_id
        self._machine_id = machine_id
        self._transport: TeamTransport | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        # Lazy-initialized applier (set in _pull_and_apply)
        self._applier: TeamEventApplier | None = None

        # Status tracking (thread-safe via lock)
        self._lock = threading.Lock()
        self._last_pull: str | None = None
        self._last_error: str | None = None
        self._events_applied_total: int = 0

    def set_transport(self, transport: TeamTransport) -> None:
        """Set or replace the transport used for pulling events.

        Args:
            transport: Transport implementation for pulling events.
        """
        self._transport = transport

    def start(self) -> None:
        """Start the background pull timer."""
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="team-pull-worker",
            daemon=True,
        )
        self._thread.start()
        logger.info(TEAM_LOG_PULL_STARTED.format(interval=self._config.pull_interval_seconds))

    def stop(self) -> None:
        """Stop the worker gracefully."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
        logger.info(TEAM_LOG_PULL_STOPPED)

    def _run_loop(self) -> None:
        """Timer loop: sleep(interval), pull, repeat."""
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=self._config.pull_interval_seconds)
            if self._stop_event.is_set():
                break
            try:
                applied = self._pull_and_apply()
                if applied > 0:
                    logger.info(TEAM_LOG_PULL_APPLIED.format(count=applied))
            except Exception as exc:
                logger.error(TEAM_LOG_PULL_ERROR.format(error=exc))
                with self._lock:
                    self._last_error = str(exc)

    def _pull_and_apply(self) -> int:
        """Pull events from server and apply them locally.

        Returns:
            Number of events applied.
        """
        if self._transport is None:
            return 0

        from open_agent_kit.features.codebase_intelligence.team.pull.applier import (
            TeamEventApplier,
        )

        if self._applier is None:
            self._applier = TeamEventApplier(self._store)  # type: ignore[assignment]

        applier = self._applier

        # Read cursor from team_pull_cursor table
        cursor = self._read_cursor()

        # Build pull request (exclude our own events)
        request = TeamPullRequest(
            since_cursor=cursor,
            exclude_machine_id=self._machine_id,
        )

        # Pull events via transport (async -> sync bridge)
        try:
            loop = asyncio.new_event_loop()
            try:
                batch = loop.run_until_complete(self._transport.pull_events(request))
            finally:
                loop.close()
        except Exception as e:
            with self._lock:
                self._last_error = str(e)
            raise

        if not batch.events:
            return 0

        # Apply events to local store
        result = applier.apply_batch(batch.events)

        with self._lock:
            self._events_applied_total += result.applied
            self._last_pull = datetime.now(UTC).isoformat()
            self._last_error = None

        # Save cursor for next pull
        if batch.cursor:
            self._save_cursor(batch.cursor)

        applied: int = result.applied
        return applied

    def _read_cursor(self) -> str | None:
        """Read the pull cursor for the configured server URL.

        Returns:
            Cursor string, or None if no cursor has been saved.
        """
        server_url = self._config.server_url or ""
        conn = self._store._get_connection()
        row = conn.execute(
            "SELECT cursor_value FROM team_pull_cursor WHERE server_url = ?",
            (server_url,),
        ).fetchone()
        return row[0] if row else None

    def _save_cursor(self, cursor: str) -> None:
        """Persist the pull cursor for the configured server URL.

        Args:
            cursor: New cursor value from the server.
        """
        server_url = self._config.server_url or ""
        now = datetime.now(UTC).isoformat()
        with self._store._transaction() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO team_pull_cursor "
                "(server_url, cursor_value, updated_at) VALUES (?, ?, ?)",
                (server_url, cursor, now),
            )

    def get_status(self) -> TeamPullStatus:
        """Return current pull status.

        Returns:
            TeamPullStatus with pull state and cursor info.
        """
        cursor = None
        try:
            cursor = self._read_cursor()
        except Exception:
            pass

        with self._lock:
            return TeamPullStatus(
                enabled=True,
                last_pull=self._last_pull,
                events_applied_total=self._events_applied_total,
                cursor=cursor,
            )
