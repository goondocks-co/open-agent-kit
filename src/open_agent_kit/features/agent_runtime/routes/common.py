"""Shared helpers for agent route modules.

Provides duck-typed ``get_agent_components()`` that works with both
``DaemonState`` (team) and ``SwarmDaemonState`` (swarm).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import HTTPException

if TYPE_CHECKING:
    from open_agent_kit.features.agent_runtime.executor import AgentExecutor
    from open_agent_kit.features.agent_runtime.registry import AgentRegistry


def get_agent_components(
    state: Any,
) -> tuple[AgentRegistry, AgentExecutor, Any]:
    """Get agent registry and executor from a daemon state object.

    Duck-typed: works with any state object that has ``agent_registry``
    and ``agent_executor`` attributes.

    Args:
        state: Daemon state (DaemonState or SwarmDaemonState).

    Returns:
        Tuple of (registry, executor, state).

    Raises:
        HTTPException: 503 if registry or executor not initialized.
    """
    if not getattr(state, "agent_registry", None):
        raise HTTPException(
            status_code=503,
            detail="Agent registry not initialized. Agents may be disabled in config.",
        )

    if not getattr(state, "agent_executor", None):
        raise HTTPException(
            status_code=503,
            detail="Agent executor not initialized. Agents may be disabled in config.",
        )

    return state.agent_registry, state.agent_executor, state
