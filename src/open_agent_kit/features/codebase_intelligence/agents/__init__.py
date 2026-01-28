"""CI Agent Subsystem.

This module provides autonomous agents powered by the Anthropic Agent SDK
(claude-code-sdk) that leverage CI data for intelligent automation tasks.

Components:
- AgentRegistry: Loads and manages agent definitions from YAML
- AgentExecutor: Executes agents using claude-code-sdk
- CI Tools: Custom MCP tools exposing CI data to agents
"""

from open_agent_kit.features.codebase_intelligence.agents.executor import AgentExecutor
from open_agent_kit.features.codebase_intelligence.agents.models import (
    AgentDefinition,
    AgentRun,
    AgentRunStatus,
)
from open_agent_kit.features.codebase_intelligence.agents.registry import AgentRegistry

__all__ = [
    "AgentDefinition",
    "AgentExecutor",
    "AgentRegistry",
    "AgentRun",
    "AgentRunStatus",
]
