"""MCP Protocol Server for Swarm Mode.

Provides native MCP protocol support for AI agents to discover and use
swarm tools (swarm_search, swarm_fetch, swarm_nodes, swarm_status) via stdio or HTTP transport.

The MCP server tries the cloud worker first (swarm_url + swarm_token),
falling back to the local swarm daemon HTTP API.
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
    SWARM_DAEMON_API_PATH_FETCH,
    SWARM_DAEMON_API_PATH_NODES,
    SWARM_DAEMON_API_PATH_SEARCH,
    SWARM_DAEMON_API_PATH_STATUS,
    SWARM_DAEMON_CONFIG_DIR,
    SWARM_DAEMON_DEFAULT_PORT,
    SWARM_DAEMON_PORT_FILE,
    SWARM_DEFAULT_FETCH_TIMEOUT_SECONDS,
    SWARM_MCP_TIMEOUT_PADDING_SECONDS,
    SWARM_RESPONSE_KEY_ERROR,
    SWARM_TOOL_FETCH,
    SWARM_TOOL_NODES,
    SWARM_TOOL_SEARCH,
    SWARM_TOOL_STATUS,
)
from open_agent_kit.features.swarm.tool_schema import SWARM_TOOL_DEFS_BY_NAME  # noqa: E402

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


def _load_cloud_config() -> tuple[str, str] | None:
    """Load cloud worker URL and agent token for direct cloud MCP access.

    Returns (swarm_url, agent_token) if both are available, None otherwise.
    """
    try:
        from open_agent_kit.config.paths import OAK_DIR
        from open_agent_kit.features.swarm.constants import (
            CI_CONFIG_KEY_SWARM,
            CI_CONFIG_SWARM_KEY_URL,
            SWARM_USER_CONFIG_KEY_AGENT_TOKEN,
            SWARM_USER_CONFIG_SECTION,
        )

        # Read swarm_url from .oak/config.yaml
        config_path = Path.cwd() / OAK_DIR / "config.yaml"
        if not config_path.exists():
            return None

        import yaml

        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        swarm_section = data.get(CI_CONFIG_KEY_SWARM, {})
        swarm_url = (
            swarm_section.get(CI_CONFIG_SWARM_KEY_URL) if isinstance(swarm_section, dict) else None
        )
        if not swarm_url:
            return None

        # Read agent_token from user config — this is the token for MCP access
        from open_agent_kit.features.team.config.user_store import read_user_value

        agent_token = read_user_value(
            Path.cwd(), SWARM_USER_CONFIG_SECTION, SWARM_USER_CONFIG_KEY_AGENT_TOKEN
        )
        if not agent_token:
            return None

        return (swarm_url, str(agent_token))
    except Exception as exc:
        logger.debug("Cloud config not available: %s", exc)
        return None


def create_mcp_server() -> FastMCP:
    """Create an MCP server that wraps the swarm REST API.

    Tries cloud worker first (swarm_url + agent_token), falls back to local daemon.

    Returns:
        FastMCP server instance configured with swarm tools.
    """
    # Try cloud-first
    cloud_config = _load_cloud_config()

    if cloud_config:
        swarm_url, agent_token = cloud_config
        base_url = swarm_url.rstrip("/")
        logger.info("MCP server using cloud worker: %s", base_url)
        auth_headers: dict[str, str] = {"Authorization": f"Bearer {agent_token}"}
    else:
        port = _find_daemon_port()
        base_url = f"http://localhost:{port}"
        logger.info("MCP server using local daemon: %s", base_url)
        auth_headers = {}

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
                response = http_client.post(
                    endpoint, json=data, timeout=timeout, headers=auth_headers
                )
            else:
                response = http_client.get(endpoint, timeout=timeout, headers=auth_headers)
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

        # Retry loop: daemon may be mid-restart (only transient connect errors)
        for _attempt in range(_CONNECT_RETRY_ATTEMPTS):
            time.sleep(_CONNECT_RETRY_DELAY_S)
            try:
                return _make_request()
            except httpx.ConnectError:
                continue
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(
                    f"Swarm daemon error: {exc.response.status_code} - {exc.response.text}"
                ) from exc

        if cloud_config:
            raise RuntimeError(
                f"Cloud swarm worker unreachable at {base_url}.\n"
                "Check your swarm_url and swarm_token configuration."
            )
        raise RuntimeError(
            "Swarm daemon is not running.\n"
            "Start it with: oak swarm start\n"
            f"Check logs in: {SWARM_DAEMON_CONFIG_DIR}"
        )

    @mcp.tool(description=SWARM_TOOL_DEFS_BY_NAME[SWARM_TOOL_SEARCH].description)
    def swarm_search(
        query: str,
        search_type: str = "all",
        limit: int = 10,
    ) -> str:
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

    @mcp.tool(description=SWARM_TOOL_DEFS_BY_NAME[SWARM_TOOL_NODES].description)
    def swarm_nodes() -> str:
        try:
            result = _call_daemon(SWARM_DAEMON_API_PATH_NODES)
            return json.dumps(result, indent=2)
        except RuntimeError as exc:
            return json.dumps({SWARM_RESPONSE_KEY_ERROR: str(exc)})

    @mcp.tool(description=SWARM_TOOL_DEFS_BY_NAME[SWARM_TOOL_STATUS].description)
    def swarm_status() -> str:
        try:
            result = _call_daemon(SWARM_DAEMON_API_PATH_STATUS)
            return json.dumps(result, indent=2)
        except RuntimeError as exc:
            return json.dumps({SWARM_RESPONSE_KEY_ERROR: str(exc)})

    @mcp.tool(description=SWARM_TOOL_DEFS_BY_NAME[SWARM_TOOL_FETCH].description)
    def swarm_fetch(
        ids: list[str],
        project_slug: str = "",
    ) -> str:
        if not ids:
            return json.dumps({SWARM_RESPONSE_KEY_ERROR: "ids list is required"})

        try:
            result = _call_daemon(
                SWARM_DAEMON_API_PATH_FETCH,
                data={
                    "ids": ids,
                    "project_slug": project_slug,
                },
                timeout=SWARM_DEFAULT_FETCH_TIMEOUT_SECONDS + SWARM_MCP_TIMEOUT_PADDING_SECONDS,
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
