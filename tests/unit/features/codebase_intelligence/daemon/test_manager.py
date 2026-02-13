"""Tests for daemon lifecycle management.

Tests cover:
- Port derivation determinism
- Port caching and retrieval
- Daemon manager initialization
- PID file operations
- Process running checks
- Health checks
- Status retrieval
"""

import builtins
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from open_agent_kit.features.codebase_intelligence.constants import (
    CI_AUTH_ENV_VAR,
    CI_LOG_FILE,
    CI_NULL_DEVICE_POSIX,
    CI_NULL_DEVICE_WINDOWS,
    CI_TOKEN_FILE,
    CI_TOKEN_FILE_PERMISSIONS,
)
from open_agent_kit.features.codebase_intelligence.daemon.manager import (
    DEFAULT_PORT,
    PORT_RANGE_SIZE,
    PORT_RANGE_START,
    DaemonManager,
    derive_port_from_path,
    get_project_port,
    read_project_port,
)

# =============================================================================
# Port Derivation Tests
# =============================================================================


class TestDerivePortFromPath:
    """Test port derivation from project path."""

    def test_deterministic_derivation(self, tmp_path: Path):
        """Test that port derivation is deterministic.

        The same path should always produce the same port.

        Args:
            tmp_path: Temporary directory from pytest.
        """
        port1 = derive_port_from_path(tmp_path)
        port2 = derive_port_from_path(tmp_path)

        assert port1 == port2

    def test_different_paths_produce_different_ports(self, tmp_path: Path):
        """Test that different paths produce different ports.

        Args:
            tmp_path: Temporary directory from pytest.
        """
        path1 = tmp_path / "project1"
        path2 = tmp_path / "project2"

        path1.mkdir()
        path2.mkdir()

        port1 = derive_port_from_path(path1)
        port2 = derive_port_from_path(path2)

        # Highly likely to be different (though theoretically could collide)
        assert port1 != port2

    def test_port_in_valid_range(self, tmp_path: Path):
        """Test that derived port is in valid range.

        Args:
            tmp_path: Temporary directory from pytest.
        """
        port = derive_port_from_path(tmp_path)

        assert PORT_RANGE_START <= port < PORT_RANGE_START + PORT_RANGE_SIZE

    def test_port_derivation_uses_resolved_path(self, tmp_path: Path):
        """Test that derivation uses resolved absolute path.

        Args:
            tmp_path: Temporary directory from pytest.
        """
        # Create a symlink
        original = tmp_path / "original"
        original.mkdir()
        symlink = tmp_path / "symlink"

        try:
            symlink.symlink_to(original)
            # Ports should be the same (resolved to same path)
            port_original = derive_port_from_path(original)
            port_symlink = derive_port_from_path(symlink)
            # They should resolve to the same port
            assert port_original == port_symlink
        except OSError:
            # Skip if symlinks not supported
            pytest.skip("Symlinks not supported on this system")


class TestReadProjectPort:
    """Test read_project_port function (read-only, no side effects)."""

    def test_returns_none_when_no_files(self, tmp_path: Path):
        """Returns None when no port files exist."""
        ci_dir = tmp_path / ".oak" / "ci"
        result = read_project_port(tmp_path, ci_dir)

        assert result is None

    def test_does_not_create_files(self, tmp_path: Path):
        """Must not create any port files as a side effect."""
        ci_dir = tmp_path / ".oak" / "ci"
        read_project_port(tmp_path, ci_dir)

        local_port_file = ci_dir / "daemon.port"
        shared_port_file = tmp_path / "oak" / "daemon.port"
        assert not local_port_file.exists()
        assert not shared_port_file.exists()

    def test_reads_local_override(self, tmp_path: Path):
        """Reads from .oak/ci/daemon.port (Priority 1)."""
        ci_dir = tmp_path / ".oak" / "ci"
        ci_dir.mkdir(parents=True)
        port_file = ci_dir / "daemon.port"
        port_file.write_text("37850")

        result = read_project_port(tmp_path, ci_dir)

        assert result == 37850

    def test_reads_shared_port(self, tmp_path: Path):
        """Reads from oak/daemon.port (Priority 2)."""
        ci_dir = tmp_path / ".oak" / "ci"
        shared_dir = tmp_path / "oak"
        shared_dir.mkdir(parents=True)
        (shared_dir / "daemon.port").write_text("37860")

        result = read_project_port(tmp_path, ci_dir)

        assert result == 37860

    def test_local_override_takes_priority(self, tmp_path: Path):
        """Local override (.oak/ci) wins over shared (oak/) file."""
        ci_dir = tmp_path / ".oak" / "ci"
        ci_dir.mkdir(parents=True)
        (ci_dir / "daemon.port").write_text("37850")

        shared_dir = tmp_path / "oak"
        shared_dir.mkdir(parents=True)
        (shared_dir / "daemon.port").write_text("37860")

        result = read_project_port(tmp_path, ci_dir)

        assert result == 37850

    def test_skips_invalid_port_file(self, tmp_path: Path):
        """Returns None when port file contains invalid data."""
        ci_dir = tmp_path / ".oak" / "ci"
        ci_dir.mkdir(parents=True)
        (ci_dir / "daemon.port").write_text("not-a-number")

        result = read_project_port(tmp_path, ci_dir)

        assert result is None

    def test_skips_out_of_range_port(self, tmp_path: Path):
        """Returns None when port file contains out-of-range value."""
        ci_dir = tmp_path / ".oak" / "ci"
        ci_dir.mkdir(parents=True)
        (ci_dir / "daemon.port").write_text("99999")

        result = read_project_port(tmp_path, ci_dir)

        assert result is None

    def test_falls_through_to_shared_on_invalid_local(self, tmp_path: Path):
        """Falls through to shared file when local override is invalid."""
        ci_dir = tmp_path / ".oak" / "ci"
        ci_dir.mkdir(parents=True)
        (ci_dir / "daemon.port").write_text("garbage")

        shared_dir = tmp_path / "oak"
        shared_dir.mkdir(parents=True)
        (shared_dir / "daemon.port").write_text("37870")

        result = read_project_port(tmp_path, ci_dir)

        assert result == 37870


