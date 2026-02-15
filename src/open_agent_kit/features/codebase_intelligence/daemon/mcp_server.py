"""MCP Protocol Server for Codebase Intelligence.

Provides native MCP protocol support for AI agents to discover and use
CI tools (oak_search, oak_remember, oak_context) via stdio or HTTP transport.

The MCP server automatically starts the CI daemon if it's not running,
providing seamless integration with AI agents like Claude Code.
"""

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

# These imports must be after logging setup to prevent stdout corruption
from open_agent_kit.config.paths import OAK_DIR  # noqa: E402
from open_agent_kit.features.codebase_intelligence.constants import (  # noqa: E402
    CI_AUTH_SCHEME_BEARER,
    CI_DATA_DIR,
    CI_TOKEN_FILE,
)
from open_agent_kit.features.codebase_intelligence.daemon.manager import (  # noqa: E402
    DaemonManager,
    get_project_port,
)
from open_agent_kit.features.codebase_intelligence.exceptions import (  # noqa: E402
    DaemonConnectionError,
    DaemonError,
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

    # Auth token — read fresh from disk on every request to survive daemon restarts.
    # The file is 64 bytes with 0600 perms; the read overhead is negligible.
    token_path = ci_data_dir / CI_TOKEN_FILE

    def _read_auth_token() -> str | None:
        """Read auth token from the daemon token file."""
        try:
            if token_path.is_file():
                return token_path.read_text().strip() or None
        except OSError:
            pass
        return None

    mcp = FastMCP(
        "OAK Codebase Intelligence",
        json_response=True,
    )

    # Guard against rapid-fire auto-start attempts.  Reset on every
    # successful request so the MCP server can recover after a daemon restart.
    _auto_start_attempted = {"value": False}

    # Retry parameters for transient ConnectErrors (daemon restarting)
    _CONNECT_RETRY_ATTEMPTS = 3
    _CONNECT_RETRY_DELAY_S = 1.0

    def _ensure_daemon_running() -> bool:
        """Ensure the daemon is running, starting it if necessary.

        Returns:
            True if daemon is running, False if start failed.
        """
        manager = DaemonManager(project_root, port=port, ci_data_dir=ci_data_dir)

        if manager.is_running():
            return True

        # Only attempt auto-start once per failure cycle to avoid loops.
        # Reset happens in _call_daemon on success.
        if _auto_start_attempted["value"]:
            return False

        _auto_start_attempted["value"] = True
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

    def _call_daemon(
        endpoint: str,
        data: dict[str, Any] | None = None,
        method: str | None = None,
    ) -> dict[str, Any]:
        """Call the CI daemon REST API.

        Resilient to daemon restarts: reads the auth token fresh from disk
        on every call, retries briefly on ConnectError (daemon may be
        restarting), and resets the auto-start guard after each success so
        recovery is always possible.

        Args:
            endpoint: API endpoint path (e.g., "/api/search")
            data: JSON data to send (for POST/PUT requests)
            method: HTTP method override ('GET', 'POST', 'PUT'). If None,
                defaults to POST when data is provided, GET otherwise.

        Returns:
            Response JSON data.

        Raises:
            Exception: If daemon cannot be started or request fails.
        """
        url = f"{base_url}{endpoint}"

        def _make_request() -> dict[str, Any]:
            token = _read_auth_token()
            req_headers: dict[str, str] = {}
            if token:
                req_headers["Authorization"] = f"{CI_AUTH_SCHEME_BEARER} {token}"
            with httpx.Client(timeout=30.0) as client:
                # Determine HTTP method
                resolved_method = method
                if resolved_method is None:
                    resolved_method = "POST" if data is not None else "GET"
                resolved_method = resolved_method.upper()

                if resolved_method == "PUT":
                    response = client.put(url, json=data, headers=req_headers)
                elif resolved_method == "POST":
                    response = client.post(url, json=data, headers=req_headers)
                else:
                    response = client.get(url, headers=req_headers)
                response.raise_for_status()
                return cast(dict[str, Any], response.json())

        # --- Happy path (daemon is up, token is current) ---
        try:
            result = _make_request()
            _auto_start_attempted["value"] = False  # Success → allow future auto-starts
            return result
        except httpx.ConnectError:
            pass  # Fall through to retry / auto-start
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 401:
                raise DaemonError(
                    f"Daemon error: {e.response.status_code} - {e.response.text}"
                ) from e
            # 401 on first attempt — token was stale but we already read fresh,
            # so the daemon may still be starting up.  Fall through to retry.

        # --- Retry loop: daemon may be mid-restart (brief ConnectError window) ---
        for _attempt in range(_CONNECT_RETRY_ATTEMPTS):
            time.sleep(_CONNECT_RETRY_DELAY_S)
            try:
                result = _make_request()
                _auto_start_attempted["value"] = False
                return result
            except (httpx.ConnectError, httpx.HTTPStatusError):
                continue  # Keep trying

        # --- Auto-start: daemon appears fully down ---
        if _ensure_daemon_running():
            try:
                result = _make_request()
                _auto_start_attempted["value"] = False
                return result
            except (httpx.ConnectError, httpx.HTTPStatusError):
                pass  # Fall through to error

        raise DaemonConnectionError(
            f"CI daemon not running and auto-start failed.\n"
            f"Try manually: oak ci start\n"
            f"Check logs: {ci_data_dir / 'daemon.log'}"
        ) from None

    @mcp.tool()
    def oak_search(
        query: str,
        search_type: str = "all",
        limit: int = 10,
        include_resolved: bool = False,
    ) -> str:
        """Search the codebase and project memories using semantic similarity.

        Use this to find relevant code implementations, past decisions, gotchas,
        and learnings. Returns ranked results with relevance scores.

        Args:
            query: Natural language search query (e.g., 'authentication middleware')
            search_type: Search code, memories, or both. Options: 'all', 'code', 'memory'
            limit: Maximum results to return (1-50)
            include_resolved: If True, include resolved/superseded memories in results

        Returns:
            JSON string with search results containing code and memory matches.
        """
        result = _call_daemon(
            "/api/search",
            {
                "query": query,
                "search_type": search_type,
                "limit": min(max(1, limit), 50),
                "include_resolved": include_resolved,
            },
        )
        return json.dumps(result)

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
        return json.dumps(result)

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
        # tool_name must be a query parameter
        result = _call_daemon(
            "/api/mcp/call?tool_name=oak_context",
            data,
        )
        return json.dumps(result)

    @mcp.tool()
    def oak_resolve_memory(
        id: str,
        status: str = "resolved",
        reason: str | None = None,
    ) -> str:
        """Mark a memory observation as resolved or superseded.

        Use this after completing work that addresses a gotcha, fixing a bug that
        was tracked as an observation, or when a newer observation replaces an older one.

        Args:
            id: The observation UUID to resolve. Use oak_search to find the ID first
                (returned in each result's "id" field, e.g. "8430042a-1b01-4c86-8026-6ede46cd93d9").
            status: New status - 'resolved' (default) or 'superseded'.
            reason: Optional reason for resolution.

        Returns:
            JSON result of the status update.
        """
        data: dict[str, Any] = {"status": status}
        if reason:
            data["reason"] = reason
        result = _call_daemon(f"/api/memories/{id}/status", data=data, method="PUT")
        return json.dumps(result)

    # Note: oak_status is available via CLI (oak ci status) but not exposed as MCP tool

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
