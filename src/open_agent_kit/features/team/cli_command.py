"""Utilities for resolving and rewriting CI CLI command invocations."""

from __future__ import annotations

import logging
from pathlib import Path

from open_agent_kit.features.team.constants import (
    CI_CLI_COMMAND_DEFAULT,
    CI_CLI_COMMAND_OAK_PREFIX,
    CI_CLI_COMMAND_VALIDATION_PATTERN,
)

logger = logging.getLogger(__name__)

CLI_COMMAND_PLACEHOLDER = "{oak-cli-command}"


def normalize_cli_command(command: str | None) -> str:
    """Normalize configured CLI command, falling back to default."""
    if command is None:
        return CI_CLI_COMMAND_DEFAULT

    normalized = command.strip()
    if not normalized:
        return CI_CLI_COMMAND_DEFAULT
    return normalized


def rewrite_oak_command(command: str, cli_command: str) -> str:
    """Rewrite an ``oak ...`` command to use the configured CLI command."""
    resolved = normalize_cli_command(cli_command)

    if command == CI_CLI_COMMAND_DEFAULT:
        return resolved

    if command.startswith(CI_CLI_COMMAND_OAK_PREFIX):
        suffix = command[len(CI_CLI_COMMAND_OAK_PREFIX) :]
        return f"{resolved} {suffix}"

    return command


def resolve_ci_cli_command(project_root: Path) -> str:
    """Resolve effective CLI command for CI-managed integrations in a project."""
    try:
        from open_agent_kit.features.team.config import load_ci_config

        config = load_ci_config(project_root)
        return normalize_cli_command(config.cli_command)
    except (OSError, ValueError, KeyError) as e:
        logger.debug(f"Falling back to default CLI command: {e}")
        return CI_CLI_COMMAND_DEFAULT


def detect_invoked_cli_command() -> str:
    """Detect the CLI binary name from the current process invocation.

    Returns the stem of sys.argv[0] if it matches the allowed pattern
    (e.g. 'oak', 'oak-beta', 'oak-dev'), falling back to the default.

    Python module entry points (e.g. ``__main__.py`` from ``python -m
    uvicorn``) are rejected because they are not real CLI commands.
    """
    import re
    import sys

    name = Path(sys.argv[0]).name
    # Reject Python module entry points — when the daemon is started via
    # ``python -m uvicorn``, argv[0] is uvicorn's ``__main__.py``.
    # Persisting that as the CLI command breaks skill rendering and
    # daemon self-restart.
    if name.endswith(".py"):
        return CI_CLI_COMMAND_DEFAULT
    if re.fullmatch(CI_CLI_COMMAND_VALIDATION_PATTERN, name):
        return name
    return CI_CLI_COMMAND_DEFAULT


def render_cli_command_placeholder(content: str, cli_command: str) -> str:
    """Render CLI command placeholder tokens in content."""
    resolved = normalize_cli_command(cli_command)
    return content.replace(CLI_COMMAND_PLACEHOLDER, resolved)
