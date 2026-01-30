"""Tests for Codebase Intelligence feature service.

Tests cover:
- CodebaseIntelligenceService initialization
- Hook management (detection, update, removal)
- Configuration file cleanup
- Constitution section management
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from open_agent_kit.features.codebase_intelligence.constants import (
    CURSOR_HOOK_SCRIPT_NAME,
    CURSOR_HOOKS_DIRNAME,
    OPENCODE_PLUGIN_DIRNAME,
    OPENCODE_PLUGIN_FILENAME,
)
from open_agent_kit.features.codebase_intelligence.service import (
    CodebaseIntelligenceService,
    execute_hook,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def ci_service(tmp_path: Path) -> CodebaseIntelligenceService:
    """Create a CodebaseIntelligenceService instance."""
    return CodebaseIntelligenceService(tmp_path)


@pytest.fixture
def project_with_oak(tmp_path: Path) -> Path:
    """Create project with .oak directory."""
    (tmp_path / ".oak").mkdir()
    return tmp_path


# =============================================================================
# Service Initialization Tests
# =============================================================================


class TestServiceInit:
    """Test service initialization."""

    def test_init_sets_project_root(self, tmp_path: Path):
        """Test that init sets project_root correctly."""
        service = CodebaseIntelligenceService(tmp_path)
        assert service.project_root == tmp_path

    def test_init_sets_ci_data_dir(self, tmp_path: Path):
        """Test that init sets ci_data_dir correctly."""
        service = CodebaseIntelligenceService(tmp_path)
        assert service.ci_data_dir == tmp_path / ".oak" / "ci"

    def test_port_is_derived_lazily(self, tmp_path: Path):
        """Test that port is None until accessed."""
        service = CodebaseIntelligenceService(tmp_path)
        assert service._port is None

    def test_port_is_cached(self, tmp_path: Path):
        """Test that port is cached after first access."""
        service = CodebaseIntelligenceService(tmp_path)
        port1 = service.port
        port2 = service.port
        assert port1 == port2
        assert service._port is not None


# =============================================================================
# Hook Detection Tests
# =============================================================================


class TestOakManagedHookDetection:
    """Test _is_oak_managed_hook method."""

    def test_detects_oak_ci_api_pattern_claude(self, ci_service: CodebaseIntelligenceService):
        """Test detection of /api/oak/ci/ pattern for Claude."""
        hook = {"hooks": [{"command": "curl http://localhost:37800/api/oak/ci/session"}]}
        assert ci_service._is_oak_managed_hook(hook, "claude") is True

    def test_detects_legacy_api_hook_pattern_claude(self, ci_service: CodebaseIntelligenceService):
        """Test detection of legacy /api/hook/ pattern for Claude."""
        hook = {"hooks": [{"command": "curl http://localhost:37800/api/hook/event"}]}
        assert ci_service._is_oak_managed_hook(hook, "claude") is True

    def test_non_oak_hook_claude(self, ci_service: CodebaseIntelligenceService):
        """Test that non-OAK hooks are not detected for Claude."""
        hook = {"hooks": [{"command": "echo 'custom hook'"}]}
        assert ci_service._is_oak_managed_hook(hook, "claude") is False

    def test_detects_oak_ci_api_pattern_cursor(self, ci_service: CodebaseIntelligenceService):
        """Test detection of /api/oak/ci/ pattern for Cursor."""
        hook = {"command": "curl http://localhost:37800/api/oak/ci/session"}
        assert ci_service._is_oak_managed_hook(hook, "cursor") is True

    def test_non_oak_hook_cursor(self, ci_service: CodebaseIntelligenceService):
        """Test that non-OAK hooks are not detected for Cursor."""
        hook = {"command": "echo 'custom hook'"}
        assert ci_service._is_oak_managed_hook(hook, "cursor") is False

    def test_empty_hook_claude(self, ci_service: CodebaseIntelligenceService):
        """Test handling of empty hook structure for Claude."""
        hook = {"hooks": [{}]}
        assert ci_service._is_oak_managed_hook(hook, "claude") is False

    def test_empty_hook_cursor(self, ci_service: CodebaseIntelligenceService):
        """Test handling of empty hook structure for Cursor."""
        hook = {}
        assert ci_service._is_oak_managed_hook(hook, "cursor") is False

    def test_detects_oak_ci_hook_command_claude(self, ci_service: CodebaseIntelligenceService):
        """Test detection of oak ci hook command for Claude."""
        hook = {"hooks": [{"command": "oak ci hook SessionStart --agent claude"}]}
        assert ci_service._is_oak_managed_hook(hook, "claude") is True

    def test_detects_oak_ci_hook_command_cursor(self, ci_service: CodebaseIntelligenceService):
        """Test detection of oak ci hook command for Cursor."""
        hook = {"command": "oak ci hook sessionStart --agent cursor"}
        assert ci_service._is_oak_managed_hook(hook, "cursor") is True

    def test_detects_oak_ci_hook_command_copilot(self, ci_service: CodebaseIntelligenceService):
        """Test detection of oak ci hook command for Copilot."""
        hook = {
            "bash": "oak ci hook sessionStart --agent copilot",
            "powershell": "oak ci hook sessionStart --agent copilot",
        }
        assert ci_service._is_oak_managed_hook(hook, "copilot") is True

    def test_detects_legacy_shell_script_cursor(self, ci_service: CodebaseIntelligenceService):
        """Test detection of legacy oak-ci-hook.sh pattern for Cursor."""
        hook = {"command": ".cursor/hooks/oak-ci-hook.sh sessionStart"}
        assert ci_service._is_oak_managed_hook(hook, "cursor") is True

    def test_detects_legacy_shell_script_copilot(self, ci_service: CodebaseIntelligenceService):
        """Test detection of legacy oak-ci-hook.sh pattern for Copilot."""
        hook = {"bash": ".github/hooks/oak-ci-hook.sh sessionStart"}
        assert ci_service._is_oak_managed_hook(hook, "copilot") is True


# =============================================================================
# Config File Cleanup Tests
# =============================================================================


class TestConfigFileCleanup:
    """Test _cleanup_empty_config_file method."""

    def test_cleanup_empty_json_file(self, tmp_path: Path):
        """Test that empty JSON file is removed."""
        service = CodebaseIntelligenceService(tmp_path)

        config_dir = tmp_path / ".claude"
        config_dir.mkdir()
        config_file = config_dir / "settings.json"
        config_file.write_text("{}")

        service._cleanup_empty_config_file(config_file, [{}])

        assert not config_file.exists()
        assert not config_dir.exists()  # Empty parent also removed

    def test_cleanup_hooks_empty_structure(self, tmp_path: Path):
        """Test that empty hooks structure is recognized."""
        service = CodebaseIntelligenceService(tmp_path)

        config_dir = tmp_path / ".cursor"
        config_dir.mkdir()
        config_file = config_dir / "hooks.json"
        config_file.write_text('{"version": 1, "hooks": {}}')

        service._cleanup_empty_config_file(
            config_file, [{}, {"hooks": {}}, {"version": 1}, {"version": 1, "hooks": {}}]
        )

        assert not config_file.exists()

    def test_no_cleanup_non_empty_file(self, tmp_path: Path):
        """Test that non-empty file is preserved."""
        service = CodebaseIntelligenceService(tmp_path)

        config_dir = tmp_path / ".claude"
        config_dir.mkdir()
        config_file = config_dir / "settings.json"
        config_file.write_text('{"custom_setting": true}')

        service._cleanup_empty_config_file(config_file, [{}])

        assert config_file.exists()

    def test_cleanup_nonexistent_file(self, tmp_path: Path):
        """Test handling of nonexistent file."""
        service = CodebaseIntelligenceService(tmp_path)

        config_file = tmp_path / "nonexistent.json"

        # Should not raise
        service._cleanup_empty_config_file(config_file, [{}])


# =============================================================================
# Hook Update Tests
# =============================================================================


class TestHookUpdates:
    """Test hook update methods."""

    def test_update_agent_hooks_returns_results(self, tmp_path: Path):
        """Test that update_agent_hooks returns results dict."""
        service = CodebaseIntelligenceService(tmp_path)

        # Mock the template loading to return empty hooks
        with patch.object(service, "_load_hook_template", return_value={"hooks": {}}):
            result = service.update_agent_hooks(["claude", "cursor", "unknown"])

        assert result["status"] == "success"
        assert "agents" in result
        assert result["agents"]["claude"] == "updated"
        assert result["agents"]["cursor"] == "updated"
        assert result["agents"]["unknown"] == "skipped"

    def test_update_claude_hooks_creates_settings_dir(self, tmp_path: Path):
        """Test that Claude hook update creates .claude directory."""
        service = CodebaseIntelligenceService(tmp_path)

        with patch.object(service, "_load_hook_template", return_value={"hooks": {}}):
            service._update_claude_hooks()

        assert (tmp_path / ".claude").exists()

    def test_update_cursor_hooks_creates_hooks_file(self, tmp_path: Path):
        """Test that Cursor hook update creates hooks.json."""
        service = CodebaseIntelligenceService(tmp_path)

        with patch.object(service, "_load_hook_template", return_value={"hooks": {}}):
            service._update_cursor_hooks()

        assert (tmp_path / ".cursor" / "hooks.json").exists()

    def test_update_cursor_hooks_uses_oak_ci_hook_command(self, tmp_path: Path):
        """Test that Cursor hook update uses oak ci hook command (no shell scripts)."""
        service = CodebaseIntelligenceService(tmp_path)

        # Mock template with oak ci hook command
        mock_hooks = {
            "hooks": {"sessionStart": [{"command": "oak ci hook sessionStart --agent cursor"}]}
        }
        with patch.object(service, "_load_hook_template", return_value=mock_hooks):
            service._update_cursor_hooks()

        # Verify hooks.json contains the command
        hooks_file = tmp_path / ".cursor" / "hooks.json"
        assert hooks_file.exists()
        hooks_content = json.loads(hooks_file.read_text())
        assert "oak ci hook" in hooks_content["hooks"]["sessionStart"][0]["command"]

        # Verify no shell script was installed (we use oak CLI now)
        script_path = tmp_path / ".cursor" / CURSOR_HOOKS_DIRNAME / CURSOR_HOOK_SCRIPT_NAME
        assert not script_path.exists()

    def test_update_gemini_hooks_creates_settings_file(self, tmp_path: Path):
        """Test that Gemini hook update creates settings.json."""
        service = CodebaseIntelligenceService(tmp_path)

        with patch.object(service, "_load_hook_template", return_value={"hooks": {}}):
            service._update_gemini_hooks()

        assert (tmp_path / ".gemini" / "settings.json").exists()

    def test_update_opencode_hooks_creates_plugin_dir(self, tmp_path: Path):
        """Test that OpenCode hook update creates .opencode/plugins directory."""
        service = CodebaseIntelligenceService(tmp_path)

        # Create the template file that the update method expects
        from open_agent_kit.features.codebase_intelligence.service import HOOKS_TEMPLATE_DIR

        template_dir = HOOKS_TEMPLATE_DIR / "opencode"
        if not template_dir.exists():
            pytest.skip("OpenCode hook template not found")

        service._update_opencode_hooks()

        assert (tmp_path / ".opencode" / OPENCODE_PLUGIN_DIRNAME).exists()

    def test_update_opencode_hooks_installs_plugin_file(self, tmp_path: Path):
        """Test that OpenCode hook update installs the TypeScript plugin."""
        service = CodebaseIntelligenceService(tmp_path)

        from open_agent_kit.features.codebase_intelligence.service import HOOKS_TEMPLATE_DIR

        template_file = HOOKS_TEMPLATE_DIR / "opencode" / OPENCODE_PLUGIN_FILENAME
        if not template_file.exists():
            pytest.skip("OpenCode plugin template not found")

        service._update_opencode_hooks()

        plugin_file = tmp_path / ".opencode" / OPENCODE_PLUGIN_DIRNAME / OPENCODE_PLUGIN_FILENAME
        assert plugin_file.exists()
        # Verify it's a TypeScript file with expected content
        content = plugin_file.read_text()
        assert "OAK" in content or "oak" in content

    def test_update_agent_hooks_includes_opencode(self, tmp_path: Path):
        """Test that update_agent_hooks handles opencode agent."""
        service = CodebaseIntelligenceService(tmp_path)

        from open_agent_kit.features.codebase_intelligence.service import HOOKS_TEMPLATE_DIR

        template_file = HOOKS_TEMPLATE_DIR / "opencode" / OPENCODE_PLUGIN_FILENAME
        if not template_file.exists():
            pytest.skip("OpenCode plugin template not found")

        result = service.update_agent_hooks(["opencode"])

        assert result["status"] == "success"
        assert result["agents"]["opencode"] == "updated"


# =============================================================================
# Hook Removal Tests
# =============================================================================


class TestHookRemoval:
    """Test hook removal methods."""

    def test_remove_claude_hooks_cleans_oak_hooks(self, tmp_path: Path):
        """Test that Claude hook removal cleans OAK hooks only."""
        service = CodebaseIntelligenceService(tmp_path)

        # Create settings with mixed hooks
        settings_dir = tmp_path / ".claude"
        settings_dir.mkdir()
        settings_file = settings_dir / "settings.json"
        settings_file.write_text(
            json.dumps(
                {
                    "hooks": {
                        "session-start": [
                            {"hooks": [{"command": "curl /api/oak/ci/session"}]},
                            {"hooks": [{"command": "echo custom"}]},
                        ]
                    }
                }
            )
        )

        service._remove_claude_hooks()

        # Read result
        with open(settings_file) as f:
            result = json.load(f)

        # OAK hook should be removed, custom hook preserved
        assert len(result["hooks"]["session-start"]) == 1
        assert "custom" in result["hooks"]["session-start"][0]["hooks"][0]["command"]

    def test_remove_cursor_hooks_nonexistent_file(self, tmp_path: Path):
        """Test that cursor hook removal handles missing file."""
        service = CodebaseIntelligenceService(tmp_path)

        # Should not raise
        service._remove_cursor_hooks()

    def test_remove_gemini_hooks_no_hooks_section(self, tmp_path: Path):
        """Test that gemini hook removal handles missing hooks section."""
        service = CodebaseIntelligenceService(tmp_path)

        settings_dir = tmp_path / ".gemini"
        settings_dir.mkdir()
        settings_file = settings_dir / "settings.json"
        settings_file.write_text('{"other_setting": true}')

        # Should not raise
        service._remove_gemini_hooks()

        # File should be unchanged
        with open(settings_file) as f:
            result = json.load(f)
        assert result == {"other_setting": True}

    def test_remove_agent_hooks_all_agents(self, tmp_path: Path):
        """Test removing hooks from multiple agents."""
        service = CodebaseIntelligenceService(tmp_path)

        # Create minimal hook files
        for agent_dir in [".claude", ".cursor", ".gemini"]:
            d = tmp_path / agent_dir
            d.mkdir()
            fname = "hooks.json" if agent_dir == ".cursor" else "settings.json"
            (d / fname).write_text('{"hooks": {}}')

        result = service._remove_agent_hooks(["claude", "cursor", "gemini", "unknown"])

        assert result["claude"] == "removed"
        assert result["cursor"] == "removed"
        assert result["gemini"] == "removed"
        assert result["unknown"] == "skipped"

    def test_remove_opencode_hooks_removes_plugin_file(self, tmp_path: Path):
        """Test that OpenCode hook removal removes the plugin file and directories."""
        service = CodebaseIntelligenceService(tmp_path)

        # Create plugin file
        agent_dir = tmp_path / ".opencode"
        plugins_dir = agent_dir / OPENCODE_PLUGIN_DIRNAME
        plugins_dir.mkdir(parents=True)
        plugin_file = plugins_dir / OPENCODE_PLUGIN_FILENAME
        plugin_file.write_text("// OAK CI plugin")

        service._remove_opencode_hooks()

        assert not plugin_file.exists()
        # Empty plugins directory should be removed
        assert not plugins_dir.exists()
        # Empty agent directory should also be removed
        assert not agent_dir.exists()

    def test_remove_opencode_hooks_nonexistent_file(self, tmp_path: Path):
        """Test that OpenCode hook removal handles missing file gracefully."""
        service = CodebaseIntelligenceService(tmp_path)

        # Should not raise
        service._remove_opencode_hooks()

    def test_remove_opencode_hooks_preserves_other_plugins(self, tmp_path: Path):
        """Test that OpenCode hook removal preserves other plugin files."""
        service = CodebaseIntelligenceService(tmp_path)

        # Create plugin directory with multiple files
        agent_dir = tmp_path / ".opencode"
        plugins_dir = agent_dir / OPENCODE_PLUGIN_DIRNAME
        plugins_dir.mkdir(parents=True)
        plugin_file = plugins_dir / OPENCODE_PLUGIN_FILENAME
        plugin_file.write_text("// OAK CI plugin")
        other_plugin = plugins_dir / "other-plugin.ts"
        other_plugin.write_text("// Other plugin")

        service._remove_opencode_hooks()

        assert not plugin_file.exists()
        # Other plugin, plugins dir, and agent dir should be preserved
        assert other_plugin.exists()
        assert plugins_dir.exists()
        assert agent_dir.exists()

    def test_remove_opencode_hooks_preserves_agent_dir_with_other_content(self, tmp_path: Path):
        """Test that OpenCode hook removal preserves agent dir with other content."""
        service = CodebaseIntelligenceService(tmp_path)

        # Create agent directory with plugins and other content
        agent_dir = tmp_path / ".opencode"
        plugins_dir = agent_dir / OPENCODE_PLUGIN_DIRNAME
        plugins_dir.mkdir(parents=True)
        plugin_file = plugins_dir / OPENCODE_PLUGIN_FILENAME
        plugin_file.write_text("// OAK CI plugin")
        # Add other content to agent directory
        other_file = agent_dir / "config.json"
        other_file.write_text("{}")

        service._remove_opencode_hooks()

        assert not plugin_file.exists()
        # Empty plugins directory should be removed
        assert not plugins_dir.exists()
        # Agent directory with other content should be preserved
        assert other_file.exists()
        assert agent_dir.exists()

    def test_remove_agent_hooks_includes_opencode(self, tmp_path: Path):
        """Test that _remove_agent_hooks handles opencode agent."""
        service = CodebaseIntelligenceService(tmp_path)

        # Create plugin file
        plugins_dir = tmp_path / ".opencode" / OPENCODE_PLUGIN_DIRNAME
        plugins_dir.mkdir(parents=True)
        plugin_file = plugins_dir / OPENCODE_PLUGIN_FILENAME
        plugin_file.write_text("// OAK CI plugin")

        result = service._remove_agent_hooks(["opencode"])

        assert result["opencode"] == "removed"
        assert not plugin_file.exists()


# =============================================================================
# Execute Hook Tests
# =============================================================================


class TestExecuteHook:
    """Test execute_hook function."""

    def test_execute_unknown_hook_returns_error(self, tmp_path: Path):
        """Test that unknown hook action returns error."""
        result = execute_hook("unknown_action", tmp_path)

        assert result["status"] == "error"
        assert "Unknown hook action" in result["message"]

    def test_execute_hook_creates_service(self, tmp_path: Path):
        """Test that execute_hook creates service instance."""
        with patch(
            "open_agent_kit.features.codebase_intelligence.service.CodebaseIntelligenceService"
        ) as MockService:
            mock_instance = MagicMock()
            mock_instance.initialize.return_value = {"status": "success"}
            MockService.return_value = mock_instance

            execute_hook("initialize", tmp_path)

            MockService.assert_called_once_with(tmp_path)
            mock_instance.initialize.assert_called_once()


# =============================================================================
# Integration Tests
# =============================================================================


class TestServiceIntegration:
    """Integration tests for service operations."""

    def test_full_hook_lifecycle(self, tmp_path: Path):
        """Test adding and removing hooks."""
        service = CodebaseIntelligenceService(tmp_path)

        # Mock template loading
        template = {
            "hooks": {"session-start": [{"hooks": [{"command": "curl /api/oak/ci/start"}]}]}
        }

        with patch.object(service, "_load_hook_template", return_value=template):
            # Add hooks
            service._update_claude_hooks()

            # Verify added
            settings_file = tmp_path / ".claude" / "settings.json"
            with open(settings_file) as f:
                settings = json.load(f)
            assert "hooks" in settings
            assert len(settings["hooks"]["session-start"]) == 1

            # Remove hooks
            service._remove_claude_hooks()

            # File should be cleaned up since it's empty
            assert not settings_file.exists()

    def test_preserves_existing_hooks(self, tmp_path: Path):
        """Test that existing non-OAK hooks are preserved."""
        service = CodebaseIntelligenceService(tmp_path)

        # Create existing settings with custom hook
        settings_dir = tmp_path / ".claude"
        settings_dir.mkdir()
        settings_file = settings_dir / "settings.json"
        settings_file.write_text(
            json.dumps(
                {
                    "hooks": {"session-start": [{"hooks": [{"command": "echo 'my custom hook'"}]}]},
                    "other_setting": "preserved",
                }
            )
        )

        # Add OAK hooks
        template = {
            "hooks": {"session-start": [{"hooks": [{"command": "curl /api/oak/ci/start"}]}]}
        }

        with patch.object(service, "_load_hook_template", return_value=template):
            service._update_claude_hooks()

            # Verify both hooks exist
            with open(settings_file) as f:
                settings = json.load(f)
            assert len(settings["hooks"]["session-start"]) == 2
            assert settings["other_setting"] == "preserved"

            # Remove OAK hooks
            service._remove_claude_hooks()

            # Custom hook should still exist
            with open(settings_file) as f:
                settings = json.load(f)
            assert len(settings["hooks"]["session-start"]) == 1
            assert "custom" in settings["hooks"]["session-start"][0]["hooks"][0]["command"]