class TestGetProjectPort:
    """Test get_project_port function."""

    def test_derives_port_when_no_file(self, tmp_path: Path):
        """Test port derivation when port file doesn't exist.

        Args:
            tmp_path: Temporary directory from pytest.
        """
        ci_dir = tmp_path / ".oak" / "ci"
        port = get_project_port(tmp_path, ci_dir)

        assert PORT_RANGE_START <= port < PORT_RANGE_START + PORT_RANGE_SIZE

    def test_port_file_is_created(self, tmp_path: Path):
        """Test that shared port file (oak/daemon.port) is created after first call.

        Args:
            tmp_path: Temporary directory from pytest.
        """
        ci_dir = tmp_path / ".oak" / "ci"
        get_project_port(tmp_path, ci_dir)

        shared_port_file = tmp_path / "oak" / "daemon.port"
        assert shared_port_file.exists()

    def test_port_file_content_is_valid(self, tmp_path: Path):
        """Test that shared port file contains valid port number.

        Args:
            tmp_path: Temporary directory from pytest.
        """
        ci_dir = tmp_path / ".oak" / "ci"
        port = get_project_port(tmp_path, ci_dir)

        shared_port_file = tmp_path / "oak" / "daemon.port"
        stored_port = int(shared_port_file.read_text().strip())
        assert stored_port == port

    def test_reuses_stored_port(self, tmp_path: Path):
        """Test that stored port is reused on subsequent calls.

        Args:
            tmp_path: Temporary directory from pytest.
        """
        ci_dir = tmp_path / ".oak" / "ci"

        port1 = get_project_port(tmp_path, ci_dir)
        port2 = get_project_port(tmp_path, ci_dir)

        assert port1 == port2

    def test_handles_invalid_port_file(self, tmp_path: Path):
        """Test handling of corrupted port file.

        Args:
            tmp_path: Temporary directory from pytest.
        """
        ci_dir = tmp_path / ".oak" / "ci"
        ci_dir.mkdir(parents=True)

        # Create invalid port file
        port_file = ci_dir / "daemon.port"
        port_file.write_text("not-a-number")

        # Should derive new port instead
        port = get_project_port(tmp_path, ci_dir)
        assert PORT_RANGE_START <= port < PORT_RANGE_START + PORT_RANGE_SIZE

    def test_handles_out_of_range_port(self, tmp_path: Path):
        """Test handling of out-of-range port in file.

        Args:
            tmp_path: Temporary directory from pytest.
        """
        ci_dir = tmp_path / ".oak" / "ci"
        ci_dir.mkdir(parents=True)

        # Create port file with out-of-range value
        port_file = ci_dir / "daemon.port"
        port_file.write_text("99999")

        # Should derive new valid port
        port = get_project_port(tmp_path, ci_dir)
        assert PORT_RANGE_START <= port < PORT_RANGE_START + PORT_RANGE_SIZE

    def test_shared_file_created_even_with_local_override(self, tmp_path: Path):
        """Shared port file (oak/daemon.port) must always be created,
        even when a local override (.oak/ci/daemon.port) exists."""
        ci_dir = tmp_path / ".oak" / "ci"
        ci_dir.mkdir(parents=True)
        (ci_dir / "daemon.port").write_text("37850")

        port = get_project_port(tmp_path, ci_dir)

        shared_port_file = tmp_path / "oak" / "daemon.port"
        assert shared_port_file.exists(), "oak/daemon.port must always be created"
        # Return value should be the local override
        assert port == 37850

    def test_local_override_does_not_change_shared_file(self, tmp_path: Path):
        """Local override affects the return value but not the shared file content."""
        ci_dir = tmp_path / ".oak" / "ci"
        ci_dir.mkdir(parents=True)
        (ci_dir / "daemon.port").write_text("37850")

        get_project_port(tmp_path, ci_dir)

        shared_port_file = tmp_path / "oak" / "daemon.port"
        shared_port = int(shared_port_file.read_text().strip())
        # Shared file has the derived port, not the override
        assert shared_port != 37850
        assert PORT_RANGE_START <= shared_port < PORT_RANGE_START + PORT_RANGE_SIZE

    def test_shared_file_not_overwritten_on_subsequent_calls(self, tmp_path: Path):
        """Once oak/daemon.port exists, it should not be re-derived."""
        ci_dir = tmp_path / ".oak" / "ci"
        shared_dir = tmp_path / "oak"
        shared_dir.mkdir(parents=True)
        (shared_dir / "daemon.port").write_text("37860")

        port = get_project_port(tmp_path, ci_dir)

        assert port == 37860
        # File content unchanged
        assert int((shared_dir / "daemon.port").read_text().strip()) == 37860


