"""``oak swarm mcp`` — run the swarm MCP server."""

import logging
import sys

logger = logging.getLogger(__name__)


def mcp_command(transport: str = "stdio") -> None:
    """Run the swarm MCP server for AI agent integration."""
    from open_agent_kit.features.swarm.daemon.mcp_server import run_mcp_server

    # For stdio transport, force logging to stderr to preserve stdout for JSON-RPC
    if transport == "stdio":
        logging.basicConfig(stream=sys.stderr, level=logging.WARNING, force=True)

    run_mcp_server(transport=transport)  # type: ignore[arg-type]
