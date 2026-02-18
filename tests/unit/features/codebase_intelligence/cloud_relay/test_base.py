"""Tests for cloud relay base classes."""

import pytest

from open_agent_kit.features.codebase_intelligence.cloud_relay.base import (
    RelayClient,
    RelayStatus,
)
from open_agent_kit.features.codebase_intelligence.constants import (
    CLOUD_RELAY_RESPONSE_KEY_CONNECTED,
    CLOUD_RELAY_RESPONSE_KEY_CONNECTED_AT,
    CLOUD_RELAY_RESPONSE_KEY_ERROR,
    CLOUD_RELAY_RESPONSE_KEY_LAST_HEARTBEAT,
    CLOUD_RELAY_RESPONSE_KEY_RECONNECT_ATTEMPTS,
    CLOUD_RELAY_RESPONSE_KEY_WORKER_URL,
)

from .fixtures import (
    TEST_CONNECTED_AT,
    TEST_ERROR_AUTH_FAILED,
    TEST_HEARTBEAT_AT,
    TEST_WORKER_URL,
)


class TestRelayStatus:
    """Tests for RelayStatus dataclass."""

    def test_connected_status(self) -> None:
        """Connected status has all fields populated."""
        status = RelayStatus(
            connected=True,
            worker_url=TEST_WORKER_URL,
            connected_at=TEST_CONNECTED_AT,
            last_heartbeat=TEST_HEARTBEAT_AT,
        )
        assert status.connected is True
        assert status.worker_url == TEST_WORKER_URL
        assert status.connected_at == TEST_CONNECTED_AT
        assert status.last_heartbeat == TEST_HEARTBEAT_AT
        assert status.error is None
        assert status.reconnect_attempts == 0

    def test_disconnected_status_defaults(self) -> None:
        """Disconnected status has sensible defaults."""
        status = RelayStatus(connected=False)
        assert status.connected is False
        assert status.worker_url is None
        assert status.connected_at is None
        assert status.last_heartbeat is None
        assert status.error is None
        assert status.reconnect_attempts == 0

    def test_error_status(self) -> None:
        """Error status includes error message and reconnect count."""
        status = RelayStatus(
            connected=False,
            worker_url=TEST_WORKER_URL,
            error=TEST_ERROR_AUTH_FAILED,
            reconnect_attempts=3,
        )
        assert status.connected is False
        assert status.error == TEST_ERROR_AUTH_FAILED
        assert status.reconnect_attempts == 3

    def test_to_dict(self) -> None:
        """to_dict returns proper dictionary with constant keys."""
        status = RelayStatus(
            connected=True,
            worker_url=TEST_WORKER_URL,
            connected_at=TEST_CONNECTED_AT,
            last_heartbeat=TEST_HEARTBEAT_AT,
        )
        d = status.to_dict()
        assert d == {
            CLOUD_RELAY_RESPONSE_KEY_CONNECTED: True,
            CLOUD_RELAY_RESPONSE_KEY_WORKER_URL: TEST_WORKER_URL,
            CLOUD_RELAY_RESPONSE_KEY_CONNECTED_AT: TEST_CONNECTED_AT,
            CLOUD_RELAY_RESPONSE_KEY_LAST_HEARTBEAT: TEST_HEARTBEAT_AT,
            CLOUD_RELAY_RESPONSE_KEY_ERROR: None,
            CLOUD_RELAY_RESPONSE_KEY_RECONNECT_ATTEMPTS: 0,
        }

    def test_to_dict_disconnected(self) -> None:
        """to_dict handles disconnected status with error."""
        status = RelayStatus(
            connected=False,
            error=TEST_ERROR_AUTH_FAILED,
            reconnect_attempts=5,
        )
        d = status.to_dict()
        assert d[CLOUD_RELAY_RESPONSE_KEY_CONNECTED] is False
        assert d[CLOUD_RELAY_RESPONSE_KEY_ERROR] == TEST_ERROR_AUTH_FAILED
        assert d[CLOUD_RELAY_RESPONSE_KEY_RECONNECT_ATTEMPTS] == 5
        assert d[CLOUD_RELAY_RESPONSE_KEY_WORKER_URL] is None


class TestRelayClientABC:
    """Tests for RelayClient abstract class."""

    def test_cannot_instantiate(self) -> None:
        """Cannot instantiate abstract class directly."""
        with pytest.raises(TypeError):
            RelayClient()  # type: ignore[abstract]

    def test_concrete_subclass(self) -> None:
        """Concrete subclass must implement all abstract methods."""

        class FakeClient(RelayClient):
            @property
            def name(self) -> str:
                return "fake-client"

            async def connect(self, worker_url: str, token: str, daemon_port: int) -> RelayStatus:
                return RelayStatus(connected=True, worker_url=worker_url)

            async def disconnect(self) -> None:
                pass

            def get_status(self) -> RelayStatus:
                return RelayStatus(connected=False)

        client = FakeClient()
        assert client.name == "fake-client"
        assert client.get_status().connected is False
