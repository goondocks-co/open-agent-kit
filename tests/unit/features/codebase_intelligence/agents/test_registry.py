"""Tests for the AgentRegistry."""

from pathlib import Path

import pytest

from open_agent_kit.features.codebase_intelligence.agents.models import (
    AgentCIAccess,
    AgentDefinition,
    AgentExecution,
    AgentPermissionMode,
    McpServerConfig,
)
from open_agent_kit.features.codebase_intelligence.agents.registry import AgentRegistry
from open_agent_kit.features.codebase_intelligence.constants import (
    AGENT_ENGINEERING_NAME,
    AGENT_PROJECT_CONFIG_DIR,
)


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
        assert "templates" in result
        assert "tasks" in result
        assert "definitions_dir" in result
        assert result["count"] >= 1
        assert "documentation" in result["templates"]

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
        assert "oak/docs/**" in agent.allowed_paths
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


class TestProjectConfig:
    """Tests for project-level agent configuration."""

    def test_registry_loads_project_config_when_project_root_set(self, tmp_path: Path) -> None:
        """Registry should load project config from oak/agents/{name}.yaml."""
        # Create a mock project structure with config
        config_dir = tmp_path / AGENT_PROJECT_CONFIG_DIR
        config_dir.mkdir(parents=True)

        config_content = """
maintained_files:
  - path: "README.md"
    purpose: "Project overview"
style:
  tone: "formal"
"""
        (config_dir / "documentation.yaml").write_text(config_content)

        # Load registry with project_root
        registry = AgentRegistry(project_root=tmp_path)
        agent = registry.get("documentation")

        assert agent is not None
        assert agent.project_config is not None
        assert "maintained_files" in agent.project_config
        assert agent.project_config["style"]["tone"] == "formal"

    def test_registry_no_project_config_without_project_root(self) -> None:
        """Registry should not load project config when project_root is None."""
        registry = AgentRegistry()
        agent = registry.get("documentation")

        assert agent is not None
        assert agent.project_config is None

    def test_registry_handles_missing_project_config(self, tmp_path: Path) -> None:
        """Registry should handle missing project config gracefully."""
        # Create project root without any agent configs
        (tmp_path / "oak").mkdir()

        registry = AgentRegistry(project_root=tmp_path)
        agent = registry.get("documentation")

        assert agent is not None
        assert agent.project_config is None

    def test_registry_handles_malformed_project_config(self, tmp_path: Path) -> None:
        """Registry should handle malformed project config gracefully."""
        config_dir = tmp_path / AGENT_PROJECT_CONFIG_DIR
        config_dir.mkdir(parents=True)

        # Write invalid YAML
        (config_dir / "documentation.yaml").write_text("{ invalid yaml: [")

        registry = AgentRegistry(project_root=tmp_path)
        agent = registry.get("documentation")

        # Should still load agent, just without config
        assert agent is not None
        assert agent.project_config is None

    def test_load_project_config_method_directly(self, tmp_path: Path) -> None:
        """load_project_config should work as a standalone method."""
        config_dir = tmp_path / AGENT_PROJECT_CONFIG_DIR
        config_dir.mkdir(parents=True)

        config_content = """
features:
  patterns:
    - "src/**"
"""
        (config_dir / "test_agent.yaml").write_text(config_content)

        registry = AgentRegistry(project_root=tmp_path)
        config = registry.load_project_config("test_agent")

        assert config is not None
        assert "features" in config
        assert config["features"]["patterns"] == ["src/**"]


