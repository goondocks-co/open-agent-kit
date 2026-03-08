"""Federation mixin for CloudRelayClient.

Handles federated search queries, federated tool calls (fan-out to all
peer nodes), relay metrics, and targeted remote tool calls.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from open_agent_kit.features.team.cloud_relay.protocol import (
    FederatedToolCallMessage,
    FederatedToolResultMessage,
    SearchQueryMessage,
    SearchResultMessage,
)
from open_agent_kit.features.team.constants import (
    CLOUD_RELAY_DAEMON_SEARCH_TIMEOUT_SECONDS,
    CLOUD_RELAY_DAEMON_SEARCH_URL_TEMPLATE,
    CLOUD_RELAY_ERROR_FEDERATION_DISABLED,
    CLOUD_RELAY_FEDERATE_TOOL_PATH,
    CLOUD_RELAY_FEDERATED_SEARCH_TIMEOUT_SECONDS,
    CLOUD_RELAY_FEDERATED_TOOL_TIMEOUT_SECONDS,
    CLOUD_RELAY_MAX_RESPONSE_BYTES,
    CLOUD_RELAY_METRICS_PATH,
    CLOUD_RELAY_METRICS_TIMEOUT_SECONDS,
    CLOUD_RELAY_SEARCH_PATH,
    CLOUD_RELAY_TOOL_CALL_PATH,
    CLOUD_RELAY_WS_TYPE_TOOL_CALL,
)

logger = logging.getLogger(__name__)


class FederationMixin:
    """Mixin providing federated search and tool call methods."""

    # Attributes set by CloudRelayClient.__init__
    _ws: Any
    _worker_url: str | None
    _token: str | None
    _machine_id: str
    _daemon_port: int | None
    _policy_accessor: Any

    # Methods provided by other mixins / core (declared for mypy)
    _get_http_client: Any
    _auth_headers: Any
    _relay_auth_headers: Any
    _call_daemon: Any

    def _is_federation_allowed(self) -> bool:
        """Check if federated tools are allowed by the current policy."""
        if not self._policy_accessor:
            return True
        policy = self._policy_accessor()
        return policy is None or policy.federated_tools

    # ------------------------------------------------------------------
    # Federated search
    # ------------------------------------------------------------------

    async def _handle_search_query(self, query: SearchQueryMessage) -> None:
        """Handle an incoming search query by querying the local daemon.

        Follows the same pattern as _handle_tool_call: run the local call,
        build a response, apply the size guard, and send over WebSocket.

        Args:
            query: The search query message from the relay.
        """
        # Check policy before executing
        if not self._is_federation_allowed():
            response = SearchResultMessage(
                request_id=query.request_id,
                from_machine_id=self._machine_id,
                error=CLOUD_RELAY_ERROR_FEDERATION_DISABLED,
            )
            if self._ws:
                await self._ws.send(response.model_dump_json())
            return

        try:
            port = self._daemon_port
            url = CLOUD_RELAY_DAEMON_SEARCH_URL_TEMPLATE.format(port=port)

            client = self._get_http_client()
            resp = await client.post(
                url,
                json={
                    "query": query.query,
                    "search_type": query.search_type,
                    "limit": query.limit,
                },
                headers=self._auth_headers(),
                timeout=CLOUD_RELAY_DAEMON_SEARCH_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            data = resp.json()

            # Local /api/search returns {code, memory, plans, sessions}.
            # Flatten into a single results list, tagging each with its type.
            results: list[dict] = []
            for item in data.get("memory", []):
                item["_result_type"] = "memory"
                results.append(item)
            for item in data.get("plans", []):
                item["_result_type"] = "plan"
                results.append(item)
            for item in data.get("sessions", []):
                item["_result_type"] = "session"
                results.append(item)
            # Skip code — project-specific, not meaningful across nodes.

            response = SearchResultMessage(
                request_id=query.request_id,
                results=results,
                from_machine_id=self._machine_id,
            )
        except Exception as exc:
            logger.warning("Failed to handle search query: %s", exc)
            response = SearchResultMessage(
                request_id=query.request_id,
                from_machine_id=self._machine_id,
                error="Internal search error",
            )

        # Serialize and truncate if needed (same guard as _handle_tool_call)
        payload = response.model_dump_json()
        if len(payload.encode()) > CLOUD_RELAY_MAX_RESPONSE_BYTES:
            response = SearchResultMessage(
                request_id=query.request_id,
                from_machine_id=self._machine_id,
                error=f"Search response too large ({len(payload.encode())} bytes, "
                f"max {CLOUD_RELAY_MAX_RESPONSE_BYTES})",
            )
            payload = response.model_dump_json()

        if self._ws:
            try:
                await self._ws.send(payload)
            except Exception as exc:
                logger.error("Failed to send search result: %s", exc)

    async def search_network(
        self,
        query: str,
        search_type: str = "all",
        limit: int = 10,
    ) -> dict[str, Any]:
        """Initiate a federated search across connected relay nodes.

        Sends an HTTP POST to the relay worker which fans the query out
        to all nodes with the ``federated_tools_v1`` capability and
        aggregates results.

        Args:
            query: Search query string.
            search_type: Type of search (e.g., "all", "code", "memory").
            limit: Maximum number of results per node.

        Returns:
            Dict with ``results`` list and optional ``error`` key.
        """
        if not self._worker_url or not self._token:
            return {"results": [], "error": "Relay not configured"}

        try:
            url = (
                f"{self._worker_url.rstrip('/')}"
                f"{CLOUD_RELAY_SEARCH_PATH}?machine_id={self._machine_id}"
            )
            timeout = CLOUD_RELAY_FEDERATED_SEARCH_TIMEOUT_SECONDS + 1.0

            client = self._get_http_client()
            resp = await client.post(
                url,
                json={
                    "query": query,
                    "search_type": search_type,
                    "limit": limit,
                },
                headers=self._relay_auth_headers(),
                timeout=timeout,
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            return data
        except Exception as exc:
            logger.warning("Federated search failed: %s", exc)
            return {"results": [], "error": str(exc)}

    # ------------------------------------------------------------------
    # Federated tool calls (generic fan-out)
    # ------------------------------------------------------------------

    async def _handle_federated_tool_call(self, call: FederatedToolCallMessage) -> None:
        """Handle an incoming federated tool call by executing locally.

        Follows the same pattern as _handle_search_query: run the local call,
        build a response, apply the size guard, and send over WebSocket.
        """
        # Check policy before executing
        if not self._is_federation_allowed():
            response = FederatedToolResultMessage(
                request_id=call.request_id,
                from_machine_id=self._machine_id,
                error=CLOUD_RELAY_ERROR_FEDERATION_DISABLED,
            )
            if self._ws:
                await self._ws.send(response.model_dump_json())
            return

        try:
            result = await self._call_daemon(
                call.tool_name,
                call.arguments,
            )

            response = FederatedToolResultMessage(
                request_id=call.request_id,
                result=result,
                from_machine_id=self._machine_id,
            )
        except Exception as exc:
            logger.warning("Federated tool call %s failed: %s", call.tool_name, exc)
            response = FederatedToolResultMessage(
                request_id=call.request_id,
                from_machine_id=self._machine_id,
                error="Internal tool call error",
            )

        # Serialize and truncate if needed (same guard as _handle_tool_call)
        payload = response.model_dump_json()
        payload_size = len(payload.encode())
        if payload_size > CLOUD_RELAY_MAX_RESPONSE_BYTES:
            response = FederatedToolResultMessage(
                request_id=call.request_id,
                from_machine_id=self._machine_id,
                error=f"Response too large ({payload_size} bytes, "
                f"max {CLOUD_RELAY_MAX_RESPONSE_BYTES})",
            )
            payload = response.model_dump_json()

        if self._ws:
            try:
                await self._ws.send(payload)
            except Exception as exc:
                logger.error("Failed to send federated tool result: %s", exc)

    async def federate_tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        timeout: float = 10.0,
        *,
        no_cache: bool = False,
    ) -> dict[str, Any]:
        """Fan out a tool call to all peer nodes and collect results.

        Sends an HTTP POST to the relay worker which fans the call out
        to all nodes with the ``federated_tools_v1`` capability.

        Args:
            tool_name: MCP tool name to call on peers.
            arguments: Tool arguments.
            timeout: Request timeout in seconds.
            no_cache: If True, bypass the relay-side result cache.

        Returns:
            Dict with ``results`` list (each entry has from_machine_id, result, error).
        """
        if not self._worker_url or not self._token:
            return {"results": [], "error": "Relay not configured"}

        try:
            url = (
                f"{self._worker_url.rstrip('/')}"
                f"{CLOUD_RELAY_FEDERATE_TOOL_PATH}?machine_id={self._machine_id}"
            )
            http_timeout = max(timeout, CLOUD_RELAY_FEDERATED_TOOL_TIMEOUT_SECONDS) + 1.0

            body: dict[str, Any] = {
                "tool_name": tool_name,
                "arguments": arguments,
            }
            if no_cache:
                body["no_cache"] = True

            client = self._get_http_client()
            resp = await client.post(
                url,
                json=body,
                headers=self._relay_auth_headers(),
                timeout=http_timeout,
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            return data
        except Exception as exc:
            logger.warning("Federated tool call failed: %s", exc)
            return {"results": [], "error": str(exc)}

    async def fetch_relay_metrics(self) -> dict[str, Any]:
        """Fetch federation metrics from the relay worker.

        Returns:
            Dict with cache hit/miss counts, per-tool stats, and recent
            latencies.  Returns ``{"error": ...}`` on failure.
        """
        if not self._worker_url or not self._token:
            return {"error": "Relay not configured"}

        try:
            url = f"{self._worker_url.rstrip('/')}{CLOUD_RELAY_METRICS_PATH}"
            client = self._get_http_client()
            resp = await client.get(
                url,
                headers=self._relay_auth_headers(),
                timeout=CLOUD_RELAY_METRICS_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            return data
        except Exception as exc:
            logger.debug("Failed to fetch relay metrics: %s", exc)
            return {"error": str(exc)}

    async def call_remote_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        target_machine_id: str,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """Call a tool on a specific remote node via the relay.

        Args:
            tool_name: MCP tool name to call.
            arguments: Tool arguments.
            target_machine_id: Machine ID of the target node.
            timeout: Request timeout in seconds.

        Returns:
            Dict with tool result or error.
        """
        if not self._worker_url or not self._token:
            return {"error": "Relay not configured"}

        try:
            url = (
                f"{self._worker_url.rstrip('/')}"
                f"{CLOUD_RELAY_TOOL_CALL_PATH}?machine_id={target_machine_id}"
            )
            body = {
                "type": CLOUD_RELAY_WS_TYPE_TOOL_CALL,
                "call_id": str(uuid4()),
                "tool_name": tool_name,
                "arguments": arguments,
                "timeout_ms": int(timeout * 1000),
            }

            client = self._get_http_client()
            resp = await client.post(
                url,
                json=body,
                headers=self._relay_auth_headers(),
                timeout=timeout,
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            return data
        except Exception as exc:
            logger.warning("Remote tool call to %s failed: %s", target_machine_id, exc)
            return {"error": str(exc)}
