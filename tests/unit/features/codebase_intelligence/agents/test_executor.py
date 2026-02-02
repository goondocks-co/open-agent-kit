"""Tests for the AgentExecutor."""

from pathlib import Path

from open_agent_kit.features.codebase_intelligence.agents.executor import AgentExecutor
from open_agent_kit.features.codebase_intelligence.agents.models import (
    AgentDefinition,
    AgentInstance,
    MaintainedFile,
)
from open_agent_kit.features.codebase_intelligence.config import AgentConfig


class TestAgentExecutorTaskPrompt:
    """Tests for AgentExecutor task prompt building."""

    def test_build_task_prompt_without_instance(self, tmp_path: Path) -> None:
        """Task prompt should include runtime context even without instance."""
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

    def test_build_task_prompt_with_instance(self, tmp_path: Path) -> None:
        """Task prompt should include instance config when provided."""
        executor = AgentExecutor(project_root=tmp_path, agent_config=AgentConfig())
        agent = AgentDefinition(
            name="test",
            display_name="Test Agent",
            description="Test agent",
        )
        instance = AgentInstance(
            name="test-instance",
            display_name="Test Instance",
            agent_type="test",
            default_task="Do the thing",
            maintained_files=[
                MaintainedFile(path="README.md", purpose="Overview"),
            ],
            style={"tone": "concise"},
        )

        task = "Update the documentation"
        prompt = executor._build_task_prompt(agent, task, instance)

        assert task in prompt
        assert "## Instance Configuration" in prompt
        assert "```yaml" in prompt
        assert "daemon_url:" in prompt
        assert "maintained_files:" in prompt
        assert "README.md" in prompt
        assert "tone: concise" in prompt

    def test_build_task_prompt_with_empty_instance(self, tmp_path: Path) -> None:
        """Task prompt should include daemon_url even with minimal instance."""
        executor = AgentExecutor(project_root=tmp_path, agent_config=AgentConfig())
        agent = AgentDefinition(
            name="test",
            display_name="Test Agent",
            description="Test agent",
        )
        instance = AgentInstance(
            name="test-instance",
            display_name="Test Instance",
            agent_type="test",
            default_task="Do the thing",
        )

        task = "Update the documentation"
        prompt = executor._build_task_prompt(agent, task, instance)

        # Even with minimal instance, should include daemon_url
        assert task in prompt
        assert "## Instance Configuration" in prompt
        assert "daemon_url:" in prompt