class TestGetProjectPortTracking:
    """Tests for state tracking of oak/daemon.port in get_project_port()."""

    def test_records_created_file_on_port_creation(self, tmp_path: Path):
        """record_created_file() should be called when oak/daemon.port is created."""
        ci_dir = tmp_path / ".oak" / "ci"

        with patch("open_agent_kit.services.state_service.StateService") as mock_cls:
            mock_state = MagicMock()
            mock_cls.return_value = mock_state

            get_project_port(tmp_path, ci_dir)

        shared_port_file = tmp_path / "oak" / "daemon.port"
        shared_port_dir = tmp_path / "oak"
        mock_state.record_created_file.assert_called_once_with(
            shared_port_file, shared_port_file.read_text()
        )
        mock_state.record_created_directory.assert_called_once_with(shared_port_dir)

    def test_does_not_track_when_port_file_exists(self, tmp_path: Path):
        """record_created_file() should NOT be called when oak/daemon.port already exists."""
        shared_dir = tmp_path / "oak"
        shared_dir.mkdir(parents=True)
        (shared_dir / "daemon.port").write_text("37860")

        ci_dir = tmp_path / ".oak" / "ci"

        with patch("open_agent_kit.services.state_service.StateService") as mock_cls:
            get_project_port(tmp_path, ci_dir)

        mock_cls.assert_not_called()

    def test_state_tracking_failure_does_not_break_port(self, tmp_path: Path):
        """State tracking failure should not prevent port derivation."""
        ci_dir = tmp_path / ".oak" / "ci"

        with patch("open_agent_kit.services.state_service.StateService") as mock_cls:
            mock_cls.side_effect = ValueError("state broken")

            port = get_project_port(tmp_path, ci_dir)

        assert PORT_RANGE_START <= port < PORT_RANGE_START + PORT_RANGE_SIZE
        # Port file should still be created
        shared_port_file = tmp_path / "oak" / "daemon.port"
        assert shared_port_file.exists()


# =============================================================================
# DaemonManager Tests
# =============================================================================


class TestDaemonManagerInit:
    """Test DaemonManager initialization."""

    def test_init_with_defaults(self, tmp_path: Path):
        """Test initialization with default values.

        Args:
            tmp_path: Temporary directory from pytest.
        """
        manager = DaemonManager(tmp_path)

        assert manager.project_root == tmp_path
        assert manager.port == DEFAULT_PORT
        assert manager.ci_data_dir == tmp_path / ".oak" / "ci"

    def test_init_with_custom_port(self, tmp_path: Path):
        """Test initialization with custom port.

        Args:
            tmp_path: Temporary directory from pytest.
        """
        custom_port = 37850
        manager = DaemonManager(tmp_path, port=custom_port)

        assert manager.port == custom_port

    def test_init_with_custom_ci_data_dir(self, tmp_path: Path):
        """Test initialization with custom CI data directory.

        Args:
            tmp_path: Temporary directory from pytest.
        """
        custom_dir = tmp_path / "custom" / "ci"
        manager = DaemonManager(tmp_path, ci_data_dir=custom_dir)

        assert manager.ci_data_dir == custom_dir

    def test_base_url_is_constructed(self, tmp_path: Path):
        """Test that base URL is constructed correctly.

        Args:
            tmp_path: Temporary directory from pytest.
        """
        manager = DaemonManager(tmp_path, port=37800)

        assert manager.base_url == "http://localhost:37800"


class TestDaemonManagerPIDOperations:
    """Test PID file operations."""

    def test_read_pid_returns_none_if_file_missing(self, tmp_path: Path):
        """Test _read_pid returns None when file doesn't exist.

        Args:
            tmp_path: Temporary directory from pytest.
        """
        manager = DaemonManager(tmp_path, ci_data_dir=tmp_path / ".oak" / "ci")
        pid = manager._read_pid()

        assert pid is None

    def test_write_pid_creates_file(self, tmp_path: Path):
        """Test _write_pid creates pid file.

        Args:
            tmp_path: Temporary directory from pytest.
        """
        manager = DaemonManager(tmp_path, ci_data_dir=tmp_path / ".oak" / "ci")
        manager._write_pid(1234)

        assert manager.pid_file.exists()
        assert int(manager.pid_file.read_text().strip()) == 1234

    def test_read_written_pid(self, tmp_path: Path):
        """Test reading back written PID.

        Args:
            tmp_path: Temporary directory from pytest.
        """
        manager = DaemonManager(tmp_path, ci_data_dir=tmp_path / ".oak" / "ci")
        manager._write_pid(5678)

        read_pid = manager._read_pid()
        assert read_pid == 5678

    def test_remove_pid_deletes_file(self, tmp_path: Path):
        """Test _remove_pid deletes pid file.

        Args:
            tmp_path: Temporary directory from pytest.
        """
        manager = DaemonManager(tmp_path, ci_data_dir=tmp_path / ".oak" / "ci")
        manager._write_pid(1234)

        assert manager.pid_file.exists()
        manager._remove_pid()
        assert not manager.pid_file.exists()

    def test_read_invalid_pid_file(self, tmp_path: Path):
        """Test _read_pid handles corrupted file gracefully.

        Args:
            tmp_path: Temporary directory from pytest.
        """
        manager = DaemonManager(tmp_path, ci_data_dir=tmp_path / ".oak" / "ci")

        # Create invalid pid file
        manager.pid_file.parent.mkdir(parents=True, exist_ok=True)
        manager.pid_file.write_text("not-a-number")

        pid = manager._read_pid()
        assert pid is None


class TestDaemonManagerProcessChecks:
    """Test process running checks."""

    @patch("os.kill")
    def test_is_process_running_with_valid_pid(self, mock_kill, tmp_path: Path):
        """Test process running check with valid PID.

        Args:
            mock_kill: Mocked os.kill function.
            tmp_path: Temporary directory from pytest.
        """
        manager = DaemonManager(tmp_path)
        # os.kill with signal 0 returns success (no exception)
        mock_kill.return_value = None

        result = manager._is_process_running(1234)

        assert result is True
        mock_kill.assert_called_once_with(1234, 0)

    @patch("os.kill")
    def test_is_process_running_with_invalid_pid(self, mock_kill, tmp_path: Path):
        """Test process running check with invalid PID.

        Args:
            mock_kill: Mocked os.kill function.
            tmp_path: Temporary directory from pytest.
        """
        manager = DaemonManager(tmp_path)
        # os.kill raises OSError for invalid PID
        mock_kill.side_effect = OSError()

        result = manager._is_process_running(9999)

        assert result is False

    @patch("socket.socket")
    def test_is_port_in_use_returns_true(self, mock_socket, tmp_path: Path):
        """Test port in use detection when port is in use.

        Args:
            mock_socket: Mocked socket.socket.
            tmp_path: Temporary directory from pytest.
        """
        manager = DaemonManager(tmp_path, port=37800)

        # Mock successful connection (port in use)
        mock_instance = MagicMock()
        mock_instance.connect_ex.return_value = 0
        mock_socket.return_value.__enter__.return_value = mock_instance

        result = manager._is_port_in_use()

        assert result is True

    @patch("socket.socket")
    def test_is_port_in_use_returns_false(self, mock_socket, tmp_path: Path):
        """Test port in use detection when port is free.

        Args:
            mock_socket: Mocked socket.socket.
            tmp_path: Temporary directory from pytest.
        """
        manager = DaemonManager(tmp_path, port=37800)

        # Mock connection refused (port free)
        mock_instance = MagicMock()
        mock_instance.connect_ex.return_value = 1
        mock_socket.return_value.__enter__.return_value = mock_instance

        result = manager._is_port_in_use()

        assert result is False


