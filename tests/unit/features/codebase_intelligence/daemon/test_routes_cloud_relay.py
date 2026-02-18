"""Tests for cloud relay routes.

Tests cover:
- POST /api/cloud/connect
- POST /api/cloud/disconnect
- GET /api/cloud/status
- POST /api/cloud/start
- POST /api/cloud/stop
- GET /api/cloud/preflight
- Error handling for missing config/worker_url/token
"""

from http import HTTPStatus
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from open_agent_kit.features.codebase_intelligence.cloud_relay.base import RelayStatus
from open_agent_kit.features.codebase_intelligence.cloud_relay.deploy import (
    WranglerAuthInfo,
)
from open_agent_kit.features.codebase_intelligence.config import (
    CIConfig,
    CloudRelayConfig,
)
from open_agent_kit.features.codebase_intelligence.constants import (
    CI_CLOUD_RELAY_API_PATH_CONNECT,
    CI_CLOUD_RELAY_API_PATH_DISCONNECT,
    CI_CLOUD_RELAY_API_PATH_PREFLIGHT,
    CI_CLOUD_RELAY_API_PATH_SETTINGS,
    CI_CLOUD_RELAY_API_PATH_START,
    CI_CLOUD_RELAY_API_PATH_STATUS,
    CI_CLOUD_RELAY_API_PATH_STOP,
    CI_CLOUD_RELAY_ERROR_CONFIG_NOT_LOADED,
    CI_CLOUD_RELAY_ERROR_NO_TOKEN,
    CI_CLOUD_RELAY_ERROR_NO_WORKER_URL,
    CLOUD_RELAY_API_STATUS_ALREADY_CONNECTED,
    CLOUD_RELAY_API_STATUS_CONNECTED,
    CLOUD_RELAY_API_STATUS_DISCONNECTED,
    CLOUD_RELAY_API_STATUS_NOT_CONNECTED,
    CLOUD_RELAY_MCP_ENDPOINT_SUFFIX,
    CLOUD_RELAY_PHASE_AUTH_CHECK,
    CLOUD_RELAY_PHASE_DEPLOY,
    CLOUD_RELAY_RESPONSE_KEY_AGENT_TOKEN,
    CLOUD_RELAY_RESPONSE_KEY_CF_ACCOUNT_NAME,
    CLOUD_RELAY_RESPONSE_KEY_CONNECTED,
    CLOUD_RELAY_RESPONSE_KEY_CUSTOM_DOMAIN,
    CLOUD_RELAY_RESPONSE_KEY_ERROR,
    CLOUD_RELAY_RESPONSE_KEY_MCP_ENDPOINT,
    CLOUD_RELAY_RESPONSE_KEY_PHASE,
    CLOUD_RELAY_RESPONSE_KEY_STATUS,
    CLOUD_RELAY_RESPONSE_KEY_WORKER_NAME,
    CLOUD_RELAY_RESPONSE_KEY_WORKER_URL,
    CLOUD_RELAY_START_STATUS_ERROR,
    CLOUD_RELAY_START_STATUS_OK,
)
from open_agent_kit.features.codebase_intelligence.daemon.server import create_app
from open_agent_kit.features.codebase_intelligence.daemon.state import (
    get_state,
    reset_state,
)

from ..cloud_relay.fixtures import (
    TEST_AGENT_TOKEN,
    TEST_CONNECTED_AT,
    TEST_DAEMON_PORT,
    TEST_HEARTBEAT_AT,
    TEST_RELAY_TOKEN,
    TEST_WORKER_URL,
    TEST_WORKER_URL_ALTERNATE,
)

# Patch paths — functions are lazily imported inside route handlers, so we
# patch at the *source* module where each function is defined.
_PATCH_GET_PORT = (
    "open_agent_kit.features.codebase_intelligence.daemon.routes.cloud_relay._get_daemon_port"
)
_PATCH_CLIENT_CLS = (
    "open_agent_kit.features.codebase_intelligence.cloud_relay.client.CloudRelayClient"
)
_SCAFFOLD_MODULE = "open_agent_kit.features.codebase_intelligence.cloud_relay.scaffold"
_DEPLOY_MODULE = "open_agent_kit.features.codebase_intelligence.cloud_relay.deploy"
_CONFIG_MODULE = "open_agent_kit.features.codebase_intelligence.config"
_PATCH_IS_SCAFFOLDED = f"{_SCAFFOLD_MODULE}.is_scaffolded"
_PATCH_RENDER_TEMPLATE = f"{_SCAFFOLD_MODULE}.render_worker_template"
_PATCH_RENDER_WRANGLER = f"{_SCAFFOLD_MODULE}.render_wrangler_config"
_PATCH_GENERATE_TOKEN = f"{_SCAFFOLD_MODULE}.generate_token"
_PATCH_MAKE_WORKER_NAME = f"{_SCAFFOLD_MODULE}.make_worker_name"
_PATCH_RUN_NPM_INSTALL = f"{_DEPLOY_MODULE}.run_npm_install"
_PATCH_CHECK_WRANGLER_AUTH = f"{_DEPLOY_MODULE}.check_wrangler_auth"
_PATCH_RUN_WRANGLER_DEPLOY = f"{_DEPLOY_MODULE}.run_wrangler_deploy"
_PATCH_CHECK_WRANGLER_AVAILABLE = f"{_DEPLOY_MODULE}.check_wrangler_available"
_PATCH_LOAD_CI_CONFIG = f"{_CONFIG_MODULE}.load_ci_config"
_PATCH_SAVE_CI_CONFIG = f"{_CONFIG_MODULE}.save_ci_config"

