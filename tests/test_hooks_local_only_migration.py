"""Tests for the hooks-local-only migration.

Covers:
- Gitignore entries added for all agent hook files
- git rm --cached called for tracked hook files
- Claude hooks moved from settings.json -> settings.local.json
- Empty settings.json cleaned up after migration
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from open_agent_kit.services.migrations import (
    _hooks_local_only,
    _migrate_claude_hooks_to_local,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CLAUDE_HOOKS = {
    "hooks": {"SessionStart": [{"hooks": [{"command": "oak ci hook SessionStart --agent claude"}]}]}
}

# Patch targets — these are local imports inside the migration function,
# so we patch at their source modules rather than on the migrations module.
_PATCH_CONFIG_SERVICE = "open_agent_kit.services.config_service.ConfigService"
_PATCH_AGENT_SERVICE = "open_agent_kit.services.agent_service.AgentService"


# ---------------------------------------------------------------------------
# _migrate_claude_hooks_to_local
# ---------------------------------------------------------------------------


class TestMigrateClaudeHooksToLocal:
    """Tests for Claude settings.json -> settings.local.json migration."""

    def test_moves_hooks_key_to_local(self, tmp_path: Path):
        """Hooks key should be moved from settings.json to settings.local.json."""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()

        old_settings = {"$schema": "https://...", **CLAUDE_HOOKS}
        (claude_dir / "settings.json").write_text(json.dumps(old_settings))

        _migrate_claude_hooks_to_local(tmp_path, ".claude")

        # settings.local.json should have hooks
        local_path = claude_dir / "settings.local.json"
        assert local_path.exists()
        local_config = json.loads(local_path.read_text())
        assert "hooks" in local_config
        assert "SessionStart" in local_config["hooks"]

        # settings.json should be removed (only $schema remained)
        assert not (claude_dir / "settings.json").exists()

    def test_preserves_non_hook_keys_in_settings_json(self, tmp_path: Path):
        """Non-hook keys in settings.json should be preserved."""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()

        old_settings = {
            "$schema": "https://...",
            "permissions": {"allow": ["Bash(oak:*)"]},
            **CLAUDE_HOOKS,
        }
        (claude_dir / "settings.json").write_text(json.dumps(old_settings))

        _migrate_claude_hooks_to_local(tmp_path, ".claude")

        # settings.json should still exist with permissions key
        old_path = claude_dir / "settings.json"
        assert old_path.exists()
        remaining = json.loads(old_path.read_text())
        assert "permissions" in remaining
        assert "hooks" not in remaining

    def test_merges_into_existing_local(self, tmp_path: Path):
        """Hooks should merge into existing settings.local.json content."""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()

        # Pre-existing settings.local.json with auto-approve
        (claude_dir / "settings.local.json").write_text(
            json.dumps({"permissions": {"allow": ["Bash(oak:*)"]}})
        )
        (claude_dir / "settings.json").write_text(json.dumps(CLAUDE_HOOKS))

        _migrate_claude_hooks_to_local(tmp_path, ".claude")

        local_config = json.loads((claude_dir / "settings.local.json").read_text())
        assert "permissions" in local_config
        assert "hooks" in local_config

    def test_noop_when_no_hooks(self, tmp_path: Path):
        """No-op when settings.json has no hooks key."""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()

        (claude_dir / "settings.json").write_text(json.dumps({"$schema": "https://..."}))

        _migrate_claude_hooks_to_local(tmp_path, ".claude")

        # settings.local.json should not be created
        assert not (claude_dir / "settings.local.json").exists()

    def test_noop_when_no_settings_json(self, tmp_path: Path):
        """No-op when settings.json doesn't exist."""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()

        _migrate_claude_hooks_to_local(tmp_path, ".claude")

        assert not (claude_dir / "settings.local.json").exists()


# ---------------------------------------------------------------------------
# _hooks_local_only (full migration)
# ---------------------------------------------------------------------------


