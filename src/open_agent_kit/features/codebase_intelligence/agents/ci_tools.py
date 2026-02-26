"""Shared CI tool-set builder for agent subsystem.

Provides ``build_ci_tools_from_access()`` which maps an ``AgentCIAccess``
definition to the set of CI tool names that should be enabled.  Used by
both ``AgentExecutor`` and ``InteractiveSessionManager``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from open_agent_kit.features.codebase_intelligence.constants import (
    CI_TOOL_ARCHIVE,
    CI_TOOL_MEMORIES,
    CI_TOOL_PROJECT_STATS,
    CI_TOOL_QUERY,
    CI_TOOL_REMEMBER,
    CI_TOOL_RESOLVE,
    CI_TOOL_SEARCH,
    CI_TOOL_SESSIONS,
)

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.agents.models import AgentCIAccess


def build_ci_tools_from_access(ci_access: AgentCIAccess) -> set[str] | None:
    """Map ``AgentCIAccess`` flags to an enabled-tools set.

    Returns ``None`` when no CI access is requested (the caller should
    skip MCP server creation entirely in that case).

    Args:
        ci_access: Access flags from an agent definition.

    Returns:
        Set of CI tool name strings, or ``None`` if nothing is enabled.
    """
    has_any = (
        ci_access.code_search
        or ci_access.memory_search
        or ci_access.session_history
        or ci_access.project_stats
        or ci_access.sql_query
        or ci_access.memory_write
    )
    if not has_any:
        return None

    enabled: set[str] = set()
    if ci_access.code_search:
        enabled.add(CI_TOOL_SEARCH)
    if ci_access.memory_search:
        enabled.add(CI_TOOL_MEMORIES)
    if ci_access.session_history:
        enabled.add(CI_TOOL_SESSIONS)
    if ci_access.project_stats:
        enabled.add(CI_TOOL_PROJECT_STATS)
    if ci_access.sql_query:
        enabled.add(CI_TOOL_QUERY)
    if ci_access.memory_write:
        enabled.add(CI_TOOL_REMEMBER)
        enabled.add(CI_TOOL_RESOLVE)
        enabled.add(CI_TOOL_ARCHIVE)

    return enabled
