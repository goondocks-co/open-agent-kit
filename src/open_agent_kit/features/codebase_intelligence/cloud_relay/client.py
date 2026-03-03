"""WebSocket-based Cloud MCP Relay client.

Maintains a persistent WebSocket connection to a Cloudflare Worker,
receives tool call requests from remote AI agents, forwards them to
the local daemon API, and returns the results.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from threading import RLock
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.cloud_relay.base import PolicyAccessor
    from open_agent_kit.features.codebase_intelligence.team.sync.obs_applier import (
        ObsApplierProtocol,
    )

import httpx
import websockets
from websockets.asyncio.client import ClientConnection
from websockets.typing import Subprotocol

from open_agent_kit.features.codebase_intelligence.cloud_relay.base import (
    RelayClient,
    RelayStatus,
)
from open_agent_kit.features.codebase_intelligence.cloud_relay.protocol import (
    FederatedToolCallMessage,
    FederatedToolResultMessage,
    HeartbeatPong,
    HttpRequestMessage,
    HttpResponseMessage,
    ObsPushMessage,
    RegisterMessage,
    RelayMessageType,
    SearchQueryMessage,
    SearchResultMessage,
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
    CLOUD_RELAY_CAPABILITY_FEDERATED_SEARCH,
    CLOUD_RELAY_CAPABILITY_FEDERATED_TOOLS,
    CLOUD_RELAY_CAPABILITY_OBS_SYNC,
    CLOUD_RELAY_CLIENT_NAME,
    CLOUD_RELAY_DAEMON_CALL_OVERHEAD_SECONDS,
    CLOUD_RELAY_DAEMON_HTTP_PROXY_URL_TEMPLATE,
    CLOUD_RELAY_DAEMON_MCP_CALL_URL_TEMPLATE,
    CLOUD_RELAY_DAEMON_MCP_TOOLS_RESPONSE_KEY,
    CLOUD_RELAY_DAEMON_MCP_TOOLS_URL_TEMPLATE,
    CLOUD_RELAY_DAEMON_SEARCH_TIMEOUT_SECONDS,
    CLOUD_RELAY_DAEMON_SEARCH_URL_TEMPLATE,
    CLOUD_RELAY_DAEMON_TOOL_LIST_TIMEOUT_SECONDS,
    CLOUD_RELAY_DEFAULT_RECONNECT_MAX_SECONDS,
    CLOUD_RELAY_DEFAULT_TOOL_TIMEOUT_SECONDS,
    CLOUD_RELAY_ERROR_FEDERATION_DISABLED,
    CLOUD_RELAY_FEDERATE_TOOL_PATH,
    CLOUD_RELAY_FEDERATED_SEARCH_TIMEOUT_SECONDS,
    CLOUD_RELAY_FEDERATED_TOOL_TIMEOUT_SECONDS,
    CLOUD_RELAY_HEARTBEAT_INTERVAL_SECONDS,
    CLOUD_RELAY_HEARTBEAT_TIMEOUT_SECONDS,
    CLOUD_RELAY_HTTP_PROXY_TIMEOUT_SECONDS,
    CLOUD_RELAY_MAX_RESPONSE_BYTES,
    CLOUD_RELAY_OBS_DRAIN_TIMEOUT_SECONDS,
    CLOUD_RELAY_OBS_HISTORY_PATH,
    CLOUD_RELAY_RECONNECT_BACKOFF_FACTOR,
    CLOUD_RELAY_RECONNECT_BASE_DELAY_SECONDS,
    CLOUD_RELAY_SEARCH_PATH,
    CLOUD_RELAY_TOOL_CALL_PATH,
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


def _is_auth_failure(exc: BaseException) -> bool:
    """Check whether an exception indicates an HTTP auth failure (401/403).

    Inspects typed exception attributes rather than fragile string matching.
    Handles websockets.exceptions.InvalidStatus (WS handshake rejection)
    and httpx.HTTPStatusError (HTTP response errors).
    """
    from open_agent_kit.features.codebase_intelligence.constants import (
        CLOUD_RELAY_AUTH_FAILURE_STATUS_CODES,
    )

    # websockets raises InvalidStatus with response.status_code on handshake rejection
    try:
        from websockets.exceptions import InvalidStatus

        if isinstance(exc, InvalidStatus):
            return exc.response.status_code in CLOUD_RELAY_AUTH_FAILURE_STATUS_CODES
    except ImportError:
        pass  # websockets not installed; skip this check

    # httpx raises HTTPStatusError with response.status_code
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in CLOUD_RELAY_AUTH_FAILURE_STATUS_CODES

    # ConnectionError from _establish_connection carries the error text from the
    # relay, but we only detect auth from typed exceptions above.
    return False


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
                    pass

        self._reconnect_task = None
        self._heartbeat_task = None
        self._message_task = None

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

    async def _establish_connection(self) -> None:
        """Open WebSocket, register, and start background loops."""
        # Create persistent HTTP client for daemon calls
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient()

        ws_url = self._build_ws_url()

        # Send relay token as Sec-WebSocket-Protocol for Worker auth.
        subprotocols = [Subprotocol(self._token)] if self._token else []
        self._ws = await websockets.connect(ws_url, subprotocols=subprotocols)

        # Send registration message with available tools and version metadata.
        import open_agent_kit
        from open_agent_kit.features.codebase_intelligence.cloud_relay.scaffold import (
            compute_template_hash,
        )

        tools = await self._get_available_tools()

        # Build capabilities list dynamically based on policy settings
        capabilities: list[str] = []
        policy = self._policy_accessor() if self._policy_accessor else None
        if policy is None or policy.sync_observations:
            capabilities.append(CLOUD_RELAY_CAPABILITY_OBS_SYNC)
        if policy is None or policy.federated_tools:
            capabilities.append(CLOUD_RELAY_CAPABILITY_FEDERATED_SEARCH)
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

                    elif msg_type == RelayMessageType.HTTP_REQUEST.value:
                        http_req = HttpRequestMessage(
                            request_id=msg["request_id"],
                            method=msg["method"],
                            path=msg["path"],
                            headers=msg.get("headers", {}),
                            body=msg.get("body"),
                        )
                        asyncio.ensure_future(self._handle_http_request(http_req))

                    elif msg_type == RelayMessageType.OBS_BATCH.value:
                        self._handle_obs_batch(msg)

                    elif msg_type == RelayMessageType.NODE_LIST.value:
                        with self._lock:
                            self._online_nodes = msg.get("nodes", [])

                    elif msg_type == CLOUD_RELAY_WS_TYPE_SEARCH_QUERY:
                        query_msg = SearchQueryMessage(
                            request_id=msg["request_id"],
                            query=msg["query"],
                            search_type=msg.get("search_type", "all"),
                            limit=msg.get("limit", 10),
                            from_machine_id=msg.get("from_machine_id", ""),
                        )
                        asyncio.ensure_future(self._handle_search_query(query_msg))

                    elif msg_type == RelayMessageType.FEDERATED_TOOL_CALL.value:
                        fed_call = FederatedToolCallMessage(
                            request_id=msg["request_id"],
                            tool_name=msg["tool_name"],
                            arguments=msg.get("arguments", {}),
                            from_machine_id=msg.get("from_machine_id", ""),
                        )
                        asyncio.ensure_future(self._handle_federated_tool_call(fed_call))

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
    # Observation sync
    # ------------------------------------------------------------------

    def set_obs_applier(self, applier: ObsApplierProtocol) -> None:
        """Set the applier for incoming obs batches from peer nodes."""
        self._obs_applier = applier

    def set_policy_accessor(self, accessor: PolicyAccessor) -> None:
        """Set a callable that returns the current DataCollectionPolicy."""
        self._policy_accessor = accessor

    def _is_federation_allowed(self) -> bool:
        """Check if federated tools are allowed by the current policy."""
        if not self._policy_accessor:
            return True
        policy = self._policy_accessor()
        return policy is None or policy.federated_tools

    async def request_reconnect(self) -> None:
        """Close the WebSocket to trigger a reconnect with updated capabilities."""
        if self._ws:
            try:
                await self._ws.close()
            except Exception as exc:
                logger.debug("Error closing WS for reconnect: %s", exc)

    @property
    def online_nodes(self) -> list[dict]:
        """List of online nodes from relay presence updates."""
        with self._lock:
            return list(self._online_nodes)

    async def push_observations(self, observations: list[dict]) -> None:
        """Push observations to peer nodes via relay WebSocket.

        Raises on failure so the outbox worker can mark events for retry
        instead of incorrectly marking them as sent.
        """
        if not self._ws or not self._connected:
            logger.debug("Relay not connected, skipping obs push (will retry on next tick)")
            return
        msg = ObsPushMessage(observations=observations)
        await self._ws.send(msg.model_dump_json())

    async def _drain_pending_obs(self) -> None:
        """Drain buffered observations from the relay (called on reconnect)."""
        if not self._worker_url or not self._token or not self._machine_id:
            return
        if not self._http_client or self._http_client.is_closed:
            return
        try:
            url = f"{self._worker_url.rstrip('/')}/obs/pending?machine_id={self._machine_id}"
            resp = await self._http_client.get(
                url,
                headers=self._relay_auth_headers(),
                timeout=CLOUD_RELAY_OBS_DRAIN_TIMEOUT_SECONDS,
            )
            if resp.status_code == 200:
                data = resp.json()
                observations = data.get("observations", [])
                if observations and self._obs_applier is not None:
                    for item in observations:
                        self._obs_applier.apply_batch([item["obs"]], item["from_machine_id"])
        except Exception as exc:
            logger.warning("Failed to drain pending obs: %s", exc)

    async def _drain_obs_history(self) -> None:
        """Drain observation history from the relay (called on reconnect).

        Fetches historical observations that were recorded while this node
        was offline. Paginates with ``offset`` until an empty page is returned.
        Deduplication is handled by content_hash checks in RemoteObsApplier.
        """
        if not self._worker_url or not self._token or not self._machine_id:
            return
        if self._obs_applier is None:
            return
        if not self._http_client or self._http_client.is_closed:
            return

        try:
            base_url = (
                f"{self._worker_url.rstrip('/')}"
                f"{CLOUD_RELAY_OBS_HISTORY_PATH}?machine_id={self._machine_id}"
            )
            headers = self._relay_auth_headers()
            offset = 0

            while True:
                url = f"{base_url}&offset={offset}"
                resp = await self._http_client.get(
                    url,
                    headers=headers,
                    timeout=CLOUD_RELAY_OBS_DRAIN_TIMEOUT_SECONDS,
                )
                if resp.status_code != 200:
                    break
                data = resp.json()
                observations = data.get("observations", [])
                if not observations:
                    break
                for item in observations:
                    self._obs_applier.apply_batch([item["obs"]], item["from_machine_id"])
                offset += len(observations)
        except Exception as exc:
            logger.warning("Failed to drain obs history: %s", exc)

    def _handle_obs_batch(self, data: dict) -> None:
        """Handle incoming obs_batch from a peer node."""
        if self._obs_applier is None:
            obs_count = len(data.get("observations", []))
            logger.warning(
                "Dropping %d obs from %s: no obs applier configured",
                obs_count,
                data.get("from_machine_id", "unknown"),
            )
            return
        from_machine_id = data.get("from_machine_id", "unknown")
        observations = data.get("observations", [])
        try:
            self._obs_applier.apply_batch(observations, from_machine_id)
        except Exception as exc:
            logger.error("Failed to apply remote obs batch: %s", exc)

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

            client = self._http_client or httpx.AsyncClient()
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
        to all nodes with the ``federated_search_v1`` capability and
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

            client = self._http_client or httpx.AsyncClient()
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
    ) -> dict[str, Any]:
        """Fan out a tool call to all peer nodes and collect results.

        Sends an HTTP POST to the relay worker which fans the call out
        to all nodes with the ``federated_tools_v1`` capability.

        Args:
            tool_name: MCP tool name to call on peers.
            arguments: Tool arguments.
            timeout: Request timeout in seconds.

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

            client = self._http_client or httpx.AsyncClient()
            resp = await client.post(
                url,
                json={
                    "tool_name": tool_name,
                    "arguments": arguments,
                },
                headers=self._relay_auth_headers(),
                timeout=http_timeout,
            )
            resp.raise_for_status()
            data: dict[str, Any] = resp.json()
            return data
        except Exception as exc:
            logger.warning("Federated tool call failed: %s", exc)
            return {"results": [], "error": str(exc)}

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

            client = self._http_client or httpx.AsyncClient()
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
        from open_agent_kit.features.codebase_intelligence.constants import (
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

            client = self._http_client or httpx.AsyncClient()
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

        client = self._http_client or httpx.AsyncClient()
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

        try:
            client = self._http_client or httpx.AsyncClient()
            response = await client.get(
                url,
                headers=self._auth_headers(),
                timeout=CLOUD_RELAY_DAEMON_TOOL_LIST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            data = response.json()
            tools: list[dict[str, Any]] = data.get(CLOUD_RELAY_DAEMON_MCP_TOOLS_RESPONSE_KEY, [])
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
