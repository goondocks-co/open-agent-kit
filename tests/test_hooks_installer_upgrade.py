"""Tests for HooksInstaller.needs_upgrade() — upgrade detection for all hook types.

Covers plugin, JSON, and OTEL hook types plus edge cases.
Uses minimal file structures (no init_command needed).
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from open_agent_kit.features.codebase_intelligence.hooks.installer import (
    HOOKS_TEMPLATE_DIR,
    HooksInstaller,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_installer(
    tmp_path: Path,
    agent: str,
    hooks_config: MagicMock,
    folder: str | None = None,
) -> HooksInstaller:
    """Build a HooksInstaller with a mock manifest (no disk manifest needed)."""
    if folder is None:
        folder = f".{agent}/"

    mock_manifest = MagicMock()
    mock_manifest.installation.folder = folder
    mock_manifest.hooks = hooks_config

    installer = HooksInstaller(tmp_path, agent)
    installer._manifest = mock_manifest
    installer._hooks_config = hooks_config
    return installer


def _json_hooks_config(
    config_file: str = "settings.json",
    hooks_key: str = "hooks",
    fmt: str = "nested",
    template_file: str = "hooks.json",
) -> MagicMock:
    """Create a MagicMock that behaves like AgentHooksConfig for JSON type."""
    cfg = MagicMock()
    cfg.type = "json"
    cfg.config_file = config_file
    cfg.hooks_key = hooks_key
    cfg.format = fmt
    cfg.template_file = template_file
    cfg.version_key = None
    cfg.plugin_dir = None
    cfg.plugin_file = None
    cfg.otel = None
    return cfg


def _plugin_hooks_config(
    plugin_dir: str = "plugins",
    plugin_file: str = "oak-ci.ts",
    template_file: str = "oak-ci.ts",
) -> MagicMock:
    """Create a MagicMock that behaves like AgentHooksConfig for plugin type."""
    cfg = MagicMock()
    cfg.type = "plugin"
    cfg.plugin_dir = plugin_dir
    cfg.plugin_file = plugin_file
    cfg.template_file = template_file
    cfg.config_file = None
    cfg.hooks_key = "hooks"
    cfg.format = "nested"
    cfg.version_key = None
    cfg.otel = None
    return cfg


def _otel_hooks_config(
    config_file: str = "config.toml",
    config_template: str = "otel_config.toml.j2",
    config_section: str = "otel",
) -> MagicMock:
    """Create a MagicMock that behaves like AgentHooksConfig for OTEL type."""
    otel = MagicMock()
    otel.enabled = True
    otel.config_template = config_template
    otel.config_section = config_section

    cfg = MagicMock()
    cfg.type = "otel"
    cfg.config_file = config_file
    cfg.otel = otel
    cfg.plugin_dir = None
    cfg.plugin_file = None
    cfg.hooks_key = "hooks"
    cfg.format = "nested"
    cfg.version_key = None
    cfg.template_file = "hooks.json"
    return cfg


# ===========================================================================
# Plugin type tests
# ===========================================================================


class TestPluginNeedsUpgrade:
    """Tests for _plugin_needs_upgrade."""

    def test_plugin_needs_upgrade_when_not_installed(self, tmp_path: Path):
        """Plugin file missing -> True."""
        hooks_cfg = _plugin_hooks_config()
        installer = _make_installer(tmp_path, "opencode", hooks_cfg)

        # Template exists (use the real one)
        assert (HOOKS_TEMPLATE_DIR / "opencode" / "oak-ci.ts").exists()
        # Installed file does NOT exist
        assert not (tmp_path / ".opencode" / "plugins" / "oak-ci.ts").exists()

        assert installer.needs_upgrade() is True

    def test_plugin_needs_upgrade_when_content_differs(self, tmp_path: Path):
        """Installed plugin differs from template -> True."""
        hooks_cfg = _plugin_hooks_config()
        installer = _make_installer(tmp_path, "opencode", hooks_cfg)

        # Create an installed file with different content
        installed_dir = tmp_path / ".opencode" / "plugins"
        installed_dir.mkdir(parents=True)
        (installed_dir / "oak-ci.ts").write_text("// old version")

        assert installer.needs_upgrade() is True

    def test_plugin_no_upgrade_when_identical(self, tmp_path: Path):
        """Installed plugin matches template -> False."""
        hooks_cfg = _plugin_hooks_config()
        installer = _make_installer(tmp_path, "opencode", hooks_cfg)

        # Copy the real template to the installed location
        template_content = (HOOKS_TEMPLATE_DIR / "opencode" / "oak-ci.ts").read_text()
        installed_dir = tmp_path / ".opencode" / "plugins"
        installed_dir.mkdir(parents=True)
        (installed_dir / "oak-ci.ts").write_text(template_content)

        assert installer.needs_upgrade() is False


# ===========================================================================
# JSON type tests
# ===========================================================================


class TestJsonNeedsUpgrade:
    """Tests for _json_needs_upgrade."""

    def test_json_needs_upgrade_when_not_installed(self, tmp_path: Path):
        """Config file missing -> True."""
        hooks_cfg = _json_hooks_config()
        installer = _make_installer(tmp_path, "claude", hooks_cfg)

        # Mock _load_hook_template to return a minimal template
        template = {
            "hooks": {
                "SessionStart": [
                    {"hooks": [{"command": "oak ci hook SessionStart --agent claude"}]}
                ]
            }
        }
        with patch.object(installer, "_load_hook_template", return_value=template):
            assert installer.needs_upgrade() is True

    def test_json_needs_upgrade_when_content_differs(self, tmp_path: Path):
        """Hook command changed in template -> True."""
        hooks_cfg = _json_hooks_config()
        installer = _make_installer(tmp_path, "claude", hooks_cfg)

        # Old installed hooks
        old_hooks = {
            "hooks": {
                "SessionStart": [
                    {"hooks": [{"command": "oak ci hook SessionStart --agent claude", "timeout": 30}]}
                ]
            }
        }
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        (config_dir / "settings.json").write_text(json.dumps(old_hooks))

        # New template has different timeout
        new_template = {
            "hooks": {
                "SessionStart": [
                    {"hooks": [{"command": "oak ci hook SessionStart --agent claude", "timeout": 60}]}
                ]
            }
        }
        with patch.object(installer, "_load_hook_template", return_value=new_template):
            assert installer.needs_upgrade() is True

    def test_json_no_upgrade_when_identical(self, tmp_path: Path):
        """Matching hooks -> False."""
        hooks_cfg = _json_hooks_config()
        installer = _make_installer(tmp_path, "claude", hooks_cfg)

        hooks_data = {
            "hooks": {
                "SessionStart": [
                    {"hooks": [{"command": "oak ci hook SessionStart --agent claude", "timeout": 60}]}
                ]
            }
        }

        # Write installed config
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        (config_dir / "settings.json").write_text(json.dumps(hooks_data))

        with patch.object(installer, "_load_hook_template", return_value=hooks_data):
            assert installer.needs_upgrade() is False

    def test_json_no_upgrade_ignores_user_hooks(self, tmp_path: Path):
        """User hooks in the installed file don't trigger upgrade."""
        hooks_cfg = _json_hooks_config()
        installer = _make_installer(tmp_path, "claude", hooks_cfg)

        # Template only has SessionStart
        template = {
            "hooks": {
                "SessionStart": [
                    {"hooks": [{"command": "oak ci hook SessionStart --agent claude", "timeout": 60}]}
                ]
            }
        }

        # Installed has SessionStart (matching) + user hook in same event
        installed = {
            "hooks": {
                "SessionStart": [
                    {"hooks": [{"command": "oak ci hook SessionStart --agent claude", "timeout": 60}]},
                    {"hooks": [{"command": "echo user hook"}]},
                ]
            }
        }
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        (config_dir / "settings.json").write_text(json.dumps(installed))

        with patch.object(installer, "_load_hook_template", return_value=template):
            assert installer.needs_upgrade() is False

    def test_json_detects_orphaned_oak_hooks(self, tmp_path: Path):
        """OAK hooks in events not defined in template -> True."""
        hooks_cfg = _json_hooks_config()
        installer = _make_installer(tmp_path, "claude", hooks_cfg)

        # Template has no hooks (empty)
        template = {"hooks": {}}

        # Installed has an orphaned OAK hook
        installed = {
            "hooks": {
                "Stop": [
                    {"hooks": [{"command": "oak ci hook Stop --agent claude"}]}
                ]
            }
        }
        config_dir = tmp_path / ".claude"
        config_dir.mkdir(parents=True)
        (config_dir / "settings.json").write_text(json.dumps(installed))

        with patch.object(installer, "_load_hook_template", return_value=template):
            assert installer.needs_upgrade() is True


