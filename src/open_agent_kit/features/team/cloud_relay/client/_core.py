"""Core CloudRelayClient class and connection lifecycle.

Defines the main ``CloudRelayClient`` class (composed from domain-specific
mixins), WebSocket connection management, message dispatch loop, heartbeat
monitoring, and exponential-backoff reconnection.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from threading import RLock
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from open_agent_kit.features.team.cloud_relay.base import PolicyAccessor
    from open_agent_kit.features.team.relay.sync.obs_applier import (
        ObsApplierProtocol,
    )

import httpx
import websockets
from websockets.asyncio.client import ClientConnection
from websockets.typing import Subprotocol

from open_agent_kit.features.team.cloud_relay.base import (
    RelayClient,
    RelayStatus,
)
from open_agent_kit.features.team.cloud_relay.client._federation import (
    FederationMixin,
)
from open_agent_kit.features.team.cloud_relay.client._helpers import (
    _is_auth_failure,
)
from open_agent_kit.features.team.cloud_relay.client._obs_sync import (
    ObsSyncMixin,
)
from open_agent_kit.features.team.cloud_relay.client._proxy import (
    ProxyMixin,
)
from open_agent_kit.features.team.cloud_relay.client._swarm import (
    SwarmMixin,
)
from open_agent_kit.features.team.cloud_relay.protocol import (
    FederatedToolCallMessage,
    HeartbeatPong,
    HttpRequestMessage,
    RegisterMessage,
    RelayMessageType,
    SearchQueryMessage,
    ToolCallRequest,
)
from open_agent_kit.features.team.constants import (
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
    CLOUD_RELAY_CAPABILITY_FEDERATED_TOOLS,
    CLOUD_RELAY_CAPABILITY_OBS_SYNC,
    CLOUD_RELAY_CLIENT_NAME,
    CLOUD_RELAY_DEFAULT_RECONNECT_MAX_SECONDS,
    CLOUD_RELAY_DEFAULT_TOOL_TIMEOUT_SECONDS,
    CLOUD_RELAY_HEARTBEAT_INTERVAL_SECONDS,
    CLOUD_RELAY_HEARTBEAT_TIMEOUT_SECONDS,
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
    CLOUD_RELAY_WS_TYPE_SEARCH_QUERY,
    CLOUD_RELAY_WS_TYPE_TOOL_CALL,
)

logger = logging.getLogger(__name__)


class CloudRelayClient(ObsSyncMixin, FederationMixin, SwarmMixin, ProxyMixin, RelayClient):
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

        # Observation sync
        self._machine_id: str = ""
        self._online_nodes: list[dict] = []
        self._obs_applier: ObsApplierProtocol | None = None

        # Policy accessor (set during startup to read live governance config)
        self._policy_accessor: PolicyAccessor | None = None

        # Persistent HTTP client for daemon calls (created on connect, closed on disconnect)
        self._http_client: httpx.AsyncClient | None = None

        # Status tracking (thread-safe)
        self._lock = RLock()
        self._connected = False
        self._connected_at: str | None = None
        self._last_heartbeat: str | None = None
        self._error: str | None = None
        self._reconnect_attempts = 0
        self._should_reconnect = False

        # Swarm status from NODE_LIST broadcasts
        self._swarm_connected: bool = False
        self._swarm_id: str | None = None

        # Pending swarm request/response correlation (request_id -> Future)
        self._pending_swarm: dict[str, asyncio.Future[dict[str, Any]]] = {}

    @property
    def name(self) -> str:
        """Human-readable client name."""
        return CLOUD_RELAY_CLIENT_NAME

    @property
    def machine_id(self) -> str:
        """Local machine identifier."""
        return self._machine_id

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
        machine_id: str = "",
    ) -> RelayStatus:
        """Connect to the cloud relay worker.

        Args:
            worker_url: URL of the Cloudflare Worker (e.g., https://relay.example.workers.dev).
            token: Shared secret for authentication.
            daemon_port: Local daemon port for forwarding tool calls.
            machine_id: Unique identifier for this machine (used for obs sync).

        Returns:
            RelayStatus reflecting the connection state.
        """
        self._worker_url = worker_url
        self._token = token
        self._daemon_port = daemon_port
        self._machine_id = machine_id
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
                    # Expected when awaiting tasks we explicitly cancelled during disconnect.
                    pass

        self._reconnect_task = None
        self._heartbeat_task = None
        self._message_task = None

        # Fail-fast any pending swarm futures so callers don't hang
        for _req_id, fut in self._pending_swarm.items():
            if not fut.done():
                fut.set_exception(ConnectionError("Relay disconnected"))
        self._pending_swarm.clear()

        # Close persistent HTTP client
        if self._http_client and not self._http_client.is_closed:
            try:
                await self._http_client.aclose()
            except Exception:
                pass  # best-effort cleanup during disconnect
            self._http_client = None

        # Close WebSocket
        if self._ws:
            try:
                await self._ws.close(CLOUD_RELAY_WS_CLOSE_NORMAL)
            except Exception:
                # Best-effort socket close during disconnect; connection may already be gone.
                pass
            self._ws = None

        with self._lock:
            self._connected = False
            self._error = None
            self._reconnect_attempts = 0

        logger.info(CI_CLOUD_RELAY_LOG_DISCONNECTED)

    # ------------------------------------------------------------------
    # Internal: shared helpers
    # ------------------------------------------------------------------

    def _get_http_client(self) -> httpx.AsyncClient:
        """Return the shared HTTP client, creating one if needed."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient()
        return self._http_client

    def _auth_headers(self) -> dict[str, str]:
        """Build auth headers for daemon HTTP calls from the environment token."""
        import os

        headers: dict[str, str] = {}
        auth_token = os.environ.get(CI_AUTH_ENV_VAR)
        if auth_token:
            headers["Authorization"] = f"{CI_AUTH_SCHEME_BEARER} {auth_token}"
        return headers

    def _relay_auth_headers(self) -> dict[str, str]:
        """Build auth headers for relay Worker HTTP calls using the relay token."""
        if self._token:
            return {"Authorization": f"Bearer {self._token}"}
        return {}

    # ------------------------------------------------------------------
    # Internal: connection lifecycle
    # ------------------------------------------------------------------

    async def _establish_connection(self) -> None:
        """Open WebSocket, register, and start background loops."""
        # Create persistent HTTP client for daemon calls
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient()

        ws_url = self._build_ws_url()

        # Send relay token as Sec-WebSocket-Protocol for Worker auth.
        # The token must come first (auth.ts reads the first value), followed
        # by "oak-relay-v1" which the worker echoes back as the agreed protocol.
        subprotocols = (
            [Subprotocol(self._token), Subprotocol("oak-relay-v1")] if self._token else []
        )
        self._ws = await websockets.connect(ws_url, subprotocols=subprotocols)

        # Send registration message with available tools and version metadata.
        import open_agent_kit
        from open_agent_kit.features.team.cloud_relay.scaffold import (
            compute_template_hash,
        )

        tools = await self._get_available_tools()

        # Build capabilities list dynamically based on policy settings
        capabilities: list[str] = []
        policy = self._policy_accessor() if self._policy_accessor else None
        if policy is None or policy.sync_observations:
            capabilities.append(CLOUD_RELAY_CAPABILITY_OBS_SYNC)
        if policy is None or policy.federated_tools:
            capabilities.append(CLOUD_RELAY_CAPABILITY_FEDERATED_TOOLS)

        register_msg = RegisterMessage(
            token=self._token or "",
            tools=tools,
            machine_id=self._machine_id,
            oak_version=getattr(open_agent_kit, "__version__", ""),
            template_hash=compute_template_hash(),
            capabilities=capabilities,
        )
        await self._ws.send(register_msg.model_dump_json())

        # Wait for registered confirmation.  The relay may broadcast other
        # messages (e.g. node_list) to this socket before sending the
        # registered confirmation — skip those during the handshake.
        deadline = asyncio.get_event_loop().time() + CLOUD_RELAY_HEARTBEAT_TIMEOUT_SECONDS
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                raise ConnectionError("Timed out waiting for registration confirmation")
            raw = await asyncio.wait_for(
                self._ws.recv(),
                timeout=remaining,
            )
            msg = json.loads(raw)
            msg_type = msg.get(CLOUD_RELAY_WS_FIELD_TYPE)

            if msg_type == RelayMessageType.ERROR.value:
                error_text = msg.get(
                    CLOUD_RELAY_WS_FIELD_MESSAGE,
                    CLOUD_RELAY_WS_DEFAULT_REGISTRATION_REJECTED,
                )
                raise ConnectionError(error_text)

            if msg_type == RelayMessageType.REGISTERED.value:
                break

            # Skip non-registration messages (e.g. node_list broadcast)
            logger.debug("Skipping message during registration handshake: %s", msg_type)

        # Mark connected
        now_iso = datetime.now(UTC).isoformat()
        with self._lock:
            self._connected = True
            self._connected_at = now_iso
            self._last_heartbeat = now_iso
            self._error = None
            self._reconnect_attempts = 0

        logger.info(CI_CLOUD_RELAY_LOG_CONNECTED.format(worker_url=self._worker_url))

        # Start background loops first so heartbeats are handled while draining.
        self._message_task = asyncio.ensure_future(self._message_loop())
        self._heartbeat_task = asyncio.ensure_future(self._heartbeat_loop())

        # Drain any observations buffered by the relay while we were offline.
        # Runs after the message loop is live to avoid heartbeat timeouts.
        await self._drain_pending_obs()
        await self._drain_obs_history()

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

    # ------------------------------------------------------------------
    # Internal: message dispatch
    # ------------------------------------------------------------------

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
                        asyncio.create_task(self._handle_tool_call(request))

                    elif msg_type == RelayMessageType.HEARTBEAT.value:
                        now_iso = datetime.now(UTC).isoformat()
                        with self._lock:
                            self._last_heartbeat = now_iso
                        logger.debug(CI_CLOUD_RELAY_LOG_HEARTBEAT)
                        # Send pong
                        pong = HeartbeatPong(timestamp=now_iso)
                        await self._ws.send(pong.model_dump_json())

                    elif msg_type == RelayMessageType.NODE_LIST.value:
                        nodes = msg.get("nodes", [])
                        with self._lock:
                            self._online_nodes = nodes

                        # Check for swarm connection info
                        swarm_id = msg.get("swarm_id")
                        if swarm_id:
                            self._swarm_connected = True
                            self._swarm_id = swarm_id
                        else:
                            self._swarm_connected = False
                            self._swarm_id = None

                    elif msg_type == CLOUD_RELAY_WS_TYPE_SEARCH_QUERY:
                        query = SearchQueryMessage(**msg)
                        asyncio.create_task(self._handle_search_query(query))

                    elif msg_type == CLOUD_RELAY_WS_TYPE_TOOL_CALL:
                        # Federated tool call (different from direct tool_call)
                        if "request_id" in msg:
                            call = FederatedToolCallMessage(**msg)
                            asyncio.create_task(self._handle_federated_tool_call(call))

                    elif msg_type == RelayMessageType.HTTP_REQUEST.value:
                        http_req = HttpRequestMessage(**msg)
                        asyncio.create_task(self._handle_http_request(http_req))

                    elif msg_type == RelayMessageType.OBS_BATCH.value:
                        self._handle_obs_batch(msg)

                    elif msg_type in (
                        RelayMessageType.SWARM_SEARCH_RESULT.value,
                        RelayMessageType.SWARM_NODE_LIST.value,
                    ):
                        request_id = msg.get("request_id", "")
                        fut = self._pending_swarm.pop(request_id, None)
                        if fut and not fut.done():
                            fut.set_result(msg)

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

        # Connection lost — fail pending swarm futures so callers don't hang
        for _req_id, fut in self._pending_swarm.items():
            if not fut.done():
                fut.set_exception(ConnectionError("WebSocket connection lost"))
        self._pending_swarm.clear()

        # Mark disconnected and start reconnect
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
                        # Ignore malformed heartbeat timestamps and retry next interval.
                        pass

        except asyncio.CancelledError:
            return

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
                error_str = str(exc)
                logger.warning(CI_CLOUD_RELAY_LOG_ERROR.format(error=error_str))
                with self._lock:
                    self._error = error_str

                # Authentication failures (401/403) cannot be resolved by
                # retrying — the token is wrong.  Stop the loop and let the
                # user re-deploy via the Connectivity tab to re-sync tokens.
                if _is_auth_failure(exc):
                    self._should_reconnect = False
                    logger.error(
                        "Relay auth failed (token mismatch). "
                        "Go to Team → Connectivity and click Re-deploy to fix."
                    )
                    return

            # Exponential backoff
            delay = min(
                delay * CLOUD_RELAY_RECONNECT_BACKOFF_FACTOR,
                float(self._reconnect_max),
            )
