"""Team CLI commands — daemon lifecycle, members, and cloud relay.

This module provides the team_app Typer instance and shared utilities
used by all team subcommand modules.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console

from open_agent_kit.config.paths import OAK_DIR
from open_agent_kit.features.team.constants import CI_DATA_DIR
from open_agent_kit.utils import dir_exists, print_error
from open_agent_kit.utils.file_utils import resolve_main_repo_root

if TYPE_CHECKING:
    from open_agent_kit.features.team.daemon.manager import DaemonManager

logger = logging.getLogger(__name__)
console = Console()

team_app = typer.Typer(
    name="team",
    help="Team daemon lifecycle and collaboration",
    no_args_is_help=True,
)


def resolve_ci_data_dir(project_root: Path) -> Path:
    """Resolve the CI data directory, looking through worktrees if needed.

    In a normal repo: returns ``project_root/.oak/ci/`` (the usual path).
    In a worktree: ``.oak/ci/`` doesn't exist locally (gitignored), so
    resolve to the main repo's ``.oak/ci/`` via git plumbing.
    """
    local_ci = project_root / OAK_DIR / CI_DATA_DIR
    if local_ci.is_dir():
        return local_ci

    # Not found locally — check if we're in a worktree
    main_root = resolve_main_repo_root(project_root)
    if main_root is not None and main_root.resolve() != project_root.resolve():
        remote_ci = main_root / OAK_DIR / CI_DATA_DIR
        if remote_ci.is_dir():
            return remote_ci

    return local_ci  # Return local path (may not exist — callers handle this)


def check_oak_initialized(project_root: Path) -> None:
    """Check if OAK is initialized in the project."""
    if not dir_exists(project_root / OAK_DIR):
        print_error("OAK is not initialized. Run 'oak init' first.")
        raise typer.Exit(code=1)


def check_ci_enabled(project_root: Path) -> None:
    """Check if Team feature is enabled."""
    ci_dir = resolve_ci_data_dir(project_root)
    if not dir_exists(ci_dir):
        print_error("Team is not enabled. Run 'oak feature add team' first.")
        raise typer.Exit(code=1)


def get_daemon_manager(project_root: Path) -> "DaemonManager":
    """Get daemon manager instance with per-project port."""
    from open_agent_kit.features.team.daemon.manager import (
        DaemonManager,
        get_project_port,
    )

    ci_data_dir = resolve_ci_data_dir(project_root)
    port = get_project_port(project_root, ci_data_dir)
    return DaemonManager(project_root=project_root, port=port, ci_data_dir=ci_data_dir)


def _register_sub_typers() -> None:
    """Register sub-Typer apps and side-effect imports onto team_app.

    Called after team_app is defined so that submodule imports can
    reference it without circular import issues.
    """
    from open_agent_kit.commands.team import cloud as _cloud  # noqa: F401
    from open_agent_kit.commands.team import daemon as _daemon  # noqa: F401
    from open_agent_kit.commands.team import mcp as _mcp  # noqa: F401
    from open_agent_kit.commands.team.members import members_app

    team_app.add_typer(members_app)


_register_sub_typers()

__all__ = [
    "team_app",
    "console",
    "logger",
    "check_oak_initialized",
    "check_ci_enabled",
    "get_daemon_manager",
    "resolve_ci_data_dir",
]