# ===========================================================================
# OTEL type tests
# ===========================================================================


class TestOtelNeedsUpgrade:
    """Tests for _otel_needs_upgrade."""

    def test_otel_needs_upgrade_when_not_installed(self, tmp_path: Path):
        """Config file missing -> True."""
        hooks_cfg = _otel_hooks_config()
        installer = _make_installer(tmp_path, "codex", hooks_cfg, folder=".codex/")

        # Patch _get_daemon_port to avoid reading real port file
        with patch.object(installer, "_get_daemon_port", return_value=37800):
            assert installer.needs_upgrade() is True

    def test_otel_no_upgrade_when_identical(self, tmp_path: Path):
        """Matching OTEL section -> False."""
        hooks_cfg = _otel_hooks_config()
        installer = _make_installer(tmp_path, "codex", hooks_cfg, folder=".codex/")

        # Render the template with port 37800
        from jinja2 import Template

        template_path = HOOKS_TEMPLATE_DIR / "codex" / "otel_config.toml.j2"
        rendered = Template(template_path.read_text()).render(daemon_port=37800)

        # Parse the rendered TOML and write it as the installed config
        import tomllib

        try:
            import tomli_w
        except ImportError:
            pytest.skip("tomli_w not installed")

        expected = tomllib.loads(rendered)

        config_dir = tmp_path / ".codex"
        config_dir.mkdir(parents=True)
        (config_dir / "config.toml").write_bytes(tomli_w.dumps(expected).encode())

        with patch.object(installer, "_get_daemon_port", return_value=37800):
            assert installer.needs_upgrade() is False

    def test_otel_needs_upgrade_when_port_differs(self, tmp_path: Path):
        """Installed OTEL has different port -> True."""
        hooks_cfg = _otel_hooks_config()
        installer = _make_installer(tmp_path, "codex", hooks_cfg, folder=".codex/")

        from jinja2 import Template

        template_path = HOOKS_TEMPLATE_DIR / "codex" / "otel_config.toml.j2"
        # Install with old port
        rendered_old = Template(template_path.read_text()).render(daemon_port=37800)

        import tomllib

        try:
            import tomli_w
        except ImportError:
            pytest.skip("tomli_w not installed")

        config_dir = tmp_path / ".codex"
        config_dir.mkdir(parents=True)
        (config_dir / "config.toml").write_bytes(
            tomli_w.dumps(tomllib.loads(rendered_old)).encode()
        )

        # Now the daemon port changed to 38000
        with patch.object(installer, "_get_daemon_port", return_value=38000):
            assert installer.needs_upgrade() is True


