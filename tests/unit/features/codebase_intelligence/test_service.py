"""Tests for Codebase Intelligence feature service.

Tests cover:
- CodebaseIntelligenceService initialization
- Hook management via HooksInstaller
- Configuration file cleanup
- Integration with manifest-driven hooks
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from open_agent_kit.features.codebase_intelligence.hooks.installer import HooksInstaller
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
# HooksInstaller Tests
# =============================================================================


class TestHooksInstallerOakDetection:
    """Test HooksInstaller._is_oak_managed_hook method."""

    def test_detects_oak_ci_hook_command_nested(self, tmp_path: Path):
        """Test detection of oak ci hook command in nested structure (Claude/Gemini)."""
        # Mock the manifest with nested format
        with patch.object(HooksInstaller, "manifest") as mock_manifest:
            mock_manifest.hooks.format = "nested"
            installer = HooksInstaller(tmp_path, "claude")
            installer._hooks_config = MagicMock(format="nested")

            hook = {"hooks": [{"command": "oak ci hook SessionStart --agent claude"}]}
            assert installer._is_oak_managed_hook(hook) is True

    def test_detects_oak_ci_hook_command_flat(self, tmp_path: Path):
        """Test detection of oak ci hook command in flat structure (Cursor)."""
        with patch.object(HooksInstaller, "manifest") as mock_manifest:
            mock_manifest.hooks.format = "flat"
            installer = HooksInstaller(tmp_path, "cursor")
            installer._hooks_config = MagicMock(format="flat")

            hook = {"command": "oak ci hook sessionStart --agent cursor"}
            assert installer._is_oak_managed_hook(hook) is True

    def test_detects_oak_ci_hook_command_copilot(self, tmp_path: Path):
        """Test detection of oak ci hook command in copilot format (bash/powershell)."""
        with patch.object(HooksInstaller, "manifest") as mock_manifest:
            mock_manifest.hooks.format = "copilot"
            installer = HooksInstaller(tmp_path, "copilot")
            installer._hooks_config = MagicMock(format="copilot")

            hook = {
                "bash": "oak ci hook sessionStart --agent copilot",
                "powershell": "oak ci hook sessionStart --agent copilot",
            }
            assert installer._is_oak_managed_hook(hook) is True

    def test_detects_legacy_api_pattern(self, tmp_path: Path):
        """Test detection of legacy /api/oak/ci/ pattern."""
        with patch.object(HooksInstaller, "manifest") as mock_manifest:
            mock_manifest.hooks.format = "nested"
            installer = HooksInstaller(tmp_path, "claude")
            installer._hooks_config = MagicMock(format="nested")

            hook = {"hooks": [{"command": "curl http://localhost:37800/api/oak/ci/session"}]}
            assert installer._is_oak_managed_hook(hook) is True

    def test_non_oak_hook_not_detected(self, tmp_path: Path):
        """Test that non-OAK hooks are not detected."""
        with patch.object(HooksInstaller, "manifest") as mock_manifest:
            mock_manifest.hooks.format = "flat"
            installer = HooksInstaller(tmp_path, "cursor")
            installer._hooks_config = MagicMock(format="flat")

            hook = {"command": "echo 'custom hook'"}
            assert installer._is_oak_managed_hook(hook) is False


# =============================================================================
# Service Hook Update Tests
# =============================================================================


class TestServiceHookUpdates:
    """Test service hook update methods using manifest-driven installer."""

    def test_update_agent_hooks_returns_results(self, tmp_path: Path):
        """Test that update_agent_hooks returns results dict."""
        service = CodebaseIntelligenceService(tmp_path)

        # Mock install_hooks to simulate success
        with patch(
            "open_agent_kit.features.codebase_intelligence.hooks.install_hooks"
        ) as mock_install:
            mock_install.return_value = MagicMock(success=True, method="json")
            result = service.update_agent_hooks(["claude", "cursor"])

        assert result["status"] == "success"
        assert "agents" in result
        assert result["agents"]["claude"] == "updated"
        assert result["agents"]["cursor"] == "updated"

    def test_update_agent_hooks_handles_errors(self, tmp_path: Path):
        """Test that update_agent_hooks handles errors gracefully."""
        service = CodebaseIntelligenceService(tmp_path)

        # Mock install_hooks to simulate failure
        with patch(
            "open_agent_kit.features.codebase_intelligence.hooks.install_hooks"
        ) as mock_install:
            mock_install.return_value = MagicMock(success=False, message="Test error")
            result = service.update_agent_hooks(["claude"])

        assert result["status"] == "success"  # Overall status is still success
        assert "error: Test error" in result["agents"]["claude"]


# =============================================================================
# Service Hook Removal Tests
# =============================================================================


class TestServiceHookRemoval:
    """Test service hook removal methods."""

    def test_remove_agent_hooks_returns_results(self, tmp_path: Path):
        """Test that _remove_agent_hooks returns results dict."""
        service = CodebaseIntelligenceService(tmp_path)

        # Mock remove_hooks to simulate success
        with patch(
            "open_agent_kit.features.codebase_intelligence.hooks.remove_hooks"
        ) as mock_remove:
            mock_remove.return_value = MagicMock(success=True, method="json")
            result = service._remove_agent_hooks(["claude", "cursor"])

        assert result["claude"] == "removed"
        assert result["cursor"] == "removed"

    def test_remove_agent_hooks_handles_errors(self, tmp_path: Path):
        """Test that _remove_agent_hooks handles errors gracefully."""
        service = CodebaseIntelligenceService(tmp_path)

        # Mock remove_hooks to simulate failure
        with patch(
            "open_agent_kit.features.codebase_intelligence.hooks.remove_hooks"
        ) as mock_remove:
            mock_remove.return_value = MagicMock(success=False, message="Test error")
            result = service._remove_agent_hooks(["claude"])

        assert "error: Test error" in result["claude"]


# =============================================================================
# Service Notification Update Tests
# =============================================================================


class TestServiceNotificationUpdates:
    """Test service notification update methods using manifest-driven installer."""

    def test_update_agent_notifications_returns_results(self, tmp_path: Path):
        """Test that update_agent_notifications returns results dict."""
        service = CodebaseIntelligenceService(tmp_path)

        with patch(
            "open_agent_kit.features.codebase_intelligence.notifications.install_notifications"
        ) as mock_install:
            mock_install.return_value = MagicMock(success=True, method="notify")
            result = service.update_agent_notifications(["claude", "codex"])

        assert result["status"] == "success"
        assert "agents" in result
        assert result["agents"]["claude"] == "updated"
        assert result["agents"]["codex"] == "updated"

    def test_update_agent_notifications_handles_errors(self, tmp_path: Path):
        """Test that update_agent_notifications handles errors gracefully."""
        service = CodebaseIntelligenceService(tmp_path)

        with patch(
            "open_agent_kit.features.codebase_intelligence.notifications.install_notifications"
        ) as mock_install:
            mock_install.return_value = MagicMock(success=False, message="Test error")
            result = service.update_agent_notifications(["claude"])

        assert result["status"] == "success"
        assert "error: Test error" in result["agents"]["claude"]


# =============================================================================
# Service Notification Removal Tests
# =============================================================================


class TestServiceNotificationRemoval:
    """Test service notification removal methods."""

    def test_remove_agent_notifications_returns_results(self, tmp_path: Path):
        """Test that _remove_agent_notifications returns results dict."""
        service = CodebaseIntelligenceService(tmp_path)

        with patch(
            "open_agent_kit.features.codebase_intelligence.notifications.remove_notifications"
        ) as mock_remove:
            mock_remove.return_value = MagicMock(success=True, method="notify")
            result = service._remove_agent_notifications(["claude", "codex"])

        assert result["claude"] == "removed"
        assert result["codex"] == "removed"

    def test_remove_agent_notifications_handles_errors(self, tmp_path: Path):
        """Test that _remove_agent_notifications handles errors gracefully."""
        service = CodebaseIntelligenceService(tmp_path)

        with patch(
            "open_agent_kit.features.codebase_intelligence.notifications.remove_notifications"
        ) as mock_remove:
            mock_remove.return_value = MagicMock(success=False, message="Test error")
            result = service._remove_agent_notifications(["claude"])

        assert "error: Test error" in result["claude"]


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
# HooksInstaller Integration Tests
# =============================================================================


class TestHooksInstallerIntegration:
    """Integration tests for HooksInstaller operations."""

    def test_install_json_hooks_creates_config_dir(self, tmp_path: Path):
        """Test that JSON hooks installation creates the config directory."""
        # Create a mock hooks config
        mock_hooks_config = MagicMock()
        mock_hooks_config.type = "json"
        mock_hooks_config.config_file = "settings.json"
        mock_hooks_config.hooks_key = "hooks"
        mock_hooks_config.format = "nested"
        mock_hooks_config.version_key = None
        mock_hooks_config.template_file = "hooks.json"

        mock_manifest = MagicMock()
        mock_manifest.installation.folder = ".claude/"
        mock_manifest.hooks = mock_hooks_config

        installer = HooksInstaller(tmp_path, "claude")
        installer._manifest = mock_manifest
        installer._hooks_config = mock_hooks_config

        # Mock the template loading
        with patch.object(installer, "_load_hook_template", return_value={"hooks": {}}):
            result = installer.install()

        # Directory should be created
        assert (tmp_path / ".claude").exists()
        assert result.success

    def test_install_plugin_copies_file(self, tmp_path: Path):
        """Test that plugin installation copies the file."""
        from open_agent_kit.features.codebase_intelligence.hooks.installer import (
            HOOKS_TEMPLATE_DIR,
        )

        # Check if template exists
        template_file = HOOKS_TEMPLATE_DIR / "opencode" / "oak-ci.ts"
        if not template_file.exists():
            pytest.skip("OpenCode template not found")

        # Create a mock hooks config
        mock_hooks_config = MagicMock()
        mock_hooks_config.type = "plugin"
        mock_hooks_config.plugin_dir = "plugins"
        mock_hooks_config.plugin_file = "oak-ci.ts"
        mock_hooks_config.template_file = "oak-ci.ts"

        mock_manifest = MagicMock()
        mock_manifest.installation.folder = ".opencode/"
        mock_manifest.hooks = mock_hooks_config

        installer = HooksInstaller(tmp_path, "opencode")
        installer._manifest = mock_manifest
        installer._hooks_config = mock_hooks_config

        result = installer.install()

        assert result.success
        assert (tmp_path / ".opencode" / "plugins" / "oak-ci.ts").exists()

    def test_remove_json_hooks_cleans_oak_hooks_only(self, tmp_path: Path):
        """Test that JSON hook removal only removes OAK hooks."""
        # Create settings with mixed hooks
        settings_dir = tmp_path / ".claude"
        settings_dir.mkdir()
        settings_file = settings_dir / "settings.json"
        settings_file.write_text(
            json.dumps(
                {
                    "hooks": {
                        "SessionStart": [
                            {"hooks": [{"command": "oak ci hook SessionStart --agent claude"}]},
                            {"hooks": [{"command": "echo custom"}]},
                        ]
                    }
                }
            )
        )

        # Create a mock hooks config
        mock_hooks_config = MagicMock()
        mock_hooks_config.type = "json"
        mock_hooks_config.config_file = "settings.json"
        mock_hooks_config.hooks_key = "hooks"
        mock_hooks_config.format = "nested"
        mock_hooks_config.version_key = None

        mock_manifest = MagicMock()
        mock_manifest.installation.folder = ".claude/"
        mock_manifest.hooks = mock_hooks_config

        installer = HooksInstaller(tmp_path, "claude")
        installer._manifest = mock_manifest
        installer._hooks_config = mock_hooks_config

        result = installer.remove()

        # Read result
        with open(settings_file) as f:
            settings = json.load(f)

        # OAK hook should be removed, custom hook preserved
        assert result.success
        assert len(settings["hooks"]["SessionStart"]) == 1
        assert "custom" in settings["hooks"]["SessionStart"][0]["hooks"][0]["command"]

    def test_remove_plugin_cleans_up_empty_dirs(self, tmp_path: Path):
        """Test that plugin removal cleans up empty directories."""
        # Create plugin file
        agent_dir = tmp_path / ".opencode"
        plugins_dir = agent_dir / "plugins"
        plugins_dir.mkdir(parents=True)
        plugin_file = plugins_dir / "oak-ci.ts"
        plugin_file.write_text("// OAK CI plugin")

        # Create a mock hooks config
        mock_hooks_config = MagicMock()
        mock_hooks_config.type = "plugin"
        mock_hooks_config.plugin_dir = "plugins"
        mock_hooks_config.plugin_file = "oak-ci.ts"

        mock_manifest = MagicMock()
        mock_manifest.installation.folder = ".opencode/"
        mock_manifest.hooks = mock_hooks_config

        installer = HooksInstaller(tmp_path, "opencode")
        installer._manifest = mock_manifest
        installer._hooks_config = mock_hooks_config

        result = installer.remove()

        assert result.success
        assert not plugin_file.exists()
        assert not plugins_dir.exists()
        assert not agent_dir.exists()

    def test_remove_plugin_preserves_other_files(self, tmp_path: Path):
        """Test that plugin removal preserves other plugin files."""
        # Create plugin directory with multiple files
        agent_dir = tmp_path / ".opencode"
        plugins_dir = agent_dir / "plugins"
        plugins_dir.mkdir(parents=True)
        plugin_file = plugins_dir / "oak-ci.ts"
        plugin_file.write_text("// OAK CI plugin")
        other_plugin = plugins_dir / "other-plugin.ts"
        other_plugin.write_text("// Other plugin")

        # Create a mock hooks config
        mock_hooks_config = MagicMock()
        mock_hooks_config.type = "plugin"
        mock_hooks_config.plugin_dir = "plugins"
        mock_hooks_config.plugin_file = "oak-ci.ts"

        mock_manifest = MagicMock()
        mock_manifest.installation.folder = ".opencode/"
        mock_manifest.hooks = mock_hooks_config

        installer = HooksInstaller(tmp_path, "opencode")
        installer._manifest = mock_manifest
        installer._hooks_config = mock_hooks_config

        result = installer.remove()

        assert result.success
        assert not plugin_file.exists()
        assert other_plugin.exists()
        assert plugins_dir.exists()
        assert agent_dir.exists()
