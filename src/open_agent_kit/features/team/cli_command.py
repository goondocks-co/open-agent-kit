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

    Homebrew workaround: Homebrew beta formula creates a shell wrapper
    ``oak-beta`` that does ``exec .../libexec/bin/oak "$@"``, so by the
    time Python starts, argv[0] is ``oak`` inside the libexec venv.
    When the detected name is the default (``oak``) but the package
    version is a PEP 440 beta (contains ``b``), we correct to
    ``oak-beta`` — the name the user actually typed.
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
        # Homebrew beta workaround: argv[0] is "oak" but we're a beta package.
        if name == CI_CLI_COMMAND_DEFAULT:
            name = _correct_for_beta_package(name)
        return name
    return CI_CLI_COMMAND_DEFAULT


def _correct_for_beta_package(name: str) -> str:
    """Return ``oak-beta`` if the running package is a PEP 440 beta release
    and the ``oak-beta`` binary exists on PATH.

    Homebrew beta formula creates a shell wrapper ``oak-beta`` that does
    ``exec .../libexec/bin/oak "$@"``, so argv[0] becomes ``oak``.
    We detect this by checking the package version + binary presence.
    The PATH check prevents false positives in dev/editable installs
    where the version may contain ``b`` but no ``oak-beta`` exists.
    """
    import shutil

    try:
        from open_agent_kit._version import __version__

        # PEP 440 beta: "1.5.0b3", "1.5.0b1" — the 'b' marker
        if "b" in __version__ and not __version__.startswith("0."):
            beta_name = f"{name}-beta"
            if shutil.which(beta_name):
                logger.debug(
                    "Detected beta package (%s) with %s on PATH, "
                    "correcting CLI command: %s -> %s",
                    __version__,
                    beta_name,
                    name,
                    beta_name,
                )
                return beta_name
    except (ImportError, AttributeError) as exc:
        logger.debug("Could not check beta version for CLI correction: %s", exc)
    return name


def render_cli_command_placeholder(content: str, cli_command: str) -> str:
    """Render CLI command placeholder tokens in content."""
    resolved = normalize_cli_command(cli_command)
    return content.replace(CLI_COMMAND_PLACEHOLDER, resolved)
