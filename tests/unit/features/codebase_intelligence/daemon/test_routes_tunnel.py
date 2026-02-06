"""Tests for tunnel sharing routes.

Tests cover:
- Start tunnel endpoint
- Stop tunnel endpoint
- Status tunnel endpoint
- Error handling for missing config/provider
"""

from http import HTTPStatus
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from open_agent_kit.features.codebase_intelligence.constants import (
    CI_TUNNEL_API_PATH_START,
    CI_TUNNEL_API_PATH_STATUS,
    CI_TUNNEL_API_PATH_STOP,
    TUNNEL_API_STATUS_ALREADY_ACTIVE,
    TUNNEL_API_STATUS_NOT_ACTIVE,
    TUNNEL_API_STATUS_STOPPED,
    TUNNEL_RESPONSE_KEY_ACTIVE,
    TUNNEL_RESPONSE_KEY_PROVIDER,
    TUNNEL_RESPONSE_KEY_PUBLIC_URL,
    TUNNEL_RESPONSE_KEY_STATUS,
)
from open_agent_kit.features.codebase_intelligence.daemon.server import create_app
from open_agent_kit.features.codebase_intelligence.daemon.state import (
    get_state,
    reset_state,
)
from open_agent_kit.features.codebase_intelligence.tunnel.base import TunnelStatus

from ..tunnel.fixtures import (
    TEST_PROCESS_EXITED_MESSAGE,
    TEST_PROVIDER_CLOUDFLARED,
    TEST_STARTED_AT,
    TEST_URL_CLOUDFLARE,
    TEST_URL_CLOUDFLARE_EXISTING,
)


@pytest.fixture(autouse=True)
def reset_daemon_state():
    """Reset daemon state before and after each test."""
    reset_state()
    yield
    reset_state()


@pytest.fixture
def client():
    """FastAPI test client."""
    app = create_app()
    return TestClient(app)


class TestTunnelStatus:
    """Tests for GET /api/tunnel/status."""

    def test_status_no_tunnel(self, client: TestClient) -> None:
        """Returns inactive when no tunnel is configured."""
        response = client.get(CI_TUNNEL_API_PATH_STATUS)
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data[TUNNEL_RESPONSE_KEY_ACTIVE] is False
        assert data[TUNNEL_RESPONSE_KEY_PUBLIC_URL] is None
        assert data[TUNNEL_RESPONSE_KEY_PROVIDER] is None

    def test_status_active_tunnel(self, client: TestClient) -> None:
        """Returns active status when tunnel is running."""
        state = get_state()
        mock_provider = MagicMock()
        mock_provider.get_status.return_value = TunnelStatus(
            active=True,
            public_url=TEST_URL_CLOUDFLARE,
            provider_name=TEST_PROVIDER_CLOUDFLARED,
            started_at=TEST_STARTED_AT,
        )
        state.tunnel_provider = mock_provider

        response = client.get(CI_TUNNEL_API_PATH_STATUS)
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data[TUNNEL_RESPONSE_KEY_ACTIVE] is True
        assert data[TUNNEL_RESPONSE_KEY_PUBLIC_URL] == TEST_URL_CLOUDFLARE
        assert data[TUNNEL_RESPONSE_KEY_PROVIDER] == TEST_PROVIDER_CLOUDFLARED

    def test_status_dead_tunnel_cleanup(self, client: TestClient) -> None:
        """Cleans up tunnel_provider when tunnel died."""
        state = get_state()
        mock_provider = MagicMock()
        mock_provider.get_status.return_value = TunnelStatus(
            active=False,
            provider_name=TEST_PROVIDER_CLOUDFLARED,
            error=TEST_PROCESS_EXITED_MESSAGE,
        )
        state.tunnel_provider = mock_provider

        response = client.get(CI_TUNNEL_API_PATH_STATUS)
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data[TUNNEL_RESPONSE_KEY_ACTIVE] is False
        # Provider should be cleaned up
        assert state.tunnel_provider is None


class TestTunnelStop:
    """Tests for POST /api/tunnel/stop."""

    def test_stop_no_tunnel(self, client: TestClient) -> None:
        """Returns not_active when no tunnel is running."""
        response = client.post(CI_TUNNEL_API_PATH_STOP)
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data[TUNNEL_RESPONSE_KEY_STATUS] == TUNNEL_API_STATUS_NOT_ACTIVE

    def test_stop_active_tunnel(self, client: TestClient) -> None:
        """Stops an active tunnel and cleans up CORS."""
        state = get_state()
        mock_provider = MagicMock()
        mock_provider.get_status.return_value = TunnelStatus(
            active=True,
            public_url=TEST_URL_CLOUDFLARE,
            provider_name=TEST_PROVIDER_CLOUDFLARED,
        )
        state.tunnel_provider = mock_provider
        state.add_cors_origin(TEST_URL_CLOUDFLARE)

        response = client.post(CI_TUNNEL_API_PATH_STOP)
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data[TUNNEL_RESPONSE_KEY_STATUS] == TUNNEL_API_STATUS_STOPPED
        assert state.tunnel_provider is None
        assert TEST_URL_CLOUDFLARE not in state.get_dynamic_cors_origins()
        mock_provider.stop.assert_called_once()


class TestTunnelStart:
    """Tests for POST /api/tunnel/start."""

    def test_start_no_config(self, client: TestClient) -> None:
        """Returns error when config not loaded."""
        state = get_state()
        state.ci_config = None

        response = client.post(CI_TUNNEL_API_PATH_START)
        assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR

    def test_start_already_active(self, client: TestClient) -> None:
        """Returns already_active when tunnel is running."""
        state = get_state()
        mock_provider = MagicMock()
        mock_provider.get_status.return_value = TunnelStatus(
            active=True,
            public_url=TEST_URL_CLOUDFLARE_EXISTING,
            provider_name=TEST_PROVIDER_CLOUDFLARED,
            started_at=TEST_STARTED_AT,
        )
        state.tunnel_provider = mock_provider

        response = client.post(CI_TUNNEL_API_PATH_START)
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data[TUNNEL_RESPONSE_KEY_STATUS] == TUNNEL_API_STATUS_ALREADY_ACTIVE
        assert data[TUNNEL_RESPONSE_KEY_PUBLIC_URL] == TEST_URL_CLOUDFLARE_EXISTING
