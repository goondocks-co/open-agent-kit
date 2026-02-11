"""Tests for CLI daemon version mismatch hint.

Tests cover:
- Prints hint on version mismatch
- No hint when versions match
- No hint when daemon not running (no PID file)
- No hint when health check fails
- Hint uses configured cli_command
- No hint when CI not initialized
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from open_agent_kit.config.paths import OAK_DIR
from open_agent_kit.constants import VERSION
from open_agent_kit.features.codebase_intelligence.constants import (
    CI_DATA_DIR,
    CI_PID_FILE,
)

# Test version values (no magic strings)
_RUNNING_VERSION = "0.9.0"
_CUSTOM_CLI_COMMAND = "oak-dev"
_DEFAULT_CLI_COMMAND = "oak"
_TEST_PORT = 37800


@pytest.fixture
def project_with_pid(tmp_path: Path) -> Path:
    """Create .oak/ci/ directory with a PID file and return project root."""
    ci_dir = tmp_path / OAK_DIR / CI_DATA_DIR
    ci_dir.mkdir(parents=True)
    pid_file = ci_dir / CI_PID_FILE
    pid_file.write_text("12345")
    return tmp_path


def _make_health_response(oak_version: str) -> MagicMock:
    """Create a mock httpx response with the given oak_version."""
    resp = MagicMock()
    resp.json.return_value = {"oak_version": oak_version}
    return resp


class TestCliVersionHint:
    """Test _check_daemon_version_hint() from cli.py."""

    def test_prints_hint_on_mismatch(
        self, project_with_pid: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Prints version mismatch hint when running != installed."""
        from open_agent_kit.cli import _check_daemon_version_hint

        mock_response = _make_health_response(_RUNNING_VERSION)

        with (
            patch.object(Path, "cwd", return_value=project_with_pid),
            patch("httpx.get", return_value=mock_response),
            patch(
                "open_agent_kit.features.codebase_intelligence.daemon.manager.get_project_port",
                return_value=_TEST_PORT,
            ),
            patch(
                "open_agent_kit.features.codebase_intelligence.cli_command.resolve_ci_cli_command",
                return_value=_DEFAULT_CLI_COMMAND,
            ),
        ):
            _check_daemon_version_hint()

        captured = capsys.readouterr()
        # The hint should mention both versions
        assert _RUNNING_VERSION in captured.out
        assert VERSION in captured.out

    def test_no_hint_when_versions_match(
        self, project_with_pid: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """No hint when running version equals installed VERSION."""
        from open_agent_kit.cli import _check_daemon_version_hint

        mock_response = _make_health_response(VERSION)

        with (
            patch.object(Path, "cwd", return_value=project_with_pid),
            patch("httpx.get", return_value=mock_response),
            patch(
                "open_agent_kit.features.codebase_intelligence.daemon.manager.get_project_port",
                return_value=_TEST_PORT,
            ),
        ):
            _check_daemon_version_hint()

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_no_hint_when_daemon_not_running(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """No hint when PID file does not exist."""
        from open_agent_kit.cli import _check_daemon_version_hint

        # No .oak/ci/ directory at all
        with patch.object(Path, "cwd", return_value=tmp_path):
            _check_daemon_version_hint()

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_no_hint_when_health_check_fails(
        self, project_with_pid: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """No hint when health check request fails (connection refused)."""
        from open_agent_kit.cli import _check_daemon_version_hint

        with (
            patch.object(Path, "cwd", return_value=project_with_pid),
            patch("httpx.get", side_effect=ConnectionError("refused")),
            patch(
                "open_agent_kit.features.codebase_intelligence.daemon.manager.get_project_port",
                return_value=_TEST_PORT,
            ),
        ):
            _check_daemon_version_hint()

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_hint_uses_configured_cli_command(
        self, project_with_pid: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Hint message uses configured cli_command (e.g., 'oak-dev')."""
        from open_agent_kit.cli import _check_daemon_version_hint

        mock_response = _make_health_response(_RUNNING_VERSION)

        with (
            patch.object(Path, "cwd", return_value=project_with_pid),
            patch("httpx.get", return_value=mock_response),
            patch(
                "open_agent_kit.features.codebase_intelligence.daemon.manager.get_project_port",
                return_value=_TEST_PORT,
            ),
            patch(
                "open_agent_kit.features.codebase_intelligence.cli_command.resolve_ci_cli_command",
                return_value=_CUSTOM_CLI_COMMAND,
            ),
        ):
            _check_daemon_version_hint()

        captured = capsys.readouterr()
        assert _CUSTOM_CLI_COMMAND in captured.out

    def test_no_hint_when_ci_not_initialized(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """No hint when .oak/ci/ directory does not exist (no PID file)."""
        from open_agent_kit.cli import _check_daemon_version_hint

        # Create .oak/ but not .oak/ci/
        (tmp_path / OAK_DIR).mkdir()

        with patch.object(Path, "cwd", return_value=tmp_path):
            _check_daemon_version_hint()

        captured = capsys.readouterr()
        assert captured.out == ""
