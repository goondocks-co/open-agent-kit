"""CI Agent Subsystem — backward-compatibility re-exports.

Core runtime classes have moved to ``open_agent_kit.features.agent_runtime``.
This shim re-exports them so existing imports continue to work.

CI-specific adapters (ci_tools, context_injection, activity_recorder)
remain in this package.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from open_agent_kit.features.agent_runtime.executor import AgentExecutor as AgentExecutor
    from open_agent_kit.features.agent_runtime.models import (
        AgentDefinition as AgentDefinition,
    )
    from open_agent_kit.features.agent_runtime.models import (
        AgentRun as AgentRun,
    )
    from open_agent_kit.features.agent_runtime.models import (
        AgentRunStatus as AgentRunStatus,
    )
    from open_agent_kit.features.agent_runtime.registry import AgentRegistry as AgentRegistry


def __getattr__(name: str) -> Any:
    """Lazy re-exports to avoid circular imports."""
    if name == "AgentExecutor":
        from open_agent_kit.features.agent_runtime.executor import AgentExecutor

        return AgentExecutor
    if name == "AgentRegistry":
        from open_agent_kit.features.agent_runtime.registry import AgentRegistry

        return AgentRegistry
    if name == "AgentDefinition":
        from open_agent_kit.features.agent_runtime.models import AgentDefinition

        return AgentDefinition
    if name == "AgentRun":
        from open_agent_kit.features.agent_runtime.models import AgentRun

        return AgentRun
    if name == "AgentRunStatus":
        from open_agent_kit.features.agent_runtime.models import AgentRunStatus

        return AgentRunStatus
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "AgentDefinition",
    "AgentExecutor",
    "AgentRegistry",
    "AgentRun",
    "AgentRunStatus",
]
