"""Pytest configuration and fixtures for open-agent-kit tests."""

import os
import shutil
import signal
import sys
import tempfile
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

# =============================================================================
# Background process reaper — prevents GH Actions orphan-detection cancel
# =============================================================================
#
# On Linux, test dependencies (onnxruntime, chromadb via OpenMP/multiprocessing)
# spawn background worker processes.  The GitHub Actions runner continuously
# monitors for orphan processes during step execution and sets a cancellation
# flag if any are detected — even if they're cleaned up before the step ends.
#
# This reaper thread kills stray child processes every few seconds so they
# never live long enough for the runner to notice.  On macOS/Windows this is
# a no-op because those platforms don't exhibit the issue.
# =============================================================================

_REAPER_INTERVAL_SECONDS = 3


def _find_child_pids(parent_pid: int) -> list[int]:
    """Return PIDs of all direct children of *parent_pid* via /proc."""
    children: list[int] = []
    proc_path = Path("/proc")
    pid_str = str(parent_pid)

    if not proc_path.is_dir():
        return children

    for entry in proc_path.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            stat = (entry / "stat").read_text()
            # Field 4 (0-indexed: 3) is PPID
            fields = stat.split()
            if len(fields) > 3 and fields[3] == pid_str:
                children.append(int(entry.name))
        except (OSError, ValueError):
            continue

    return children


def _kill_pids(pids: list[int], sig: int = signal.SIGKILL) -> None:
    """Send *sig* to each pid, ignoring already-dead processes."""
    for pid in pids:
        try:
            os.kill(pid, sig)
        except (ProcessLookupError, PermissionError):
            pass


def _reaper_loop(parent_pid: int) -> None:
    """Background loop: find and kill child processes every few seconds."""
    while True:
        time.sleep(_REAPER_INTERVAL_SECONDS)
        children = _find_child_pids(parent_pid)
        if children:
            _kill_pids(children, signal.SIGKILL)


if sys.platform == "linux":
    _reaper = threading.Thread(
        target=_reaper_loop,
        args=(os.getpid(),),
        daemon=True,  # dies when the main process exits
    )
    _reaper.start()


# =============================================================================
# Project-level fixtures
# =============================================================================


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