class TestDaemonManagerHealthCheck:
    """Test health checking."""

    @patch("httpx.Client")
    def test_health_check_success(self, mock_client, tmp_path: Path):
        """Test successful health check.

        Args:
            mock_client: Mocked httpx.Client.
            tmp_path: Temporary directory from pytest.
        """
        manager = DaemonManager(tmp_path, port=37800)

        # Mock successful health check
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_instance = MagicMock()
        mock_instance.get.return_value = mock_response
        mock_client.return_value.__enter__.return_value = mock_instance

        result = manager._health_check()

        assert result is True

    @patch("httpx.Client")
    def test_health_check_failure(self, mock_client, tmp_path: Path):
        """Test failed health check.

        Args:
            mock_client: Mocked httpx.Client.
            tmp_path: Temporary directory from pytest.
        """
        manager = DaemonManager(tmp_path, port=37800)

        # Mock failed health check
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_instance = MagicMock()
        mock_instance.get.return_value = mock_response
        mock_client.return_value.__enter__.return_value = mock_instance

        result = manager._health_check()

        assert result is False

    @patch("httpx.Client", side_effect=ImportError("httpx not installed"))
    @patch(
        "open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager._is_port_in_use"
    )
    def test_health_check_fallback_to_port_check(
        self, mock_port_check, mock_client, tmp_path: Path
    ):
        """Test health check fallback when httpx unavailable.

        Args:
            mock_port_check: Mocked _is_port_in_use method.
            mock_client: Mocked httpx.Client that raises ImportError.
            tmp_path: Temporary directory from pytest.
        """
        manager = DaemonManager(tmp_path)
        mock_port_check.return_value = True

        result = manager._health_check()

        assert result is True


class TestDaemonManagerStatus:
    """Test status retrieval."""

    @patch("open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager._read_pid")
    @patch(
        "open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager._is_process_running"
    )
    @patch(
        "open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager._health_check"
    )
    @patch(
        "open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager._check_daemon_project_root"
    )
    def test_is_running_true(
        self, mock_project_root, mock_health, mock_running, mock_read_pid, tmp_path: Path
    ):
        """Test is_running returns True when daemon is healthy and owns this project.

        Args:
            mock_project_root: Mocked _check_daemon_project_root method.
            mock_health: Mocked _health_check method.
            mock_running: Mocked _is_process_running method.
            mock_read_pid: Mocked _read_pid method.
            tmp_path: Temporary directory from pytest.
        """
        manager = DaemonManager(tmp_path)
        mock_read_pid.return_value = 1234
        mock_running.return_value = True
        mock_health.return_value = True
        mock_project_root.return_value = True

        result = manager.is_running()

        assert result is True

    @patch("open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager._read_pid")
    @patch(
        "open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager._is_process_running"
    )
    @patch(
        "open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager._health_check"
    )
    @patch(
        "open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager._check_daemon_project_root"
    )
    def test_is_running_false_when_rogue_daemon(
        self, mock_project_root, mock_health, mock_running, mock_read_pid, tmp_path: Path
    ):
        """Test is_running returns False when daemon belongs to a different project.

        Args:
            mock_project_root: Mocked _check_daemon_project_root method.
            mock_health: Mocked _health_check method.
            mock_running: Mocked _is_process_running method.
            mock_read_pid: Mocked _read_pid method.
            tmp_path: Temporary directory from pytest.
        """
        manager = DaemonManager(tmp_path)
        mock_read_pid.return_value = 1234
        mock_running.return_value = True
        mock_health.return_value = True
        mock_project_root.return_value = False

        result = manager.is_running()

        assert result is False

    @patch("open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager._read_pid")
    @patch(
        "open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager._is_process_running"
    )
    def test_is_running_false_when_pid_stale(self, mock_running, mock_read_pid, tmp_path: Path):
        """Test is_running handles stale PID files.

        Args:
            mock_running: Mocked _is_process_running method.
            mock_read_pid: Mocked _read_pid method.
            tmp_path: Temporary directory from pytest.
        """
        manager = DaemonManager(tmp_path)
        mock_read_pid.return_value = 9999
        mock_running.return_value = False

        result = manager.is_running()

        assert result is False

    @patch("open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager._read_pid")
    @patch("open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager.is_running")
    def test_get_status_includes_port_and_pid(self, mock_running, mock_read_pid, tmp_path: Path):
        """Test that get_status includes port and pid.

        Args:
            mock_running: Mocked is_running method.
            mock_read_pid: Mocked _read_pid method.
            tmp_path: Temporary directory from pytest.
        """
        manager = DaemonManager(tmp_path, port=37800)
        mock_read_pid.return_value = 5678
        mock_running.return_value = True

        status = manager.get_status()

        assert status["port"] == 37800
        assert status["pid"] == 5678
        assert status["running"] is True

    @patch(
        "open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager._health_check"
    )
    def test_get_status_not_running(self, mock_health_check, tmp_path: Path):
        """Test get_status when daemon not running.

        Args:
            mock_health_check: Mocked _health_check method.
            tmp_path: Temporary directory from pytest.
        """
        mock_health_check.return_value = False
        manager = DaemonManager(tmp_path, ci_data_dir=tmp_path / ".oak" / "ci")

        status = manager.get_status()

        assert status["running"] is False
        assert status["port"] == DEFAULT_PORT


