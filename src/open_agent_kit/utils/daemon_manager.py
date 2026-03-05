"""Base daemon lifecycle management.

Provides ``BaseDaemonManager``, an abstract base class that encapsulates
common daemon lifecycle operations (PID management, health checks, start/stop,
log tailing).  Concrete subclasses supply a ``DaemonConfig`` and implement
``start()``.
"""

import abc
import logging
import socket
import time
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any

from open_agent_kit.utils.platform import (
    find_pid_by_port,
    terminate_process,
)
from open_agent_kit.utils.platform import (
    is_process_running as platform_is_process_running,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DaemonConfig:
    """Configuration for a daemon managed by BaseDaemonManager."""

    config_dir: Path
    port: int
    pid_filename: str
    log_filename: str
    health_endpoint: str
    startup_timeout: float
    health_check_interval: float


class BaseDaemonManager(abc.ABC):
    """Abstract base for daemon lifecycle managers.

    Subclasses must implement ``start()``.  All other lifecycle methods
    (stop, restart, health check, PID management, log tailing) are
    provided by this base class and can be overridden where needed.
    """

    def __init__(self, config: DaemonConfig) -> None:
        self._config = config
        self.port = config.port
        self.config_dir = config.config_dir
        self.pid_file = config.config_dir / config.pid_filename
        self.log_file = config.config_dir / config.log_filename
        self.base_url = f"http://localhost:{config.port}"
        self._lock_handle: IO[Any] | None = None

    # -- PID file operations ------------------------------------------------

    def _read_pid(self) -> int | None:
        if not self.pid_file.exists():
            return None
        try:
            return int(self.pid_file.read_text().strip())
        except (ValueError, OSError):
            return None

    def _write_pid(self, pid: int) -> None:
        self._ensure_config_dir()
        self.pid_file.write_text(str(pid))

    def _remove_pid(self) -> None:
        if self.pid_file.exists():
            self.pid_file.unlink()

    # -- Directory setup ----------------------------------------------------

    def _ensure_config_dir(self) -> None:
        self.config_dir.mkdir(parents=True, exist_ok=True)

    # -- Health & port checks -----------------------------------------------

    @staticmethod
    def _is_port_available(port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(("localhost", port)) != 0

    def _find_available_port(self, start_port: int, range_size: int) -> int:
        """Probe ports starting from *start_port* up to *range_size* offsets.

        Args:
            start_port: First port to try.
            range_size: Number of consecutive ports to probe.

        Returns:
            First available port in the range.

        Raises:
            RuntimeError: If no port is available in the range.
        """
        for offset in range(range_size):
            candidate = start_port + offset
            if self._is_port_available(candidate):
                return candidate
        msg = f"No available port found in range {start_port}-{start_port + range_size - 1}"
        raise RuntimeError(msg)

    def _health_check(self, timeout: float = 2.0) -> bool:
        try:
            import httpx

            with httpx.Client(timeout=timeout) as client:
                response = client.get(f"{self.base_url}{self._config.health_endpoint}")
                return response.status_code == 200
        except ImportError:
            return not self._is_port_available(self.port)
        except Exception as exc:
            logger.debug("Health check failed: %s", exc)
            return False

    # -- Lifecycle ----------------------------------------------------------

    def is_running(self) -> bool:
        pid = self._read_pid()
        if pid and not platform_is_process_running(pid):
            self._remove_pid()
            return False
        return self._health_check()

    @abc.abstractmethod
    def start(self, wait: bool = True) -> bool: ...

    def _wait_for_startup(self) -> bool:
        start_time = time.time()
        while time.time() - start_time < self._config.startup_timeout:
            if self._health_check():
                logger.info("Daemon is ready")
                return True
            time.sleep(self._config.health_check_interval)
        logger.error(
            "Daemon failed to start within %ss. Check logs: %s",
            self._config.startup_timeout,
            self.log_file,
        )
        self.stop()
        return False

    def stop(self) -> bool:
        pid = self._read_pid()
        if not pid:
            pid = find_pid_by_port(self.port)
            if pid:
                logger.info("Found daemon PID %d by port %d", pid, self.port)
        if not pid:
            logger.info("No daemon process found")
            self._cleanup_files()
            return True
        if not platform_is_process_running(pid):
            logger.info("Daemon process is not running")
            self._cleanup_files()
            return True
        if not terminate_process(pid, graceful=True):
            logger.error("Failed to send termination signal to PID %d", pid)
            return False
        logger.info("Sent termination signal to daemon PID %d", pid)
        for _ in range(10):
            if not platform_is_process_running(pid):
                break
            time.sleep(0.5)
        else:
            if not terminate_process(pid, graceful=False):
                logger.error("Failed to force kill daemon PID %d", pid)
                return False
            logger.warning("Force killed daemon PID %d", pid)
        self._cleanup_files()
        logger.info("Daemon stopped")
        return True

    def _cleanup_files(self) -> None:
        self._remove_pid()

    def restart(self) -> bool:
        self.stop()
        time.sleep(0.5)
        return self.start()

    def ensure_running(self) -> bool:
        if self.is_running():
            return True
        return self.start()

    def tail_logs(self, lines: int = 50) -> str:
        if not self.log_file.exists():
            return "No log file found"
        try:
            content = self.log_file.read_text()
            log_lines = content.strip().split("\n")
            return "\n".join(log_lines[-lines:])
        except (OSError, UnicodeDecodeError) as exc:
            return f"Error reading log file: {exc}"

    def get_status(self) -> dict[str, Any]:
        pid = self._read_pid()
        running = self.is_running()
        return {
            "running": running,
            "port": self.port,
            "pid": pid if running else None,
        }
