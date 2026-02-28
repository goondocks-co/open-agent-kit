"""Unit tests for team management API routes.

Tests cover:
- GET /api/team/config returns defaults when unconfigured
- POST /api/team/config updates config
- GET /api/team/status when not configured
- GET /api/team/status when configured
- GET /api/team/policy returns defaults
- POST /api/team/policy updates policy
- GET /api/team/keys returns 403 when not server mode
- POST /api/team/leave disconnects and clears config
- POST /api/team/sync/flush when sync not active
- POST /api/team/sync/pull placeholder response
- POST /api/team/serve enable/disable server mode
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from open_agent_kit.features.codebase_intelligence.config.governance import (
    DataCollectionPolicy,
    GovernanceConfig,
)
from open_agent_kit.features.codebase_intelligence.config.team import TeamConfig
from open_agent_kit.features.codebase_intelligence.constants.team import (
    TEAM_API_PATH_CONFIG,
    TEAM_API_PATH_KEYS,
    TEAM_API_PATH_LEAVE,
    TEAM_API_PATH_POLICY,
    TEAM_API_PATH_SERVE,
    TEAM_API_PATH_STATUS,
    TEAM_API_PATH_SYNC_FLUSH,
    TEAM_API_PATH_SYNC_PULL,
    TEAM_DEFAULT_PULL_INTERVAL_SECONDS,
    TEAM_DEFAULT_SYNC_INTERVAL_SECONDS,
    TEAM_LOOPBACK_KEY_NAME,
    TEAM_SERVER_MODE_ENV_VAR,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes.team import router
from open_agent_kit.features.codebase_intelligence.daemon.state import (
    DaemonState,
    reset_state,
)

# Module path for patching imports used inside route handler functions
_CONFIG_PKG = "open_agent_kit.features.codebase_intelligence.config"
_ROUTE_MOD = "open_agent_kit.features.codebase_intelligence.daemon.routes.team"


@pytest.fixture(autouse=True)
def _clean_state():
    """Reset daemon state before and after each test."""
    reset_state()
    yield
    reset_state()


@pytest.fixture()
def client() -> TestClient:
    """Create a test client with team routes mounted."""
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _make_ci_config(
    *,
    server_url: str | None = None,
    auto_sync: bool = False,
    api_key: str | None = None,
) -> MagicMock:
    """Build a minimal mock CIConfig with team and governance sections."""
    ci_config = MagicMock()
    ci_config.team = TeamConfig(
        server_url=server_url,
        auto_sync=auto_sync,
        api_key=api_key,
    )
    ci_config.governance = GovernanceConfig(
        data_collection=DataCollectionPolicy(),
    )
    return ci_config


def _mock_state_with_config(
    ci_config: MagicMock | None = None,
    project_root: Path | None = None,
) -> MagicMock:
    """Create a mock DaemonState with controllable ci_config property.

    This avoids the mtime-based disk reload in the real ci_config property.
    """
    mock_state = MagicMock(spec=DaemonState)
    mock_state.project_root = project_root
    mock_state.ci_config = ci_config
    mock_state.team_sync_worker = None
    mock_state.team_gateway = None
    mock_state.activity_store = None
    return mock_state


# =========================================================================
# GET /api/team/config
# =========================================================================


class TestGetTeamConfig:
    """Tests for GET /api/team/config."""

    def test_returns_defaults_when_no_config(self, client: TestClient) -> None:
        """When ci_config is None, returns default TeamConfigResponse."""
        resp = client.get(TEAM_API_PATH_CONFIG)
        assert resp.status_code == 200
        data = resp.json()
        assert data["server_url"] is None
        assert data["auto_sync"] is False
        assert data["sync_interval_seconds"] == TEAM_DEFAULT_SYNC_INTERVAL_SECONDS
        assert data["pull_interval_seconds"] == TEAM_DEFAULT_PULL_INTERVAL_SECONDS
        assert data["transport"] == "direct"
        assert data["server_mode"] is False

    @patch(f"{_ROUTE_MOD}.get_state")
    def test_returns_configured_values(self, mock_get_state: MagicMock, client: TestClient) -> None:
        """When team config is set, returns its values."""
        ci_config = _make_ci_config(
            server_url="http://team.example.com",
            auto_sync=True,
        )
        mock_get_state.return_value = _mock_state_with_config(ci_config)

        resp = client.get(TEAM_API_PATH_CONFIG)
        assert resp.status_code == 200
        data = resp.json()
        assert data["server_url"] == "http://team.example.com"
        assert data["auto_sync"] is True


# =========================================================================
# POST /api/team/config
# =========================================================================


class TestUpdateTeamConfig:
    """Tests for POST /api/team/config."""

    @patch(f"{_ROUTE_MOD}.get_state")
    def test_returns_500_when_no_project_root(
        self, mock_get_state: MagicMock, client: TestClient
    ) -> None:
        """When project_root is not set, returns 500."""
        mock_state = MagicMock()
        mock_state.project_root = None
        mock_get_state.return_value = mock_state
        resp = client.post(TEAM_API_PATH_CONFIG, json={"auto_sync": True})
        assert resp.status_code == 500

    @patch(f"{_CONFIG_PKG}.save_ci_config")
    @patch(f"{_CONFIG_PKG}.load_ci_config")
    @patch(f"{_ROUTE_MOD}.get_state")
    def test_updates_config_fields(
        self,
        mock_get_state: MagicMock,
        mock_load: MagicMock,
        mock_save: MagicMock,
        client: TestClient,
    ) -> None:
        """Config update applies provided fields and saves."""
        ci_config = _make_ci_config()
        mock_state = _mock_state_with_config(ci_config, project_root=Path("/tmp/test-project"))
        mock_get_state.return_value = mock_state
        mock_load.return_value = ci_config

        resp = client.post(
            TEAM_API_PATH_CONFIG,
            json={
                "server_url": "http://new-server.example.com",
                "auto_sync": True,
            },
        )
        assert resp.status_code == 200
        mock_save.assert_called_once()
        assert ci_config.team.server_url == "http://new-server.example.com"
        assert ci_config.team.auto_sync is True


# =========================================================================
# GET /api/team/status
# =========================================================================


class TestGetTeamStatus:
    """Tests for GET /api/team/status."""

    def test_not_configured(self, client: TestClient) -> None:
        """When no server_url is set, reports not configured."""
        resp = client.get(TEAM_API_PATH_STATUS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["configured"] is False
        assert data["server_url"] is None
        assert data["connected"] is False

    @patch(f"{_ROUTE_MOD}.get_state")
    def test_configured_without_sync_worker(
        self, mock_get_state: MagicMock, client: TestClient
    ) -> None:
        """When configured but sync worker not running."""
        ci_config = _make_ci_config(server_url="http://team.example.com")
        mock_state = _mock_state_with_config(ci_config, project_root=Path("/tmp/test-project"))
        mock_get_state.return_value = mock_state

        with patch(
            "open_agent_kit.features.codebase_intelligence.team.identity.get_project_identity",
        ) as mock_identity:
            mock_id = MagicMock()
            mock_id.full_id = "test-project:abc123"
            mock_identity.return_value = mock_id
            resp = client.get(TEAM_API_PATH_STATUS)

        assert resp.status_code == 200
        data = resp.json()
        assert data["configured"] is True
        assert data["server_url"] == "http://team.example.com"
        assert data["connected"] is False
        assert data["project_id"] == "test-project:abc123"
        assert data["sync"] is None

    @patch(f"{_ROUTE_MOD}.get_state")
    def test_configured_with_sync_worker(
        self, mock_get_state: MagicMock, client: TestClient
    ) -> None:
        """When configured and sync worker is running, includes sync status."""
        ci_config = _make_ci_config(server_url="http://team.example.com")
        mock_state = _mock_state_with_config(ci_config, project_root=Path("/tmp/test-project"))

        mock_worker = MagicMock()
        mock_status = MagicMock()
        mock_status.model_dump.return_value = {
            "enabled": True,
            "queue_depth": 5,
            "last_sync": None,
            "last_error": None,
            "events_sent_total": 10,
        }
        mock_worker.get_status.return_value = mock_status
        mock_state.team_sync_worker = mock_worker
        mock_get_state.return_value = mock_state

        with patch(
            "open_agent_kit.features.codebase_intelligence.team.identity.get_project_identity",
        ) as mock_identity:
            mock_id = MagicMock()
            mock_id.full_id = "test-project:abc123"
            mock_identity.return_value = mock_id
            resp = client.get(TEAM_API_PATH_STATUS)

        assert resp.status_code == 200
        data = resp.json()
        assert data["connected"] is True
        assert data["sync"]["enabled"] is True
        assert data["sync"]["queue_depth"] == 5


# =========================================================================
# GET /api/team/policy
# =========================================================================


class TestGetTeamPolicy:
    """Tests for GET /api/team/policy."""

    def test_returns_defaults_when_no_config(self, client: TestClient) -> None:
        """When ci_config is None, returns default policy."""
        resp = client.get(TEAM_API_PATH_POLICY)
        assert resp.status_code == 200
        data = resp.json()
        assert data["collect_activities"] is True
        assert data["collect_prompts"] is True
        assert data["sync_observations"] is True
        assert data["sync_activities"] is False
        assert data["sync_prompts"] is False
        assert data["allow_server_llm"] is False

    @patch(f"{_ROUTE_MOD}.get_state")
    def test_returns_configured_policy(self, mock_get_state: MagicMock, client: TestClient) -> None:
        """When config exists, returns its data_collection policy."""
        ci_config = _make_ci_config()
        ci_config.governance.data_collection.sync_activities = True
        ci_config.governance.data_collection.allow_server_llm = True
        mock_get_state.return_value = _mock_state_with_config(ci_config)

        resp = client.get(TEAM_API_PATH_POLICY)
        assert resp.status_code == 200
        data = resp.json()
        assert data["sync_activities"] is True
        assert data["allow_server_llm"] is True


# =========================================================================
# POST /api/team/policy
# =========================================================================


class TestUpdateTeamPolicy:
    """Tests for POST /api/team/policy."""

    @patch(f"{_CONFIG_PKG}.save_ci_config")
    @patch(f"{_CONFIG_PKG}.load_ci_config")
    @patch(f"{_ROUTE_MOD}.get_state")
    def test_updates_policy_fields(
        self,
        mock_get_state: MagicMock,
        mock_load: MagicMock,
        mock_save: MagicMock,
        client: TestClient,
    ) -> None:
        """Policy update applies provided fields and saves."""
        ci_config = _make_ci_config()
        mock_state = _mock_state_with_config(ci_config, project_root=Path("/tmp/test-project"))
        mock_get_state.return_value = mock_state
        mock_load.return_value = ci_config

        resp = client.post(
            TEAM_API_PATH_POLICY,
            json={"sync_activities": True, "allow_server_llm": True},
        )
        assert resp.status_code == 200
        mock_save.assert_called_once()
        assert ci_config.governance.data_collection.sync_activities is True
        assert ci_config.governance.data_collection.allow_server_llm is True


# =========================================================================
# GET /api/team/keys (server mode gate)
# =========================================================================


class TestListKeys:
    """Tests for GET /api/team/keys."""

    def test_returns_403_when_not_server_mode(self, client: TestClient) -> None:
        """Returns 403 when OAK_CI_TEAM_SERVER is not set."""
        resp = client.get(TEAM_API_PATH_KEYS)
        assert resp.status_code == 403
        assert "Server mode only" in resp.json()["detail"]

    @patch.dict("os.environ", {TEAM_SERVER_MODE_ENV_VAR: "1"})
    def test_returns_500_when_no_store(self, client: TestClient) -> None:
        """Returns 500 when activity_store is not initialized."""
        resp = client.get(TEAM_API_PATH_KEYS)
        assert resp.status_code == 500

    @patch.dict("os.environ", {TEAM_SERVER_MODE_ENV_VAR: "1"})
    @patch(f"{_ROUTE_MOD}.get_state")
    def test_returns_keys_when_server_mode(
        self, mock_get_state: MagicMock, client: TestClient
    ) -> None:
        """Returns key list when in server mode with store."""
        mock_store = MagicMock()
        mock_conn = MagicMock()
        mock_store._get_connection.return_value = mock_conn

        mock_state = MagicMock(spec=DaemonState)
        mock_state.activity_store = mock_store
        mock_get_state.return_value = mock_state

        with patch(
            f"{_ROUTE_MOD}.list_api_keys",
            create=True,
        ) as mock_list:
            mock_list.return_value = []
            resp = client.get(TEAM_API_PATH_KEYS)

        assert resp.status_code == 200
        assert resp.json() == []


# =========================================================================
# POST /api/team/leave
# =========================================================================


class TestLeaveTeam:
    """Tests for POST /api/team/leave."""

    @patch(f"{_CONFIG_PKG}.save_ci_config")
    @patch(f"{_CONFIG_PKG}.load_ci_config")
    @patch(f"{_ROUTE_MOD}.get_state")
    def test_disconnects_and_stops_worker(
        self,
        mock_get_state: MagicMock,
        mock_load: MagicMock,
        mock_save: MagicMock,
        client: TestClient,
    ) -> None:
        """Leave clears config, stops sync worker."""
        ci_config = _make_ci_config(
            server_url="http://team.example.com",
            auto_sync=True,
        )
        mock_worker = MagicMock()
        mock_state = _mock_state_with_config(ci_config, project_root=Path("/tmp/test-project"))
        mock_state.team_sync_worker = mock_worker
        mock_get_state.return_value = mock_state
        mock_load.return_value = ci_config

        resp = client.post(TEAM_API_PATH_LEAVE)
        assert resp.status_code == 200
        assert resp.json()["status"] == "disconnected"

        # Config should be cleared (api_key preserved for re-join)
        assert ci_config.team.server_url is None
        assert ci_config.team.auto_sync is False
        mock_save.assert_called_once()

        # Worker should be stopped, gateway cleared
        mock_worker.stop.assert_called_once()
        assert mock_state.team_sync_worker is None
        assert mock_state.team_gateway is None


# =========================================================================
# Sync control
# =========================================================================


class TestSyncControl:
    """Tests for sync flush/pull endpoints."""

    def test_flush_returns_400_when_no_worker(self, client: TestClient) -> None:
        """Force flush returns 400 when sync worker not active."""
        resp = client.post(TEAM_API_PATH_SYNC_FLUSH)
        assert resp.status_code == 400
        assert "not active" in resp.json()["detail"]

    @patch(f"{_ROUTE_MOD}.get_state")
    def test_flush_calls_flush_outbox(self, mock_get_state: MagicMock, client: TestClient) -> None:
        """Force flush delegates to worker._flush_outbox()."""
        mock_worker = MagicMock()
        mock_worker._flush_outbox.return_value = 3
        mock_state = MagicMock(spec=DaemonState)
        mock_state.team_sync_worker = mock_worker
        mock_get_state.return_value = mock_state

        resp = client.post(TEAM_API_PATH_SYNC_FLUSH)
        assert resp.status_code == 200
        assert resp.json()["flushed"] == 3

    def test_pull_returns_placeholder(self, client: TestClient) -> None:
        """Force pull returns placeholder since pull worker is not implemented."""
        resp = client.post(TEAM_API_PATH_SYNC_PULL)
        assert resp.status_code == 200
        assert resp.json()["status"] == "pull_worker_not_available"


# =========================================================================
# POST /api/team/serve (server mode toggle)
# =========================================================================


class TestToggleServerMode:
    """Tests for POST /api/team/serve."""

    @patch(f"{_ROUTE_MOD}.get_state")
    def test_enable_returns_500_when_no_project_root(
        self, mock_get_state: MagicMock, client: TestClient
    ) -> None:
        """When project_root is not set, returns 500."""
        mock_state = MagicMock()
        mock_state.project_root = None
        mock_get_state.return_value = mock_state
        resp = client.post(TEAM_API_PATH_SERVE, json={"enable": True})
        assert resp.status_code == 500

    @patch(f"{_CONFIG_PKG}.save_ci_config")
    @patch(f"{_CONFIG_PKG}.load_ci_config")
    @patch(f"{_ROUTE_MOD}.get_state")
    def test_enable_creates_tables_and_loopback_key(
        self,
        mock_get_state: MagicMock,
        mock_load: MagicMock,
        mock_save: MagicMock,
        client: TestClient,
    ) -> None:
        """Enable creates server tables, loopback key, and updates config."""
        ci_config = _make_ci_config()
        mock_store = MagicMock()
        mock_conn = MagicMock()
        mock_store._get_connection.return_value = mock_conn

        mock_state = _mock_state_with_config(ci_config, project_root=Path("/tmp/test-project"))
        mock_state.activity_store = mock_store
        mock_get_state.return_value = mock_state
        mock_load.return_value = ci_config

        with (
            patch(
                "open_agent_kit.features.codebase_intelligence.daemon.manager.get_project_port",
                return_value=37842,
            ),
            patch(
                "open_agent_kit.features.codebase_intelligence.team.server.auth.create_api_key",
                return_value=("key123", "oak_team_testtoken"),
            ) as mock_create_key,
        ):
            resp = client.post(TEAM_API_PATH_SERVE, json={"enable": True})

        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is True
        assert data["server_url"] == "http://127.0.0.1:37842"
        assert data["restart_required"] is True

        # Server tables created
        assert mock_conn.executescript.call_count == 3

        # Loopback key created
        mock_create_key.assert_called_once_with(mock_conn, TEAM_LOOPBACK_KEY_NAME)

        # Config updated
        assert ci_config.team.server_mode is True
        assert ci_config.team.server_url == "http://127.0.0.1:37842"
        assert ci_config.team.api_key == "oak_team_testtoken"
        assert ci_config.team.auto_sync is True
        mock_save.assert_called_once()

    @patch(f"{_CONFIG_PKG}.save_ci_config")
    @patch(f"{_CONFIG_PKG}.load_ci_config")
    @patch(f"{_ROUTE_MOD}.get_state")
    def test_disable_clears_loopback_config(
        self,
        mock_get_state: MagicMock,
        mock_load: MagicMock,
        mock_save: MagicMock,
        client: TestClient,
    ) -> None:
        """Disable clears loopback server_url/api_key and sets server_mode=False."""
        ci_config = _make_ci_config(
            server_url="http://127.0.0.1:37842",
            auto_sync=True,
            api_key="oak_team_testtoken",
        )
        ci_config.team.server_mode = True

        mock_state = _mock_state_with_config(ci_config, project_root=Path("/tmp/test-project"))
        mock_get_state.return_value = mock_state
        mock_load.return_value = ci_config

        resp = client.post(TEAM_API_PATH_SERVE, json={"enable": False})
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is False
        assert data["restart_required"] is True

        # Config cleared
        assert ci_config.team.server_mode is False
        assert ci_config.team.server_url is None
        assert ci_config.team.api_key is None
        assert ci_config.team.auto_sync is False
        mock_save.assert_called_once()

    @patch(f"{_CONFIG_PKG}.save_ci_config")
    @patch(f"{_CONFIG_PKG}.load_ci_config")
    @patch(f"{_ROUTE_MOD}.get_state")
    def test_disable_preserves_remote_config(
        self,
        mock_get_state: MagicMock,
        mock_load: MagicMock,
        mock_save: MagicMock,
        client: TestClient,
    ) -> None:
        """Disable preserves server_url/api_key when connected to a remote server."""
        ci_config = _make_ci_config(
            server_url="https://team.example.com",
            auto_sync=True,
            api_key="remote_token",
        )
        ci_config.team.server_mode = True

        mock_state = _mock_state_with_config(ci_config, project_root=Path("/tmp/test-project"))
        mock_get_state.return_value = mock_state
        mock_load.return_value = ci_config

        resp = client.post(TEAM_API_PATH_SERVE, json={"enable": False})
        assert resp.status_code == 200

        # server_mode cleared, but remote URL/api_key preserved
        assert ci_config.team.server_mode is False
        assert ci_config.team.server_url == "https://team.example.com"
        assert ci_config.team.api_key == "remote_token"
        assert ci_config.team.auto_sync is True
