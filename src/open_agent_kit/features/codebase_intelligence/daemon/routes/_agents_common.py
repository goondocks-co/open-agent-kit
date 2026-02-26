"""Shared helpers for agent route modules.

Provides the common ``get_agent_components()`` helper used by agents.py,
agent_runs.py, and agent_settings.py to obtain the registry, executor,
and daemon state — raising HTTP 503 when agents are not initialized.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException

from open_agent_kit.features.codebase_intelligence.daemon.state import get_state

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.agents.executor import AgentExecutor
    from open_agent_kit.features.codebase_intelligence.agents.registry import AgentRegistry
    from open_agent_kit.features.codebase_intelligence.daemon.state import DaemonState


def get_agent_components() -> tuple[AgentRegistry, AgentExecutor, DaemonState]:
    """Get agent registry and executor or raise HTTP error."""
    state = get_state()

    if not state.agent_registry:
        raise HTTPException(
            status_code=503,
            detail="Agent registry not initialized. Agents may be disabled in config.",
        )

    if not state.agent_executor:
        raise HTTPException(
            status_code=503,
            detail="Agent executor not initialized. Agents may be disabled in config.",
        )

    return state.agent_registry, state.agent_executor, state