class TestDaemonManagerEnsureDataDir:
    """Test data directory management."""

    def test_ensure_data_dir_creates_directory(self, tmp_path: Path):
        """Test that _ensure_data_dir creates directory.

        Args:
            tmp_path: Temporary directory from pytest.
        """
        ci_dir = tmp_path / "custom" / "deep" / "ci"
        manager = DaemonManager(tmp_path, ci_data_dir=ci_dir)

        manager._ensure_data_dir()

        assert ci_dir.exists()
        assert ci_dir.is_dir()

    def test_ensure_data_dir_idempotent(self, tmp_path: Path):
        """Test that _ensure_data_dir is idempotent.

        Args:
            tmp_path: Temporary directory from pytest.
        """
        ci_dir = tmp_path / ".oak" / "ci"
        manager = DaemonManager(tmp_path, ci_data_dir=ci_dir)

        manager._ensure_data_dir()
        manager._ensure_data_dir()  # Second call should not fail

        assert ci_dir.exists()


# =============================================================================
# Start/Stop/Restart Tests
# =============================================================================


class TestDaemonManagerStart:
    """Test daemon start functionality."""

    @patch("open_agent_kit.features.codebase_intelligence.deps.check_ci_dependencies")
    @patch("open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager.is_running")
    def test_start_returns_true_when_already_running(
        self, mock_is_running, mock_check_deps, tmp_path: Path
    ):
        """Test that start returns True if daemon is already running."""
        mock_check_deps.return_value = []  # No missing deps
        manager = DaemonManager(tmp_path)
        mock_is_running.return_value = True

        result = manager.start()

        assert result is True

    @patch("open_agent_kit.features.codebase_intelligence.deps.check_ci_dependencies")
    @patch("open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager.is_running")
    @patch(
        "open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager._is_port_in_use"
    )
    @patch(
        "open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager._find_pid_by_port"
    )
    def test_start_raises_when_port_in_use_by_unknown(
        self, mock_find_pid, mock_port_in_use, mock_is_running, mock_check_deps, tmp_path: Path
    ):
        """Test that start raises RuntimeError when port is in use by unknown process."""
        mock_check_deps.return_value = []  # No missing deps
        manager = DaemonManager(tmp_path)
        mock_is_running.return_value = False
        # Port is in use
        mock_port_in_use.return_value = True
        # Can't find the PID (unknown process)
        mock_find_pid.return_value = None

        with pytest.raises(RuntimeError, match="in use by an unknown process"):
            manager.start()

    @patch("open_agent_kit.features.codebase_intelligence.deps.check_ci_dependencies")
    @patch("open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager.is_running")
    @patch(
        "open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager._is_port_in_use"
    )
    @patch(
        "open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager._find_pid_by_port"
    )
    @patch("open_agent_kit.features.codebase_intelligence.daemon.manager.terminate_process")
    def test_start_raises_when_cannot_terminate_hanging_process(
        self,
        mock_terminate,
        mock_find_pid,
        mock_port_in_use,
        mock_is_running,
        mock_check_deps,
        tmp_path: Path,
    ):
        """Test that start raises RuntimeError when hanging process cannot be terminated."""
        mock_check_deps.return_value = []  # No missing deps
        manager = DaemonManager(tmp_path)
        mock_is_running.return_value = False
        # Port is in use
        mock_port_in_use.return_value = True
        # Found a hanging process
        mock_find_pid.return_value = 12345
        # But can't terminate it (both graceful and force fail)
        mock_terminate.return_value = False

        with pytest.raises(RuntimeError, match="could not be terminated"):
            manager.start()

    @patch("open_agent_kit.features.codebase_intelligence.deps.check_ci_dependencies")
    @patch("open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager.is_running")
    @patch(
        "open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager._is_port_in_use"
    )
    @patch("subprocess.Popen")
    @patch(
        "open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager._wait_for_startup"
    )
    def test_start_without_wait(
        self,
        mock_wait,
        mock_popen,
        mock_port_in_use,
        mock_is_running,
        mock_check_deps,
        tmp_path: Path,
    ):
        """Test start with wait=False returns immediately."""
        mock_check_deps.return_value = []  # No missing deps
        manager = DaemonManager(tmp_path, ci_data_dir=tmp_path / ".oak" / "ci")
        mock_is_running.return_value = False
        mock_port_in_use.return_value = False

        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        result = manager.start(wait=False)

        assert result is True
        mock_wait.assert_not_called()
        assert manager._read_pid() == 12345

    @patch("open_agent_kit.features.codebase_intelligence.deps.check_ci_dependencies")
    @patch("open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager.is_running")
    @patch(
        "open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager._is_port_in_use"
    )
    @patch("open_agent_kit.features.codebase_intelligence.daemon.manager.subprocess.Popen")
    @patch("open_agent_kit.features.codebase_intelligence.daemon.manager.open")
    def test_start_falls_back_when_log_open_fails(
        self,
        mock_open,
        mock_popen,
        mock_port_in_use,
        mock_is_running,
        mock_check_deps,
        tmp_path: Path,
    ):
        """Test start falls back when daemon log file cannot be opened."""
        mock_check_deps.return_value = []  # No missing deps
        manager = DaemonManager(tmp_path, ci_data_dir=tmp_path / ".oak" / "ci")
        mock_is_running.return_value = False
        mock_port_in_use.return_value = False

        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        def fake_open(path, *args, **kwargs):
            if str(path).endswith(CI_LOG_FILE):
                raise OSError("log open failed")
            return builtins.open(path, *args, **kwargs)

        mock_open.side_effect = fake_open

        result = manager.start(wait=False)

        assert result is True
        assert mock_popen.called is True
        opened_paths = [str(call.args[0]) for call in mock_open.call_args_list]
        assert any(path.endswith(CI_LOG_FILE) for path in opened_paths)
        assert any(path in {CI_NULL_DEVICE_POSIX, CI_NULL_DEVICE_WINDOWS} for path in opened_paths)


