"""Tests for oak ci team CLI commands."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from open_agent_kit.commands.ci.team import team_app

runner = CliRunner()

# Shared mock paths
_CHECK_OAK = "open_agent_kit.commands.ci.team.check_oak_initialized"
_CHECK_CI = "open_agent_kit.commands.ci.team.check_ci_enabled"
_LOAD_CONFIG = "open_agent_kit.features.codebase_intelligence.config.load_ci_config"
_SAVE_CONFIG = "open_agent_kit.features.codebase_intelligence.config.save_ci_config"
_GET_DAEMON = "open_agent_kit.commands.ci.team.get_daemon_manager"


def _make_config(server_url=None, api_key=None, auto_sync=False):
    """Create a mock CIConfig with team settings."""
    config = MagicMock()
    config.team.server_url = server_url
    config.team.api_key = api_key
    config.team.auto_sync = auto_sync
    config.team.server_mode = False
    config.team.bind_host = "127.0.0.1"
    config.team.bind_port = 8600
    return config


def _mock_daemon_manager(running=True, port=37800):
    """Create a mock DaemonManager."""
    manager = MagicMock()
    manager.is_running.return_value = running
    manager.get_status.return_value = {"port": port, "running": running}
    manager.start.return_value = True
    manager.stop.return_value = True
    return manager


class TestTeamJoin:
    """Tests for team join command."""

    @patch(_GET_DAEMON)
    @patch(_CHECK_CI)
    @patch(_CHECK_OAK)
    def test_join_delegates_to_daemon(self, mock_oak, mock_ci, mock_daemon):
        """Test that join delegates to the daemon /api/team/join endpoint."""
        mock_daemon.return_value = _mock_daemon_manager()

        with patch("open_agent_kit.commands.ci.team.httpx.Client") as mock_client_cls:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "status": "pending_approval",
                "key_id": "abc123",
                "server_url": "https://team.example.com",
            }
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            result = runner.invoke(
                team_app,
                ["join", "--server-url", "https://team.example.com"],
            )

        assert result.exit_code == 0
        # Should have posted to daemon join endpoint
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "/api/team/join" in call_args[0][0]
        assert call_args[1]["json"] == {"server_url": "https://team.example.com"}

    @patch(_CHECK_CI)
    @patch(_CHECK_OAK)
    def test_join_rejects_invalid_url(self, mock_oak, mock_ci):
        """Test that join rejects URLs without http:// or https://."""
        result = runner.invoke(
            team_app,
            ["join", "--server-url", "ftp://bad.example.com"],
        )
        assert result.exit_code != 0

    @patch(_GET_DAEMON)
    @patch(_CHECK_CI)
    @patch(_CHECK_OAK)
    def test_join_shows_pending_status(self, mock_oak, mock_ci, mock_daemon):
        """Test that join shows pending approval message."""
        mock_daemon.return_value = _mock_daemon_manager()

        with patch("open_agent_kit.commands.ci.team.httpx.Client") as mock_client_cls:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "status": "pending_approval",
                "key_id": "abc123",
                "server_url": "https://team.example.com",
            }
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            result = runner.invoke(
                team_app,
                ["join", "--server-url", "https://team.example.com"],
            )

        assert result.exit_code == 0
        assert "approval" in result.output.lower()


class TestTeamLeave:
    """Tests for team leave command."""

    @patch(_GET_DAEMON)
    @patch(_CHECK_CI)
    @patch(_CHECK_OAK)
    def test_leave_via_daemon(self, mock_oak, mock_ci, mock_daemon):
        """Test that leave goes through daemon API when running."""
        mock_daemon.return_value = _mock_daemon_manager()

        with patch("open_agent_kit.commands.ci.team.httpx.Client") as mock_client_cls:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "disconnected"}
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            result = runner.invoke(team_app, ["leave"])

        assert result.exit_code == 0
        mock_client.post.assert_called_once()
        assert "/api/team/leave" in mock_client.post.call_args[0][0]

    @patch(_SAVE_CONFIG)
    @patch(_LOAD_CONFIG)
    @patch(_GET_DAEMON)
    @patch(_CHECK_CI)
    @patch(_CHECK_OAK)
    def test_leave_fallback_when_daemon_not_running(
        self, mock_oak, mock_ci, mock_daemon, mock_load, mock_save
    ):
        """Test that leave falls back to direct config write when daemon is down."""
        mock_daemon.return_value = _mock_daemon_manager(running=False)
        mock_load.return_value = _make_config(
            server_url="https://team.example.com",
            api_key="old-token",
            auto_sync=True,
        )

        result = runner.invoke(team_app, ["leave"])

        assert result.exit_code == 0
        mock_save.assert_called_once()
        saved_config = mock_save.call_args[0][1]
        assert saved_config.team.server_url is None
        assert saved_config.team.api_key is None
        assert saved_config.team.auto_sync is False

    @patch(_GET_DAEMON)
    @patch(_CHECK_CI)
    @patch(_CHECK_OAK)
    def test_leave_when_not_configured(self, mock_oak, mock_ci, mock_daemon):
        """Test that leave handles not-configured gracefully when daemon is down."""
        mock_daemon.return_value = _mock_daemon_manager(running=False)

        with patch(_LOAD_CONFIG) as mock_load:
            mock_load.return_value = _make_config()
            result = runner.invoke(team_app, ["leave"])

        assert result.exit_code == 0


