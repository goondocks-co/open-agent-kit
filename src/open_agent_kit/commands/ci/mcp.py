"""CI MCP integration commands: mcp."""

import os
from pathlib import Path
from typing import cast

import typer

from open_agent_kit.utils import (
    print_error,
    print_info,
    print_success,
    print_warning,
)

from . import (
    check_ci_enabled,
    check_oak_initialized,
    ci_app,
    get_daemon_manager,
)


@ci_app.command("mcp")
def ci_mcp(
    transport: str = typer.Option(
        "stdio",
        "--transport",
        "-t",
        help="MCP transport type: 'stdio' (for Claude Code) or 'streamable-http' (for web)",
    ),
    port: int = typer.Option(
        8080,
        "--port",
        "-p",
        help="Port for HTTP transport (only used with streamable-http)",
    ),
    project: str = typer.Option(
        None,
        "--project",
        help="Project root directory (defaults to current directory or OAK_CI_PROJECT_ROOT env)",
    ),
) -> None:
    """Run the MCP protocol server for native tool discovery.

    This starts an MCP server that exposes CI tools (oak_search, oak_remember,
    oak_context, oak_status) via the Model Context Protocol.

    For Claude Code, add to your MCP config (.mcp.json at project root):
    {
      "mcpServers": {
        "oak-ci": {
          "type": "stdio",
          "command": "oak",
          "args": ["ci", "mcp"]
        }
      }
    }

    Note: The MCP server uses the current working directory to find the project.
    Run the command from your project root, or use --project to specify a path.

    The MCP server requires the CI daemon to be running (oak ci start).
    """
    # Determine project root: --project flag > OAK_CI_PROJECT_ROOT env > cwd
    if project:
        project_root = Path(project)
    elif os.environ.get("OAK_CI_PROJECT_ROOT"):
        project_root = Path(os.environ["OAK_CI_PROJECT_ROOT"])
    else:
        project_root = Path.cwd()

    check_oak_initialized(project_root)
    check_ci_enabled(project_root)

    # Check if daemon is running
    manager = get_daemon_manager(project_root)
    if not manager.is_running():
        # When using stdio transport, we must NOT print to stdout as it corrupts the MCP protocol
        if transport == "stdio":
            import sys

            # Use stderr for status messages so they don't interfere with stdio transport
            print("⚠ CI daemon is not running. Starting it now...", file=sys.stderr)
            if not manager.start():
                print(
                    "✗ Failed to start daemon. Run 'oak ci start' manually and check logs.",
                    file=sys.stderr,
                )
                raise typer.Exit(code=1)
            print(f"✓ Daemon started at http://localhost:{manager.port}", file=sys.stderr)
        else:
            print_warning("CI daemon is not running. Starting it now...")
            if not manager.start():
                print_error("Failed to start daemon. Run 'oak ci start' manually and check logs.")
                raise typer.Exit(code=1)
            print_success(f"Daemon started at http://localhost:{manager.port}")

    try:
        from open_agent_kit.features.codebase_intelligence.daemon.mcp_server import run_mcp_server
    except ImportError as e:
        print_error(f"MCP server not available: {e}")
        print_info("Install the mcp package: pip install mcp")
        raise typer.Exit(code=1)

    if transport == "streamable-http":
        print_info(f"Starting MCP server on http://localhost:{port}/mcp")
        print_info("Press Ctrl+C to stop.")
        # Set port via environment for streamable-http
        os.environ["FASTMCP_PORT"] = str(port)

    # Run the MCP server (blocks)
    from open_agent_kit.features.codebase_intelligence.daemon.mcp_server import MCPTransport

    # Validate transport before cast
    valid_transports = {"stdio", "sse", "streamable-http"}
    if transport not in valid_transports:
        print_error(
            f"Invalid transport: {transport}. Must be one of: {', '.join(sorted(valid_transports))}"
        )
        raise typer.Exit(code=1)
    run_mcp_server(project_root, transport=cast(MCPTransport, transport))
