"""Tests for the AgentRegistry."""

from pathlib import Path

import pytest

from open_agent_kit.features.codebase_intelligence.agents.models import (
    AgentCIAccess,
    AgentDefinition,
    AgentExecution,
    AgentPermissionMode,
)
from open_agent_kit.features.codebase_intelligence.agents.registry import AgentRegistry


class TestAgentRegistry:
    """Tests for AgentRegistry class."""

    def test_registry_loads_builtin_agents(self) -> None:
        """Registry should load built-in agent definitions."""
        registry = AgentRegistry()
        agents = registry.list_agents()

        # Should have at least the documentation agent
        assert len(agents) >= 1

        names = registry.list_names()
        assert "documentation" in names

    def test_registry_get_agent_by_name(self) -> None:
        """Registry should return agent by name."""
        registry = AgentRegistry()

        agent = registry.get("documentation")
        assert agent is not None
        assert agent.name == "documentation"
        assert agent.display_name == "Documentation Agent"

    def test_registry_get_nonexistent_agent_returns_none(self) -> None:
        """Registry should return None for unknown agent."""
        registry = AgentRegistry()

        agent = registry.get("nonexistent_agent")
        assert agent is None

    def test_registry_reload(self) -> None:
        """Registry should support reloading definitions."""
        registry = AgentRegistry()
        registry.load_all()

        # Reload should return count
        count = registry.reload()
        assert count >= 1

    def test_registry_to_dict(self) -> None:
        """Registry should convert to dict for API responses."""
        registry = AgentRegistry()

        result = registry.to_dict()

        assert "count" in result
        assert "agents" in result
        assert "definitions_dir" in result
        assert result["count"] >= 1
        assert "documentation" in result["agents"]

    def test_registry_handles_missing_directory(self, tmp_path: Path) -> None:
        """Registry should handle missing definitions directory."""
        missing_dir = tmp_path / "nonexistent"
        registry = AgentRegistry(definitions_dir=missing_dir)

        count = registry.load_all()
        assert count == 0
        assert len(registry.list_agents()) == 0


class TestAgentDefinition:
    """Tests for AgentDefinition model."""

    def test_documentation_agent_structure(self) -> None:
        """Documentation agent should have expected structure."""
        registry = AgentRegistry()
        agent = registry.get("documentation")
        assert agent is not None

        # Check basic fields
        assert agent.name == "documentation"
        assert "documentation" in agent.description.lower()

        # Check execution settings
        assert agent.execution.max_turns == 100
        assert agent.execution.timeout_seconds == 600
        assert agent.execution.permission_mode == AgentPermissionMode.ACCEPT_EDITS

        # Check allowed tools
        assert "Read" in agent.allowed_tools
        assert "Write" in agent.allowed_tools
        assert "Edit" in agent.allowed_tools

        # Check disallowed tools
        assert "Bash" in agent.disallowed_tools
        assert "Task" in agent.disallowed_tools

        # Check CI access
        assert agent.ci_access.code_search is True
        assert agent.ci_access.memory_search is True
        assert agent.ci_access.session_history is True

        # Check path restrictions
        assert "docs/**" in agent.allowed_paths
        assert "README.md" in agent.allowed_paths
        assert ".env" in agent.disallowed_paths

    def test_get_effective_tools_filters_disallowed(self) -> None:
        """get_effective_tools should remove disallowed tools."""
        agent = AgentDefinition(
            name="test",
            display_name="Test Agent",
            description="Test",
            allowed_tools=["Read", "Write", "Bash"],
            disallowed_tools=["Bash"],
        )

        effective = agent.get_effective_tools()
        assert "Read" in effective
        assert "Write" in effective
        assert "Bash" not in effective

    def test_system_prompt_loaded_from_file(self) -> None:
        """Documentation agent should have system prompt loaded from file."""
        registry = AgentRegistry()
        agent = registry.get("documentation")
        assert agent is not None

        # System prompt should be loaded from prompts/system.md
        assert agent.system_prompt is not None
        assert len(agent.system_prompt) > 100
        assert "Documentation Agent" in agent.system_prompt


class TestAgentModels:
    """Tests for agent Pydantic models."""

    def test_agent_ci_access_defaults(self) -> None:
        """AgentCIAccess should have sensible defaults."""
        access = AgentCIAccess()

        assert access.code_search is True
        assert access.memory_search is True
        assert access.session_history is True
        assert access.project_stats is True

    def test_agent_execution_defaults(self) -> None:
        """AgentExecution should have sensible defaults."""
        execution = AgentExecution()

        assert execution.max_turns == 50
        assert execution.timeout_seconds == 600
        assert execution.permission_mode == AgentPermissionMode.ACCEPT_EDITS

    def test_agent_execution_validation(self) -> None:
        """AgentExecution should validate bounds."""
        # max_turns too low
        with pytest.raises(ValueError):
            AgentExecution(max_turns=0)

        # max_turns too high
        with pytest.raises(ValueError):
            AgentExecution(max_turns=1000)

        # timeout too low
        with pytest.raises(ValueError):
            AgentExecution(timeout_seconds=10)

        # timeout too high
        with pytest.raises(ValueError):
            AgentExecution(timeout_seconds=10000)