class TestHooksLocalOnlyMigration:
    """Tests for the full hooks-local-only migration function.

    These tests let the real ``add_gitignore_entries`` run against tmp_path
    (safe) and mock service classes at their source module + subprocess.
    """

    def _mock_manifest(self, agent_name: str, folder: str, hook_type: str, config_file: str):
        """Create a mock manifest for testing."""
        manifest = MagicMock()
        manifest.installation.folder = folder
        manifest.hooks.type = hook_type
        manifest.hooks.config_file = config_file
        manifest.hooks.plugin_dir = None
        manifest.hooks.plugin_file = None
        return manifest

    def _run_migration(self, tmp_path, agents_config, get_manifest_fn):
        """Run the migration with mocked services and subprocess."""
        with (
            patch("subprocess.run") as mock_run,
            patch(_PATCH_CONFIG_SERVICE) as mock_config_cls,
            patch(_PATCH_AGENT_SERVICE) as mock_agent_cls,
        ):
            mock_config_cls.return_value.load_config.return_value = agents_config
            mock_agent_cls.return_value.get_agent_manifest.side_effect = get_manifest_fn

            _hooks_local_only(tmp_path)

            return mock_run

    def test_adds_gitignore_entries_for_configured_agents(self, tmp_path: Path):
        """Migration should add gitignore entries for all agent hook files."""
        mock_config = MagicMock()
        mock_config.agents = ["claude", "cursor"]

        claude_manifest = self._mock_manifest("claude", ".claude/", "json", "settings.local.json")
        cursor_manifest = self._mock_manifest("cursor", ".cursor/", "json", "hooks.json")

        def get_manifest(name):
            return {"claude": claude_manifest, "cursor": cursor_manifest}[name]

        self._run_migration(tmp_path, mock_config, get_manifest)

        gitignore = (tmp_path / ".gitignore").read_text()
        assert ".claude/settings.local.json" in gitignore
        assert ".cursor/hooks.json" in gitignore

    def test_adds_gitignore_for_plugin_agents(self, tmp_path: Path):
        """Migration should handle plugin-type agents (e.g., OpenCode)."""
        mock_config = MagicMock()
        mock_config.agents = ["opencode"]

        manifest = MagicMock()
        manifest.installation.folder = ".opencode/"
        manifest.hooks.type = "plugin"
        manifest.hooks.config_file = None
        manifest.hooks.plugin_dir = "plugins"
        manifest.hooks.plugin_file = "oak-ci.ts"

        self._run_migration(tmp_path, mock_config, lambda _: manifest)

        gitignore = (tmp_path / ".gitignore").read_text()
        assert ".opencode/plugins/oak-ci.ts" in gitignore

    def test_calls_git_rm_cached_for_existing_files(self, tmp_path: Path):
        """Migration should untrack existing hook files from git."""
        mock_config = MagicMock()
        mock_config.agents = ["cursor"]

        manifest = self._mock_manifest("cursor", ".cursor/", "json", "hooks.json")

        # Create the hook file so git rm --cached is attempted
        hook_dir = tmp_path / ".cursor"
        hook_dir.mkdir()
        (hook_dir / "hooks.json").write_text("{}")

        mock_run = self._run_migration(tmp_path, mock_config, lambda _: manifest)

        mock_run.assert_called()
        git_call = mock_run.call_args
        assert "git" in git_call[0][0]
        assert "rm" in git_call[0][0]
        assert "--cached" in git_call[0][0]

    def test_triggers_claude_hooks_migration(self, tmp_path: Path):
        """Migration should move Claude hooks from settings.json to settings.local.json."""
        mock_config = MagicMock()
        mock_config.agents = ["claude"]

        manifest = self._mock_manifest("claude", ".claude/", "json", "settings.local.json")

        # Create settings.json with hooks
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "settings.json").write_text(json.dumps(CLAUDE_HOOKS))

        self._run_migration(tmp_path, mock_config, lambda _: manifest)

        # settings.local.json should have hooks
        local = json.loads((claude_dir / "settings.local.json").read_text())
        assert "hooks" in local

    def test_noop_when_no_agents(self, tmp_path: Path):
        """Migration should be a no-op when no agents are configured."""
        mock_config = MagicMock()
        mock_config.agents = []

        with patch(_PATCH_CONFIG_SERVICE) as mock_config_cls:
            mock_config_cls.return_value.load_config.return_value = mock_config
            _hooks_local_only(tmp_path)

        # No gitignore should be created
        assert not (tmp_path / ".gitignore").exists()

    def test_noop_when_config_missing(self, tmp_path: Path):
        """Migration should be a no-op when config can't be loaded."""
        with patch(_PATCH_CONFIG_SERVICE) as mock_config_cls:
            mock_config_cls.return_value.load_config.side_effect = FileNotFoundError
            _hooks_local_only(tmp_path)

        assert not (tmp_path / ".gitignore").exists()
