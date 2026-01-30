"""Daemon lifecycle management."""

import hashlib
import logging
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import IO, Any

from open_agent_kit.config.paths import OAK_DIR
from open_agent_kit.features.codebase_intelligence.constants import (
    CI_DATA_DIR,
    CI_LOG_FILE,
    CI_PID_FILE,
    CI_PORT_FILE,
    CI_SHARED_PORT_DIR,
    CI_SHARED_PORT_FILE,
)
from open_agent_kit.utils.platform import (
    acquire_file_lock,
    find_pid_by_port,
    get_process_detach_kwargs,
    release_file_lock,
    terminate_process,
)
from open_agent_kit.utils.platform import (
    is_process_running as platform_is_process_running,
)

logger = logging.getLogger(__name__)


class MissingDependenciesError(RuntimeError):
    """Raised when CI daemon dependencies are not installed."""

    pass


# Port range for CI daemons: 37800-38799 (1000 ports)
DEFAULT_PORT = 37800
PORT_RANGE_START = 37800
PORT_RANGE_SIZE = 1000
LOCK_FILE = "daemon.lock"
STARTUP_TIMEOUT = 30.0  # Allow time for first-time package initialization
HEALTH_CHECK_INTERVAL = 1.0
MAX_LOCK_RETRIES = 5
LOCK_RETRY_DELAY = 0.1  # Start with 100ms, will exponentially backoff

# Port conflict resolution
MAX_PORT_RETRIES = 10  # Try up to 10 sequential ports if original is taken