class TestDaemonManagerStop:
    """Test daemon stop functionality."""

    @patch("open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager._read_pid")
    @patch(
        "open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager._find_pid_by_port"
    )
    @patch(
        "open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager._find_ci_daemon_pid"
    )
    def test_stop_when_no_process_found(
        self, mock_find_ci, mock_find_port, mock_read_pid, tmp_path: Path
    ):
        """Test stop when no daemon process can be found."""
        manager = DaemonManager(tmp_path, ci_data_dir=tmp_path / ".oak" / "ci")
        mock_read_pid.return_value = None
        mock_find_port.return_value = None
        mock_find_ci.return_value = None

        result = manager.stop()

        assert result is True

    @patch("open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager._read_pid")
    @patch(
        "open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager._is_process_running"
    )
    def test_stop_when_process_not_running(self, mock_is_running, mock_read_pid, tmp_path: Path):
        """Test stop when PID exists but process is not running."""
        manager = DaemonManager(tmp_path, ci_data_dir=tmp_path / ".oak" / "ci")
        mock_read_pid.return_value = 12345
        mock_is_running.return_value = False

        result = manager.stop()

        assert result is True

    @patch("open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager._read_pid")
    @patch(
        "open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager._is_process_running"
    )
    @patch("open_agent_kit.features.codebase_intelligence.daemon.manager.terminate_process")
    def test_stop_sends_sigterm(
        self, mock_terminate, mock_is_running, mock_read_pid, tmp_path: Path
    ):
        """Test that stop sends graceful termination signal to daemon process."""
        manager = DaemonManager(tmp_path, ci_data_dir=tmp_path / ".oak" / "ci")
        mock_read_pid.return_value = 12345
        # First check returns True, then after terminate returns False
        mock_is_running.side_effect = [True, False]
        mock_terminate.return_value = True

        result = manager.stop()

        assert result is True
        mock_terminate.assert_called_once_with(12345, graceful=True)

    @patch("open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager._read_pid")
    @patch(
        "open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager._is_process_running"
    )
    @patch("open_agent_kit.features.codebase_intelligence.daemon.manager.terminate_process")
    @patch("open_agent_kit.features.codebase_intelligence.daemon.manager.time.sleep")
    def test_stop_force_kills_if_sigterm_fails(
        self, mock_sleep, mock_terminate, mock_is_running, mock_read_pid, tmp_path: Path
    ):
        """Test that stop force kills if graceful termination doesn't work."""
        manager = DaemonManager(tmp_path, ci_data_dir=tmp_path / ".oak" / "ci")
        mock_read_pid.return_value = 12345
        # Always return True (process won't die from graceful termination)
        mock_is_running.return_value = True
        mock_terminate.return_value = True

        result = manager.stop()

        assert result is True
        # Should have called with graceful=True first, then graceful=False
        assert mock_terminate.call_count == 2
        mock_terminate.assert_any_call(12345, graceful=True)
        mock_terminate.assert_any_call(12345, graceful=False)

    @patch("open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager._read_pid")
    @patch(
        "open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager._is_process_running"
    )
    @patch("open_agent_kit.features.codebase_intelligence.daemon.manager.terminate_process")
    def test_stop_handles_os_error(
        self, mock_terminate, mock_is_running, mock_read_pid, tmp_path: Path
    ):
        """Test that stop handles termination failure gracefully."""
        manager = DaemonManager(tmp_path, ci_data_dir=tmp_path / ".oak" / "ci")
        mock_read_pid.return_value = 12345
        mock_is_running.return_value = True
        # terminate_process returns False on failure (instead of raising)
        mock_terminate.return_value = False

        result = manager.stop()

        assert result is False


class TestDaemonManagerRestart:
    """Test daemon restart functionality."""

    @patch("open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager.stop")
    @patch("open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager.start")
    def test_restart_calls_stop_then_start(self, mock_start, mock_stop, tmp_path: Path):
        """Test that restart calls stop and then start."""
        manager = DaemonManager(tmp_path)
        mock_stop.return_value = True
        mock_start.return_value = True

        result = manager.restart()

        assert result is True
        mock_stop.assert_called_once()
        mock_start.assert_called_once()


class TestDaemonManagerEnsureRunning:
    """Test ensure_running functionality."""

    @patch("open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager.is_running")
    def test_ensure_running_returns_true_if_already_running(self, mock_is_running, tmp_path: Path):
        """Test ensure_running returns True when already running."""
        manager = DaemonManager(tmp_path)
        mock_is_running.return_value = True

        result = manager.ensure_running()

        assert result is True

    @patch("open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager.is_running")
    @patch("open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager.start")
    def test_ensure_running_starts_daemon_if_not_running(
        self, mock_start, mock_is_running, tmp_path: Path
    ):
        """Test ensure_running starts daemon when not running."""
        manager = DaemonManager(tmp_path)
        mock_is_running.return_value = False
        mock_start.return_value = True

        result = manager.ensure_running()

        assert result is True
        mock_start.assert_called_once()


# =============================================================================
# PID Finding Tests
# =============================================================================


