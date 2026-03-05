"""Swarm MCP server installation API.

Delegates to the shared MCPInstaller from the team feature,
parameterized with swarm-specific server name and command.
"""

from open_agent_kit.features.team.mcp import (
    install_mcp_server,
    remove_mcp_server,
)

__all__ = [
    "install_mcp_server",
    "remove_mcp_server",
]
