"""``oak swarm mcp`` — run the swarm MCP server."""

import logging
import sys

import typer

logger = logging.getLogger(__name__)


def mcp_command(
    transport: str = typer.Option(
        "stdio",
        "--transport",
        "-t",
        help="MCP transport type (stdio, sse, streamable-http).",
    ),
    name: str = typer.Option(
        "",
        "--name",
        "-n",
        help="Swarm name. Auto-detected from ~/.oak/swarms/ if omitted.",
    ),
    port: int = typer.Option(
        0,
        "--port",
        "-p",
        help="HTTP port for streamable-http transport.",
    ),
) -> None:
    """Run the swarm MCP server for AI agent integration."""
    from open_agent_kit.features.swarm.daemon.mcp_server import run_mcp_server

    # For stdio transport, force logging to stderr to preserve stdout for JSON-RPC
    if transport == "stdio":
        logging.basicConfig(stream=sys.stderr, level=logging.WARNING, force=True)

    run_mcp_server(transport=transport)  # type: ignore[arg-type]
