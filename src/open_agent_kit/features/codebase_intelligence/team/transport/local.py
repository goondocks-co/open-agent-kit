"""Local transport for server-mode outbox sync.

In server mode the daemon *is* the team server, so events produced locally
are written directly into the ``team_events`` table via ``store_events()``
rather than being sent over HTTP.  No pull worker is needed because
client-pushed events are already applied in the push endpoint.
"""

import logging
import sqlite3
from collections.abc import Callable

from open_agent_kit.features.codebase_intelligence.constants.team import (
    TEAM_LOG_LOCAL_TRANSPORT,
)
from open_agent_kit.features.codebase_intelligence.team.protocol import (
    PushResult,
    TeamEventBatch,
    TeamPullRequest,
    TransportStatus,
)
from open_agent_kit.features.codebase_intelligence.team.server.cursors import (
    get_latest_cursor,
    store_events,
)
from open_agent_kit.features.codebase_intelligence.team.transport.base import (
    TeamTransport,
)

logger = logging.getLogger(__name__)


class LocalTransport(TeamTransport):
    """Transport for server mode — writes events directly to the local event table.

    Args:
        conn_factory: Callable returning a ``sqlite3.Connection`` with the
            ``team_events`` table available.
        project_id: Project identity string for stored events.
    """

    def __init__(
        self,
        conn_factory: Callable[[], sqlite3.Connection],
        project_id: str,
    ) -> None:
        self._conn_factory = conn_factory
        self._project_id = project_id
        logger.info(TEAM_LOG_LOCAL_TRANSPORT)

    async def push_events(self, batch: TeamEventBatch) -> PushResult:
        """Store events directly in the team_events table."""
        conn = self._conn_factory()
        accepted = store_events(conn, batch.events, self._project_id)
        cursor = get_latest_cursor(conn) or ""
        return PushResult(
            accepted=accepted,
            rejected=len(batch.events) - accepted,
            cursor=cursor,
        )

    async def pull_events(self, request: TeamPullRequest) -> TeamEventBatch:
        """No-op — server doesn't pull from itself.

        Client events are applied via ``_apply_events_locally()`` in the
        push endpoint.
        """
        return TeamEventBatch(events=[], cursor=request.since_cursor)

    async def connect(self) -> None:
        """No-op — local transport is always connected."""

    async def disconnect(self) -> None:
        """No-op — nothing to tear down."""

    def get_status(self) -> TransportStatus:
        """Always connected."""
        return TransportStatus(connected=True, last_error=None)
