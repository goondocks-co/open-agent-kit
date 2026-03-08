"""Swarm daemon state management."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from open_agent_kit.features.swarm.daemon.client import (
        SwarmWorkerClient,
    )


@dataclass
class SwarmDaemonState:
    """Type-safe state container for the swarm daemon."""

    swarm_url: str = ""
    swarm_token: str = ""
    swarm_id: str = ""
    custom_domain: str = ""
    auth_token: str | None = None
    http_client: SwarmWorkerClient | None = None


_state: SwarmDaemonState | None = None


def get_swarm_state() -> SwarmDaemonState:
    """Get the singleton swarm daemon state, creating it if needed."""
    global _state  # noqa: PLW0603
    if _state is None:
        _state = SwarmDaemonState()
    return _state


def reset_swarm_state() -> None:
    """Reset the swarm daemon state (primarily for testing)."""
    global _state  # noqa: PLW0603
    _state = None
