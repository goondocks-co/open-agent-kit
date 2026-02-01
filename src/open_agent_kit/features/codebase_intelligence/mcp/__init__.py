"""MCP server management for Codebase Intelligence.

This module provides a Python-based API for installing and removing MCP servers
across different AI coding agents. Configuration is read from agent manifests,
making it portable and cross-platform.

Example usage:
    from open_agent_kit.features.codebase_intelligence.mcp import (
        install_mcp_server,
        remove_mcp_server,
    )

    # Install for a single agent
    result = install_mcp_server(
        project_root=Path("/path/to/project"),
        agent="claude",
        server_name="oak-ci",
        command="oak ci mcp",
    )

    # Remove from a single agent
    result = remove_mcp_server(
        project_root=Path("/path/to/project"),
        agent="claude",
        server_name="oak-ci",
    )
"""

from __future__ import annotations

import logging
from pathlib import Path

from open_agent_kit.features.codebase_intelligence.mcp.installer import (
    InstallResult,
    MCPInstaller,
)

__all__ = [
    "MCPInstaller",
    "InstallResult",
    "install_mcp_server",
    "remove_mcp_server",
]

logger = logging.getLogger(__name__)


def install_mcp_server(
    project_root: Path,
    agent: str,
    server_name: str,
    command: str,
) -> InstallResult:
    """Install an MCP server for a specific agent.

    Uses the agent's manifest configuration to determine how to install
    the MCP server. Tries CLI first if available, falls back to JSON.

    Args:
        project_root: Project root directory.
        agent: Agent name (e.g., "claude", "cursor", "gemini").
        server_name: Name for the MCP server (e.g., "oak-ci").
        command: Full command to run the MCP server (e.g., "oak ci mcp").

    Returns:
        InstallResult with success status and details.
    """
    installer = MCPInstaller(
        project_root=project_root,
        agent=agent,
        server_name=server_name,
        command=command,
    )
    return installer.install()


def remove_mcp_server(
    project_root: Path,
    agent: str,
    server_name: str,
) -> InstallResult:
    """Remove an MCP server from a specific agent.

    Uses the agent's manifest configuration to determine how to remove
    the MCP server. Tries CLI first if available, falls back to JSON.

    Args:
        project_root: Project root directory.
        agent: Agent name (e.g., "claude", "cursor", "gemini").
        server_name: Name for the MCP server (e.g., "oak-ci").

    Returns:
        InstallResult with success status and details.
    """
    installer = MCPInstaller(
        project_root=project_root,
        agent=agent,
        server_name=server_name,
        command="",  # Not needed for removal
    )
    return installer.remove()
