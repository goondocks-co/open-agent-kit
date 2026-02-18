"""Tests for CloudRelayClient (WebSocket-based cloud relay)."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from open_agent_kit.features.codebase_intelligence.cloud_relay.base import RelayStatus
from open_agent_kit.features.codebase_intelligence.cloud_relay.client import (
    CloudRelayClient,
)
from open_agent_kit.features.codebase_intelligence.cloud_relay.protocol import (
    ToolCallRequest,
)
from open_agent_kit.features.codebase_intelligence.constants import (
    CLOUD_RELAY_DEFAULT_RECONNECT_MAX_SECONDS,
    CLOUD_RELAY_DEFAULT_TOOL_TIMEOUT_SECONDS,
    CLOUD_RELAY_MAX_RESPONSE_BYTES,
    CLOUD_RELAY_WS_FIELD_TYPE,
    CLOUD_RELAY_WS_TYPE_REGISTERED,
)

from .fixtures import (
    TEST_CALL_ID,
    TEST_DAEMON_PORT,
    TEST_RELAY_TOKEN,
    TEST_TIMESTAMP,
    TEST_TOOL_ARGUMENTS,
    TEST_TOOL_NAME,
    TEST_WORKER_URL,
)


@pytest.fixture
def anyio_backend():
    """Restrict anyio tests to asyncio backend."""
    return "asyncio"


@pytest.fixture
def client() -> CloudRelayClient:
    """Create a fresh CloudRelayClient for each test."""
    return CloudRelayClient()


class TestClientInit:
    """Tests for client initialization."""

    def test_default_timeouts(self, client: CloudRelayClient) -> None:
        assert client._tool_timeout == CLOUD_RELAY_DEFAULT_TOOL_TIMEOUT_SECONDS
        assert client._reconnect_max == CLOUD_RELAY_DEFAULT_RECONNECT_MAX_SECONDS

    def test_custom_timeouts(self) -> None:
        custom = CloudRelayClient(tool_timeout_seconds=60, reconnect_max_seconds=120)
        assert custom._tool_timeout == 60
        assert custom._reconnect_max == 120

    def test_initial_status_disconnected(self, client: CloudRelayClient) -> None:
        status = client.get_status()
        assert status.connected is False
        assert status.worker_url is None
        assert status.error is None
        assert status.reconnect_attempts == 0

    def test_name_property(self, client: CloudRelayClient) -> None:
        assert client.name == "cloud-relay-websocket"


class TestClientConnect:
    """Tests for connect/disconnect lifecycle."""

    @pytest.mark.anyio
    async def test_connect_success(self, client: CloudRelayClient) -> None:
        """Successful connection returns connected status."""
        mock_ws = AsyncMock()
        mock_ws.recv = AsyncMock(
            return_value=json.dumps({CLOUD_RELAY_WS_FIELD_TYPE: CLOUD_RELAY_WS_TYPE_REGISTERED})
        )
        mock_ws.__aiter__ = AsyncMock(return_value=iter([]))

        with patch("websockets.connect", AsyncMock(return_value=mock_ws)):
            with patch.object(client, "_get_available_tools", AsyncMock(return_value=[])):
                status = await client.connect(TEST_WORKER_URL, TEST_RELAY_TOKEN, TEST_DAEMON_PORT)

        assert status.connected is True
        assert status.worker_url == TEST_WORKER_URL
        assert status.error is None

    @pytest.mark.anyio
    async def test_connect_failure_starts_reconnect(self, client: CloudRelayClient) -> None:
        """Failed connection sets error and attempts reconnect."""
        with patch("websockets.connect", AsyncMock(side_effect=ConnectionError("refused"))):
            with patch.object(client, "_get_available_tools", AsyncMock(return_value=[])):
                with patch.object(client, "_start_reconnect_loop"):
                    status = await client.connect(
                        TEST_WORKER_URL, TEST_RELAY_TOKEN, TEST_DAEMON_PORT
                    )

        assert status.connected is False
        assert status.error is not None

    @pytest.mark.anyio
    async def test_disconnect_cleans_up(self, client: CloudRelayClient) -> None:
        """Disconnect closes WebSocket and resets state."""
        mock_ws = AsyncMock()
        client._ws = mock_ws
        client._connected = True
        client._should_reconnect = True

        await client.disconnect()

        assert client._connected is False
        assert client._should_reconnect is False
        assert client._ws is None
        mock_ws.close.assert_called_once()

    @pytest.mark.anyio
    async def test_disconnect_when_not_connected(self, client: CloudRelayClient) -> None:
        """Disconnect is safe when already disconnected."""
        await client.disconnect()
        assert client._connected is False


class TestClientGetStatus:
    """Tests for get_status() thread safety."""

    def test_get_status_disconnected(self, client: CloudRelayClient) -> None:
        status = client.get_status()
        assert isinstance(status, RelayStatus)
        assert status.connected is False

    def test_get_status_connected(self, client: CloudRelayClient) -> None:
        with client._lock:
            client._connected = True
            client._worker_url = TEST_WORKER_URL
            client._connected_at = TEST_TIMESTAMP
            client._last_heartbeat = TEST_TIMESTAMP

        status = client.get_status()
        assert status.connected is True
        assert status.worker_url == TEST_WORKER_URL
        assert status.connected_at == TEST_TIMESTAMP


class TestClientWsUrl:
    """Tests for WebSocket URL building."""

    def test_https_to_wss(self, client: CloudRelayClient) -> None:
        client._worker_url = "https://relay.example.com"
        assert client._build_ws_url() == "wss://relay.example.com/ws"

    def test_http_to_ws(self, client: CloudRelayClient) -> None:
        client._worker_url = "http://localhost:8787"
        assert client._build_ws_url() == "ws://localhost:8787/ws"

    def test_already_wss(self, client: CloudRelayClient) -> None:
        client._worker_url = "wss://relay.example.com"
        assert client._build_ws_url() == "wss://relay.example.com/ws"

    def test_bare_hostname_gets_wss(self, client: CloudRelayClient) -> None:
        client._worker_url = "relay.example.com"
        assert client._build_ws_url() == "wss://relay.example.com/ws"

    def test_trailing_slash_stripped(self, client: CloudRelayClient) -> None:
        client._worker_url = "https://relay.example.com/"
        assert client._build_ws_url() == "wss://relay.example.com/ws"

    def test_already_has_ws_path(self, client: CloudRelayClient) -> None:
        client._worker_url = "wss://relay.example.com/ws"
        assert client._build_ws_url() == "wss://relay.example.com/ws"


class TestClientToolCallHandling:
    """Tests for tool call forwarding to local daemon."""

    @pytest.mark.anyio
    async def test_handle_tool_call_success(self, client: CloudRelayClient) -> None:
        """Tool call is forwarded to daemon and response sent back over WS."""
        client._ws = AsyncMock()
        client._daemon_port = TEST_DAEMON_PORT

        request = ToolCallRequest(
            call_id=TEST_CALL_ID,
            tool_name=TEST_TOOL_NAME,
            arguments=TEST_TOOL_ARGUMENTS,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "found"}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_http

            await client._handle_tool_call(request)

        client._ws.send.assert_called_once()
        sent_data = json.loads(client._ws.send.call_args[0][0])
        assert sent_data["call_id"] == TEST_CALL_ID
        assert sent_data["result"] == {"result": "found"}
        assert sent_data["error"] is None

    @pytest.mark.anyio
    async def test_handle_tool_call_error(self, client: CloudRelayClient) -> None:
        """Tool call error is captured and sent as error response."""
        client._ws = AsyncMock()
        client._daemon_port = TEST_DAEMON_PORT

        request = ToolCallRequest(
            call_id=TEST_CALL_ID,
            tool_name=TEST_TOOL_NAME,
        )

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(side_effect=Exception("connection refused"))
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_http

            await client._handle_tool_call(request)

        client._ws.send.assert_called_once()
        sent_data = json.loads(client._ws.send.call_args[0][0])
        assert sent_data["call_id"] == TEST_CALL_ID
        assert sent_data["error"] is not None
        assert sent_data["result"] is None

    @pytest.mark.anyio
    async def test_large_response_truncated(self, client: CloudRelayClient) -> None:
        """Responses exceeding max size are replaced with an error."""
        client._ws = AsyncMock()
        client._daemon_port = TEST_DAEMON_PORT

        request = ToolCallRequest(
            call_id=TEST_CALL_ID,
            tool_name=TEST_TOOL_NAME,
        )

        large_result = "x" * (CLOUD_RELAY_MAX_RESPONSE_BYTES + 1)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = large_result
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_http

            await client._handle_tool_call(request)

        sent_data = json.loads(client._ws.send.call_args[0][0])
        assert sent_data["error"] is not None
        assert "too large" in sent_data["error"].lower()
