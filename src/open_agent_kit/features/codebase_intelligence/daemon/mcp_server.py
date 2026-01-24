"""MCP Protocol Server for Codebase Intelligence.

Provides native MCP protocol support for AI agents to discover and use
CI tools (oak_search, oak_remember, oak_context) via stdio or HTTP transport.

The MCP server automatically starts the CI daemon if it's not running,
providing seamless integration with AI agents like Claude Code.
"""

import json
import logging
from pathlib import Path
from typing import Any, Literal, cast

import httpx
from mcp.server.fastmcp import FastMCP

from open_agent_kit.config.paths import OAK_DIR
from open_agent_kit.features.codebase_intelligence.constants import CI_DATA_DIR
from open_agent_kit.features.codebase_intelligence.daemon.manager import (
    DaemonManager,
    get_project_port,
)

logger = logging.getLogger(__name__)


def create_mcp_server(project_root: Path) -> FastMCP:
    """Create an MCP server that wraps the CI daemon REST API.

    Args:
        project_root: Root directory of the OAK project.

    Returns:
        FastMCP server instance configured with CI tools.
    """
    ci_data_dir = project_root / OAK_DIR / CI_DATA_DIR
    port = get_project_port(project_root, ci_data_dir)
    base_url = f"http://localhost:{port}"

    mcp = FastMCP(
        "OAK Codebase Intelligence",
        json_response=True,
    )

    # Track if we've already tried to start the daemon this session
    daemon_start_attempted = {"value": False}

    def _ensure_daemon_running() -> bool:
        """Ensure the daemon is running, starting it if necessary.

        Returns:
            True if daemon is running, False if start failed.
        """
        manager = DaemonManager(project_root, port=port, ci_data_dir=ci_data_dir)

        if manager.is_running():
            return True

        # Only attempt auto-start once per MCP session to avoid loops
        if daemon_start_attempted["value"]:
            return False

        daemon_start_attempted["value"] = True
        logger.info("CI daemon not running - attempting auto-start...")

        try:
            success = manager.start(wait=True)
            if success:
                logger.info("CI daemon auto-started successfully")
            else:
                logger.error("CI daemon auto-start failed")
            return success
        except (OSError, RuntimeError) as e:
            logger.error(f"CI daemon auto-start error: {e}")
            return False

    def _call_daemon(endpoint: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Call the CI daemon REST API.

        Automatically starts the daemon if it's not running.

        Args:
            endpoint: API endpoint path (e.g., "/api/search")
            data: JSON data to send (for POST requests)

        Returns:
            Response JSON data.

        Raises:
            Exception: If daemon cannot be started or request fails.
        """
        url = f"{base_url}{endpoint}"

        def _make_request() -> dict[str, Any]:
            with httpx.Client(timeout=30.0) as client:
                if data is not None:
                    response = client.post(url, json=data)
                else:
                    response = client.get(url)
                response.raise_for_status()
                return cast(dict[str, Any], response.json())

        try:
            return _make_request()
        except httpx.ConnectError:
            # Daemon not running - try to auto-start
            if _ensure_daemon_running():
                # Retry after successful start
                try:
                    return _make_request()
                except httpx.ConnectError:
                    pass  # Fall through to error

            raise Exception(
                f"CI daemon not running and auto-start failed.\n"
                f"Try manually: oak ci start\n"
                f"Check logs: {ci_data_dir / 'daemon.log'}"
            ) from None
        except httpx.HTTPStatusError as e:
            raise Exception(f"Daemon error: {e.response.status_code} - {e.response.text}") from e

    @mcp.tool()
    def oak_search(
        query: str,
        search_type: str = "all",
        limit: int = 10,
    ) -> str:
        """Search the codebase and project memories using semantic similarity.

        Use this to find relevant code implementations, past decisions, gotchas,
        and learnings. Returns ranked results with relevance scores.

        Args:
            query: Natural language search query (e.g., 'authentication middleware')
            search_type: Search code, memories, or both. Options: 'all', 'code', 'memory'
            limit: Maximum results to return (1-50)

        Returns:
            JSON string with search results containing code and memory matches.
        """
        result = _call_daemon(
            "/api/search",
            {
                "query": query,
                "search_type": search_type,
                "limit": min(max(1, limit), 50),
            },
        )
        return json.dumps(result, indent=2)

    @mcp.tool()
    def oak_remember(
        observation: str,
        memory_type: str = "discovery",
        context: str | None = None,
    ) -> str:
        """Store an observation, decision, or learning for future sessions.

        Use this when you discover something important about the codebase that
        would help in future work.

        Args:
            observation: The observation or learning to store
            memory_type: Type of observation. Options: 'gotcha', 'bug_fix', 'decision', 'discovery', 'trade_off'
            context: Related file path or additional context

        Returns:
            JSON string confirming storage with observation ID.
        """
        data: dict[str, Any] = {
            "observation": observation,
            "memory_type": memory_type,
        }
        if context:
            data["context"] = context

        result = _call_daemon("/api/remember", data)
        return json.dumps(result, indent=2)

    @mcp.tool()
    def oak_context(
        task: str,
        current_files: list[str] | None = None,
        max_tokens: int = 2000,
    ) -> str:
        """Get relevant context for your current task.

        Call this when starting work on something to retrieve related code,
        past decisions, and applicable project guidelines.

        Args:
            task: Description of what you're working on
            current_files: Files currently being viewed/edited
            max_tokens: Maximum tokens of context to return

        Returns:
            JSON string with curated context including code and memories.
        """
        data: dict[str, Any] = {
            "task": task,
            "max_tokens": max_tokens,
        }
        if current_files:
            data["current_files"] = current_files

        # oak_context calls the MCP tool endpoint
        result = _call_daemon(
            "/api/mcp/call",
            {
                "tool_name": "oak_context",
                "arguments": data,
            },
        )
        return json.dumps(result, indent=2)

    # Note: Keeping tools minimal (3 tools) to avoid context bloat for agents
    # oak_status is available via CLI (oak ci status) but not exposed as MCP tool

    return mcp


MCPTransport = Literal["stdio", "sse", "streamable-http"]


def run_mcp_server(project_root: Path, transport: MCPTransport = "stdio") -> None:
    """Run the MCP server.

    Args:
        project_root: Root directory of the OAK project.
        transport: Transport type ('stdio', 'sse', or 'streamable-http')
    """
    mcp = create_mcp_server(project_root)
    mcp.run(transport=transport)


if __name__ == "__main__":
    # For testing: run from project root
    import sys

    project_root = Path.cwd()
    transport_arg = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    run_mcp_server(project_root, cast(MCPTransport, transport_arg))
