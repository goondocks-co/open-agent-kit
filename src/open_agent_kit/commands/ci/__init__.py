"""Codebase Intelligence CLI commands - shared utilities.

This module provides shared utilities and the ci_app Typer instance
used by all CI subcommand modules.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console

from open_agent_kit.config.paths import OAK_DIR
from open_agent_kit.features.codebase_intelligence.constants import CI_DATA_DIR
from open_agent_kit.utils import dir_exists, print_error

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.daemon.manager import DaemonManager

logger = logging.getLogger(__name__)
console = Console()

ci_app = typer.Typer(
    name="ci",
    help="Manage Codebase Intelligence daemon and index",
    no_args_is_help=True,
)


def check_oak_initialized(project_root: Path) -> None:
    """Check if OAK is initialized in the project."""
    if not dir_exists(project_root / OAK_DIR):
        print_error("OAK is not initialized. Run 'oak init' first.")
        raise typer.Exit(code=1)


def check_ci_enabled(project_root: Path) -> None:
    """Check if Codebase Intelligence feature is enabled."""
    ci_dir = project_root / OAK_DIR / CI_DATA_DIR
    if not dir_exists(ci_dir):
        print_error(
            "Codebase Intelligence is not enabled. "
            "Run 'oak feature add codebase-intelligence' first."
        )
        raise typer.Exit(code=1)


def get_daemon_manager(project_root: Path) -> "DaemonManager":
    """Get daemon manager instance with per-project port."""
    from open_agent_kit.features.codebase_intelligence.daemon.manager import (
        DaemonManager,
        get_project_port,
    )

    ci_data_dir = project_root / OAK_DIR / CI_DATA_DIR
    port = get_project_port(project_root, ci_data_dir)
    return DaemonManager(project_root=project_root, port=port, ci_data_dir=ci_data_dir)


__all__ = [
    "ci_app",
    "console",
    "logger",
    "check_oak_initialized",
    "check_ci_enabled",
    "get_daemon_manager",
]
