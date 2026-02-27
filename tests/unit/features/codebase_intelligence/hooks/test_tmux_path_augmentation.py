"""Tests for POSIX PATH augmentation in rendered hook commands.

Verifies that hook commands are rendered with PATH augmentation so
the ``oak`` binary is findable in tmux and other environments where
PATH may be stale.
"""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import MagicMock

import pytest

from open_agent_kit.features.codebase_intelligence.hooks.strategies import (
    _POSIX_HOOK_PATH_DIRS,
    _render_hook_template_commands,
)

# Shorthand for the expected PATH prefix on POSIX
_EXPECTED_PREFIX = f'PATH="{_POSIX_HOOK_PATH_DIRS}:$PATH" '

# Minimal hook template structure (Claude-style nested format)
_TEMPLATE_NESTED = {
    "hooks": {
        "SessionStart": [
            {
                "hooks": [
                    {
                        "command": "{oak-cli-command} ci hook SessionStart --agent claude 2>/dev/null || true",
                        "timeout": 60,
                    }
                ]
            }
        ]
    }
}

# Flat hook format (Cursor-style)
_TEMPLATE_FLAT = {
    "hooks": {
        "sessionStart": [
            {"command": "{oak-cli-command} ci hook sessionStart --agent cursor 2>/dev/null || true"}
        ]
    }
}

# Copilot-style with bash/powershell keys
_TEMPLATE_COPILOT = {
    "hooks": {
        "sessionStart": [
            {
                "bash": "{oak-cli-command} ci hook sessionStart --agent vscode-copilot 2>/dev/null || true",
                "powershell": "{oak-cli-command} ci hook sessionStart --agent vscode-copilot 2>$null; exit 0",
            }
        ]
    }
}


class TestPosixPathAugmentation:
    """PATH augmentation for POSIX shell commands."""

    @pytest.mark.skipif(os.name == "nt", reason="POSIX PATH augmentation only")
    def test_command_key_gets_path_prefix(self) -> None:
        """Nested ``command`` keys should be prefixed with PATH augmentation."""
        rendered = _render_hook_template_commands(_TEMPLATE_NESTED, "oak")
        command = rendered["hooks"]["SessionStart"][0]["hooks"][0]["command"]
        assert command.startswith(_EXPECTED_PREFIX)
        assert "oak ci hook SessionStart --agent claude" in command

    @pytest.mark.skipif(os.name == "nt", reason="POSIX PATH augmentation only")
    def test_flat_command_key_gets_path_prefix(self) -> None:
        """Flat ``command`` keys should be prefixed with PATH augmentation."""
        rendered = _render_hook_template_commands(_TEMPLATE_FLAT, "oak")
        command = rendered["hooks"]["sessionStart"][0]["command"]
        assert command.startswith(_EXPECTED_PREFIX)
        assert "oak ci hook sessionStart --agent cursor" in command

    @pytest.mark.skipif(os.name == "nt", reason="POSIX PATH augmentation only")
    def test_bash_key_gets_path_prefix(self) -> None:
        """``bash`` keys should be prefixed with PATH augmentation."""
        rendered = _render_hook_template_commands(_TEMPLATE_COPILOT, "oak")
        bash_cmd = rendered["hooks"]["sessionStart"][0]["bash"]
        assert bash_cmd.startswith(_EXPECTED_PREFIX)
        assert "oak ci hook sessionStart --agent vscode-copilot" in bash_cmd

    @pytest.mark.skipif(os.name == "nt", reason="POSIX PATH augmentation only")
    def test_powershell_key_skips_path_prefix(self) -> None:
        """``powershell`` keys must NOT get POSIX PATH augmentation."""
        rendered = _render_hook_template_commands(_TEMPLATE_COPILOT, "oak")
        ps_cmd = rendered["hooks"]["sessionStart"][0]["powershell"]
        assert not ps_cmd.startswith("PATH=")
        assert "oak ci hook sessionStart --agent vscode-copilot" in ps_cmd

    @pytest.mark.skipif(os.name == "nt", reason="POSIX PATH augmentation only")
    def test_absolute_cli_command_skips_path_prefix(self) -> None:
        """Absolute CLI paths don't need PATH augmentation."""
        rendered = _render_hook_template_commands(_TEMPLATE_NESTED, "/usr/local/bin/oak")
        command = rendered["hooks"]["SessionStart"][0]["hooks"][0]["command"]
        assert not command.startswith("PATH=")
        assert command.startswith("/usr/local/bin/oak ci hook")

    @pytest.mark.skipif(os.name == "nt", reason="POSIX PATH augmentation only")
    def test_custom_cli_command_gets_path_prefix(self) -> None:
        """Custom (non-absolute) CLI commands also get PATH augmentation."""
        rendered = _render_hook_template_commands(_TEMPLATE_NESTED, "oak-dev")
        command = rendered["hooks"]["SessionStart"][0]["hooks"][0]["command"]
        assert command.startswith(_EXPECTED_PREFIX)
        assert "oak-dev ci hook SessionStart --agent claude" in command

    @pytest.mark.skipif(os.name == "nt", reason="POSIX PATH augmentation only")
    def test_placeholder_replaced_and_path_prepended(self) -> None:
        """Both placeholder replacement and PATH prepend happen correctly."""
        rendered = _render_hook_template_commands(_TEMPLATE_NESTED, "oak")
        command = rendered["hooks"]["SessionStart"][0]["hooks"][0]["command"]

        # No leftover placeholders
        assert "{oak-cli-command}" not in command
        # PATH is first, then the oak command
        assert command == (
            f"{_EXPECTED_PREFIX}oak ci hook SessionStart --agent claude 2>/dev/null || true"
        )

    @pytest.mark.skipif(os.name == "nt", reason="POSIX PATH augmentation only")
    def test_non_command_keys_unchanged(self) -> None:
        """Non-command keys like ``timeout`` are not modified."""
        rendered = _render_hook_template_commands(_TEMPLATE_NESTED, "oak")
        timeout = rendered["hooks"]["SessionStart"][0]["hooks"][0]["timeout"]
        assert timeout == 60


