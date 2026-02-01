"""Hooks management for Codebase Intelligence.

This module provides a Python-based API for installing and removing CI hooks
across different AI coding agents. Configuration is read from agent manifests,
making it portable and cross-platform.

Example usage:
    from open_agent_kit.features.codebase_intelligence.hooks import (
        install_hooks,
        remove_hooks,
    )

    # Install for a single agent
    result = install_hooks(
        project_root=Path("/path/to/project"),
        agent="claude",
    )

    # Remove from a single agent
    result = remove_hooks(
        project_root=Path("/path/to/project"),
        agent="claude",
    )
"""

from __future__ import annotations

import logging
from pathlib import Path

from open_agent_kit.features.codebase_intelligence.hooks.installer import (
    HooksInstaller,
    HooksInstallResult,
)

__all__ = [
    "HooksInstaller",
    "HooksInstallResult",
    "install_hooks",
    "remove_hooks",
]

logger = logging.getLogger(__name__)


def install_hooks(project_root: Path, agent: str) -> HooksInstallResult:
    """Install CI hooks for a specific agent.

    Uses the agent's manifest configuration to determine how to install
    hooks. Supports JSON config files and plugin files.

    Args:
        project_root: Project root directory.
        agent: Agent name (e.g., "claude", "cursor", "gemini").

    Returns:
        HooksInstallResult with success status and details.
    """
    installer = HooksInstaller(project_root=project_root, agent=agent)
    return installer.install()


def remove_hooks(project_root: Path, agent: str) -> HooksInstallResult:
    """Remove CI hooks from a specific agent.

    Uses the agent's manifest configuration to determine how to remove
    hooks. Preserves non-OAK hooks when using JSON config files.

    Args:
        project_root: Project root directory.
        agent: Agent name (e.g., "claude", "cursor", "gemini").

    Returns:
        HooksInstallResult with success status and details.
    """
    installer = HooksInstaller(project_root=project_root, agent=agent)
    return installer.remove()
