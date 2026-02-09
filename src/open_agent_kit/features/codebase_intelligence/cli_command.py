"""Utilities for resolving and rewriting CI CLI command invocations."""

from __future__ import annotations

import logging
from pathlib import Path

from open_agent_kit.features.codebase_intelligence.constants import (
    CI_CLI_COMMAND_DEFAULT,
    CI_CLI_COMMAND_OAK_PREFIX,
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
        from open_agent_kit.features.codebase_intelligence.config import load_ci_config

        config = load_ci_config(project_root)
        return normalize_cli_command(config.cli_command)
    except Exception as e:
        logger.debug(f"Falling back to default CLI command: {e}")
        return CI_CLI_COMMAND_DEFAULT


def render_cli_command_placeholder(content: str, cli_command: str) -> str:
    """Render CLI command placeholder tokens in content."""
    resolved = normalize_cli_command(cli_command)
    return content.replace(CLI_COMMAND_PLACEHOLDER, resolved)
