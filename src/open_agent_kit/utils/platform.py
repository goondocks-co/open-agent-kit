"""Cross-platform abstractions for Windows and POSIX systems.

This module provides platform-agnostic functions for:
- File locking (fcntl on POSIX, msvcrt on Windows)
- Process detachment for daemon processes
- Process termination signals
- Process discovery by port
- UV tools path detection

All functions are designed to work correctly on both Windows and POSIX systems.
"""

import logging
import os
import subprocess
import sys
from typing import IO, Any, Final

logger = logging.getLogger(__name__)

# Platform detection
IS_WINDOWS: Final[bool] = sys.platform == "win32"
IS_POSIX: Final[bool] = os.name == "posix"


# =============================================================================
# File Locking
# =============================================================================


def acquire_file_lock(file_handle: IO[Any], blocking: bool = False) -> bool:
    """Acquire an exclusive lock on a file.

    Uses fcntl.flock() on POSIX systems and msvcrt.locking() on Windows.

    Args:
        file_handle: Open file handle to lock.
        blocking: If True, block until lock is acquired. If False, fail immediately
                  if lock is not available.

    Returns:
        True if lock was acquired, False if non-blocking and lock unavailable.

    Raises:
        OSError: If blocking=True and lock cannot be acquired, or other I/O errors.
    """
    if IS_WINDOWS:
        import msvcrt

        try:
            # Lock the first byte of the file
            # LK_NBLCK = non-blocking exclusive lock
            # LK_LOCK = blocking exclusive lock
            lock_mode = msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK  # type: ignore[attr-defined]
            file_handle.seek(0)
            msvcrt.locking(file_handle.fileno(), lock_mode, 1)  # type: ignore[attr-defined]
            return True
        except OSError:
            if not blocking:
                return False
            raise
    else:
        import fcntl

        try:
            flags = fcntl.LOCK_EX
            if not blocking:
                flags |= fcntl.LOCK_NB
            fcntl.flock(file_handle, flags)
            return True
        except OSError:
            if not blocking:
                return False
            raise


def release_file_lock(file_handle: IO[Any]) -> None:
    """Release a file lock.

    Args:
        file_handle: File handle that was previously locked.

    Note:
        This is a no-op if the file was not locked. Always safe to call.
    """
    if IS_WINDOWS:
        import msvcrt

        try:
            file_handle.seek(0)
            msvcrt.locking(file_handle.fileno(), msvcrt.LK_UNLCK, 1)  # type: ignore[attr-defined]
        except OSError as e:
            logger.debug(f"Failed to release Windows file lock: {e}")
    else:
        import fcntl

        try:
            fcntl.flock(file_handle, fcntl.LOCK_UN)
        except OSError as e:
            logger.debug(f"Failed to release POSIX file lock: {e}")


# =============================================================================
# Process Management
# =============================================================================


def get_process_detach_kwargs() -> dict[str, Any]:
    """Get subprocess.Popen kwargs for detaching a process from the parent.

    Returns kwargs to pass to subprocess.Popen that will:
    - On POSIX: Create a new session (setsid)
    - On Windows: Create a new process group with DETACHED_PROCESS flags

    Returns:
        Dictionary of kwargs to pass to subprocess.Popen.
    """
    if IS_WINDOWS:
        # Windows process creation flags
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        DETACHED_PROCESS = 0x00000008
        return {
            "creationflags": CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS,
        }
    else:
        return {
            "start_new_session": True,
        }


def is_process_running(pid: int) -> bool:
    """Check if a process with the given PID is running.

    Args:
        pid: Process ID to check.

    Returns:
        True if the process is running, False otherwise.
    """
    if IS_WINDOWS:
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            kernel32.CloseHandle(handle)
            return True
        return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def terminate_process(pid: int, graceful: bool = True) -> bool:
    """Terminate a process by PID.

    Args:
        pid: Process ID to terminate.
        graceful: If True, try SIGTERM first (POSIX) or TerminateProcess (Windows).
                  If False, use SIGKILL (POSIX) or TerminateProcess (Windows).

    Returns:
        True if process was terminated or was not running, False on error.
    """
    if not is_process_running(pid):
        return True

    if IS_WINDOWS:
        import ctypes

        PROCESS_TERMINATE = 0x0001
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
        if handle:
            result = kernel32.TerminateProcess(handle, 1)
            kernel32.CloseHandle(handle)
            return bool(result)
        return False
    else:
        import signal

        try:
            sig = signal.SIGTERM if graceful else signal.SIGKILL
            os.kill(pid, sig)
            return True
        except OSError as e:
            logger.error(f"Failed to terminate process {pid}: {e}")
            return False


def force_terminate_process(pid: int) -> bool:
    """Force terminate a process (SIGKILL on POSIX, TerminateProcess on Windows).

    Args:
        pid: Process ID to terminate.

    Returns:
        True if process was terminated or was not running, False on error.
    """
    return terminate_process(pid, graceful=False)


# =============================================================================
# Port Discovery
# =============================================================================


def find_pid_by_port(port: int) -> int | None:
    """Find the PID of the process listening on a given port.

    Uses platform-specific tools:
    - POSIX: lsof
    - Windows: netstat

    Args:
        port: Port number to check.

    Returns:
        PID of the process listening on the port, or None if not found.
    """
    if IS_WINDOWS:
        return _find_pid_by_port_windows(port)
    else:
        return _find_pid_by_port_posix(port)


def _find_pid_by_port_posix(port: int) -> int | None:
    """Find PID by port on POSIX systems using lsof."""
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return int(result.stdout.strip().split()[0])
    except FileNotFoundError:
        logger.warning("lsof not found - cannot find process by port")
    except (ValueError, OSError) as e:
        logger.debug(f"Failed to find process by port: {e}")
    return None


def _find_pid_by_port_windows(port: int) -> int | None:
    """Find PID by port on Windows using netstat."""
    try:
        result = subprocess.run(
            ["netstat", "-ano", "-p", "TCP"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                # Format: TCP    127.0.0.1:37800    0.0.0.0:0    LISTENING    12345
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.split()
                    if len(parts) >= 5:
                        try:
                            return int(parts[-1])
                        except ValueError:
                            continue
    except FileNotFoundError:
        logger.warning("netstat not found - cannot find process by port")
    except (ValueError, OSError) as e:
        logger.debug(f"Failed to find process by port: {e}")
    return None


# =============================================================================
# UV Tools Path Detection
# =============================================================================


def get_uv_tools_path_pattern() -> str:
    """Get the platform-specific path pattern for UV tool installations.

    Returns:
        Path pattern string that appears in sys.executable for uv tool installs.
        - POSIX: ".local/share/uv/tools/"
        - Windows: "\\uv\\tools\\" or "/uv/tools/" (normalized)
    """
    if IS_WINDOWS:
        # Windows: %LOCALAPPDATA%\uv\tools\
        # sys.executable might use forward or back slashes
        return "\\uv\\tools\\"
    else:
        # POSIX: ~/.local/share/uv/tools/
        return ".local/share/uv/tools/"


def is_uv_tool_install() -> bool:
    """Check if the current Python environment is a UV tool installation.

    Returns:
        True if running from a UV tool-installed environment.
    """
    pattern = get_uv_tools_path_pattern()
    executable = sys.executable

    # On Windows, also check forward slash variant
    if IS_WINDOWS:
        return pattern in executable or "/uv/tools/" in executable
    else:
        return pattern in executable
