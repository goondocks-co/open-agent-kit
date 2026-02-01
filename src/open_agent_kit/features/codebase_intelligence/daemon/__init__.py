"""Daemon server for Codebase Intelligence.

This module uses lazy imports to avoid loading heavy dependencies (FastAPI, etc.)
until they're actually needed. This allows the DaemonManager to be imported
for lifecycle hooks without requiring all dependencies to be installed.

State management classes (DaemonState, IndexStatus) are imported directly as
they have no heavy dependencies. Session tracking is handled entirely by SQLite
(ActivityStore) - there is no in-memory session state.
"""

from typing import Any

# State management classes are lightweight - import directly
from open_agent_kit.features.codebase_intelligence.daemon.state import (
    DaemonState,
    IndexStatus,
    daemon_state,
    get_state,
    reset_state,
)


def __getattr__(name: str) -> Any:
    """Lazy import module members to avoid loading heavy dependencies."""
    if name == "DaemonManager":
        from open_agent_kit.features.codebase_intelligence.daemon.manager import (
            DaemonManager,
        )

        return DaemonManager
    elif name == "create_app":
        from open_agent_kit.features.codebase_intelligence.daemon.server import (
            create_app,
        )

        return create_app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "create_app",
    "DaemonManager",
    "DaemonState",
    "IndexStatus",
    "daemon_state",
    "get_state",
    "reset_state",
]
