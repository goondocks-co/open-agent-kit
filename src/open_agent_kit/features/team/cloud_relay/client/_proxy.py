"""Proxy and daemon-forwarding mixin for CloudRelayClient.

Handles tool call forwarding (from relay to local daemon), HTTP proxy
requests, and the internal ``_call_daemon`` / ``_get_available_tools``
helpers used by multiple mixins.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from open_agent_kit.features.team.cloud_relay.protocol import (
    HttpRequestMessage,
    HttpResponseMessage,
    ToolCallRequest,
    ToolCallResponse,
)
from open_agent_kit.features.team.constants import (
    CLOUD_RELAY_DAEMON_CALL_OVERHEAD_SECONDS,
    CLOUD_RELAY_DAEMON_HTTP_PROXY_URL_TEMPLATE,
    CLOUD_RELAY_DAEMON_MCP_CALL_URL_TEMPLATE,
    CLOUD_RELAY_DAEMON_MCP_TOOLS_RESPONSE_KEY,
    CLOUD_RELAY_DAEMON_MCP_TOOLS_URL_TEMPLATE,
    CLOUD_RELAY_DAEMON_TOOL_LIST_TIMEOUT_SECONDS,
    CLOUD_RELAY_HTTP_PROXY_TIMEOUT_SECONDS,
    CLOUD_RELAY_MAX_RESPONSE_BYTES,
)

logger = logging.getLogger(__name__)


class ProxyMixin:
    """Mixin providing tool call forwarding and HTTP proxy methods."""

    # Attributes set by CloudRelayClient.__init__
    _ws: Any
    _daemon_port: int | None
    _tool_timeout: int

    # Methods provided by other mixins / core (declared for mypy)
    _get_http_client: Any
    _auth_headers: Any

    async def _handle_tool_call(self, request: ToolCallRequest) -> None:
        """Handle a tool call request by forwarding to the local daemon.

        Args:
            request: The tool call request from the worker.
        """
        try:
            timeout = request.timeout_ms / 1000.0
            result = await self._call_daemon(
                request.tool_name,
                request.arguments,
                timeout=timeout,
            )

            response = ToolCallResponse(
                call_id=request.call_id,
                result=result,
            )
        except Exception as exc:
            logger.warning("Tool call %s failed: %s", request.tool_name, exc)
            response = ToolCallResponse(
                call_id=request.call_id,
                error="Internal tool call error",
            )

        # Serialize and truncate if needed
        payload = response.model_dump_json()
        if len(payload.encode()) > CLOUD_RELAY_MAX_RESPONSE_BYTES:
            response = ToolCallResponse(
                call_id=request.call_id,
                error=f"Response too large ({len(payload.encode())} bytes, "
                f"max {CLOUD_RELAY_MAX_RESPONSE_BYTES})",
            )
            payload = response.model_dump_json()

        if self._ws:
            try:
                await self._ws.send(payload)
            except Exception as exc:
                logger.error("Failed to send tool response: %s", exc)

    async def _handle_http_request(self, request: HttpRequestMessage) -> None:
        """Handle an HTTP proxy request by forwarding to the local daemon.

        Only paths matching CLOUD_RELAY_ALLOWED_PROXY_PREFIXES are forwarded;
        all others are rejected with 403 to prevent SSRF.

        Args:
            request: The HTTP request message from the worker.
        """
        from open_agent_kit.features.team.constants import (
            CI_RELAY_DAEMON_AUTH_HEADER,
            CI_RELAY_SOURCE_HEADER,
            CI_RELAY_SOURCE_VALUE,
            CLOUD_RELAY_ALLOWED_PROXY_PREFIXES,
            CLOUD_RELAY_PROXY_FORBIDDEN_STATUS,
        )

        # SSRF protection: reject paths outside the allowlist
        if not any(
            request.path.startswith(prefix) for prefix in CLOUD_RELAY_ALLOWED_PROXY_PREFIXES
        ):
            logger.warning("Blocked proxy request to disallowed path: %s", request.path)
            response = HttpResponseMessage(
                request_id=request.request_id,
                status=CLOUD_RELAY_PROXY_FORBIDDEN_STATUS,
                body="Forbidden: path not in proxy allowlist",
            )
            if self._ws:
                try:
                    await self._ws.send(response.model_dump_json())
                except Exception as exc:
                    logger.error("Failed to send proxy forbidden response: %s", exc)
            return

        try:
            port = self._daemon_port
            url = CLOUD_RELAY_DAEMON_HTTP_PROXY_URL_TEMPLATE.format(port=port, path=request.path)

            # Mark as relay traffic so middleware reads daemon auth from the
            # dedicated header, leaving Authorization for the team API key.
            fwd_headers = dict(request.headers) if request.headers else {}
            fwd_headers[CI_RELAY_SOURCE_HEADER] = CI_RELAY_SOURCE_VALUE
            daemon_auth = self._auth_headers()
            if "Authorization" in daemon_auth:
                fwd_headers[CI_RELAY_DAEMON_AUTH_HEADER] = daemon_auth["Authorization"]

            client = self._get_http_client()
            resp = await client.request(
                method=request.method,
                url=url,
                headers=fwd_headers,
                content=request.body,
                timeout=CLOUD_RELAY_HTTP_PROXY_TIMEOUT_SECONDS,
            )

            response_headers = dict(resp.headers)
            response = HttpResponseMessage(
                request_id=request.request_id,
                status=resp.status_code,
                headers=response_headers,
                body=resp.text,
            )
        except Exception as exc:
            logger.error("HTTP proxy request failed: %s", exc)
            response = HttpResponseMessage(
                request_id=request.request_id,
                status=502,
                body="Internal proxy error",
            )

        if self._ws:
            try:
                await self._ws.send(response.model_dump_json())
            except Exception as exc:
                logger.error("Failed to send HTTP proxy response: %s", exc)

    async def _call_daemon(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        timeout: float | None = None,
    ) -> Any:
        """Call the local daemon MCP tool endpoint.

        Args:
            tool_name: MCP tool name to call.
            arguments: Tool arguments.
            timeout: Request timeout in seconds.

        Returns:
            Tool result from the daemon.

        Raises:
            Exception: If the daemon call fails.
        """
        if timeout is None:
            timeout = float(self._tool_timeout + CLOUD_RELAY_DAEMON_CALL_OVERHEAD_SECONDS)

        port = self._daemon_port
        url = CLOUD_RELAY_DAEMON_MCP_CALL_URL_TEMPLATE.format(port=port, tool_name=tool_name)

        client = self._get_http_client()
        response = await client.post(
            url, json=arguments, headers=self._auth_headers(), timeout=timeout
        )
        response.raise_for_status()
        return response.json()

    async def _get_available_tools(self) -> list[dict[str, Any]]:
        """Get the list of available MCP tools from the daemon.

        Returns:
            List of tool descriptors (name, description, input_schema).
        """
        port = self._daemon_port
        url = CLOUD_RELAY_DAEMON_MCP_TOOLS_URL_TEMPLATE.format(port=port)

        # Retry with backoff — the daemon HTTP server may not be ready at startup.
        max_attempts = 5
        delay = 1.0
        for attempt in range(1, max_attempts + 1):
            try:
                client = self._get_http_client()
                response = await client.get(
                    url,
                    headers=self._auth_headers(),
                    timeout=CLOUD_RELAY_DAEMON_TOOL_LIST_TIMEOUT_SECONDS,
                )
                response.raise_for_status()
                data = response.json()
                tools: list[dict[str, Any]] = data.get(
                    CLOUD_RELAY_DAEMON_MCP_TOOLS_RESPONSE_KEY, []
                )
                return tools
            except Exception as exc:
                if attempt < max_attempts:
                    logger.debug(
                        "Tool list fetch attempt %d failed, retrying in %.0fs: %s",
                        attempt,
                        delay,
                        exc,
                    )
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 8.0)
                else:
                    logger.warning(
                        "Failed to get tool list from daemon after %d attempts: %s",
                        max_attempts,
                        exc,
                    )
                    return []
        return []  # unreachable, satisfies type checker
