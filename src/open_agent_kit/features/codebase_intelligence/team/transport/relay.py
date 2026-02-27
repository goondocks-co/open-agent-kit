"""Cloudflare Worker relay transport for team event sync.

Delegates all operations to an HttpTransport instance pointed at the
relay worker URL. The Worker proxies HTTP requests over the WebSocket
connection to the local daemon, making this transport transparent to
callers.
"""

from open_agent_kit.features.codebase_intelligence.config.team import TeamConfig
from open_agent_kit.features.codebase_intelligence.team.protocol import (
    PushResult,
    TeamEventBatch,
    TeamPullRequest,
    TransportStatus,
)
from open_agent_kit.features.codebase_intelligence.team.transport.base import (
    TeamTransport,
)
from open_agent_kit.features.codebase_intelligence.team.transport.http import (
    HttpTransport,
)


class RelayTransport(TeamTransport):
    """CF Worker relay transport -- delegates to HttpTransport.

    The relay worker URL is used as the server URL, causing all team API
    requests to flow through the Cloudflare Worker's HTTP proxy, which
    forwards them over the WebSocket connection to the local daemon.

    Args:
        config: Team configuration with relay settings.
    """

    def __init__(self, config: TeamConfig) -> None:
        self._config = config
        self._inner = HttpTransport(
            server_url=config.relay_worker_url or "",
            token=config.api_key or "",
        )

    async def push_events(self, batch: TeamEventBatch) -> PushResult:
        """Push events via the relay worker."""
        return await self._inner.push_events(batch)

    async def pull_events(self, request: TeamPullRequest) -> TeamEventBatch:
        """Pull events via the relay worker."""
        return await self._inner.pull_events(request)

    async def connect(self) -> None:
        """Establish connection via the relay worker."""
        await self._inner.connect()

    async def disconnect(self) -> None:
        """Disconnect from the relay worker."""
        await self._inner.disconnect()

    def get_status(self) -> TransportStatus:
        """Return current transport status."""
        return self._inner.get_status()
