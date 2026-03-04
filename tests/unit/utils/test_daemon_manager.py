"""Tests for BaseDaemonManager."""

from pathlib import Path
from unittest.mock import patch

import pytest

from open_agent_kit.utils.daemon_manager import BaseDaemonManager, DaemonConfig


class ConcreteDaemon(BaseDaemonManager):
    """Minimal concrete subclass for testing."""

    def start(self, wait: bool = True) -> bool:
        return True


@pytest.fixture
def config(tmp_path: Path) -> DaemonConfig:
    return DaemonConfig(
        config_dir=tmp_path / "daemon",
        port=39999,
        pid_filename="test.pid",
        log_filename="test.log",
        health_endpoint="/api/health",
        startup_timeout=2.0,
        health_check_interval=0.1,
    )


@pytest.fixture
def manager(config: DaemonConfig) -> ConcreteDaemon:
    return ConcreteDaemon(config)


class TestPidFileOperations:
    """Tests for PID file read/write/remove."""

    def test_read_pid_returns_none_when_no_file(self, manager: ConcreteDaemon) -> None:
        assert manager._read_pid() is None

    def test_write_pid_creates_file_and_read_returns_it(self, manager: ConcreteDaemon) -> None:
        manager._write_pid(12345)
        assert manager._read_pid() == 12345

    def test_remove_pid_deletes_file(self, manager: ConcreteDaemon) -> None:
        manager._write_pid(12345)
        assert manager.pid_file.exists()
        manager._remove_pid()
        assert not manager.pid_file.exists()

    def test_remove_pid_noop_when_no_file(self, manager: ConcreteDaemon) -> None:
        # Should not raise
        manager._remove_pid()

    def test_read_pid_returns_none_on_invalid_content(self, manager: ConcreteDaemon) -> None:
        manager._ensure_config_dir()
        manager.pid_file.write_text("not-a-number")
        assert manager._read_pid() is None


class TestConfigDir:
    """Tests for _ensure_config_dir."""

    def test_ensure_config_dir_creates_directory(self, manager: ConcreteDaemon) -> None:
        assert not manager.config_dir.exists()
        manager._ensure_config_dir()
        assert manager.config_dir.is_dir()

    def test_ensure_config_dir_idempotent(self, manager: ConcreteDaemon) -> None:
        manager._ensure_config_dir()
        manager._ensure_config_dir()
        assert manager.config_dir.is_dir()


class TestPortAvailability:
    """Tests for _is_port_available static method."""

    def test_is_port_available_returns_bool(self) -> None:
        # Port 1 is typically not available to connect to (TCPMUX),
        # so connect_ex should fail and _is_port_available returns True
        result = BaseDaemonManager._is_port_available(1)
        assert isinstance(result, bool)


class TestTailLogs:
    """Tests for tail_logs."""

    def test_tail_logs_no_file(self, manager: ConcreteDaemon) -> None:
        assert manager.tail_logs() == "No log file found"

    def test_tail_logs_returns_last_lines(self, manager: ConcreteDaemon) -> None:
        manager._ensure_config_dir()
        lines = [f"line {i}" for i in range(100)]
        manager.log_file.write_text("\n".join(lines))
        result = manager.tail_logs(lines=5)
        result_lines = result.split("\n")
        assert len(result_lines) == 5
        assert result_lines[-1] == "line 99"

    def test_tail_logs_fewer_lines_than_requested(self, manager: ConcreteDaemon) -> None:
        manager._ensure_config_dir()
        manager.log_file.write_text("only one line")
        result = manager.tail_logs(lines=50)
        assert result == "only one line"


class TestGetStatus:
    """Tests for get_status."""

    def test_get_status_returns_expected_keys(self, manager: ConcreteDaemon) -> None:
        with patch.object(manager, "is_running", return_value=False):
            status = manager.get_status()
        assert "running" in status
        assert "port" in status
        assert "pid" in status
        assert status["running"] is False
        assert status["port"] == 39999
        assert status["pid"] is None

    def test_get_status_includes_pid_when_running(self, manager: ConcreteDaemon) -> None:
        manager._write_pid(42)
        with patch.object(manager, "is_running", return_value=True):
            status = manager.get_status()
        assert status["running"] is True
        assert status["pid"] == 42


class TestEnsureRunning:
    """Tests for ensure_running."""

    def test_ensure_running_delegates_to_start_when_not_running(
        self, manager: ConcreteDaemon
    ) -> None:
        with (
            patch.object(manager, "is_running", return_value=False),
            patch.object(manager, "start", return_value=True) as mock_start,
        ):
            result = manager.ensure_running()
        assert result is True
        mock_start.assert_called_once()

    def test_ensure_running_skips_start_when_already_running(self, manager: ConcreteDaemon) -> None:
        with (
            patch.object(manager, "is_running", return_value=True),
            patch.object(manager, "start", return_value=True) as mock_start,
        ):
            result = manager.ensure_running()
        assert result is True
        mock_start.assert_not_called()


class TestCleanupFiles:
    """Tests for _cleanup_files."""

    def test_cleanup_files_removes_pid_file(self, manager: ConcreteDaemon) -> None:
        manager._write_pid(999)
        assert manager.pid_file.exists()
        manager._cleanup_files()
        assert not manager.pid_file.exists()

    def test_cleanup_files_noop_when_no_pid_file(self, manager: ConcreteDaemon) -> None:
        # Should not raise
        manager._cleanup_files()


class TestConstructor:
    """Tests for __init__ attribute wiring."""

    def test_attributes_from_config(self, config: DaemonConfig) -> None:
        mgr = ConcreteDaemon(config)
        assert mgr.port == config.port
        assert mgr.config_dir == config.config_dir
        assert mgr.pid_file == config.config_dir / config.pid_filename
        assert mgr.log_file == config.config_dir / config.log_filename
        assert mgr.base_url == f"http://localhost:{config.port}"
        assert mgr._lock_handle is None