class TestDaemonManagerFindPID:
    """Test PID finding methods."""

    @patch("subprocess.run")
    def test_find_pid_by_port_success(self, mock_run, tmp_path: Path):
        """Test finding PID by port using lsof."""
        manager = DaemonManager(tmp_path, port=37800)

        mock_run.return_value = MagicMock(returncode=0, stdout="12345\n")

        result = manager._find_pid_by_port()

        assert result == 12345

    @patch("subprocess.run")
    def test_find_pid_by_port_no_process(self, mock_run, tmp_path: Path):
        """Test finding PID by port when no process found."""
        manager = DaemonManager(tmp_path, port=37800)

        mock_run.return_value = MagicMock(returncode=1, stdout="")

        result = manager._find_pid_by_port()

        assert result is None

    @patch("subprocess.run")
    def test_find_pid_by_port_command_fails(self, mock_run, tmp_path: Path):
        """Test finding PID by port when lsof command fails."""
        manager = DaemonManager(tmp_path, port=37800)

        mock_run.side_effect = FileNotFoundError("lsof not found")

        result = manager._find_pid_by_port()

        assert result is None

    @patch("subprocess.run")
    def test_find_ci_daemon_pid_success(self, mock_run, tmp_path: Path):
        """Test finding CI daemon PID using pgrep."""
        manager = DaemonManager(tmp_path)

        mock_run.return_value = MagicMock(returncode=0, stdout="54321\n")

        result = manager._find_ci_daemon_pid()

        assert result == 54321

    @patch("subprocess.run")
    def test_find_ci_daemon_pid_no_process(self, mock_run, tmp_path: Path):
        """Test finding CI daemon PID when no process found."""
        manager = DaemonManager(tmp_path)

        mock_run.return_value = MagicMock(returncode=1, stdout="")

        result = manager._find_ci_daemon_pid()

        assert result is None


# =============================================================================
# Tail Logs Tests
# =============================================================================


class TestDaemonManagerTailLogs:
    """Test log tailing functionality."""

    def test_tail_logs_no_file(self, tmp_path: Path):
        """Test tail_logs when log file doesn't exist."""
        manager = DaemonManager(tmp_path, ci_data_dir=tmp_path / ".oak" / "ci")

        result = manager.tail_logs()

        assert result == "No log file found"

    def test_tail_logs_returns_content(self, tmp_path: Path):
        """Test tail_logs returns log content."""
        ci_dir = tmp_path / ".oak" / "ci"
        ci_dir.mkdir(parents=True)
        log_file = ci_dir / "daemon.log"
        log_file.write_text("line1\nline2\nline3\n")

        manager = DaemonManager(tmp_path, ci_data_dir=ci_dir)

        result = manager.tail_logs(lines=2)

        assert "line2" in result
        assert "line3" in result

    def test_tail_logs_respects_line_limit(self, tmp_path: Path):
        """Test tail_logs respects the lines parameter."""
        ci_dir = tmp_path / ".oak" / "ci"
        ci_dir.mkdir(parents=True)
        log_file = ci_dir / "daemon.log"
        # Create log with many lines
        lines = [f"line{i}" for i in range(100)]
        log_file.write_text("\n".join(lines))

        manager = DaemonManager(tmp_path, ci_data_dir=ci_dir)

        result = manager.tail_logs(lines=5)
        result_lines = result.strip().split("\n")

        assert len(result_lines) == 5
        assert "line99" in result


# =============================================================================
# Cleanup Files Tests
# =============================================================================


class TestDaemonManagerCleanup:
    """Test cleanup file functionality."""

    def test_cleanup_files_removes_pid_file(self, tmp_path: Path):
        """Test that _cleanup_files removes the PID file."""
        manager = DaemonManager(tmp_path, ci_data_dir=tmp_path / ".oak" / "ci")
        manager._write_pid(12345)

        assert manager.pid_file.exists()

        manager._cleanup_files()

        assert not manager.pid_file.exists()

    def test_cleanup_files_removes_token_file(self, tmp_path: Path):
        """Test that _cleanup_files removes the token file."""
        manager = DaemonManager(tmp_path, ci_data_dir=tmp_path / ".oak" / "ci")
        manager._ensure_data_dir()
        manager.token_file.write_text("test-token")

        assert manager.token_file.exists()

        manager._cleanup_files()

        assert not manager.token_file.exists()

    def test_cleanup_files_handles_missing_token_file(self, tmp_path: Path):
        """Test that _cleanup_files handles missing token file gracefully."""
        manager = DaemonManager(tmp_path, ci_data_dir=tmp_path / ".oak" / "ci")
        manager._ensure_data_dir()

        # Should not raise even when token file doesn't exist
        manager._cleanup_files()

        assert not manager.token_file.exists()


# =============================================================================
# Token Lifecycle Tests
# =============================================================================


