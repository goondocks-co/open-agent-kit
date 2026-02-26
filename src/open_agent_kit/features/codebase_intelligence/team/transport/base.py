"""Abstract base class for team event transport."""

from abc import ABC, abstractmethod

from open_agent_kit.features.codebase_intelligence.team.protocol import (
    PushResult,
    TeamEventBatch,
    TeamPullRequest,
    TransportStatus,
)


class TeamTransport(ABC):
    """Abstract transport for team event sync.

    Implementations handle the details of how events are pushed to and
    pulled from a team server (direct HTTPS, relay WebSocket, etc.).
    """

    @abstractmethod
    async def push_events(self, batch: TeamEventBatch) -> PushResult:
        """Push a batch of events to the team server.

        Args:
            batch: Events to push.

        Returns:
            PushResult with accepted/rejected counts.
        """
        ...

    @abstractmethod
    async def pull_events(self, request: TeamPullRequest) -> TeamEventBatch:
        """Pull events from the team server.

        Args:
            request: Pull request with cursor and filters.

        Returns:
            TeamEventBatch with events and new cursor.
        """
        ...

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the team server."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the team server."""
        ...

    @abstractmethod
    def get_status(self) -> TransportStatus:
        """Get current transport connection status.

        Returns:
            TransportStatus with connection info.
        """
        ...
