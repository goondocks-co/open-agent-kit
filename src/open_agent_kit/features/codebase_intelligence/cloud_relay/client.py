"""WebSocket-based Cloud MCP Relay client.

Maintains a persistent WebSocket connection to a Cloudflare Worker,
receives tool call requests from remote AI agents, forwards them to
the local daemon API, and returns the results.
"""

import asyncio
import json
import logging
from datetime import UTC, datetime
from threading import RLock
from typing import Any

import httpx
import websockets
from websockets.asyncio.client import ClientConnection
from websockets.typing import Subprotocol

from open_agent_kit.features.codebase_intelligence.cloud_relay.base import (
    RelayClient,
    RelayStatus,
)
from open_agent_kit.features.codebase_intelligence.cloud_relay.protocol import (
    HeartbeatPong,
    RegisterMessage,
    RelayMessageType,
    ToolCallRequest,
    ToolCallResponse,
)
from open_agent_kit.features.codebase_intelligence.constants import (
    CI_AUTH_ENV_VAR,
    CI_AUTH_SCHEME_BEARER,
    CI_CLOUD_RELAY_ERROR_CONNECT_FAILED,
    CI_CLOUD_RELAY_LOG_CONNECTED,
    CI_CLOUD_RELAY_LOG_CONNECTING,
    CI_CLOUD_RELAY_LOG_DISCONNECTED,
    CI_CLOUD_RELAY_LOG_ERROR,
    CI_CLOUD_RELAY_LOG_HEARTBEAT,
    CI_CLOUD_RELAY_LOG_HEARTBEAT_TIMEOUT,
    CI_CLOUD_RELAY_LOG_RECONNECTING,
    CLOUD_RELAY_CLIENT_NAME,
    CLOUD_RELAY_DAEMON_CALL_OVERHEAD_SECONDS,
    CLOUD_RELAY_DAEMON_MCP_CALL_URL_TEMPLATE,
    CLOUD_RELAY_DAEMON_MCP_TOOLS_RESPONSE_KEY,
    CLOUD_RELAY_DAEMON_MCP_TOOLS_URL_TEMPLATE,
    CLOUD_RELAY_DAEMON_TOOL_LIST_TIMEOUT_SECONDS,
    CLOUD_RELAY_DEFAULT_RECONNECT_MAX_SECONDS,
    CLOUD_RELAY_DEFAULT_TOOL_TIMEOUT_SECONDS,
    CLOUD_RELAY_HEARTBEAT_INTERVAL_SECONDS,
    CLOUD_RELAY_HEARTBEAT_TIMEOUT_SECONDS,
    CLOUD_RELAY_MAX_RESPONSE_BYTES,
    CLOUD_RELAY_RECONNECT_BACKOFF_FACTOR,
    CLOUD_RELAY_RECONNECT_BASE_DELAY_SECONDS,
    CLOUD_RELAY_WS_CLOSE_GOING_AWAY,
    CLOUD_RELAY_WS_CLOSE_NORMAL,
    CLOUD_RELAY_WS_DEFAULT_REGISTRATION_REJECTED,
    CLOUD_RELAY_WS_DEFAULT_UNKNOWN_RELAY_ERROR,
    CLOUD_RELAY_WS_ENDPOINT_PATH,
    CLOUD_RELAY_WS_FIELD_ARGUMENTS,
    CLOUD_RELAY_WS_FIELD_CALL_ID,
    CLOUD_RELAY_WS_FIELD_MESSAGE,
    CLOUD_RELAY_WS_FIELD_TIMEOUT_MS,
    CLOUD_RELAY_WS_FIELD_TOOL_NAME,
    CLOUD_RELAY_WS_FIELD_TYPE,
)

logger = logging.getLogger(__name__)


