"""Pytest configuration and fixtures for open-agent-kit tests."""

import os
import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

# =============================================================================
# CI environment: force immediate process exit after pytest completes
# =============================================================================
#
# GitHub Actions runner cancels steps whose process tree has lingering children.
# os._exit() in pytest_unconfigure ensures the pytest process exits immediately
# after all reporting is done, without waiting for Python's slow interpreter
# shutdown (atexit handlers, thread joins, GC of C-extension modules).
# The outer wrapper in the CI workflow handles orphan process cleanup.

_ci_exit_status = 0


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Capture the pytest exit status for use in pytest_unconfigure."""
    global _ci_exit_status  # noqa: PLW0603
    _ci_exit_status = exitstatus


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
