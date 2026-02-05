"""Tests for the AgentExecutor."""

from pathlib import Path

from open_agent_kit.features.codebase_intelligence.agents.executor import AgentExecutor
from open_agent_kit.features.codebase_intelligence.agents.models import (
    AgentDefinition,
    AgentTask,
    MaintainedFile,
)
from open_agent_kit.features.codebase_intelligence.config import AgentConfig


class TestAgentExecutorTaskPrompt:
    """Tests for AgentExecutor task prompt building."""

    def test_build_task_prompt_without_task(self, tmp_path: Path) -> None:
        """Task prompt should include runtime context even without agent_task."""
        executor = AgentExecutor(project_root=tmp_path, agent_config=AgentConfig())
        agent = AgentDefinition(
            name="test",
            display_name="Test Agent",
            description="Test agent",
        )

        task = "Update the documentation"
        prompt = executor._build_task_prompt(agent, task)

        # Should include task and runtime context with daemon_url
        assert task in prompt
        assert "## Runtime Context" in prompt
        assert "daemon_url:" in prompt

    def test_build_task_prompt_with_task(self, tmp_path: Path) -> None:
        """Task prompt should include task config when provided."""
        executor = AgentExecutor(project_root=tmp_path, agent_config=AgentConfig())
        agent = AgentDefinition(
            name="test",
            display_name="Test Agent",
            description="Test agent",
        )
        agent_task = AgentTask(
            name="test-task",
            display_name="Test Task",
            agent_type="test",
            default_task="Do the thing",
            maintained_files=[
                MaintainedFile(path="README.md", purpose="Overview"),
            ],
            style={"tone": "concise"},
        )

        task = "Update the documentation"
        prompt = executor._build_task_prompt(agent, task, agent_task)

        assert task in prompt
        assert "## Task Configuration" in prompt
        assert "```yaml" in prompt
        assert "daemon_url:" in prompt
        assert "maintained_files:" in prompt
        assert "README.md" in prompt
        assert "tone: concise" in prompt

    def test_build_task_prompt_with_empty_task(self, tmp_path: Path) -> None:
        """Task prompt should include daemon_url even with minimal agent_task."""
        executor = AgentExecutor(project_root=tmp_path, agent_config=AgentConfig())
        agent = AgentDefinition(
            name="test",
            display_name="Test Agent",
            description="Test agent",
        )
        agent_task = AgentTask(
            name="test-task",
            display_name="Test Task",
            agent_type="test",
            default_task="Do the thing",
        )

        task = "Update the documentation"
        prompt = executor._build_task_prompt(agent, task, agent_task)

        # Even with minimal agent_task, should include daemon_url
        assert task in prompt
        assert "## Task Configuration" in prompt
        assert "daemon_url:" in prompt
