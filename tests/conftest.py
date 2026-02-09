"""Pytest configuration and fixtures for open-agent-kit tests."""

import os
import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

# =============================================================================
# CI environment: clean up orphan processes and force immediate exit
# =============================================================================
#
# GitHub Actions runner monitors the process tree for each step.  When the main
# pytest process finishes but orphan child processes remain, the runner cancels
# the step ("The operation was canceled") even though all tests passed.
#
# Fix (two-phase):
#   1. pytest_sessionfinish — kill any orphan Python children so the runner
#      sees a clean process tree.  This runs BEFORE the terminal summary.
#   2. pytest_unconfigure  — call os._exit() to skip Python's slow interpreter
#      shutdown (atexit, GC, thread joins) which can also trigger the runner.

_ci_exit_status = 0


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Kill orphan child processes in CI, then capture exit status."""
    global _ci_exit_status  # noqa: PLW0603
    _ci_exit_status = exitstatus

    if not os.environ.get("CI"):
        return

    import signal
    import subprocess

    my_pid = str(os.getpid())
    result = subprocess.run(
        ["ps", "-eo", "pid,ppid,command"],
        capture_output=True,
        text=True,
    )
    for line in result.stdout.splitlines()[1:]:  # skip header
        parts = line.split(None, 2)
        if len(parts) < 3:
            continue
        pid_str, ppid_str, cmd = parts
        if pid_str == my_pid:
            continue
        if "python" not in cmd.lower():
            continue
        # Log for diagnostics, then terminate
        print(f"ci-cleanup: killing orphan pid={pid_str} ppid={ppid_str} cmd={cmd[:120]}")
        try:
            os.kill(int(pid_str), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass


def pytest_unconfigure(config: pytest.Config) -> None:
    """Force immediate exit in CI to prevent runner cancellation."""
    if os.environ.get("CI"):
        os._exit(_ci_exit_status)


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