class TestWindowsPathAugmentation:
    """On Windows, PATH augmentation should be skipped."""

    @pytest.mark.skipif(os.name != "nt", reason="Windows-only test")
    def test_no_path_prefix_on_windows(self) -> None:
        """Windows should not get POSIX PATH augmentation."""
        rendered = _render_hook_template_commands(_TEMPLATE_NESTED, "oak")
        command = rendered["hooks"]["SessionStart"][0]["hooks"][0]["command"]
        assert not command.startswith("PATH=")
        assert command.startswith("oak ci hook")


class TestOakManagedDetectionWithPathPrefix:
    """OAK-managed hook detection must still work with PATH-prefixed commands."""

    @pytest.mark.skipif(os.name == "nt", reason="POSIX PATH augmentation only")
    def test_oak_managed_detected_with_path_prefix(self) -> None:
        """Hooks with PATH prefix should still be detected as OAK-managed."""
        from open_agent_kit.features.codebase_intelligence.hooks.strategies import (
            _check_oak_managed,
        )

        hooks_config = MagicMock()
        hooks_config.format = "nested"

        # Simulate a hook with PATH augmentation (as rendered by our code)
        hook_with_prefix: dict[str, Any] = {
            "hooks": [
                {
                    "command": f"{_EXPECTED_PREFIX}oak ci hook SessionStart --agent claude 2>/dev/null || true"
                }
            ]
        }
        assert _check_oak_managed(hook_with_prefix, hooks_config, "oak", "claude") is True

    @pytest.mark.skipif(os.name == "nt", reason="POSIX PATH augmentation only")
    def test_oak_managed_detected_without_path_prefix(self) -> None:
        """Hooks without PATH prefix (legacy) should still be detected as OAK-managed."""
        from open_agent_kit.features.codebase_intelligence.hooks.strategies import (
            _check_oak_managed,
        )

        hooks_config = MagicMock()
        hooks_config.format = "nested"

        hook_without_prefix: dict[str, Any] = {
            "hooks": [{"command": "oak ci hook SessionStart --agent claude 2>/dev/null || true"}]
        }
        assert _check_oak_managed(hook_without_prefix, hooks_config, "oak", "claude") is True