def _is_port_available(port: int) -> bool:
    """Check if a port is available for binding.

    Args:
        port: Port number to check.

    Returns:
        True if the port is available, False if in use.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) != 0


def find_available_port(start_port: int, max_retries: int = MAX_PORT_RETRIES) -> int | None:
    """Find an available port starting from start_port.

    Tries sequential ports starting from start_port up to max_retries.
    Respects the port range bounds.

    Args:
        start_port: Port to start searching from.
        max_retries: Maximum number of ports to try.

    Returns:
        An available port number, or None if no port found within range.
    """
    for offset in range(max_retries):
        candidate = start_port + offset
        if candidate >= PORT_RANGE_START + PORT_RANGE_SIZE:
            logger.warning(f"Port search exceeded range at {candidate}")
            break
        if _is_port_available(candidate):
            return candidate
        logger.debug(f"Port {candidate} is in use, trying next")
    return None


def derive_port_from_path(project_root: Path) -> int:
    """Derive a deterministic port from project path.

    Uses a hash of the absolute project path to assign a unique port
    in the range PORT_RANGE_START to PORT_RANGE_START + PORT_RANGE_SIZE.

    Args:
        project_root: Project root directory.

    Returns:
        Port number in the valid range.
    """
    path_str = str(project_root.resolve())
    hash_value = int(hashlib.md5(path_str.encode()).hexdigest()[:8], 16)
    return PORT_RANGE_START + (hash_value % PORT_RANGE_SIZE)


# Timeout for git remote command (seconds)
GIT_REMOTE_TIMEOUT = 5


def derive_port_from_git_remote(project_root: Path) -> int | None:
    """Derive a deterministic port from git remote URL.

    Uses the git remote origin URL to derive a consistent port across
    all team members' machines. The URL is normalized (stripped of .git
    suffix and trailing slashes) before hashing.

    Args:
        project_root: Project root directory.

    Returns:
        Port number in the valid range, or None if not a git repo or no remote.
    """
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=GIT_REMOTE_TIMEOUT,
            check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None

        # Normalize URL: strip .git suffix and trailing slashes
        remote_url = result.stdout.strip()
        remote_url = remote_url.rstrip("/")
        if remote_url.endswith(".git"):
            remote_url = remote_url[:-4]

        # Hash and map to port range
        hash_value = int(hashlib.md5(remote_url.encode()).hexdigest()[:8], 16)
        return PORT_RANGE_START + (hash_value % PORT_RANGE_SIZE)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        logger.debug(f"Failed to get git remote: {e}")
        return None


def get_project_port(project_root: Path, ci_data_dir: Path | None = None) -> int:
    """Get the port for a project, creating one if needed.

    Port resolution priority:
    1. .oak/ci/daemon.port (local override for conflicts, not git-tracked)
    2. oak/ci/daemon.port (team-shared, git-tracked)
    3. Auto-derive from git remote URL -> write to oak/ci/daemon.port
    4. Fall back to path-based derivation (non-git projects)

    Args:
        project_root: Project root directory.
        ci_data_dir: CI data directory (default: .oak/ci).

    Returns:
        Port number for this project.
    """
    data_dir = ci_data_dir or (project_root / OAK_DIR / CI_DATA_DIR)
    local_port_file = data_dir / CI_PORT_FILE
    shared_port_dir = project_root / CI_SHARED_PORT_DIR
    shared_port_file = shared_port_dir / CI_SHARED_PORT_FILE

    # Priority 1: Local override (.oak/ci/daemon.port)
    if local_port_file.exists():
        try:
            stored_port = int(local_port_file.read_text().strip())
            if PORT_RANGE_START <= stored_port < PORT_RANGE_START + PORT_RANGE_SIZE:
                return stored_port
        except (ValueError, OSError):
            pass

    # Priority 2: Team-shared port (oak/ci/daemon.port)
    if shared_port_file.exists():
        try:
            stored_port = int(shared_port_file.read_text().strip())
            if PORT_RANGE_START <= stored_port < PORT_RANGE_START + PORT_RANGE_SIZE:
                return stored_port
        except (ValueError, OSError):
            pass

    # Priority 3: Derive from git remote and write to team-shared file
    port = derive_port_from_git_remote(project_root)
    if port is not None:
        # Store in team-shared location for consistency across machines
        shared_port_dir.mkdir(parents=True, exist_ok=True)
        shared_port_file.write_text(str(port))
        return port

    # Priority 4: Fall back to path-based derivation (non-git projects)
    port = derive_port_from_path(project_root)
    # For non-git projects, store in local directory
    data_dir.mkdir(parents=True, exist_ok=True)
    local_port_file.write_text(str(port))

    return port


class DaemonManager:
    """Manage the Codebase Intelligence daemon lifecycle.

    Handles starting, stopping, and monitoring the daemon process.
    Uses a PID file for process tracking and automatic restart on failure.
    """

    def __init__(
        self,
        project_root: Path,
        port: int = DEFAULT_PORT,
        ci_data_dir: Path | None = None,
    ):
        """Initialize daemon manager.

        Args:
            project_root: Root directory of the OAK project.
            port: Port to run the daemon on.
            ci_data_dir: Directory for CI data (default: .oak/ci).
        """
        self.project_root = project_root
        self.port = port
        self.ci_data_dir = ci_data_dir or (project_root / OAK_DIR / CI_DATA_DIR)
        self.pid_file = self.ci_data_dir / CI_PID_FILE
        self.log_file = self.ci_data_dir / CI_LOG_FILE
        self.lock_file = self.ci_data_dir / LOCK_FILE
        self.base_url = f"http://localhost:{port}"
        self._lock_handle: IO[Any] | None = None

    def _ensure_data_dir(self) -> None:
        """Ensure the CI data directory exists."""
        self.ci_data_dir.mkdir(parents=True, exist_ok=True)

    def _read_pid(self) -> int | None:
        """Read PID from file."""
        if not self.pid_file.exists():
            return None
        try:
            return int(self.pid_file.read_text().strip())
        except (ValueError, OSError):
            return None

    def _write_pid(self, pid: int) -> None:
        """Write PID to file."""
        self._ensure_data_dir()
        self.pid_file.write_text(str(pid))

    def _write_port(self, port: int) -> None:
        """Write port to local file for conflict resolution.

        This is called when the daemon port changes due to conflict resolution.
        Writes to .oak/ci/daemon.port (local override) rather than the team-shared
        oak/ci/daemon.port, so conflict resolution is machine-specific and doesn't
        affect other team members.
        """
        self._ensure_data_dir()
        port_file = self.ci_data_dir / CI_PORT_FILE
        port_file.write_text(str(port))

    def _remove_pid(self) -> None:
        """Remove PID file."""
        if self.pid_file.exists():
            self.pid_file.unlink()

    def _acquire_lock(self) -> bool:
        """Acquire exclusive lock on daemon startup.

        Uses exponential backoff for retry logic. This ensures atomic
        test-and-set semantics: only one process can proceed past the lock.
        Works on both POSIX and Windows systems.

        Returns:
            True if lock acquired successfully.

        Raises:
            RuntimeError: If lock cannot be acquired after all retries.
        """
        self._ensure_data_dir()

        # Create lock file if it doesn't exist
        lock_file_handle = open(self.lock_file, "a+")
        retry_delay = LOCK_RETRY_DELAY

        for attempt in range(MAX_LOCK_RETRIES):
            if acquire_file_lock(lock_file_handle, blocking=False):
                self._lock_handle = lock_file_handle
                logger.debug(f"Acquired startup lock on attempt {attempt + 1}")
                return True
            else:
                if attempt < MAX_LOCK_RETRIES - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    lock_file_handle.close()
                    raise RuntimeError(
                        f"Failed to acquire startup lock after {MAX_LOCK_RETRIES} attempts"
                    )

        lock_file_handle.close()
        return False

    def _release_lock(self) -> None:
        """Release the startup lock.

        Should only be called after daemon process is started or on failure.
        Works on both POSIX and Windows systems.
        """
        if self._lock_handle is not None:
            try:
                release_file_lock(self._lock_handle)
                self._lock_handle.close()
                self._lock_handle = None
                logger.debug("Released startup lock")
            except OSError as e:
                logger.warning(f"Failed to release startup lock: {e}")
                self._lock_handle = None

    def _is_process_running(self, pid: int) -> bool:
        """Check if a process with the given PID is running.

        Works on both POSIX and Windows systems.
        """
        return platform_is_process_running(pid)

    def _is_port_in_use(self) -> bool:
        """Check if the daemon port is in use."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(("localhost", self.port)) == 0

    def _health_check(self, timeout: float = 2.0) -> bool:
        """Check if daemon is responding to health checks."""
        try:
            import httpx

            with httpx.Client(timeout=timeout) as client:
                response = client.get(f"{self.base_url}/api/health")
                return response.status_code == 200
        except ImportError:
            # httpx not installed yet - check if port is in use as fallback
            return self._is_port_in_use()
        except Exception as e:
            # Catch all exceptions from httpx calls (ConnectError, HTTPError, etc.)
            # to ensure health check returns gracefully without raising
            logger.debug(f"Health check failed: {e}")
            return False

    def is_running(self) -> bool:
        """Check if the daemon is running and healthy.

        Returns:
            True if daemon is running and responding to health checks.
        """
        # Check PID file first
        pid = self._read_pid()
        if pid and not self._is_process_running(pid):
            # Stale PID file
            self._remove_pid()
            return False

        # Check health endpoint
        return self._health_check()

    def get_status(self) -> dict:
        """Get daemon status.

        Returns:
            Dictionary with status information.
        """
        pid = self._read_pid()
        running = self.is_running()

        status = {
            "running": running,
            "port": self.port,
            "pid": pid if running else None,
            "pid_file": str(self.pid_file),
            "log_file": str(self.log_file),
        }

        if running:
            try:
                import httpx

                with httpx.Client(timeout=2.0) as client:
                    response = client.get(f"{self.base_url}/api/health")
                    if response.status_code == 200:
                        health = response.json()
                        status["uptime_seconds"] = health.get("uptime_seconds", 0)
                        status["project_root"] = health.get("project_root")
            except Exception as e:
                # Catch all exceptions from httpx calls (ConnectError, HTTPError, etc.)
                # to ensure get_status always returns gracefully
                logger.debug(f"Failed to get health info: {e}")

        return status

    def start(self, wait: bool = True) -> bool:
        """Start the daemon.

        Args:
            wait: Wait for daemon to be ready before returning.

        Returns:
            True if daemon started successfully.

        Raises:
            RuntimeError: If daemon is already running or fails to start.
            MissingDependenciesError: If CI dependencies are not installed.
        """
        # Check dependencies before attempting to start
        from open_agent_kit.features.codebase_intelligence.deps import (
            check_ci_dependencies,
        )

        missing = check_ci_dependencies()
        if missing:
            raise MissingDependenciesError(
                f"CI daemon requires: {', '.join(missing)}\n\n"
                "Run 'oak init' to auto-install dependencies."
            )

        # Acquire lock before checking if daemon is running. This prevents
        # a race condition where two processes could both decide to start
        # a daemon between the check and the actual startup.
        self._acquire_lock()

        try:
            # Check again after acquiring lock
            if self.is_running():
                logger.info("Daemon is already running")
                return True

            # Clean up stale PID file
            if self.pid_file.exists():
                self._remove_pid()

            # Check if port is already in use by something else
            if self._is_port_in_use():
                logger.info(f"Port {self.port} is in use, searching for available port...")
                new_port = find_available_port(self.port + 1)
                if new_port is None:
                    raise RuntimeError(
                        f"Port {self.port} is in use and no available ports found "
                        f"in range {self.port + 1}-{PORT_RANGE_START + PORT_RANGE_SIZE - 1}"
                    )
                logger.info(f"Found available port: {new_port}")
                self.port = new_port
                self.base_url = f"http://localhost:{self.port}"
                # Update port file so hooks use the correct port
                self._write_port(self.port)

            self._ensure_data_dir()

            # Build the command to start the daemon
            # We use uvicorn directly with the app factory
            cmd = [
                sys.executable,
                "-m",
                "uvicorn",
                "open_agent_kit.features.codebase_intelligence.daemon.server:create_app",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                str(self.port),
                "--log-level",
                "warning",  # Suppress uvicorn's info logs - we handle our own logging
                "--no-access-log",  # Disable uvicorn access log - prevents duplicate request logs
            ]

            # Set environment variables for the daemon
            env = os.environ.copy()
            env["OAK_CI_PROJECT_ROOT"] = str(self.project_root)

            # Start the process (platform-aware detachment)
            # Redirect stdout/stderr to null device instead of log file.
            # All logging is now handled by RotatingFileHandler in server.py,
            # which also captures uvicorn errors through the uvicorn.error logger.
            null_device = "NUL" if os.name == "nt" else "/dev/null"
            with open(null_device, "w") as null_out:
                process = subprocess.Popen(
                    cmd,
                    stdout=null_out,
                    stderr=subprocess.STDOUT,
                    env=env,
                    cwd=str(self.project_root),
                    **get_process_detach_kwargs(),  # Platform-aware detachment
                )

            self._write_pid(process.pid)
            logger.info(f"Started daemon with PID {process.pid}")

            if wait:
                return self._wait_for_startup()

            return True
        finally:
            # Always release lock after startup attempt (success or failure)
            self._release_lock()

    def _wait_for_startup(self) -> bool:
        """Wait for daemon to become ready."""
        start_time = time.time()

        while time.time() - start_time < STARTUP_TIMEOUT:
            if self._health_check():
                logger.info("Daemon is ready")
                return True
            time.sleep(HEALTH_CHECK_INTERVAL)

        # Include helpful debug info in log
        logger.error(
            f"Daemon failed to start within {STARTUP_TIMEOUT}s timeout. "
            f"Check logs at: {self.log_file}"
        )

        # Try to get last few lines of log for debugging
        if self.log_file.exists():
            try:
                lines = self.log_file.read_text().strip().split("\n")[-10:]
                for line in lines:
                    logger.error(f"  {line}")
            except (OSError, UnicodeDecodeError) as e:
                logger.debug(f"Failed to read log file: {e}")

        self.stop()  # Clean up
        return False

    def stop(self) -> bool:
        """Stop the daemon.

        Tries project-specific approaches only:
        1. Use PID file if available
        2. Find process by port if no PID file

        Note: We intentionally do NOT use global process search (pgrep) as that
        could kill daemons from other projects. If both PID file and port lookup
        fail, we assume no daemon is running for this project.

        Returns:
            True if daemon was stopped successfully.
        """
        pid = self._read_pid()

        # If no PID file, try to find by port (project-specific)
        if not pid:
            pid = self._find_pid_by_port()
            if pid:
                logger.info(f"Found daemon PID {pid} by port {self.port}")

        if not pid:
            logger.info("No daemon process found")
            self._cleanup_files()
            return True

        if not self._is_process_running(pid):
            logger.info("Daemon process is not running")
            self._cleanup_files()
            return True

        # Try graceful shutdown first (platform-aware)
        if not terminate_process(pid, graceful=True):
            logger.error(f"Failed to send termination signal to daemon PID {pid}")
            return False

        logger.info(f"Sent termination signal to daemon PID {pid}")

        # Wait for process to exit
        for _ in range(10):
            if not self._is_process_running(pid):
                break
            time.sleep(0.5)
        else:
            # Force kill if still running
            if not terminate_process(pid, graceful=False):
                logger.error(f"Failed to force kill daemon PID {pid}")
                return False
            logger.warning(f"Force killed daemon PID {pid}")

        self._cleanup_files()
        logger.info("Daemon stopped")
        return True

    def _find_pid_by_port(self) -> int | None:
        """Find daemon PID by checking what's listening on our port.

        Uses platform-specific tools (lsof on POSIX, netstat on Windows)
        to find the process listening on the daemon's port.
        This is project-specific since each project gets a unique port.

        Returns:
            PID of the process on the port, or None if not found.
        """
        pid = find_pid_by_port(self.port)
        if pid is None:
            logger.debug(f"No process found on port {self.port}")
        return pid

    def _find_ci_daemon_pid(self) -> int | None:
        """Find any running CI daemon process globally.

        WARNING: This method performs a GLOBAL process search using pgrep.
        It will find ANY codebase_intelligence daemon running on the system,
        not just the one for this project. This should NOT be used for normal
        stop operations - use _find_pid_by_port() instead for project-specific
        daemon lookup.

        This method is kept for diagnostic purposes and explicit orphan cleanup.

        Returns:
            PID of the first matching CI daemon process, or None if not found.
        """
        try:
            # Search for uvicorn codebase_intelligence process (GLOBAL search!)
            result = subprocess.run(
                ["pgrep", "-f", "uvicorn.*codebase_intelligence"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                # Return first match
                return int(result.stdout.strip().split()[0])
        except (ValueError, OSError, FileNotFoundError):
            pass
        return None

    def _cleanup_files(self) -> None:
        """Clean up PID file on daemon stop.

        Note: Port file is intentionally preserved. The port is deterministic
        (derived from project path) and keeping the file provides visibility
        for debugging and avoids unnecessary recalculation.
        """
        self._remove_pid()

    def restart(self) -> bool:
        """Restart the daemon.

        Returns:
            True if daemon restarted successfully.
        """
        self.stop()
        time.sleep(0.5)  # Brief pause
        return self.start()

    def ensure_running(self) -> bool:
        """Ensure daemon is running, starting it if necessary.

        Returns:
            True if daemon is running (either was already or started).
        """
        if self.is_running():
            return True
        return self.start()

    def tail_logs(self, lines: int = 50) -> str:
        """Get recent log output.

        Args:
            lines: Number of lines to return.

        Returns:
            Recent log content.
        """
        if not self.log_file.exists():
            return "No log file found"

        try:
            content = self.log_file.read_text()
            log_lines = content.strip().split("\n")
            return "\n".join(log_lines[-lines:])
        except OSError:
            return "Failed to read log file"
