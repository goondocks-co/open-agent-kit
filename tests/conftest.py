"""Pytest configuration and fixtures for open-agent-kit tests."""

import os
import shutil
import signal
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

# =============================================================================
# Session-scoped cleanup for background processes
# =============================================================================


@pytest.fixture(autouse=True, scope="session")
def _cleanup_child_processes():
    """Terminate child processes spawned by test dependencies during teardown.

    On Linux, libraries like onnxruntime and chromadb spawn background worker
    processes (via OpenMP / multiprocessing) that persist after pytest exits.
    GitHub Actions detects these orphans and cancels the CI step.

    This fixture kills them during pytest session teardown — before the process
    exits — so the runner never sees orphans.  On macOS/Windows this is a no-op
    because those platforms don't exhibit the issue.
    """
    yield

    if sys.platform != "linux":
        return

    _terminate_child_processes(os.getpid())


@pytest.fixture
def temp_project_dir() -> Iterator[Path]:
    """Create a temporary project directory for testing.

    Yields:
        Path to temporary directory
    """
    temp_dir = Path(tempfile.mkdtemp(prefix="open-agent-kit-test-"))
    original_cwd = Path.cwd()
    try:
        os.chdir(temp_dir)
        yield temp_dir
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def initialized_project(temp_project_dir: Path) -> Path:
    """Create a temporary project with .oak initialized.

    Args:
        temp_project_dir: Temporary project directory

    Returns:
        Path to initialized project
    """
    from open_agent_kit.commands.init_cmd import init_command

    init_command(force=False, agent=[], no_interactive=True)
    return temp_project_dir


@pytest.fixture
def sample_rfc_data() -> dict:
    """Sample RFC data for testing.

    Returns:
        Dictionary with RFC test data
    """
    return {
        "title": "Test RFC for Automated Testing",
        "author": "Test Author",
        "description": "This is a test RFC to verify the CLI functionality",
        "template": "engineering",
        "tags": ["test", "automation"],
    }


# =============================================================================
# Helpers (not fixtures)
# =============================================================================


def _terminate_child_processes(parent_pid: int) -> None:
    """Send SIGTERM then SIGKILL to all child processes of *parent_pid*.

    Uses /proc on Linux to discover children without external dependencies.
    Silently ignores processes that have already exited.
    """
    import time

    children: list[int] = []
    proc_path = Path("/proc")
    pid_str = str(parent_pid)

    # Walk /proc/<pid>/stat to find children of our process
    if proc_path.is_dir():
        for entry in proc_path.iterdir():
            if not entry.name.isdigit():
                continue
            try:
                stat = (entry / "stat").read_text()
                # Field 4 (0-indexed: 3) in /proc/<pid>/stat is the PPID
                fields = stat.split()
                if len(fields) > 3 and fields[3] == pid_str:
                    children.append(int(entry.name))
            except (OSError, ValueError):
                continue

    if not children:
        return

    # SIGTERM first (graceful)
    for pid in children:
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass

    time.sleep(0.3)

    # SIGKILL stragglers
    for pid in children:
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
