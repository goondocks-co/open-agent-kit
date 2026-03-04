"""CI CLI commands - shared utilities.

This module provides shared utilities and the ci_app Typer instance
used by all CI subcommand modules (index, search, config, etc.).

Daemon lifecycle, cloud relay, and team member commands have moved
to ``open_agent_kit.commands.team``.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console

from open_agent_kit.commands.team import (
    check_ci_enabled,
    check_oak_initialized,
    get_daemon_manager,
    resolve_ci_data_dir,
)

if TYPE_CHECKING:
    from open_agent_kit.features.team.daemon.manager import DaemonManager

logger = logging.getLogger(__name__)
console = Console()

ci_app = typer.Typer(
    name="ci",
    help="Codebase index, search, and configuration",
    no_args_is_help=True,
)

__all__ = [
    "ci_app",
    "console",
    "logger",
    "check_oak_initialized",
    "check_ci_enabled",
    "get_daemon_manager",
    "resolve_ci_data_dir",
]
