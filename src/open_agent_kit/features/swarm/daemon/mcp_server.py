"""MCP Protocol Server for Swarm Mode.

Provides native MCP protocol support for AI agents to discover and use
swarm tools (swarm_search, swarm_nodes, swarm_call, swarm_broadcast,
swarm_status) via stdio or HTTP transport.

The MCP server proxies all calls to the local swarm daemon HTTP API.
"""

import atexit
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Literal, cast

import httpx
from mcp.server.fastmcp import FastMCP

# Force all logging to stderr to preserve stdout for MCP protocol
# This prevents stdout pollution that corrupts the JSON-RPC handshake
logging.basicConfig(stream=sys.stderr, level=logging.INFO, force=True)
logging.getLogger("httpx").setLevel(logging.WARNING)

from open_agent_kit.features.swarm.constants import (  # noqa: E402
    SWARM_DAEMON_API_PATH_BROADCAST,
    SWARM_DAEMON_API_PATH_FETCH,
    SWARM_DAEMON_API_PATH_NODES,
    SWARM_DAEMON_API_PATH_SEARCH,
    SWARM_DAEMON_API_PATH_STATUS,
    SWARM_DAEMON_API_PATH_TOOL_CALL,
    SWARM_DAEMON_CONFIG_DIR,
    SWARM_DAEMON_DEFAULT_PORT,
    SWARM_DAEMON_PORT_FILE,
    SWARM_DEFAULT_FETCH_TIMEOUT_SECONDS,
    SWARM_DEFAULT_TOOL_TIMEOUT_SECONDS,
    SWARM_RESPONSE_KEY_ERROR,
)

logger = logging.getLogger(__name__)

# Retry parameters for transient ConnectErrors (daemon restarting)
_CONNECT_RETRY_ATTEMPTS = 3
_CONNECT_RETRY_DELAY_S = 1.0

# Connection pool limits for the shared httpx client
_POOL_MAX_CONNECTIONS = 20
_POOL_MAX_KEEPALIVE = 10
_DEFAULT_TIMEOUT_S = 30.0


def _find_daemon_port() -> int:
    """Find the swarm daemon port by reading port files.

    Searches ``~/.oak/swarms/*/daemon.port`` for the first match.
    Falls back to the default port if no port file is found.

    Returns:
        The port number the swarm daemon is listening on.
    """
    config_root = Path(SWARM_DAEMON_CONFIG_DIR).expanduser()
    if config_root.is_dir():
        for port_file in sorted(config_root.glob(f"*/{SWARM_DAEMON_PORT_FILE}")):
            try:
                port = int(port_file.read_text().strip())
                if port > 0:
                    return port
            except (ValueError, OSError):
                continue
    return SWARM_DAEMON_DEFAULT_PORT


def _create_pooled_client(base_url: str) -> httpx.Client:
    """Create a shared httpx.Client with connection pooling.

    Args:
        base_url: Base URL for the swarm daemon.

    Returns:
        Configured httpx.Client with connection pool limits.
    """
    pool_limits = httpx.Limits(
        max_connections=_POOL_MAX_CONNECTIONS,
        max_keepalive_connections=_POOL_MAX_KEEPALIVE,
    )
    return httpx.Client(
        base_url=base_url,
        limits=pool_limits,
        timeout=_DEFAULT_TIMEOUT_S,
    )


