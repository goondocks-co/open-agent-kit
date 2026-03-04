"""Tests for oak team members CLI commands."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from open_agent_kit.commands.team.members import members_app

runner = CliRunner()

# Shared mock paths
_CHECK_OAK = "open_agent_kit.commands.team.members.check_oak_initialized"
_CHECK_CI = "open_agent_kit.commands.team.members.check_ci_enabled"
_GET_DAEMON = "open_agent_kit.commands.team.members.get_daemon_manager"


def _mock_daemon_manager(running=True, port=37800):
    """Create a mock DaemonManager."""
    manager = MagicMock()
    manager.is_running.return_value = running
    manager.get_status.return_value = {"port": port, "running": running}
    return manager


class TestMembersStatus:
    """Tests for members status command."""

    @patch(_GET_DAEMON)
    @patch(_CHECK_CI)
    @patch(_CHECK_OAK)
    def test_status_daemon_not_running(self, mock_oak, mock_ci, mock_daemon):
        """Test status shows warning when daemon is not running."""
        mock_daemon.return_value = _mock_daemon_manager(running=False)

        result = runner.invoke(members_app, ["status"])

        assert result.exit_code == 0

    @patch(_GET_DAEMON)
    @patch(_CHECK_CI)
    @patch(_CHECK_OAK)
    def test_status_not_configured(self, mock_oak, mock_ci, mock_daemon):
        """Test status shows not-configured when relay not connected."""
        mock_daemon.return_value = _mock_daemon_manager()

        with patch("httpx.Client") as mock_client_cls:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"configured": False}
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.return_value = mock_response
            mock_client_cls.return_value = mock_client

            result = runner.invoke(members_app, ["status"])

        assert result.exit_code == 0
        assert "not configured" in result.output.lower() or "Not configured" in result.output


class TestMembersList:
    """Tests for members list command."""

    @patch(_GET_DAEMON)
    @patch(_CHECK_CI)
    @patch(_CHECK_OAK)
    def test_members_no_members(self, mock_oak, mock_ci, mock_daemon):
        """Test members shows message when no members found."""
        mock_daemon.return_value = _mock_daemon_manager()

        with patch("httpx.Client") as mock_client_cls:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"members": []}
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.get.return_value = mock_response
            mock_client_cls.return_value = mock_client

            result = runner.invoke(members_app, ["list"])

        assert result.exit_code == 0


class TestCommandRegistration:
    """Tests for command registration."""

    def test_members_app_is_registered(self):
        """Test that members_app is importable and has expected commands."""
        from open_agent_kit.commands.team.members import members_app

        # Get registered command names
        command_names = []
        if hasattr(members_app, "registered_commands"):
            command_names = [cmd.name for cmd in members_app.registered_commands if cmd.name]

        # Verify core commands exist
        assert "status" in command_names
        assert "list" in command_names

    def test_team_app_registered_on_main_app(self):
        """Test that team_app is registered as a top-level command group."""
        from open_agent_kit.cli import app

        group_names = []
        if hasattr(app, "registered_groups"):
            group_names = [
                g.typer_instance.info.name
                for g in app.registered_groups
                if g.typer_instance and g.typer_instance.info
            ]

        assert "team" in group_names
