"""Tests for the AgentExecutor."""

import logging
from pathlib import Path

import pytest

from open_agent_kit.features.codebase_intelligence.agents.executor import (
    AGENT_FORBIDDEN_TOOLS,
    AgentExecutor,
)
from open_agent_kit.features.codebase_intelligence.agents.models import (
    AgentDefinition,
    AgentProvider,
    AgentTask,
    MaintainedFile,
    McpServerConfig,
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


class TestBashOverridePattern:
    """Tests for additional_tools Bash override in _build_options.

    When a task declares additional_tools: ["Bash"], the Bash restriction
    is lifted for that execution only. Task remains permanently forbidden.
    """

    def _get_allowed_tools(
        self,
        tmp_path: Path,
        agent: AgentDefinition,
        additional_tools: list[str] | None = None,
    ) -> list[str]:
        """Helper to extract allowed_tools from _build_options without SDK dependency.

        Uses the same logic as _build_options for tool filtering without
        actually constructing ClaudeAgentOptions.
        """
        has_bash_override = any(
            t == "Bash" or t.startswith("Bash(") for t in (additional_tools or [])
        )
        forbidden = AGENT_FORBIDDEN_TOOLS
        if has_bash_override:
            forbidden = tuple(t for t in AGENT_FORBIDDEN_TOOLS if t != "Bash")

        allowed_tools = [t for t in agent.get_effective_tools() if t not in forbidden]

        if additional_tools:
            for tool in additional_tools:
                if tool not in forbidden and tool not in allowed_tools:
                    allowed_tools.append(tool)

        return allowed_tools

    def test_bash_in_additional_tools_lifts_restriction(self, tmp_path: Path) -> None:
        """Bash in additional_tools should allow Bash through the filter."""
        agent = AgentDefinition(
            name="test",
            display_name="Test",
            description="Test",
            allowed_tools=["Read", "Write"],
        )

        tools = self._get_allowed_tools(tmp_path, agent, additional_tools=["Bash"])

        assert "Bash" in tools
        assert "Read" in tools
        assert "Write" in tools

    def test_scoped_bash_pattern_lifts_restriction(self, tmp_path: Path) -> None:
        """Scoped Bash(git *) should also lift the Bash restriction."""
        agent = AgentDefinition(
            name="test",
            display_name="Test",
            description="Test",
            allowed_tools=["Read"],
        )

        tools = self._get_allowed_tools(tmp_path, agent, additional_tools=["Bash(git *)"])

        assert "Bash(git *)" in tools
        assert "Read" in tools

    def test_task_remains_forbidden_with_bash_override(self, tmp_path: Path) -> None:
        """Task tool must stay forbidden even when Bash is overridden."""
        agent = AgentDefinition(
            name="test",
            display_name="Test",
            description="Test",
            allowed_tools=["Read"],
        )

        tools = self._get_allowed_tools(tmp_path, agent, additional_tools=["Bash", "Task"])

        assert "Bash" in tools
        assert "Task" not in tools

    def test_no_additional_tools_keeps_bash_forbidden(self, tmp_path: Path) -> None:
        """Without additional_tools, Bash stays forbidden."""
        agent = AgentDefinition(
            name="test",
            display_name="Test",
            description="Test",
            allowed_tools=["Read", "Bash"],
        )

        tools = self._get_allowed_tools(tmp_path, agent, additional_tools=None)

        assert "Bash" not in tools
        assert "Read" in tools

    def test_empty_additional_tools_keeps_bash_forbidden(self, tmp_path: Path) -> None:
        """Empty additional_tools list should not lift Bash restriction."""
        agent = AgentDefinition(
            name="test",
            display_name="Test",
            description="Test",
            allowed_tools=["Read"],
        )

        tools = self._get_allowed_tools(tmp_path, agent, additional_tools=[])

        assert "Bash" not in tools

    def test_non_bash_additional_tools_dont_lift_restriction(self, tmp_path: Path) -> None:
        """Non-Bash additional_tools should not affect the Bash restriction."""
        agent = AgentDefinition(
            name="test",
            display_name="Test",
            description="Test",
            allowed_tools=["Read"],
        )

        tools = self._get_allowed_tools(tmp_path, agent, additional_tools=["WebSearch"])

        assert "Bash" not in tools
        assert "WebSearch" in tools
        assert "Read" in tools


class TestExternalMcpServers:
    """Tests for _get_external_mcp_servers (Phase 2 injection point)."""

    def test_returns_empty_dict(self, tmp_path: Path) -> None:
        """Phase 1 baseline: _get_external_mcp_servers returns empty dict."""
        executor = AgentExecutor(project_root=tmp_path, agent_config=AgentConfig())
        agent = AgentDefinition(
            name="test",
            display_name="Test",
            description="Test",
            mcp_servers={
                "github": McpServerConfig(enabled=True, required=False),
            },
        )

        result = executor._get_external_mcp_servers(agent)

        assert result == {}

    def test_returns_empty_dict_without_mcp_servers(self, tmp_path: Path) -> None:
        """Agent with no mcp_servers should also return empty dict."""
        executor = AgentExecutor(project_root=tmp_path, agent_config=AgentConfig())
        agent = AgentDefinition(
            name="test",
            display_name="Test",
            description="Test",
        )

        result = executor._get_external_mcp_servers(agent)

        assert result == {}


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
