"""Validate that mcp.yaml capabilities.tools stays in sync with runtime tool registration.

mcp.yaml is the declarative contract for which MCP tools exist. This test
ensures the two Python-side tool registries don't drift from that contract:

- MCP_TOOLS (daemon-side handler in mcp_tools.py) must match YAML exactly.
- mcp_server.py (stdio proxy) may expose a subset, but never undeclared tools.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

import yaml

_MCP_YAML_PATH = (
    Path(__file__).resolve().parents[5]
    / "src"
    / "open_agent_kit"
    / "features"
    / "team"
    / "mcp"
    / "mcp.yaml"
)


def _load_yaml_tools() -> set[str]:
    """Load the declared tool names from mcp.yaml."""
    with open(_MCP_YAML_PATH, encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return set(config["capabilities"]["tools"])


def _load_mcp_tools_names() -> set[str]:
    """Extract tool names from the daemon-side MCP_TOOLS list."""
    from open_agent_kit.features.team.daemon.mcp_tools import MCP_TOOLS

    return {t["name"] for t in MCP_TOOLS}


def _load_mcp_server_tool_names() -> set[str]:
    """Extract tool names from the FastMCP stdio server.

    Mocks get_project_port to avoid filesystem side-effects (port file creation).
    """
    with patch(
        "open_agent_kit.features.team.daemon.mcp_server.get_project_port",
        return_value=19999,
    ):
        from open_agent_kit.features.team.daemon.mcp_server import create_mcp_server

        mcp = create_mcp_server(Path("/nonexistent/dummy"))

    tools = asyncio.run(mcp.list_tools())
    return {t.name for t in tools}


class TestMcpYamlSync:
    """Ensure mcp.yaml stays in sync with Python tool registrations."""

    def test_yaml_file_exists(self) -> None:
        assert _MCP_YAML_PATH.exists(), f"mcp.yaml not found at {_MCP_YAML_PATH}"

    def test_daemon_tools_match_yaml(self) -> None:
        """MCP_TOOLS (daemon-side) must declare exactly the tools in mcp.yaml."""
        yaml_tools = _load_yaml_tools()
        daemon_tools = _load_mcp_tools_names()

        missing_from_yaml = daemon_tools - yaml_tools
        missing_from_code = yaml_tools - daemon_tools

        assert not missing_from_yaml, (
            f"Tools in MCP_TOOLS but not declared in mcp.yaml: {sorted(missing_from_yaml)}. "
            f"Add them to capabilities.tools in {_MCP_YAML_PATH.name}."
        )
        assert not missing_from_code, (
            f"Tools declared in mcp.yaml but missing from MCP_TOOLS: {sorted(missing_from_code)}. "
            f"Add them to MCP_TOOLS in mcp_tools.py or remove from {_MCP_YAML_PATH.name}."
        )

    def test_server_tools_subset_of_yaml(self) -> None:
        """mcp_server.py tools must be a subset of the mcp.yaml contract.

        The stdio proxy may intentionally omit internal/admin tools, but it
        must never expose a tool that isn't declared in the YAML.
        """
        yaml_tools = _load_yaml_tools()
        server_tools = _load_mcp_server_tool_names()

        undeclared = server_tools - yaml_tools
        assert not undeclared, (
            f"Tools in mcp_server.py not declared in mcp.yaml: {sorted(undeclared)}. "
            f"Add them to capabilities.tools in {_MCP_YAML_PATH.name}."
        )
