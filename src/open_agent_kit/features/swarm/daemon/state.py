"""Swarm daemon state management."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterator, MutableMapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from open_agent_kit.features.agent_runtime.executor import AgentExecutor
    from open_agent_kit.features.agent_runtime.registry import AgentRegistry
    from open_agent_kit.features.swarm.daemon.client import (
        SwarmWorkerClient,
    )

_MAX_AGENT_SESSIONS = 1000


class _LRUDict(MutableMapping[str, Any]):
    """OrderedDict-backed mapping with a maximum size and LRU eviction."""

    def __init__(self, maxsize: int = _MAX_AGENT_SESSIONS) -> None:
        self._maxsize = maxsize
        self._data: OrderedDict[str, Any] = OrderedDict()

    # --- MutableMapping interface ---

    def __getitem__(self, key: str) -> Any:
        value = self._data[key]
        self._data.move_to_end(key)
        return value

    def __setitem__(self, key: str, value: Any) -> None:
        if key in self._data:
            self._data.move_to_end(key)
        self._data[key] = value
        while len(self._data) > self._maxsize:
            self._data.popitem(last=False)

    def __delitem__(self, key: str) -> None:
        del self._data[key]

    def __iter__(self) -> Iterator[str]:  # type: ignore[override]
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __repr__(self) -> str:
        return f"_LRUDict(maxsize={self._maxsize}, len={len(self._data)})"


@dataclass
class SwarmDaemonState:
    """Type-safe state container for the swarm daemon."""

    swarm_url: str = ""
    swarm_token: str = ""
    swarm_id: str = ""
    custom_domain: str = ""
    auth_token: str | None = None
    http_client: SwarmWorkerClient | None = None
    agent_sessions: _LRUDict = field(default_factory=_LRUDict)

    # Agent runtime (initialized in server lifespan)
    agent_registry: AgentRegistry | None = None
    agent_executor: AgentExecutor | None = None


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
