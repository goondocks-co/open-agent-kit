"""Base classes for tunnel providers.

Defines the abstract interface and shared data structures for tunnel sharing.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from open_agent_kit.features.codebase_intelligence.constants import (
    TUNNEL_RESPONSE_KEY_ACTIVE,
    TUNNEL_RESPONSE_KEY_ERROR,
    TUNNEL_RESPONSE_KEY_PROVIDER,
    TUNNEL_RESPONSE_KEY_PUBLIC_URL,
    TUNNEL_RESPONSE_KEY_STARTED_AT,
)


@dataclass
class TunnelStatus:
    """Status of a tunnel connection.

    Attributes:
        active: Whether the tunnel is currently active.
        public_url: The public URL of the tunnel (None if inactive).
        provider_name: Name of the tunnel provider.
        started_at: ISO timestamp when the tunnel was started.
        error: Error message if the tunnel failed to start.
    """

    active: bool
    public_url: str | None = None
    provider_name: str | None = None
    started_at: str | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            TUNNEL_RESPONSE_KEY_ACTIVE: self.active,
            TUNNEL_RESPONSE_KEY_PUBLIC_URL: self.public_url,
            TUNNEL_RESPONSE_KEY_PROVIDER: self.provider_name,
            TUNNEL_RESPONSE_KEY_STARTED_AT: self.started_at,
            TUNNEL_RESPONSE_KEY_ERROR: self.error,
        }


class TunnelProvider(ABC):
    """Abstract base class for tunnel providers.

    Implementations must provide start/stop/status methods and
    indicate whether the provider binary/SDK is available.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name."""
        ...

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider binary or SDK is installed."""
        ...

    @abstractmethod
    def start(self, local_port: int) -> TunnelStatus:
        """Start the tunnel to the given local port.

        Args:
            local_port: The local port the daemon is listening on.

        Returns:
            TunnelStatus with the public URL on success.
        """
        ...

    @abstractmethod
    def stop(self) -> None:
        """Stop the tunnel if running."""
        ...

    @abstractmethod
    def get_status(self) -> TunnelStatus:
        """Get current tunnel status.

        Returns:
            TunnelStatus reflecting the current state.
        """
        ...