FAKE_PROJECT_ROOT = Path("/tmp/fake-project")


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


def _setup_state_with_config(
    worker_url: str | None = None,
    token: str | None = None,
) -> None:
    """Set up daemon state with CI config.

    Args:
        worker_url: Optional worker URL in config.
        token: Optional relay token in config.
    """
    state = get_state()
    state.ci_config = CIConfig()
    state.ci_config.cloud_relay = CloudRelayConfig(
        worker_url=worker_url,
        token=token,
    )


class TestCloudRelayStatus:
    """Tests for GET /api/cloud/status."""

    def test_status_no_client(self, client: TestClient) -> None:
        """Returns disconnected when no cloud relay client is active."""
        response = client.get(CI_CLOUD_RELAY_API_PATH_STATUS)
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data[CLOUD_RELAY_RESPONSE_KEY_CONNECTED] is False
        assert data[CLOUD_RELAY_RESPONSE_KEY_WORKER_URL] is None
        assert data[CLOUD_RELAY_RESPONSE_KEY_ERROR] is None

    def test_status_connected_client(self, client: TestClient) -> None:
        """Returns connected status when cloud relay client is active."""
        state = get_state()
        mock_client = MagicMock()
        mock_client.get_status.return_value = RelayStatus(
            connected=True,
            worker_url=TEST_WORKER_URL,
            connected_at=TEST_CONNECTED_AT,
            last_heartbeat=TEST_HEARTBEAT_AT,
        )
        state.cloud_relay_client = mock_client

        response = client.get(CI_CLOUD_RELAY_API_PATH_STATUS)
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data[CLOUD_RELAY_RESPONSE_KEY_CONNECTED] is True
        assert data[CLOUD_RELAY_RESPONSE_KEY_WORKER_URL] == TEST_WORKER_URL

    def test_status_disconnected_client_with_error(self, client: TestClient) -> None:
        """Returns error info when client exists but is disconnected with error."""
        state = get_state()
        mock_client = MagicMock()
        mock_client.get_status.return_value = RelayStatus(
            connected=False,
            worker_url=TEST_WORKER_URL,
            error="connection lost",
            reconnect_attempts=3,
        )
        state.cloud_relay_client = mock_client

        response = client.get(CI_CLOUD_RELAY_API_PATH_STATUS)
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data[CLOUD_RELAY_RESPONSE_KEY_CONNECTED] is False
        assert data[CLOUD_RELAY_RESPONSE_KEY_ERROR] == "connection lost"


class TestCloudRelayDisconnect:
    """Tests for POST /api/cloud/disconnect."""

    def test_disconnect_no_client(self, client: TestClient) -> None:
        """Returns not_connected when no cloud relay is active."""
        response = client.post(CI_CLOUD_RELAY_API_PATH_DISCONNECT)
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["status"] == CLOUD_RELAY_API_STATUS_NOT_CONNECTED

    def test_disconnect_active_client(self, client: TestClient) -> None:
        """Disconnects and cleans up active client."""
        state = get_state()
        mock_client = AsyncMock()
        state.cloud_relay_client = mock_client

        response = client.post(CI_CLOUD_RELAY_API_PATH_DISCONNECT)
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["status"] == CLOUD_RELAY_API_STATUS_DISCONNECTED
        assert state.cloud_relay_client is None
        mock_client.disconnect.assert_called_once()

    def test_disconnect_error_still_cleans_up(self, client: TestClient) -> None:
        """Client is cleaned up even if disconnect() raises."""
        state = get_state()
        mock_client = AsyncMock()
        mock_client.disconnect.side_effect = Exception("ws error")
        state.cloud_relay_client = mock_client

        response = client.post(CI_CLOUD_RELAY_API_PATH_DISCONNECT)
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["status"] == CLOUD_RELAY_API_STATUS_DISCONNECTED
        # Client should still be cleaned up
        assert state.cloud_relay_client is None


