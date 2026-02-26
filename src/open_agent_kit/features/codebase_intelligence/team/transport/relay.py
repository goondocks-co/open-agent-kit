"""Cloudflare Worker WebSocket transport -- skeleton for zero-infrastructure path.

This transport will be fleshed out when the Worker relay is extended
for team events. For now, all methods raise NotImplementedError.
"""

from open_agent_kit.features.codebase_intelligence.config.team import TeamConfig
from open_agent_kit.features.codebase_intelligence.constants.team import (
    TEAM_TRANSPORT_ERROR_NOT_IMPLEMENTED,
)
from open_agent_kit.features.codebase_intelligence.team.protocol import (
    PushResult,
    TeamEventBatch,
    TeamPullRequest,
    TransportStatus,
)
from open_agent_kit.features.codebase_intelligence.team.transport.base import (
    TeamTransport,
)


class RelayTransport(TeamTransport):
    """CF Worker WebSocket transport -- stub implementation.

    Args:
        config: Team configuration with relay settings.
    """

    def __init__(self, config: TeamConfig) -> None:
        self._config = config

    async def push_events(self, batch: TeamEventBatch) -> PushResult:
        """Not yet implemented."""
        raise NotImplementedError(TEAM_TRANSPORT_ERROR_NOT_IMPLEMENTED)

    async def pull_events(self, request: TeamPullRequest) -> TeamEventBatch:
        """Not yet implemented."""
        raise NotImplementedError(TEAM_TRANSPORT_ERROR_NOT_IMPLEMENTED)

    async def connect(self) -> None:
        """Not yet implemented."""
        raise NotImplementedError(TEAM_TRANSPORT_ERROR_NOT_IMPLEMENTED)

    async def disconnect(self) -> None:
        """Not yet implemented."""
        raise NotImplementedError(TEAM_TRANSPORT_ERROR_NOT_IMPLEMENTED)

    def get_status(self) -> TransportStatus:
        """Return disconnected status (stub)."""
        return TransportStatus(
            connected=False,
            server_url=self._config.relay_worker_url,
            last_error=TEAM_TRANSPORT_ERROR_NOT_IMPLEMENTED,
        )