class TestTeamStatus:
    """Tests for team status command."""

    @patch(_GET_DAEMON)
    @patch(_LOAD_CONFIG)
    @patch(_CHECK_CI)
    @patch(_CHECK_OAK)
    def test_status_not_configured(self, mock_oak, mock_ci, mock_load, mock_daemon):
        """Test status shows not-configured when no server_url."""
        mock_load.return_value = _make_config()

        result = runner.invoke(team_app, ["status"])

        assert result.exit_code == 0
        # The message constant value is used
        assert "not configured" in result.output.lower() or "Not configured" in result.output

    @patch(_GET_DAEMON)
    @patch(_LOAD_CONFIG)
    @patch(_CHECK_CI)
    @patch(_CHECK_OAK)
    def test_status_shows_server_url(self, mock_oak, mock_ci, mock_load, mock_daemon):
        """Test status shows server URL when configured."""
        mock_load.return_value = _make_config(
            server_url="https://team.example.com",
            auto_sync=True,
        )
        mock_daemon.return_value = _mock_daemon_manager(running=False)

        result = runner.invoke(team_app, ["status"])

        assert result.exit_code == 0
        assert "team.example.com" in result.output


class TestKeyCreate:
    """Tests for team key create command."""

    @patch(_GET_DAEMON)
    @patch(_CHECK_CI)
    @patch(_CHECK_OAK)
    def test_key_create_displays_key(self, mock_oak, mock_ci, mock_daemon):
        """Test key create displays the plaintext key."""
        mock_daemon.return_value = _mock_daemon_manager()

        with patch("open_agent_kit.commands.ci.team.httpx.Client") as mock_client_cls:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"key": "oak_team_abc123", "id": "key-1"}
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            result = runner.invoke(team_app, ["key", "create", "--name", "test-key"])

        assert result.exit_code == 0
        assert "oak_team_abc123" in result.output


class TestKeyRevoke:
    """Tests for team key revoke command."""

    @patch(_GET_DAEMON)
    @patch(_CHECK_CI)
    @patch(_CHECK_OAK)
    def test_key_revoke_success(self, mock_oak, mock_ci, mock_daemon):
        """Test key revoke prints confirmation."""
        mock_daemon.return_value = _mock_daemon_manager()

        with patch("open_agent_kit.commands.ci.team.httpx.Client") as mock_client_cls:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.delete.return_value = mock_response
            mock_client_cls.return_value = mock_client

            result = runner.invoke(team_app, ["key", "revoke", "key-123"])

        assert result.exit_code == 0


class TestCommandRegistration:
    """Tests for command registration."""

    def test_team_app_is_registered(self):
        """Test that team_app is importable and has expected commands."""
        from open_agent_kit.commands.ci.team import team_app

        # Get registered command names
        command_names = []
        if hasattr(team_app, "registered_commands"):
            command_names = [cmd.name for cmd in team_app.registered_commands if cmd.name]
        # Also check registered_groups for sub-typer apps
        group_names = []
        if hasattr(team_app, "registered_groups"):
            group_names = [
                g.typer_instance.info.name
                for g in team_app.registered_groups
                if g.typer_instance and g.typer_instance.info
            ]

        # Verify core commands exist
        assert "join" in command_names
        assert "leave" in command_names
        assert "status" in command_names
        assert "members" in command_names
        assert "serve" in command_names
        # Verify key sub-group exists
        assert "key" in group_names

    def test_team_app_registered_on_ci_app(self):
        """Test that team_app is registered as a sub-typer on ci_app."""
        from open_agent_kit.commands.ci import ci_app

        group_names = []
        if hasattr(ci_app, "registered_groups"):
            group_names = [
                g.typer_instance.info.name
                for g in ci_app.registered_groups
                if g.typer_instance and g.typer_instance.info
            ]

        assert "team" in group_names
