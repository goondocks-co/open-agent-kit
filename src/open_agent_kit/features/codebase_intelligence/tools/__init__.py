"""Shared CI tool logic for MCP and SDK integrations.

This package contains the core implementation of CI tools that can be
used by both:
- daemon/mcp_tools.py (MCP protocol handlers)
- agents/tools.py (claude-code-sdk tool wrappers)

The separation keeps protocol-specific code thin while sharing the
actual tool logic.
"""

from open_agent_kit.features.codebase_intelligence.tools.formatting import (
    format_code_results,
    format_context_results,
    format_memory_results,
    format_plan_results,
    format_search_results,
    format_session_results,
)
from open_agent_kit.features.codebase_intelligence.tools.operations import (
    ToolOperations,
)
from open_agent_kit.features.codebase_intelligence.tools.schemas import (
    ContextInput,
    MemoriesInput,
    RememberInput,
    SearchInput,
    SessionsInput,
    StatsInput,
)

__all__ = [
    # Formatting
    "format_code_results",
    "format_memory_results",
    "format_plan_results",
    "format_session_results",
    "format_search_results",
    "format_context_results",
    # Operations
    "ToolOperations",
    # Schemas
    "SearchInput",
    "RememberInput",
    "ContextInput",
    "MemoriesInput",
    "SessionsInput",
    "StatsInput",
]
