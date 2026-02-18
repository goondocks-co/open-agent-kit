"""Base classes for Cloud MCP Relay.

Defines the abstract interface and shared data structures for the
WebSocket-based cloud relay through a Cloudflare Worker.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from open_agent_kit.features.codebase_intelligence.constants import (
    CLOUD_RELAY_RESPONSE_KEY_CONNECTED,
    CLOUD_RELAY_RESPONSE_KEY_CONNECTED_AT,
    CLOUD_RELAY_RESPONSE_KEY_ERROR,
    CLOUD_RELAY_RESPONSE_KEY_LAST_HEARTBEAT,
    CLOUD_RELAY_RESPONSE_KEY_RECONNECT_ATTEMPTS,
    CLOUD_RELAY_RESPONSE_KEY_WORKER_URL,
)


@dataclass
class RelayStatus:
    """Status of a cloud relay connection.

    Attributes:
        connected: Whether the relay is currently connected.
        worker_url: The Cloudflare Worker URL (None if not connected).
        connected_at: ISO timestamp when the relay was connected.
        last_heartbeat: ISO timestamp of the last successful heartbeat.
        error: Error message if the relay is in an error state.
        reconnect_attempts: Number of reconnect attempts since last successful connection.
    """

    connected: bool
    worker_url: str | None = None
    connected_at: str | None = None
    last_heartbeat: str | None = None
    error: str | None = None
    reconnect_attempts: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            CLOUD_RELAY_RESPONSE_KEY_CONNECTED: self.connected,
            CLOUD_RELAY_RESPONSE_KEY_WORKER_URL: self.worker_url,
            CLOUD_RELAY_RESPONSE_KEY_CONNECTED_AT: self.connected_at,
            CLOUD_RELAY_RESPONSE_KEY_LAST_HEARTBEAT: self.last_heartbeat,
            CLOUD_RELAY_RESPONSE_KEY_ERROR: self.error,
            CLOUD_RELAY_RESPONSE_KEY_RECONNECT_ATTEMPTS: self.reconnect_attempts,
        }


class RelayClient(ABC):
    """Abstract base class for cloud relay clients.

    Implementations must provide connect/disconnect/status methods for
    maintaining a WebSocket connection to the Cloudflare Worker.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable client name."""
        ...

    @abstractmethod
    async def connect(
        self,
        worker_url: str,
        token: str,
        daemon_port: int,
    ) -> RelayStatus:
        """Connect to the cloud relay worker.

        Args:
            worker_url: URL of the Cloudflare Worker.
            token: Shared secret for authentication.
            daemon_port: Local daemon port (for tool call forwarding).

        Returns:
            RelayStatus reflecting the connection state.
        """
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the cloud relay."""
        ...

    @abstractmethod
    def get_status(self) -> RelayStatus:
        """Get current relay connection status.

        Returns:
            RelayStatus reflecting the current state.
        """
        ...