class TestAgentTasks:
    """Tests for agent task functionality."""

    def test_list_tasks_returns_builtins_without_project_root(self) -> None:
        """list_tasks should return built-in tasks even without project_root."""
        registry = AgentRegistry()
        tasks = registry.list_tasks()
        # Should have built-in tasks from the package
        assert len(tasks) >= 1
        # All should be marked as built-in
        for task in tasks:
            assert task.is_builtin is True

    def test_list_tasks_empty_when_no_definitions_dir(self, tmp_path: Path) -> None:
        """list_tasks should return empty list when no definitions dir exists."""
        # Use a non-existent directory for definitions (no templates = no built-in tasks)
        registry = AgentRegistry(definitions_dir=tmp_path / "nonexistent_defs")
        tasks = registry.list_tasks()
        assert tasks == []

    def test_list_templates(self) -> None:
        """list_templates should return all templates."""
        registry = AgentRegistry()
        templates = registry.list_templates()

        assert len(templates) >= 1
        names = [t.name for t in templates]
        assert "documentation" in names

    def test_get_template(self) -> None:
        """get_template should return template by name."""
        registry = AgentRegistry()

        template = registry.get_template("documentation")
        assert template is not None
        assert template.name == "documentation"

    def test_get_task_returns_none_without_tasks(self) -> None:
        """get_task should return None when no tasks exist."""
        registry = AgentRegistry()

        task = registry.get_task("nonexistent")
        assert task is None

    def test_create_task(self, tmp_path: "Path") -> None:
        """create_task should create task YAML file."""
        registry = AgentRegistry(project_root=tmp_path)
        registry.load_all()

        task = registry.create_task(
            name="test-docs",
            template_name="documentation",
            display_name="Test Documentation",
            description="Test task",
            default_task="Update the README",
        )

        assert task.name == "test-docs"
        assert task.display_name == "Test Documentation"
        assert task.agent_type == "documentation"
        # default_task may have extra whitespace due to YAML literal block
        assert "Update the README" in task.default_task

        # File should exist
        yaml_path = tmp_path / AGENT_PROJECT_CONFIG_DIR / "test-docs.yaml"
        assert yaml_path.exists()

        # Task should be registered
        assert registry.get_task("test-docs") is not None

    def test_create_task_invalid_name(self, tmp_path: "Path") -> None:
        """create_task should reject invalid names."""
        registry = AgentRegistry(project_root=tmp_path)
        registry.load_all()

        with pytest.raises(ValueError, match="Invalid task name"):
            registry.create_task(
                name="Invalid Name!",
                template_name="documentation",
                display_name="Test",
                description="",
                default_task="Do something",
            )

    def test_create_task_unknown_template(self, tmp_path: "Path") -> None:
        """create_task should reject unknown templates."""
        registry = AgentRegistry(project_root=tmp_path)
        registry.load_all()

        with pytest.raises(ValueError, match="not found"):
            registry.create_task(
                name="test",
                template_name="nonexistent_template",
                display_name="Test",
                description="",
                default_task="Do something",
            )

    def test_load_tasks_from_project(self, tmp_path: "Path") -> None:
        """Registry should load user tasks from oak/agents/*.yaml."""
        # Create task YAML
        config_dir = tmp_path / AGENT_PROJECT_CONFIG_DIR
        config_dir.mkdir(parents=True)

        task_yaml = """
name: my-docs
display_name: "My Documentation"
agent_type: documentation
description: "Custom docs task"
default_task: |
  Update all markdown files in docs/

maintained_files:
  - path: "docs/*.md"
    purpose: "Project documentation"
"""
        (config_dir / "my-docs.yaml").write_text(task_yaml)

        # Load registry
        registry = AgentRegistry(project_root=tmp_path)
        tasks = registry.list_tasks()

        # Find our user task
        user_task = next((t for t in tasks if t.name == "my-docs"), None)
        assert user_task is not None
        assert user_task.display_name == "My Documentation"
        assert user_task.agent_type == "documentation"
        assert "Update all markdown" in user_task.default_task
        assert user_task.is_builtin is False

    def test_load_tasks_skips_invalid_template_reference(self, tmp_path: "Path") -> None:
        """Registry should skip user tasks with unknown agent_type."""
        config_dir = tmp_path / AGENT_PROJECT_CONFIG_DIR
        config_dir.mkdir(parents=True)

        task_yaml = """
name: bad-task
display_name: "Bad Task"
agent_type: nonexistent_template
default_task: Do something
"""
        (config_dir / "bad-task.yaml").write_text(task_yaml)

        registry = AgentRegistry(project_root=tmp_path)
        tasks = registry.list_tasks()

        # Should skip the bad user task (but may still have built-ins)
        bad_task = next((t for t in tasks if t.name == "bad-task"), None)
        assert bad_task is None