class TestDaemonManagerTokenLifecycle:
    """Test auth token generation, file writing, and permissions."""

    def test_token_file_attribute_set_on_init(self, tmp_path: Path):
        """Test that token_file path is set during initialization."""
        manager = DaemonManager(tmp_path, ci_data_dir=tmp_path / ".oak" / "ci")

        assert manager.token_file == tmp_path / ".oak" / "ci" / CI_TOKEN_FILE

    @patch("open_agent_kit.features.codebase_intelligence.deps.check_ci_dependencies")
    @patch("open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager.is_running")
    @patch(
        "open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager._is_port_in_use"
    )
    @patch("subprocess.Popen")
    @patch(
        "open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager._wait_for_startup"
    )
    def test_start_creates_token_file(
        self,
        mock_wait,
        mock_popen,
        mock_port_in_use,
        mock_is_running,
        mock_check_deps,
        tmp_path: Path,
    ):
        """Test that start() creates a token file."""
        mock_check_deps.return_value = []
        manager = DaemonManager(tmp_path, ci_data_dir=tmp_path / ".oak" / "ci")
        mock_is_running.return_value = False
        mock_port_in_use.return_value = False

        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        manager.start(wait=False)

        assert manager.token_file.exists()

    @patch("open_agent_kit.features.codebase_intelligence.deps.check_ci_dependencies")
    @patch("open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager.is_running")
    @patch(
        "open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager._is_port_in_use"
    )
    @patch("subprocess.Popen")
    @patch(
        "open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager._wait_for_startup"
    )
    def test_start_token_file_has_correct_permissions(
        self,
        mock_wait,
        mock_popen,
        mock_port_in_use,
        mock_is_running,
        mock_check_deps,
        tmp_path: Path,
    ):
        """Test that token file has 0600 permissions (owner-only)."""
        mock_check_deps.return_value = []
        manager = DaemonManager(tmp_path, ci_data_dir=tmp_path / ".oak" / "ci")
        mock_is_running.return_value = False
        mock_port_in_use.return_value = False

        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        manager.start(wait=False)

        file_mode = oct(manager.token_file.stat().st_mode & 0o777)
        assert file_mode == oct(CI_TOKEN_FILE_PERMISSIONS)

    @patch("open_agent_kit.features.codebase_intelligence.deps.check_ci_dependencies")
    @patch("open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager.is_running")
    @patch(
        "open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager._is_port_in_use"
    )
    @patch("subprocess.Popen")
    @patch(
        "open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager._wait_for_startup"
    )
    def test_start_token_is_64_hex_chars(
        self,
        mock_wait,
        mock_popen,
        mock_port_in_use,
        mock_is_running,
        mock_check_deps,
        tmp_path: Path,
    ):
        """Test that generated token is 64 hex characters (secrets.token_hex(32))."""
        mock_check_deps.return_value = []
        manager = DaemonManager(tmp_path, ci_data_dir=tmp_path / ".oak" / "ci")
        mock_is_running.return_value = False
        mock_port_in_use.return_value = False

        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        manager.start(wait=False)

        token = manager.token_file.read_text()
        assert len(token) == 64
        # Should be valid hex
        int(token, 16)

    @patch("open_agent_kit.features.codebase_intelligence.deps.check_ci_dependencies")
    @patch("open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager.is_running")
    @patch(
        "open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager._is_port_in_use"
    )
    @patch("subprocess.Popen")
    @patch(
        "open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager._wait_for_startup"
    )
    def test_start_passes_token_as_env_var(
        self,
        mock_wait,
        mock_popen,
        mock_port_in_use,
        mock_is_running,
        mock_check_deps,
        tmp_path: Path,
    ):
        """Test that start() passes OAK_CI_TOKEN env var to the subprocess."""
        mock_check_deps.return_value = []
        manager = DaemonManager(tmp_path, ci_data_dir=tmp_path / ".oak" / "ci")
        mock_is_running.return_value = False
        mock_port_in_use.return_value = False

        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        manager.start(wait=False)

        # Check the env dict passed to Popen
        popen_call = mock_popen.call_args
        env = popen_call.kwargs.get("env") or popen_call[1].get("env")
        assert env is not None
        assert CI_AUTH_ENV_VAR in env
        # Token in env should match token in file
        token = manager.token_file.read_text()
        assert env[CI_AUTH_ENV_VAR] == token


# =============================================================================
# Wait For Startup Tests
# =============================================================================


class TestDaemonManagerWaitForStartup:
    """Test startup waiting functionality."""

    @patch(
        "open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager._health_check"
    )
    def test_wait_for_startup_success_immediate(self, mock_health_check, tmp_path: Path):
        """Test wait_for_startup returns True when health check succeeds."""
        manager = DaemonManager(tmp_path)
        mock_health_check.return_value = True

        result = manager._wait_for_startup()

        assert result is True

    @patch(
        "open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager._health_check"
    )
    @patch("open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager.stop")
    @patch(
        "open_agent_kit.features.codebase_intelligence.daemon.manager.STARTUP_TIMEOUT",
        0.1,
    )
    @patch(
        "open_agent_kit.features.codebase_intelligence.daemon.manager.HEALTH_CHECK_INTERVAL",
        0.01,
    )
    def test_wait_for_startup_timeout(self, mock_stop, mock_health_check, tmp_path: Path):
        """Test wait_for_startup returns False on timeout."""
        manager = DaemonManager(tmp_path, ci_data_dir=tmp_path / ".oak" / "ci")
        mock_health_check.return_value = False

        result = manager._wait_for_startup()

        assert result is False
        mock_stop.assert_called_once()


# =============================================================================
# Get Status Extended Tests
# =============================================================================


class TestDaemonManagerStatusExtended:
    """Extended tests for status retrieval with health data."""

    @patch("open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager._read_pid")
    @patch("open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager.is_running")
    @patch("httpx.Client")
    def test_get_status_includes_health_data(
        self, mock_client, mock_is_running, mock_read_pid, tmp_path: Path
    ):
        """Test get_status includes health data when available."""
        manager = DaemonManager(tmp_path, port=37800)
        mock_read_pid.return_value = 1234
        mock_is_running.return_value = True

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "uptime_seconds": 120,
            "project_root": "/some/path",
        }
        mock_instance = MagicMock()
        mock_instance.get.return_value = mock_response
        mock_client.return_value.__enter__.return_value = mock_instance

        status = manager.get_status()

        assert status["uptime_seconds"] == 120
        assert status["project_root"] == "/some/path"

    @patch("open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager._read_pid")
    @patch("open_agent_kit.features.codebase_intelligence.daemon.manager.DaemonManager.is_running")
    @patch("httpx.Client")
    def test_get_status_handles_health_exception(
        self, mock_client, mock_is_running, mock_read_pid, tmp_path: Path
    ):
        """Test get_status handles health endpoint exceptions gracefully."""
        manager = DaemonManager(tmp_path, port=37800)
        mock_read_pid.return_value = 1234
        mock_is_running.return_value = True

        mock_client.side_effect = OSError("Connection error")

        status = manager.get_status()

        # Should still return basic status without health data
        assert status["running"] is True
        assert status["port"] == 37800
        assert "uptime_seconds" not in status
