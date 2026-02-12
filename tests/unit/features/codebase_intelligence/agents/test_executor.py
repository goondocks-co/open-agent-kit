"""Tests for the AgentExecutor."""

import logging
from pathlib import Path

import pytest

from open_agent_kit.features.codebase_intelligence.agents.executor import AgentExecutor
from open_agent_kit.features.codebase_intelligence.agents.models import (
    AgentDefinition,
    AgentProvider,
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


class TestConfigAccessor:
    """Tests for live config accessor pattern (stale-config fix).

    Services receive a config_accessor callable that returns the current
    CIConfig. This ensures config changes via the UI take effect immediately
    without a daemon restart.
    """

    def test_accessor_reads_live_provider_settings(self, tmp_path: Path) -> None:
        """Executor reads provider config from accessor, not init snapshot."""
        from open_agent_kit.features.codebase_intelligence.config import CIConfig

        live_config = CIConfig()
        live_config.agents = AgentConfig(provider_type="cloud")
        executor = AgentExecutor(
            project_root=tmp_path,
            agent_config=AgentConfig(),  # static fallback (ignored when accessor set)
            config_accessor=lambda: live_config,
        )

        # Simulate user changing provider via the UI settings page
        live_config.agents = AgentConfig(
            provider_type="lmstudio",
            provider_base_url="http://localhost:1234",
            provider_model="mistralai/devstral-small-2-2512",
        )

        # Executor should see the updated config without any explicit push
        assert executor._agent_config.provider_type == "lmstudio"
        assert executor._agent_config.provider_base_url == "http://localhost:1234"
        assert executor._agent_config.provider_model == "mistralai/devstral-small-2-2512"

    def test_fallback_used_when_no_accessor(self, tmp_path: Path) -> None:
        """Without config_accessor, executor uses static fallback (test path)."""
        fallback = AgentConfig(max_turns=5)
        executor = AgentExecutor(project_root=tmp_path, agent_config=fallback)

        assert executor._agent_config.max_turns == 5

    def test_accessor_none_return_uses_fallback(self, tmp_path: Path) -> None:
        """If accessor returns None, executor falls back to static config."""
        fallback = AgentConfig(max_turns=7)
        executor = AgentExecutor(
            project_root=tmp_path,
            agent_config=fallback,
            config_accessor=lambda: None,
        )

        assert executor._agent_config.max_turns == 7


class TestApplyProviderEnv:
    """Tests for _apply_provider_env security (M-SEC4)."""

    def test_api_key_value_absent_from_logs(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify _apply_provider_env does not log API key values."""
        executor = AgentExecutor(project_root=tmp_path, agent_config=AgentConfig())
        secret_key = "sk-supersecretkey1234567890abcdef"
        provider = AgentProvider(
            type="openrouter",
            api_key=secret_key,
            base_url="https://openrouter.ai/api/v1",
        )

        with caplog.at_level(
            logging.DEBUG, logger="open_agent_kit.features.codebase_intelligence.agents.executor"
        ):
            original = executor._apply_provider_env(provider)
            executor._restore_provider_env(original)

        # The key VALUE must not appear in any log message
        for record in caplog.records:
            assert (
                secret_key[:20] not in record.getMessage()
            ), f"API key value leaked in log: {record.getMessage()}"
            assert (
                secret_key not in record.getMessage()
            ), f"Full API key leaked in log: {record.getMessage()}"
