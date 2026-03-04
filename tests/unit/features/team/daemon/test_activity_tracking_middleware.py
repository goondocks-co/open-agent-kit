"""Tests for ActivityTrackingMiddleware.

Tests cover:
- /api/* requests call record_hook_activity()
- /api/health requests do NOT call record_hook_activity()
- /api/status requests do NOT call record_hook_activity()
- Non-/api/ requests (static files, dashboard) do NOT call record_hook_activity()
- Unauthenticated requests never reach the activity middleware (auth rejects first)
"""

from http import HTTPStatus
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from open_agent_kit.features.team.constants import (
    CI_AUTH_ENV_VAR,
    CI_AUTH_SCHEME_BEARER,
)
from open_agent_kit.features.team.daemon.server import create_app
from open_agent_kit.features.team.daemon.state import get_state, reset_state

TEST_TOKEN = "b" * 64


@pytest.fixture(autouse=True)
def _reset_daemon_state():
    """Reset daemon state before and after each test."""
    reset_state()
    yield
    reset_state()


@pytest.fixture
def client(monkeypatch, tmp_path: Path):
    """FastAPI test client with auth token configured."""
    monkeypatch.setenv(CI_AUTH_ENV_VAR, TEST_TOKEN)
    app = create_app(project_root=tmp_path)
    return TestClient(app)


def _auth_headers() -> dict[str, str]:
    """Return headers with valid Bearer token."""
    return {"Authorization": f"{CI_AUTH_SCHEME_BEARER} {TEST_TOKEN}"}


# =============================================================================
# Tracked API endpoints (should call record_hook_activity)
# =============================================================================


class TestActivityTrackingTrackedEndpoints:
    """Verify that authenticated /api/* requests trigger activity tracking."""

    def test_api_team_status_triggers_activity(self, client):
        """GET /api/team/status calls record_hook_activity()."""
        state = get_state()
        with patch.object(state, "record_hook_activity") as mock_record:
            client.get("/api/team/status", headers=_auth_headers())

        mock_record.assert_called()

    def test_api_team_config_triggers_activity(self, client):
        """GET /api/team/config calls record_hook_activity()."""
        state = get_state()
        with patch.object(state, "record_hook_activity") as mock_record:
            client.get("/api/team/config", headers=_auth_headers())

        mock_record.assert_called()

    def test_api_cloud_relay_status_triggers_activity(self, client):
        """GET /api/cloud-relay/status calls record_hook_activity()."""
        state = get_state()
        with patch.object(state, "record_hook_activity") as mock_record:
            client.get("/api/cloud-relay/status", headers=_auth_headers())

        mock_record.assert_called()


# =============================================================================
# Exempt endpoints (should NOT call record_hook_activity)
# =============================================================================


class TestActivityTrackingExemptEndpoints:
    """Verify that exempt endpoints do NOT trigger activity tracking."""

    def test_api_health_does_not_trigger_activity(self, client):
        """GET /api/health does NOT call record_hook_activity()."""
        state = get_state()
        with patch.object(state, "record_hook_activity") as mock_record:
            client.get("/api/health")

        mock_record.assert_not_called()

    def test_api_status_does_not_trigger_activity(self, client):
        """GET /api/status does NOT call record_hook_activity()."""
        state = get_state()
        with patch.object(state, "record_hook_activity") as mock_record:
            client.get("/api/status", headers=_auth_headers())

        mock_record.assert_not_called()


# =============================================================================
# Non-API paths (should NOT call record_hook_activity)
# =============================================================================


class TestActivityTrackingNonApiPaths:
    """Verify that non-/api/ paths do NOT trigger activity tracking."""

    def test_static_asset_does_not_trigger_activity(self, client):
        """GET /static/app.js does NOT call record_hook_activity()."""
        state = get_state()
        with patch.object(state, "record_hook_activity") as mock_record:
            client.get("/static/nonexistent.js")

        mock_record.assert_not_called()

    def test_dashboard_root_does_not_trigger_activity(self, client):
        """GET / does NOT call record_hook_activity()."""
        state = get_state()
        with patch.object(state, "record_hook_activity") as mock_record:
            client.get("/")

        mock_record.assert_not_called()

    def test_favicon_does_not_trigger_activity(self, client):
        """GET /favicon.png does NOT call record_hook_activity()."""
        state = get_state()
        with patch.object(state, "record_hook_activity") as mock_record:
            client.get("/favicon.png")

        mock_record.assert_not_called()


# =============================================================================
# Unauthenticated requests — auth rejects before activity middleware
# =============================================================================


class TestActivityTrackingAuth:
    """Verify that unauthenticated requests are rejected by auth before
    reaching the activity tracking middleware.

    ActivityTrackingMiddleware is registered as the innermost middleware.
    In Starlette's add_middleware LIFO ordering, TokenAuthMiddleware (added
    after activity) runs first. Unauthenticated requests are rejected by
    auth and never reach the activity middleware.
    """

    def test_unauthenticated_api_request_not_tracked(self, client):
        """Unauthenticated /api/team/config is rejected by auth, never tracked."""
        state = get_state()
        with patch.object(state, "record_hook_activity") as mock_record:
            response = client.get("/api/team/config")

        assert response.status_code == HTTPStatus.UNAUTHORIZED
        mock_record.assert_not_called()