# ===========================================================================
# Edge cases
# ===========================================================================


class TestNeedsUpgradeEdgeCases:
    """Edge cases for needs_upgrade()."""

    def test_no_hooks_config_returns_false(self, tmp_path: Path):
        """Agent with no hooks manifest -> False."""
        installer = HooksInstaller(tmp_path, "claude")
        # Set _hooks_config to None explicitly
        mock_manifest = MagicMock()
        mock_manifest.hooks = None
        installer._manifest = mock_manifest
        installer._hooks_config = None

        assert installer.needs_upgrade() is False

    def test_missing_template_returns_false_plugin(self, tmp_path: Path):
        """Plugin template file doesn't exist -> False (nothing to upgrade to)."""
        cfg = _plugin_hooks_config(template_file="nonexistent.ts")
        installer = _make_installer(tmp_path, "opencode", cfg)

        assert installer.needs_upgrade() is False

    def test_missing_template_returns_false_otel(self, tmp_path: Path):
        """OTEL template file doesn't exist -> False."""
        cfg = _otel_hooks_config(config_template="nonexistent.toml.j2")
        installer = _make_installer(tmp_path, "codex", cfg, folder=".codex/")

        assert installer.needs_upgrade() is False

    def test_missing_template_returns_false_json(self, tmp_path: Path):
        """JSON template that can't be loaded -> False."""
        cfg = _json_hooks_config(template_file="nonexistent.json")
        installer = _make_installer(tmp_path, "claude", cfg)

        # _load_hook_template returns None for missing template
        assert installer.needs_upgrade() is False