class CloudRelayClient(RelayClient):
    """WebSocket-based cloud relay client.

    Connects to a Cloudflare Worker via WebSocket, registers available
    MCP tools, and forwards incoming tool call requests to the local daemon.

    Thread-safe: status updates use a lock so get_status() can be called
    from any thread (e.g., HTTP handler thread).
    """

    def __init__(
        self,
        tool_timeout_seconds: int = CLOUD_RELAY_DEFAULT_TOOL_TIMEOUT_SECONDS,
        reconnect_max_seconds: int = CLOUD_RELAY_DEFAULT_RECONNECT_MAX_SECONDS,
    ) -> None:
        self._tool_timeout = tool_timeout_seconds
        self._reconnect_max = reconnect_max_seconds

        # Connection state
        self._ws: ClientConnection | None = None
        self._worker_url: str | None = None
        self._token: str | None = None
        self._daemon_port: int | None = None

        # Background tasks
        self._message_task: asyncio.Task[None] | None = None
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._reconnect_task: asyncio.Task[None] | None = None

        # Status tracking (thread-safe)
        self._lock = RLock()
        self._connected = False
        self._connected_at: str | None = None
        self._last_heartbeat: str | None = None
        self._error: str | None = None
        self._reconnect_attempts = 0
        self._should_reconnect = False

    @property
    def name(self) -> str:
        """Human-readable client name."""
        return CLOUD_RELAY_CLIENT_NAME

    def get_status(self) -> RelayStatus:
        """Get current relay connection status (thread-safe)."""
        with self._lock:
            return RelayStatus(
                connected=self._connected,
                worker_url=self._worker_url,
                connected_at=self._connected_at,
                last_heartbeat=self._last_heartbeat,
                error=self._error,
                reconnect_attempts=self._reconnect_attempts,
            )

    async def connect(
        self,
        worker_url: str,
        token: str,
        daemon_port: int,
    ) -> RelayStatus:
        """Connect to the cloud relay worker.

        Args:
            worker_url: URL of the Cloudflare Worker (e.g., https://relay.example.workers.dev).
            token: Shared secret for authentication.
            daemon_port: Local daemon port for forwarding tool calls.

        Returns:
            RelayStatus reflecting the connection state.
        """
        self._worker_url = worker_url
        self._token = token
        self._daemon_port = daemon_port
        self._should_reconnect = True

        logger.info(CI_CLOUD_RELAY_LOG_CONNECTING.format(worker_url=worker_url))

        try:
            await self._establish_connection()
        except Exception as exc:
            error_msg = CI_CLOUD_RELAY_ERROR_CONNECT_FAILED.format(error=str(exc))
            logger.error(error_msg)
            with self._lock:
                self._error = str(exc)
            # Start reconnect loop in background
            self._start_reconnect_loop()

        return self.get_status()

    async def disconnect(self) -> None:
        """Disconnect from the cloud relay and cancel background tasks."""
        self._should_reconnect = False

        # Cancel background tasks
        for task in (self._reconnect_task, self._heartbeat_task, self._message_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self._reconnect_task = None
        self._heartbeat_task = None
        self._message_task = None

        # Close WebSocket
        if self._ws:
            try:
                await self._ws.close(CLOUD_RELAY_WS_CLOSE_NORMAL)
            except Exception:
                pass
            self._ws = None

        with self._lock:
            self._connected = False
            self._error = None
            self._reconnect_attempts = 0

        logger.info(CI_CLOUD_RELAY_LOG_DISCONNECTED)

    # ------------------------------------------------------------------
    # Internal: connection lifecycle
    # ------------------------------------------------------------------

    async def _establish_connection(self) -> None:
        """Open WebSocket, register, and start background loops."""
        ws_url = self._build_ws_url()

        # Send relay token as Sec-WebSocket-Protocol for Worker auth.
        subprotocols = [Subprotocol(self._token)] if self._token else []
        self._ws = await websockets.connect(ws_url, subprotocols=subprotocols)

        # Send registration message with available tools
        tools = await self._get_available_tools()
        register_msg = RegisterMessage(token=self._token or "", tools=tools)
        await self._ws.send(register_msg.model_dump_json())

        # Wait for registered confirmation
        raw = await asyncio.wait_for(
            self._ws.recv(),
            timeout=CLOUD_RELAY_HEARTBEAT_TIMEOUT_SECONDS,
        )
        msg = json.loads(raw)
        msg_type = msg.get(CLOUD_RELAY_WS_FIELD_TYPE)

        if msg_type == RelayMessageType.ERROR.value:
            error_text = msg.get(
                CLOUD_RELAY_WS_FIELD_MESSAGE,
                CLOUD_RELAY_WS_DEFAULT_REGISTRATION_REJECTED,
            )
            raise ConnectionError(error_text)

        if msg_type != RelayMessageType.REGISTERED.value:
            raise ConnectionError(f"Unexpected response type: {msg_type}")

        # Mark connected
        now_iso = datetime.now(UTC).isoformat()
        with self._lock:
            self._connected = True
            self._connected_at = now_iso
            self._last_heartbeat = now_iso
            self._error = None
            self._reconnect_attempts = 0

        logger.info(CI_CLOUD_RELAY_LOG_CONNECTED.format(worker_url=self._worker_url))

        # Start background loops
        self._message_task = asyncio.ensure_future(self._message_loop())
        self._heartbeat_task = asyncio.ensure_future(self._heartbeat_loop())

    def _build_ws_url(self) -> str:
        """Build WebSocket URL from worker URL."""
        url = self._worker_url or ""
        # Convert https:// to wss://, http:// to ws://
        if url.startswith("https://"):
            url = "wss://" + url[len("https://") :]
        elif url.startswith("http://"):
            url = "ws://" + url[len("http://") :]
        elif not url.startswith(("ws://", "wss://")):
            url = "wss://" + url

        # Ensure WebSocket endpoint path
        if not url.endswith(CLOUD_RELAY_WS_ENDPOINT_PATH):
            url = url.rstrip("/") + CLOUD_RELAY_WS_ENDPOINT_PATH

        return url

    async def _message_loop(self) -> None:
        """Read messages from WebSocket and dispatch them."""
        try:
            assert self._ws is not None
            async for raw in self._ws:
                try:
                    msg = json.loads(raw)
                    msg_type = msg.get(CLOUD_RELAY_WS_FIELD_TYPE)

                    if msg_type == RelayMessageType.TOOL_CALL.value:
                        request = ToolCallRequest(
                            call_id=msg[CLOUD_RELAY_WS_FIELD_CALL_ID],
                            tool_name=msg[CLOUD_RELAY_WS_FIELD_TOOL_NAME],
                            arguments=msg.get(CLOUD_RELAY_WS_FIELD_ARGUMENTS, {}),
                            timeout_ms=msg.get(
                                CLOUD_RELAY_WS_FIELD_TIMEOUT_MS,
                                self._tool_timeout * 1000,
                            ),
                        )
                        # Handle tool call in background to not block the loop
                        asyncio.ensure_future(self._handle_tool_call(request))

                    elif msg_type == RelayMessageType.HEARTBEAT.value:
                        pong = HeartbeatPong(
                            timestamp=datetime.now(UTC).isoformat(),
                        )
                        await self._ws.send(pong.model_dump_json())
                        with self._lock:
                            self._last_heartbeat = pong.timestamp
                        logger.debug(CI_CLOUD_RELAY_LOG_HEARTBEAT)

                    elif msg_type == RelayMessageType.ERROR.value:
                        error_text = msg.get(
                            CLOUD_RELAY_WS_FIELD_MESSAGE,
                            CLOUD_RELAY_WS_DEFAULT_UNKNOWN_RELAY_ERROR,
                        )
                        logger.error(CI_CLOUD_RELAY_LOG_ERROR.format(error=error_text))
                        with self._lock:
                            self._error = error_text

                except (json.JSONDecodeError, KeyError, ValueError) as exc:
                    logger.warning("Invalid relay message: %s", exc)

        except websockets.ConnectionClosed:
            logger.info("WebSocket connection closed")
        except asyncio.CancelledError:
            return
        except Exception as exc:
            logger.error(CI_CLOUD_RELAY_LOG_ERROR.format(error=str(exc)))

        # Connection lost - mark disconnected and start reconnect
        with self._lock:
            self._connected = False

        if self._should_reconnect:
            self._start_reconnect_loop()

    async def _heartbeat_loop(self) -> None:
        """Periodically check connection health via heartbeat timing."""
        try:
            while True:
                await asyncio.sleep(CLOUD_RELAY_HEARTBEAT_INTERVAL_SECONDS)

                # Check if last heartbeat is too old
                with self._lock:
                    if not self._connected:
                        return
                    last_hb = self._last_heartbeat

                if last_hb:
                    try:
                        last_dt = datetime.fromisoformat(last_hb)
                        elapsed = (datetime.now(UTC) - last_dt).total_seconds()
                        threshold = (
                            CLOUD_RELAY_HEARTBEAT_INTERVAL_SECONDS
                            + CLOUD_RELAY_HEARTBEAT_TIMEOUT_SECONDS
                        )
                        if elapsed > threshold:
                            logger.warning(CI_CLOUD_RELAY_LOG_HEARTBEAT_TIMEOUT)
                            # Force close and reconnect
                            if self._ws:
                                await self._ws.close(CLOUD_RELAY_WS_CLOSE_GOING_AWAY)
                            return
                    except ValueError:
                        pass

        except asyncio.CancelledError:
            return

    # ------------------------------------------------------------------
    # Internal: tool call forwarding
    # ------------------------------------------------------------------

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
            response = ToolCallResponse(
                call_id=request.call_id,
                error=str(exc),
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
        import os

        if timeout is None:
            timeout = float(self._tool_timeout + CLOUD_RELAY_DAEMON_CALL_OVERHEAD_SECONDS)

        port = self._daemon_port
        url = CLOUD_RELAY_DAEMON_MCP_CALL_URL_TEMPLATE.format(port=port, tool_name=tool_name)

        # Read auth token from environment
        headers: dict[str, str] = {}
        auth_token = os.environ.get(CI_AUTH_ENV_VAR)
        if auth_token:
            headers["Authorization"] = f"{CI_AUTH_SCHEME_BEARER} {auth_token}"

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=arguments, headers=headers)
            response.raise_for_status()
            return response.json()

    async def _get_available_tools(self) -> list[dict[str, Any]]:
        """Get the list of available MCP tools from the daemon.

        Returns:
            List of tool descriptors (name, description, input_schema).
        """
        import os

        port = self._daemon_port
        url = CLOUD_RELAY_DAEMON_MCP_TOOLS_URL_TEMPLATE.format(port=port)

        headers: dict[str, str] = {}
        auth_token = os.environ.get(CI_AUTH_ENV_VAR)
        if auth_token:
            headers["Authorization"] = f"{CI_AUTH_SCHEME_BEARER} {auth_token}"

        try:
            async with httpx.AsyncClient(
                timeout=CLOUD_RELAY_DAEMON_TOOL_LIST_TIMEOUT_SECONDS,
            ) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
                tools: list[dict[str, Any]] = data.get(
                    CLOUD_RELAY_DAEMON_MCP_TOOLS_RESPONSE_KEY, []
                )
                return tools
        except Exception as exc:
            logger.warning("Failed to get tool list from daemon: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Internal: reconnection
    # ------------------------------------------------------------------

    def _start_reconnect_loop(self) -> None:
        """Start the reconnect loop if not already running."""
        if self._reconnect_task and not self._reconnect_task.done():
            return
        self._reconnect_task = asyncio.ensure_future(self._reconnect_loop())

    async def _reconnect_loop(self) -> None:
        """Reconnect with exponential backoff."""
        delay = CLOUD_RELAY_RECONNECT_BASE_DELAY_SECONDS

        while self._should_reconnect:
            with self._lock:
                self._reconnect_attempts += 1
                attempt = self._reconnect_attempts

            logger.info(CI_CLOUD_RELAY_LOG_RECONNECTING.format(attempt=attempt))

            try:
                await asyncio.sleep(delay)
                await self._establish_connection()
                # Success - reconnect loop done
                return
            except asyncio.CancelledError:
                return
            except Exception as exc:
                logger.warning(CI_CLOUD_RELAY_LOG_ERROR.format(error=str(exc)))
                with self._lock:
                    self._error = str(exc)

            # Exponential backoff
            delay = min(
                delay * CLOUD_RELAY_RECONNECT_BACKOFF_FACTOR,
                float(self._reconnect_max),
            )