class TestCloudRelayConnect:
    """Tests for POST /api/cloud/connect."""

    def test_connect_no_config(self, client: TestClient) -> None:
        """Returns error when CI config not loaded."""
        state = get_state()
        state.ci_config = None
        state.project_root = None  # prevent lazy-load from disk

        response = client.post(
            CI_CLOUD_RELAY_API_PATH_CONNECT,
            json={"worker_url": TEST_WORKER_URL, "token": TEST_RELAY_TOKEN},
        )
        assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
        assert CI_CLOUD_RELAY_ERROR_CONFIG_NOT_LOADED in response.json()["detail"]

    def test_connect_no_worker_url(self, client: TestClient) -> None:
        """Returns error when no worker URL provided."""
        _setup_state_with_config()

        response = client.post(
            CI_CLOUD_RELAY_API_PATH_CONNECT,
            json={"token": TEST_RELAY_TOKEN},
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert CI_CLOUD_RELAY_ERROR_NO_WORKER_URL in response.json()["detail"]

    def test_connect_no_token(self, client: TestClient) -> None:
        """Returns error when no token provided."""
        _setup_state_with_config(worker_url=TEST_WORKER_URL)

        response = client.post(CI_CLOUD_RELAY_API_PATH_CONNECT, json={})
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert CI_CLOUD_RELAY_ERROR_NO_TOKEN in response.json()["detail"]

    def test_connect_already_connected(self, client: TestClient) -> None:
        """Returns already_connected when client exists and is connected."""
        state = get_state()
        state.ci_config = CIConfig()
        mock_client = MagicMock()
        mock_client.get_status.return_value = RelayStatus(
            connected=True,
            worker_url=TEST_WORKER_URL,
        )
        state.cloud_relay_client = mock_client

        response = client.post(
            CI_CLOUD_RELAY_API_PATH_CONNECT,
            json={"worker_url": TEST_WORKER_URL_ALTERNATE, "token": TEST_RELAY_TOKEN},
        )
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["status"] == CLOUD_RELAY_API_STATUS_ALREADY_CONNECTED
        assert data[CLOUD_RELAY_RESPONSE_KEY_WORKER_URL] == TEST_WORKER_URL

    def test_connect_success(self, client: TestClient) -> None:
        """Successful connect creates client and returns connected status."""
        _setup_state_with_config()

        mock_instance = AsyncMock()
        mock_instance.connect = AsyncMock(
            return_value=RelayStatus(connected=True, worker_url=TEST_WORKER_URL)
        )

        with (
            patch(_PATCH_GET_PORT, return_value=TEST_DAEMON_PORT),
            patch(_PATCH_CLIENT_CLS, return_value=mock_instance),
        ):
            response = client.post(
                CI_CLOUD_RELAY_API_PATH_CONNECT,
                json={"worker_url": TEST_WORKER_URL, "token": TEST_RELAY_TOKEN},
            )
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["status"] == CLOUD_RELAY_API_STATUS_CONNECTED
        assert data[CLOUD_RELAY_RESPONSE_KEY_CONNECTED] is True

    def test_connect_uses_config_url_and_token(self, client: TestClient) -> None:
        """Falls back to config values when body is empty."""
        _setup_state_with_config(worker_url=TEST_WORKER_URL, token=TEST_RELAY_TOKEN)

        mock_instance = AsyncMock()
        mock_instance.connect = AsyncMock(
            return_value=RelayStatus(connected=True, worker_url=TEST_WORKER_URL)
        )

        with (
            patch(_PATCH_GET_PORT, return_value=TEST_DAEMON_PORT),
            patch(_PATCH_CLIENT_CLS, return_value=mock_instance),
        ):
            response = client.post(CI_CLOUD_RELAY_API_PATH_CONNECT, json={})
        assert response.status_code == HTTPStatus.OK
        mock_instance.connect.assert_called_once_with(
            TEST_WORKER_URL, TEST_RELAY_TOKEN, TEST_DAEMON_PORT
        )

    def test_connect_body_overrides_config(self, client: TestClient) -> None:
        """Request body values override config values."""
        _setup_state_with_config(worker_url=TEST_WORKER_URL, token="config-token")

        mock_instance = AsyncMock()
        mock_instance.connect = AsyncMock(
            return_value=RelayStatus(connected=True, worker_url=TEST_WORKER_URL_ALTERNATE)
        )

        with (
            patch(_PATCH_GET_PORT, return_value=TEST_DAEMON_PORT),
            patch(_PATCH_CLIENT_CLS, return_value=mock_instance),
        ):
            response = client.post(
                CI_CLOUD_RELAY_API_PATH_CONNECT,
                json={
                    "worker_url": TEST_WORKER_URL_ALTERNATE,
                    "token": TEST_RELAY_TOKEN,
                },
            )
        assert response.status_code == HTTPStatus.OK
        mock_instance.connect.assert_called_once_with(
            TEST_WORKER_URL_ALTERNATE, TEST_RELAY_TOKEN, TEST_DAEMON_PORT
        )


def _setup_state_for_start(
    *,
    worker_url: str | None = None,
    token: str | None = TEST_RELAY_TOKEN,
    agent_token: str | None = TEST_AGENT_TOKEN,
) -> None:
    """Set up daemon state for /api/cloud/start tests."""
    state = get_state()
    state.project_root = FAKE_PROJECT_ROOT
    state.ci_config = CIConfig()
    state.ci_config.cloud_relay = CloudRelayConfig(
        worker_url=worker_url,
        token=token,
        agent_token=agent_token,
    )


def _make_config_with(
    *,
    worker_url: str | None = None,
    token: str | None = TEST_RELAY_TOKEN,
    agent_token: str | None = TEST_AGENT_TOKEN,
) -> CIConfig:
    """Create a CIConfig for mocking load_ci_config."""
    ci = CIConfig()
    ci.cloud_relay = CloudRelayConfig(
        worker_url=worker_url,
        token=token,
        agent_token=agent_token,
    )
    return ci


class TestCloudRelayStart:
    """Tests for POST /api/cloud/start."""

    def test_start_full_flow(self, client: TestClient) -> None:
        """Full pipeline: scaffold -> npm install -> auth -> deploy -> connect."""
        _setup_state_for_start()

        mock_relay_instance = AsyncMock()
        mock_relay_instance.connect = AsyncMock(
            return_value=RelayStatus(connected=True, worker_url=TEST_WORKER_URL)
        )

        # load_ci_config is called 4 times in the full flow:
        # 1. inside scaffold phase (persist tokens)
        # 2. re-read after scaffold
        # 3. after deploy (save worker_url)
        # 4. final read for connect phase
        configs = [
            _make_config_with(),  # 1: scaffold persist
            _make_config_with(),  # 2: re-read after scaffold
            _make_config_with(),  # 3: deploy save
            _make_config_with(worker_url=TEST_WORKER_URL),  # 4: final read
        ]

        with (
            patch(_PATCH_IS_SCAFFOLDED, return_value=False),
            patch(_PATCH_RENDER_TEMPLATE, return_value=FAKE_PROJECT_ROOT / "oak/cloud-relay"),
            patch(_PATCH_RENDER_WRANGLER),
            patch(_PATCH_GENERATE_TOKEN, return_value="gen-token"),
            patch(_PATCH_MAKE_WORKER_NAME, return_value="oak-relay-fake-project"),
            patch(_PATCH_LOAD_CI_CONFIG, side_effect=configs),
            patch(_PATCH_SAVE_CI_CONFIG),
            patch(_PATCH_RUN_NPM_INSTALL, return_value=(True, "ok")),
            patch(
                _PATCH_CHECK_WRANGLER_AUTH,
                return_value=WranglerAuthInfo(
                    account_name="Test Account",
                    account_id="a" * 32,
                    authenticated=True,
                ),
            ),
            patch(
                _PATCH_RUN_WRANGLER_DEPLOY,
                return_value=(True, TEST_WORKER_URL, "Published"),
            ),
            patch(_PATCH_GET_PORT, return_value=TEST_DAEMON_PORT),
            patch(_PATCH_CLIENT_CLS, return_value=mock_relay_instance),
        ):
            response = client.post(CI_CLOUD_RELAY_API_PATH_START, json={})

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data[CLOUD_RELAY_RESPONSE_KEY_STATUS] == CLOUD_RELAY_START_STATUS_OK
        assert data[CLOUD_RELAY_RESPONSE_KEY_CONNECTED] is True
        assert data[CLOUD_RELAY_RESPONSE_KEY_WORKER_URL] == TEST_WORKER_URL
        assert (
            data[CLOUD_RELAY_RESPONSE_KEY_MCP_ENDPOINT]
            == TEST_WORKER_URL + CLOUD_RELAY_MCP_ENDPOINT_SUFFIX
        )
        assert data[CLOUD_RELAY_RESPONSE_KEY_CF_ACCOUNT_NAME] == "Test Account"

    def test_start_skips_scaffold_but_always_deploys(self, client: TestClient) -> None:
        """Skips scaffold when already done, but always deploys (idempotent)."""
        _setup_state_for_start(worker_url=TEST_WORKER_URL)

        mock_relay_instance = AsyncMock()
        mock_relay_instance.connect = AsyncMock(
            return_value=RelayStatus(connected=True, worker_url=TEST_WORKER_URL)
        )

        config_with_url = _make_config_with(worker_url=TEST_WORKER_URL)

        with (
            patch(_PATCH_IS_SCAFFOLDED, return_value=True),
            patch(_PATCH_RENDER_TEMPLATE) as mock_render,
            patch(_PATCH_RENDER_WRANGLER),
            patch(_PATCH_LOAD_CI_CONFIG, return_value=config_with_url),
            patch(_PATCH_SAVE_CI_CONFIG),
            patch(
                _PATCH_CHECK_WRANGLER_AUTH,
                return_value=WranglerAuthInfo(
                    account_name="Acct",
                    account_id="b" * 32,
                    authenticated=True,
                ),
            ),
            patch(_PATCH_RUN_NPM_INSTALL) as mock_npm,
            patch(
                _PATCH_RUN_WRANGLER_DEPLOY,
                return_value=(True, TEST_WORKER_URL, "Published"),
            ) as mock_deploy,
            patch(_PATCH_GET_PORT, return_value=TEST_DAEMON_PORT),
            patch(_PATCH_CLIENT_CLS, return_value=mock_relay_instance),
            patch("pathlib.Path.is_dir", return_value=True),
        ):
            response = client.post(CI_CLOUD_RELAY_API_PATH_START, json={})

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data[CLOUD_RELAY_RESPONSE_KEY_STATUS] == CLOUD_RELAY_START_STATUS_OK
        # Scaffold should NOT have been called (already scaffolded)
        mock_render.assert_not_called()
        mock_npm.assert_not_called()
        # Deploy ALWAYS runs (idempotent — ensures config changes are applied)
        mock_deploy.assert_called_once()

    def test_start_auth_check_failure(self, client: TestClient) -> None:
        """Returns error when wrangler auth fails."""
        _setup_state_for_start()

        config = _make_config_with()

        with (
            patch(_PATCH_IS_SCAFFOLDED, return_value=True),
            patch(_PATCH_RENDER_WRANGLER),
            patch(_PATCH_LOAD_CI_CONFIG, return_value=config),
            patch(
                _PATCH_CHECK_WRANGLER_AUTH,
                return_value=WranglerAuthInfo(authenticated=False),
            ),
            patch("pathlib.Path.is_dir", return_value=True),
        ):
            response = client.post(CI_CLOUD_RELAY_API_PATH_START, json={})

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data[CLOUD_RELAY_RESPONSE_KEY_STATUS] == CLOUD_RELAY_START_STATUS_ERROR
        assert data[CLOUD_RELAY_RESPONSE_KEY_PHASE] == CLOUD_RELAY_PHASE_AUTH_CHECK
        assert "Not authenticated" in data[CLOUD_RELAY_RESPONSE_KEY_ERROR]

    def test_start_deploy_failure(self, client: TestClient) -> None:
        """Returns error when wrangler deploy fails."""
        _setup_state_for_start()

        config = _make_config_with()

        with (
            patch(_PATCH_IS_SCAFFOLDED, return_value=True),
            patch(_PATCH_RENDER_WRANGLER),
            patch(_PATCH_LOAD_CI_CONFIG, return_value=config),
            patch(
                _PATCH_CHECK_WRANGLER_AUTH,
                return_value=WranglerAuthInfo(
                    account_name="Acct",
                    account_id="c" * 32,
                    authenticated=True,
                ),
            ),
            patch(
                _PATCH_RUN_WRANGLER_DEPLOY,
                return_value=(False, None, "Error: deploy failed"),
            ),
            patch("pathlib.Path.is_dir", return_value=True),
        ):
            response = client.post(CI_CLOUD_RELAY_API_PATH_START, json={})

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data[CLOUD_RELAY_RESPONSE_KEY_STATUS] == CLOUD_RELAY_START_STATUS_ERROR
        assert data[CLOUD_RELAY_RESPONSE_KEY_PHASE] == CLOUD_RELAY_PHASE_DEPLOY

    def test_start_no_project_root(self, client: TestClient) -> None:
        """Returns error when project_root is not set."""
        state = get_state()
        state.project_root = None
        state.ci_config = None

        response = client.post(CI_CLOUD_RELAY_API_PATH_START, json={})
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data[CLOUD_RELAY_RESPONSE_KEY_STATUS] == CLOUD_RELAY_START_STATUS_ERROR


class TestCloudRelayStop:
    """Tests for POST /api/cloud/stop."""

    def test_stop_active_client(self, client: TestClient) -> None:
        """Disconnects and cleans up active client."""
        state = get_state()
        mock_client = AsyncMock()
        state.cloud_relay_client = mock_client
        state.cf_account_name = "Test"

        response = client.post(CI_CLOUD_RELAY_API_PATH_STOP)
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data[CLOUD_RELAY_RESPONSE_KEY_STATUS] == CLOUD_RELAY_API_STATUS_DISCONNECTED
        assert state.cloud_relay_client is None
        assert state.cf_account_name is None
        mock_client.disconnect.assert_called_once()

    def test_stop_no_client(self, client: TestClient) -> None:
        """Returns not_connected when no relay is active."""
        response = client.post(CI_CLOUD_RELAY_API_PATH_STOP)
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data[CLOUD_RELAY_RESPONSE_KEY_STATUS] == CLOUD_RELAY_API_STATUS_NOT_CONNECTED


class TestCloudRelayPreflight:
    """Tests for GET /api/cloud/preflight."""

    def test_preflight_all_available(self, client: TestClient) -> None:
        """Returns all-true when everything is set up."""
        state = get_state()
        state.project_root = FAKE_PROJECT_ROOT
        state.ci_config = CIConfig()
        state.ci_config.cloud_relay = CloudRelayConfig(worker_url=TEST_WORKER_URL)

        with (
            patch(_PATCH_IS_SCAFFOLDED, return_value=True),
            patch(_PATCH_CHECK_WRANGLER_AVAILABLE, return_value=True),
            patch(
                _PATCH_CHECK_WRANGLER_AUTH,
                return_value=WranglerAuthInfo(
                    account_name="Test Account",
                    account_id="a" * 32,
                    authenticated=True,
                ),
            ),
            patch("shutil.which", return_value="/usr/bin/npm"),
            patch("pathlib.Path.is_dir", return_value=True),
        ):
            response = client.get(CI_CLOUD_RELAY_API_PATH_PREFLIGHT)

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["npm_available"] is True
        assert data["wrangler_available"] is True
        assert data["wrangler_authenticated"] is True
        assert data["cf_account_name"] == "Test Account"
        assert data["cf_account_id"] == "a" * 32
        assert data["scaffolded"] is True
        assert data["installed"] is True
        assert data["deployed"] is True
        assert data["worker_url"] == TEST_WORKER_URL

    def test_preflight_nothing_available(self, client: TestClient) -> None:
        """Returns all-false when nothing is set up."""
        state = get_state()
        state.project_root = FAKE_PROJECT_ROOT
        state.ci_config = CIConfig()

        with (
            patch(_PATCH_IS_SCAFFOLDED, return_value=False),
            patch(_PATCH_CHECK_WRANGLER_AVAILABLE, return_value=False),
            patch("shutil.which", return_value=None),
        ):
            response = client.get(CI_CLOUD_RELAY_API_PATH_PREFLIGHT)

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["npm_available"] is False
        assert data["wrangler_available"] is False
        assert data["wrangler_authenticated"] is False
        assert data["cf_account_name"] is None
        assert data["cf_account_id"] is None
        assert data["scaffolded"] is False
        assert data["installed"] is False
        assert data["deployed"] is False
        assert data["worker_url"] is None


class TestCloudRelayStatusEnriched:
    """Tests for enriched GET /api/cloud/status response."""

    def test_status_includes_agent_token_and_mcp_endpoint(self, client: TestClient) -> None:
        """Status response includes agent_token, mcp_endpoint, cf_account_name."""
        state = get_state()
        state.cf_account_name = "My Account"
        state.ci_config = CIConfig()
        state.ci_config.cloud_relay = CloudRelayConfig(agent_token=TEST_AGENT_TOKEN)

        mock_client = MagicMock()
        mock_client.get_status.return_value = RelayStatus(
            connected=True,
            worker_url=TEST_WORKER_URL,
            connected_at=TEST_CONNECTED_AT,
            last_heartbeat=TEST_HEARTBEAT_AT,
        )
        state.cloud_relay_client = mock_client

        response = client.get(CI_CLOUD_RELAY_API_PATH_STATUS)
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data[CLOUD_RELAY_RESPONSE_KEY_AGENT_TOKEN] == TEST_AGENT_TOKEN
        assert (
            data[CLOUD_RELAY_RESPONSE_KEY_MCP_ENDPOINT]
            == TEST_WORKER_URL + CLOUD_RELAY_MCP_ENDPOINT_SUFFIX
        )
        assert data[CLOUD_RELAY_RESPONSE_KEY_CF_ACCOUNT_NAME] == "My Account"

    def test_status_no_client_includes_null_fields(self, client: TestClient) -> None:
        """Disconnected status includes null agent_token/mcp_endpoint/cf_account_name."""
        # Prevent ci_config property from lazy-loading the real project config
        # (create_app sets project_root = cwd, which triggers disk reads).
        state = get_state()
        state.project_root = None
        response = client.get(CI_CLOUD_RELAY_API_PATH_STATUS)
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data[CLOUD_RELAY_RESPONSE_KEY_AGENT_TOKEN] is None
        assert data[CLOUD_RELAY_RESPONSE_KEY_MCP_ENDPOINT] is None
        assert data[CLOUD_RELAY_RESPONSE_KEY_CF_ACCOUNT_NAME] is None
        assert data[CLOUD_RELAY_RESPONSE_KEY_CUSTOM_DOMAIN] is None


class TestCloudRelayCustomDomainInStatus:
    """Tests for custom_domain in GET /api/cloud/status."""

    def test_status_uses_worker_url_even_with_custom_domain(self, client: TestClient) -> None:
        """mcp_endpoint always uses workers.dev URL (custom domain DNS may lag)."""
        state = get_state()
        state.cf_account_name = "My Account"
        state.project_root = FAKE_PROJECT_ROOT
        state.ci_config = CIConfig()
        state.ci_config.cloud_relay = CloudRelayConfig(
            agent_token=TEST_AGENT_TOKEN,
            custom_domain="example.com",
            worker_name="oak-relay-myproject",
        )

        mock_client = MagicMock()
        mock_client.get_status.return_value = RelayStatus(
            connected=True,
            worker_url=TEST_WORKER_URL,
            connected_at=TEST_CONNECTED_AT,
            last_heartbeat=TEST_HEARTBEAT_AT,
        )
        state.cloud_relay_client = mock_client

        response = client.get(CI_CLOUD_RELAY_API_PATH_STATUS)
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        # mcp_endpoint uses workers.dev URL, not custom domain
        assert (
            data[CLOUD_RELAY_RESPONSE_KEY_MCP_ENDPOINT]
            == TEST_WORKER_URL + CLOUD_RELAY_MCP_ENDPOINT_SUFFIX
        )
        # custom_domain and worker_name are still in the response for UI display
        assert data[CLOUD_RELAY_RESPONSE_KEY_CUSTOM_DOMAIN] == "example.com"
        assert data[CLOUD_RELAY_RESPONSE_KEY_WORKER_NAME] == "oak-relay-myproject"

    def test_status_falls_back_to_worker_url_when_no_custom_domain(
        self, client: TestClient
    ) -> None:
        """When custom_domain is None, mcp_endpoint uses worker_url."""
        state = get_state()
        state.ci_config = CIConfig()
        state.ci_config.cloud_relay = CloudRelayConfig(agent_token=TEST_AGENT_TOKEN)

        mock_client = MagicMock()
        mock_client.get_status.return_value = RelayStatus(
            connected=True,
            worker_url=TEST_WORKER_URL,
        )
        state.cloud_relay_client = mock_client

        response = client.get(CI_CLOUD_RELAY_API_PATH_STATUS)
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert (
            data[CLOUD_RELAY_RESPONSE_KEY_MCP_ENDPOINT]
            == TEST_WORKER_URL + CLOUD_RELAY_MCP_ENDPOINT_SUFFIX
        )
        assert data[CLOUD_RELAY_RESPONSE_KEY_CUSTOM_DOMAIN] is None


class TestCloudRelaySettings:
    """Tests for PUT /api/cloud/settings."""

    def test_save_custom_domain(self, client: TestClient) -> None:
        """PUT saves custom_domain and returns updated status."""
        state = get_state()
        state.project_root = FAKE_PROJECT_ROOT
        state.ci_config = CIConfig()

        ci_config = CIConfig()
        saved_configs: list[CIConfig] = []

        def mock_save(root: Path, cfg: CIConfig) -> None:
            saved_configs.append(cfg)

        with (
            patch(_PATCH_LOAD_CI_CONFIG, return_value=ci_config),
            patch(_PATCH_SAVE_CI_CONFIG, side_effect=mock_save),
        ):
            response = client.put(
                CI_CLOUD_RELAY_API_PATH_SETTINGS,
                json={"custom_domain": "relay.example.com"},
            )

        assert response.status_code == HTTPStatus.OK
        # Config was saved with the custom domain
        assert len(saved_configs) == 1
        assert saved_configs[0].cloud_relay.custom_domain == "relay.example.com"

    def test_clear_custom_domain(self, client: TestClient) -> None:
        """PUT with null clears custom_domain."""
        state = get_state()
        state.project_root = FAKE_PROJECT_ROOT
        state.ci_config = CIConfig()

        ci_config = CIConfig()
        ci_config.cloud_relay.custom_domain = "old.example.com"
        saved_configs: list[CIConfig] = []

        def mock_save(root: Path, cfg: CIConfig) -> None:
            saved_configs.append(cfg)

        with (
            patch(_PATCH_LOAD_CI_CONFIG, return_value=ci_config),
            patch(_PATCH_SAVE_CI_CONFIG, side_effect=mock_save),
        ):
            response = client.put(
                CI_CLOUD_RELAY_API_PATH_SETTINGS,
                json={"custom_domain": None},
            )

        assert response.status_code == HTTPStatus.OK
        assert len(saved_configs) == 1
        assert saved_configs[0].cloud_relay.custom_domain is None

    def test_settings_strips_https_prefix(self, client: TestClient) -> None:
        """PUT normalizes input (strips https://)."""
        state = get_state()
        state.project_root = FAKE_PROJECT_ROOT
        state.ci_config = CIConfig()

        ci_config = CIConfig()
        saved_configs: list[CIConfig] = []

        def mock_save(root: Path, cfg: CIConfig) -> None:
            saved_configs.append(cfg)

        with (
            patch(_PATCH_LOAD_CI_CONFIG, return_value=ci_config),
            patch(_PATCH_SAVE_CI_CONFIG, side_effect=mock_save),
        ):
            response = client.put(
                CI_CLOUD_RELAY_API_PATH_SETTINGS,
                json={"custom_domain": "https://relay.example.com"},
            )

        assert response.status_code == HTTPStatus.OK
        assert saved_configs[0].cloud_relay.custom_domain == "relay.example.com"

    def test_settings_rejects_path(self, client: TestClient) -> None:
        """PUT rejects domain with path component."""
        state = get_state()
        state.project_root = FAKE_PROJECT_ROOT
        state.ci_config = CIConfig()

        response = client.put(
            CI_CLOUD_RELAY_API_PATH_SETTINGS,
            json={"custom_domain": "relay.example.com/some/path"},
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST

    def test_settings_no_config(self, client: TestClient) -> None:
        """PUT returns 500 when daemon not initialized."""
        state = get_state()
        state.project_root = None
        state.ci_config = None

        response = client.put(
            CI_CLOUD_RELAY_API_PATH_SETTINGS,
            json={"custom_domain": "relay.example.com"},
        )

        assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR

    def test_settings_rerenders_wrangler_when_scaffolded(self, client: TestClient) -> None:
        """PUT re-renders wrangler.toml when project is scaffolded."""
        state = get_state()
        state.project_root = FAKE_PROJECT_ROOT
        state.ci_config = CIConfig()

        ci_config = CIConfig()
        ci_config.cloud_relay.token = TEST_RELAY_TOKEN
        ci_config.cloud_relay.agent_token = TEST_AGENT_TOKEN
        ci_config.cloud_relay.worker_name = "oak-relay-fake"

        _PATCH_SETTINGS_IS_SCAFFOLDED = (
            "open_agent_kit.features.codebase_intelligence.cloud_relay.scaffold.is_scaffolded"
        )
        _PATCH_SETTINGS_RENDER_WRANGLER = "open_agent_kit.features.codebase_intelligence.cloud_relay.scaffold.render_wrangler_config"

        with (
            patch(_PATCH_LOAD_CI_CONFIG, return_value=ci_config),
            patch(_PATCH_SAVE_CI_CONFIG),
            patch(_PATCH_SETTINGS_IS_SCAFFOLDED, return_value=True),
            patch(_PATCH_SETTINGS_RENDER_WRANGLER) as mock_render,
        ):
            response = client.put(
                CI_CLOUD_RELAY_API_PATH_SETTINGS,
                json={"custom_domain": "example.com"},
            )

        assert response.status_code == HTTPStatus.OK
        mock_render.assert_called_once()
        call_kwargs = mock_render.call_args
        assert call_kwargs.kwargs.get("custom_domain") == "example.com"
        assert call_kwargs.kwargs.get("worker_name") == "oak-relay-fake"


class TestCloudRelayWorkerNameInResponse:
    """Tests for worker_name in API responses."""

    def test_status_includes_worker_name(self, client: TestClient) -> None:
        """Status response includes worker_name from config."""
        state = get_state()
        state.project_root = FAKE_PROJECT_ROOT
        state.ci_config = CIConfig()
        state.ci_config.cloud_relay = CloudRelayConfig(
            worker_name="oak-relay-myproject",
        )

        response = client.get(CI_CLOUD_RELAY_API_PATH_STATUS)
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data[CLOUD_RELAY_RESPONSE_KEY_WORKER_NAME] == "oak-relay-myproject"

    def test_status_derives_worker_name_from_project_root(self, client: TestClient) -> None:
        """Status response derives worker_name when not in config."""
        state = get_state()
        state.project_root = FAKE_PROJECT_ROOT
        state.ci_config = CIConfig()

        response = client.get(CI_CLOUD_RELAY_API_PATH_STATUS)
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        # make_worker_name("fake-project") → "oak-relay-fake-project"
        assert data[CLOUD_RELAY_RESPONSE_KEY_WORKER_NAME] == "oak-relay-fake-project"

    def test_start_response_includes_worker_name(self, client: TestClient) -> None:
        """Start response includes worker_name."""
        _setup_state_for_start(worker_url=TEST_WORKER_URL)

        mock_relay_instance = AsyncMock()
        mock_relay_instance.connect = AsyncMock(
            return_value=RelayStatus(connected=True, worker_url=TEST_WORKER_URL)
        )

        config_with_url = _make_config_with(worker_url=TEST_WORKER_URL)
        config_with_url.cloud_relay.worker_name = "oak-relay-fake-project"

        with (
            patch(_PATCH_IS_SCAFFOLDED, return_value=True),
            patch(_PATCH_RENDER_WRANGLER),
            patch(_PATCH_LOAD_CI_CONFIG, return_value=config_with_url),
            patch(_PATCH_SAVE_CI_CONFIG),
            patch(
                _PATCH_CHECK_WRANGLER_AUTH,
                return_value=WranglerAuthInfo(
                    account_name="Acct",
                    account_id="b" * 32,
                    authenticated=True,
                ),
            ),
            patch(
                _PATCH_RUN_WRANGLER_DEPLOY,
                return_value=(True, TEST_WORKER_URL, "Published"),
            ),
            patch(_PATCH_GET_PORT, return_value=TEST_DAEMON_PORT),
            patch(_PATCH_CLIENT_CLS, return_value=mock_relay_instance),
            patch("pathlib.Path.is_dir", return_value=True),
        ):
            response = client.post(CI_CLOUD_RELAY_API_PATH_START, json={})

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data[CLOUD_RELAY_RESPONSE_KEY_WORKER_NAME] == "oak-relay-fake-project"


class TestMcpEndpointDerivation:
    """Tests for _mcp_endpoint() via status API.

    mcp_endpoint always uses the workers.dev URL because custom-domain
    DNS provisioning can lag behind deploy.  The custom domain info is
    returned separately so the UI can show it once propagation completes.
    """

    def test_always_uses_worker_url_even_with_custom_domain(self, client: TestClient) -> None:
        """mcp_endpoint uses workers.dev URL regardless of custom_domain."""
        state = get_state()
        state.project_root = FAKE_PROJECT_ROOT
        state.ci_config = CIConfig()
        state.ci_config.cloud_relay = CloudRelayConfig(
            agent_token=TEST_AGENT_TOKEN,
            custom_domain="goondocks.co",
            worker_name="oak-relay-myproject",
        )

        mock_client = MagicMock()
        mock_client.get_status.return_value = RelayStatus(
            connected=True,
            worker_url=TEST_WORKER_URL,
        )
        state.cloud_relay_client = mock_client

        response = client.get(CI_CLOUD_RELAY_API_PATH_STATUS)
        data = response.json()
        assert (
            data[CLOUD_RELAY_RESPONSE_KEY_MCP_ENDPOINT]
            == TEST_WORKER_URL + CLOUD_RELAY_MCP_ENDPOINT_SUFFIX
        )
        # Custom domain info still present for UI display
        assert data[CLOUD_RELAY_RESPONSE_KEY_CUSTOM_DOMAIN] == "goondocks.co"
        assert data[CLOUD_RELAY_RESPONSE_KEY_WORKER_NAME] == "oak-relay-myproject"

    def test_no_custom_domain_uses_worker_url(self, client: TestClient) -> None:
        """Without custom_domain, mcp_endpoint uses worker_url."""
        state = get_state()
        state.project_root = FAKE_PROJECT_ROOT
        state.ci_config = CIConfig()
        state.ci_config.cloud_relay = CloudRelayConfig(
            agent_token=TEST_AGENT_TOKEN,
            worker_name="oak-relay-myproject",
        )

        mock_client = MagicMock()
        mock_client.get_status.return_value = RelayStatus(
            connected=True,
            worker_url=TEST_WORKER_URL,
        )
        state.cloud_relay_client = mock_client

        response = client.get(CI_CLOUD_RELAY_API_PATH_STATUS)
        data = response.json()
        assert (
            data[CLOUD_RELAY_RESPONSE_KEY_MCP_ENDPOINT]
            == TEST_WORKER_URL + CLOUD_RELAY_MCP_ENDPOINT_SUFFIX
        )