class TestEngineeringAgent:
    """Tests for the engineering agent template and tasks."""

    def test_engineering_agent_loads(self) -> None:
        """Engineering agent template should be discovered by the registry."""
        registry = AgentRegistry()
        agent = registry.get(AGENT_ENGINEERING_NAME)

        assert agent is not None
        assert agent.name == AGENT_ENGINEERING_NAME
        assert agent.display_name == "Engineering Team"

    def test_engineering_agent_structure(self) -> None:
        """Engineering agent should have expected configuration."""
        registry = AgentRegistry()
        agent = registry.get(AGENT_ENGINEERING_NAME)
        assert agent is not None

        # Execution: bypassPermissions, higher limits than documentation
        assert agent.execution.max_turns == 200
        assert agent.execution.timeout_seconds == 1800
        assert agent.execution.permission_mode == AgentPermissionMode.BYPASS_PERMISSIONS

        # Allowed tools — Bash is NOT at template level
        assert "Read" in agent.allowed_tools
        assert "Write" in agent.allowed_tools
        assert "Edit" in agent.allowed_tools
        assert "Glob" in agent.allowed_tools
        assert "Grep" in agent.allowed_tools
        assert "Bash" not in agent.allowed_tools

        # Disallowed tools
        assert "Task" in agent.disallowed_tools

        # Full CI access including sql_query
        assert agent.ci_access.code_search is True
        assert agent.ci_access.memory_search is True
        assert agent.ci_access.session_history is True
        assert agent.ci_access.project_stats is True
        assert agent.ci_access.sql_query is True

        # Security: disallowed paths
        assert ".env" in agent.disallowed_paths

        # External MCP servers declared
        assert "github" in agent.mcp_servers
        assert agent.mcp_servers["github"].enabled is True
        assert agent.mcp_servers["github"].required is False

    def test_engineering_agent_system_prompt(self) -> None:
        """Engineering agent should have a system prompt loaded from file."""
        registry = AgentRegistry()
        agent = registry.get(AGENT_ENGINEERING_NAME)
        assert agent is not None

        assert agent.system_prompt is not None
        assert len(agent.system_prompt) > 100
        assert "Engineering Team Agent" in agent.system_prompt
        assert "ci_search" in agent.system_prompt
        assert "ci_memories" in agent.system_prompt

    def test_engineering_tasks_discovered(self) -> None:
        """Both engineering built-in tasks should be discovered."""
        registry = AgentRegistry()
        tasks = registry.list_tasks()

        engineering_tasks = [t for t in tasks if t.agent_type == AGENT_ENGINEERING_NAME]
        engineering_names = {t.name for t in engineering_tasks}

        assert len(engineering_tasks) == 2
        assert "engineer" in engineering_names
        assert "product-manager" in engineering_names

        # All should be built-in
        for task in engineering_tasks:
            assert task.is_builtin is True

    def test_engineer_has_bash_additional_tools(self) -> None:
        """Engineer task should declare Bash in additional_tools."""
        registry = AgentRegistry()
        task = registry.get_task("engineer")

        assert task is not None
        assert task.agent_type == AGENT_ENGINEERING_NAME
        assert "Bash" in task.additional_tools

    def test_product_manager_has_no_bash(self) -> None:
        """Product manager task should not have Bash in additional_tools."""
        registry = AgentRegistry()
        task = registry.get_task("product-manager")

        assert task is not None
        assert "Bash" not in task.additional_tools

    def test_product_manager_has_maintained_files(self) -> None:
        """Product manager should declare maintained_files for its report."""
        registry = AgentRegistry()
        task = registry.get_task("product-manager")

        assert task is not None
        assert len(task.maintained_files) >= 1


class TestMcpServersParsing:
    """Tests for mcp_servers field parsing from YAML."""

    def test_mcp_servers_parsed_from_agent_yaml(self) -> None:
        """Engineering agent should have mcp_servers parsed from YAML."""
        registry = AgentRegistry()
        agent = registry.get(AGENT_ENGINEERING_NAME)
        assert agent is not None

        assert isinstance(agent.mcp_servers, dict)
        assert "github" in agent.mcp_servers
        assert isinstance(agent.mcp_servers["github"], McpServerConfig)

    def test_documentation_agent_has_no_mcp_servers(self) -> None:
        """Documentation agent (no mcp_servers in YAML) should have empty dict."""
        registry = AgentRegistry()
        agent = registry.get("documentation")
        assert agent is not None

        assert agent.mcp_servers == {}

    def test_additional_tools_parsed_from_task_yaml(self) -> None:
        """Tasks with additional_tools in YAML should have them parsed."""
        registry = AgentRegistry()
        task = registry.get_task("engineer")
        assert task is not None

        assert isinstance(task.additional_tools, list)
        assert "Bash" in task.additional_tools


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