def create_mcp_server() -> FastMCP:
    """Create an MCP server that wraps the swarm daemon REST API.

    Returns:
        FastMCP server instance configured with swarm tools.
    """
    port = _find_daemon_port()
    base_url = f"http://localhost:{port}"

    http_client = _create_pooled_client(base_url)
    atexit.register(http_client.close)

    mcp = FastMCP(
        "oak-swarm",
        json_response=True,
    )

    def _call_daemon(
        endpoint: str,
        data: dict[str, Any] | None = None,
        method: str | None = None,
        timeout: float = _DEFAULT_TIMEOUT_S,
    ) -> dict[str, Any]:
        """Call the swarm daemon REST API.

        Args:
            endpoint: API endpoint path (e.g., "/api/swarm/search").
            data: JSON data to send (for POST requests).
            method: HTTP method override. Defaults to POST when data
                is provided, GET otherwise.
            timeout: Request timeout in seconds.

        Returns:
            Response JSON data.

        Raises:
            Exception: If daemon is unreachable after retries.
        """

        def _make_request() -> dict[str, Any]:
            resolved_method = method
            if resolved_method is None:
                resolved_method = "POST" if data is not None else "GET"
            resolved_method = resolved_method.upper()

            if resolved_method == "POST":
                response = http_client.post(endpoint, json=data, timeout=timeout)
            else:
                response = http_client.get(endpoint, timeout=timeout)
            response.raise_for_status()
            return cast(dict[str, Any], response.json())

        # Happy path
        try:
            return _make_request()
        except httpx.ConnectError:
            pass  # Fall through to retry
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Swarm daemon error: {exc.response.status_code} - {exc.response.text}"
            ) from exc

        # Retry loop: daemon may be mid-restart
        for _attempt in range(_CONNECT_RETRY_ATTEMPTS):
            time.sleep(_CONNECT_RETRY_DELAY_S)
            try:
                return _make_request()
            except (httpx.ConnectError, httpx.HTTPStatusError):
                continue

        raise RuntimeError(
            "Swarm daemon is not running.\n"
            "Start it with: oak swarm start\n"
            f"Check logs in: {SWARM_DAEMON_CONFIG_DIR}"
        )

    @mcp.tool()
    def swarm_search(
        query: str,
        search_type: str = "all",
        limit: int = 10,
    ) -> str:
        """Search across all projects in the swarm.

        Use this to find code, memories, and context from other projects
        connected to the same swarm.

        Args:
            query: Natural language search query (e.g., 'authentication middleware').
            search_type: Search scope. Options: 'all', 'code', 'memory'.
            limit: Maximum results to return (1-50).

        Returns:
            JSON string with search results from swarm nodes.
        """
        try:
            result = _call_daemon(
                SWARM_DAEMON_API_PATH_SEARCH,
                data={
                    "query": query,
                    "search_type": search_type,
                    "limit": min(max(1, limit), 50),
                },
            )
            return json.dumps(result, indent=2)
        except RuntimeError as exc:
            return json.dumps({SWARM_RESPONSE_KEY_ERROR: str(exc)})

    @mcp.tool()
    def swarm_nodes() -> str:
        """List all teams in the swarm with their connection status.

        Use this to see which projects are connected and available
        for cross-project queries and tool calls.

        Returns:
            JSON string with list of swarm teams and their status.
        """
        try:
            result = _call_daemon(SWARM_DAEMON_API_PATH_NODES)
            return json.dumps(result, indent=2)
        except RuntimeError as exc:
            return json.dumps({SWARM_RESPONSE_KEY_ERROR: str(exc)})

    @mcp.tool()
    def swarm_call(
        tool_name: str,
        arguments: str = "{}",
        target_project: str = "",
    ) -> str:
        """Call a tool on a specific project in the swarm.

        Routes the tool invocation to the target project's CI daemon,
        allowing cross-project operations like searching a specific
        project's codebase or reading its memories.

        Args:
            tool_name: Name of the tool to invoke (e.g., 'oak_search').
            arguments: JSON string of tool arguments.
            target_project: Project slug to route the call to.

        Returns:
            JSON string with the tool call result.
        """
        try:
            parsed_args = json.loads(arguments)
        except json.JSONDecodeError as exc:
            return json.dumps({SWARM_RESPONSE_KEY_ERROR: f"Invalid JSON arguments: {exc}"})

        if not target_project:
            return json.dumps({SWARM_RESPONSE_KEY_ERROR: "target_project is required"})

        try:
            result = _call_daemon(
                SWARM_DAEMON_API_PATH_TOOL_CALL,
                data={
                    "tool_name": tool_name,
                    "arguments": parsed_args,
                    "target_project": target_project,
                },
                timeout=SWARM_DEFAULT_TOOL_TIMEOUT_SECONDS + 2.0,
            )
            return json.dumps(result, indent=2)
        except RuntimeError as exc:
            return json.dumps({SWARM_RESPONSE_KEY_ERROR: str(exc)})

    @mcp.tool()
    def swarm_broadcast(
        tool_name: str,
        arguments: str = "{}",
    ) -> str:
        """Broadcast a tool call to all projects in the swarm.

        Sends the same tool invocation to every connected project and
        aggregates the results. Useful for swarm-wide searches or
        collecting information from all projects at once.

        Args:
            tool_name: Name of the tool to invoke (e.g., 'oak_search').
            arguments: JSON string of tool arguments.

        Returns:
            JSON string with aggregated results from all projects.
        """
        try:
            parsed_args = json.loads(arguments)
        except json.JSONDecodeError as exc:
            return json.dumps({SWARM_RESPONSE_KEY_ERROR: f"Invalid JSON arguments: {exc}"})

        try:
            result = _call_daemon(
                SWARM_DAEMON_API_PATH_BROADCAST,
                data={
                    "tool_name": tool_name,
                    "arguments": parsed_args,
                },
                timeout=SWARM_DEFAULT_TOOL_TIMEOUT_SECONDS + 2.0,
            )
            return json.dumps(result, indent=2)
        except RuntimeError as exc:
            return json.dumps({SWARM_RESPONSE_KEY_ERROR: str(exc)})

    @mcp.tool()
    def swarm_status() -> str:
        """Get swarm connection status.

        Shows whether this node is connected to the swarm, the swarm ID,
        swarm URL, and current connection state.

        Returns:
            JSON string with swarm connection status.
        """
        try:
            result = _call_daemon(SWARM_DAEMON_API_PATH_STATUS)
            return json.dumps(result, indent=2)
        except RuntimeError as exc:
            return json.dumps({SWARM_RESPONSE_KEY_ERROR: str(exc)})

    @mcp.tool()
    def swarm_fetch(
        ids: list[str],
        project_slug: str = "",
    ) -> str:
        """Fetch full details for items found via swarm_search.

        Use this after swarm_search to get the complete content of specific
        results. Pass the chunk IDs and project slug from search results.

        Args:
            ids: List of chunk IDs from swarm_search results.
            project_slug: Project slug from the search result (used for routing).

        Returns:
            JSON string with full content for the requested items.
        """
        if not ids:
            return json.dumps({SWARM_RESPONSE_KEY_ERROR: "ids list is required"})

        try:
            result = _call_daemon(
                SWARM_DAEMON_API_PATH_FETCH,
                data={
                    "ids": ids,
                    "project_slug": project_slug,
                },
                timeout=SWARM_DEFAULT_FETCH_TIMEOUT_SECONDS + 2.0,
            )
            return json.dumps(result, indent=2)
        except RuntimeError as exc:
            return json.dumps({SWARM_RESPONSE_KEY_ERROR: str(exc)})

    return mcp


MCPTransport = Literal["stdio", "sse", "streamable-http"]


def run_mcp_server(transport: MCPTransport = "stdio") -> None:
    """Run the swarm MCP server.

    Args:
        transport: Transport type ('stdio', 'sse', or 'streamable-http').
    """
    mcp = create_mcp_server()
    mcp.run(transport=transport)


if __name__ == "__main__":
    transport_arg = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    run_mcp_server(cast(MCPTransport, transport_arg))
