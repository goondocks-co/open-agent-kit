"""Tests for daemon authentication and request size middleware.

Tests cover:
- TokenAuthMiddleware: Bearer token validation on /api/* routes
- TokenAuthMiddleware: Exempt paths bypass authentication
- TokenAuthMiddleware: Graceful degradation when no token configured
- RequestSizeLimitMiddleware: Content-Length enforcement
"""

from http import HTTPStatus
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from open_agent_kit.features.codebase_intelligence.constants import (
    CI_AUTH_ENV_VAR,
    CI_AUTH_ERROR_INVALID_SCHEME,
    CI_AUTH_ERROR_INVALID_TOKEN,
    CI_AUTH_ERROR_MISSING,
    CI_AUTH_ERROR_PAYLOAD_TOO_LARGE,
    CI_AUTH_SCHEME_BEARER,
    CI_MAX_REQUEST_BODY_BYTES,
)
from open_agent_kit.features.codebase_intelligence.daemon.server import create_app
from open_agent_kit.features.codebase_intelligence.daemon.state import reset_state

TEST_TOKEN = "a" * 64  # 64 hex chars, like secrets.token_hex(32)


@pytest.fixture(autouse=True)
def _reset_daemon_state():
    """Reset daemon state before and after each test."""
    reset_state()
    yield
    reset_state()


@pytest.fixture
def authed_client(monkeypatch, tmp_path: Path):
    """FastAPI test client with auth token configured."""
    monkeypatch.setenv(CI_AUTH_ENV_VAR, TEST_TOKEN)
    app = create_app(project_root=tmp_path)
    return TestClient(app)


@pytest.fixture
def no_auth_client(monkeypatch, tmp_path: Path):
    """FastAPI test client with NO auth token (graceful degradation)."""
    monkeypatch.delenv(CI_AUTH_ENV_VAR, raising=False)
    app = create_app(project_root=tmp_path)
    return TestClient(app)


# =============================================================================
# TokenAuthMiddleware — Valid Token Tests
# =============================================================================


class TestTokenAuthValidToken:
    """Test requests with valid Bearer token."""

    def test_valid_token_returns_200(self, authed_client):
        """Test that a valid token passes authentication."""
        response = authed_client.get(
            "/api/health",
            headers={"Authorization": f"{CI_AUTH_SCHEME_BEARER} {TEST_TOKEN}"},
        )
        assert response.status_code == HTTPStatus.OK

    def test_valid_token_on_api_status(self, authed_client):
        """Test that a valid token works on /api/status."""
        response = authed_client.get(
            "/api/status",
            headers={"Authorization": f"{CI_AUTH_SCHEME_BEARER} {TEST_TOKEN}"},
        )
        assert response.status_code == HTTPStatus.OK


# =============================================================================
# TokenAuthMiddleware — Missing / Invalid Token Tests
# =============================================================================


class TestTokenAuthInvalidToken:
    """Test requests with missing or invalid tokens."""

    def test_missing_auth_header_returns_401(self, authed_client):
        """Test that missing Authorization header returns 401."""
        response = authed_client.get("/api/status")
        assert response.status_code == HTTPStatus.UNAUTHORIZED
        assert response.json()["detail"] == CI_AUTH_ERROR_MISSING

    def test_wrong_token_returns_401(self, authed_client):
        """Test that an incorrect token returns 401."""
        response = authed_client.get(
            "/api/status",
            headers={"Authorization": f"{CI_AUTH_SCHEME_BEARER} wrong-token"},
        )
        assert response.status_code == HTTPStatus.UNAUTHORIZED
        assert response.json()["detail"] == CI_AUTH_ERROR_INVALID_TOKEN

    def test_wrong_scheme_returns_401(self, authed_client):
        """Test that a non-Bearer scheme returns 401."""
        response = authed_client.get(
            "/api/status",
            headers={"Authorization": f"Basic {TEST_TOKEN}"},
        )
        assert response.status_code == HTTPStatus.UNAUTHORIZED
        assert response.json()["detail"] == CI_AUTH_ERROR_INVALID_SCHEME

    def test_empty_auth_header_returns_401(self, authed_client):
        """Test that an empty Authorization header returns 401."""
        response = authed_client.get(
            "/api/status",
            headers={"Authorization": ""},
        )
        assert response.status_code == HTTPStatus.UNAUTHORIZED

    def test_bearer_without_token_returns_401(self, authed_client):
        """Test that 'Bearer' without a token value returns 401."""
        response = authed_client.get(
            "/api/status",
            headers={"Authorization": CI_AUTH_SCHEME_BEARER},
        )
        assert response.status_code == HTTPStatus.UNAUTHORIZED


# =============================================================================
# TokenAuthMiddleware — Exempt Path Tests
# =============================================================================


class TestTokenAuthExemptPaths:
    """Test that exempt paths bypass authentication."""

    def test_health_endpoint_exempt(self, authed_client):
        """Test that GET /api/health is accessible without token."""
        response = authed_client.get("/api/health")
        assert response.status_code == HTTPStatus.OK

    def test_health_endpoint_post_not_exempt(self, authed_client):
        """Test that POST /api/health is NOT exempt (only GET is)."""
        response = authed_client.post("/api/health")
        # POST to /api/health needs auth (will be 401 or 405 depending on route)
        # The key is that it's not exempt — middleware should check auth
        assert response.status_code in (
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.METHOD_NOT_ALLOWED,
        )

    def test_dashboard_root_exempt(self, authed_client):
        """Test that / (dashboard) is accessible without token."""
        response = authed_client.get("/")
        # Should not be 401 — dashboard routes are exempt
        assert response.status_code != HTTPStatus.UNAUTHORIZED

    def test_dashboard_ui_route_exempt(self, authed_client):
        """Test that /ui is accessible without token."""
        response = authed_client.get("/ui")
        assert response.status_code != HTTPStatus.UNAUTHORIZED

    def test_dashboard_search_route_exempt(self, authed_client):
        """Test that /search is accessible without token."""
        response = authed_client.get("/search")
        assert response.status_code != HTTPStatus.UNAUTHORIZED

    def test_dashboard_devtools_route_exempt(self, authed_client):
        """Test that /devtools HTML route is accessible without token."""
        response = authed_client.get("/devtools")
        assert response.status_code != HTTPStatus.UNAUTHORIZED

    def test_static_assets_exempt(self, authed_client):
        """Test that /static/ paths are accessible without token."""
        response = authed_client.get("/static/nonexistent.js")
        # 404 is fine — the key is it's not 401
        assert response.status_code != HTTPStatus.UNAUTHORIZED

    def test_favicon_exempt(self, authed_client):
        """Test that /favicon.png is accessible without token."""
        response = authed_client.get("/favicon.png")
        assert response.status_code != HTTPStatus.UNAUTHORIZED


# =============================================================================
# TokenAuthMiddleware — Graceful Degradation (No Token)
# =============================================================================


class TestTokenAuthNoTokenConfigured:
    """Test that auth is disabled when no token is configured."""

    def test_api_accessible_without_token_when_not_configured(self, no_auth_client):
        """Test that /api/status passes when no auth token is set."""
        response = no_auth_client.get("/api/status")
        assert response.status_code == HTTPStatus.OK

    def test_health_still_works(self, no_auth_client):
        """Test that /api/health works when auth is disabled."""
        response = no_auth_client.get("/api/health")
        assert response.status_code == HTTPStatus.OK


# =============================================================================
# TokenAuthMiddleware — OPTIONS Preflight
# =============================================================================


class TestTokenAuthPreflight:
    """Test that CORS preflight requests bypass auth."""

    def test_options_preflight_bypasses_auth(self, monkeypatch, tmp_path: Path):
        """Test that OPTIONS preflight with matching origin bypasses auth.

        CORS preflight is handled by the outermost CORS middleware
        before reaching TokenAuth. The origin must match the daemon's
        allowed origins for CORS to intercept the request.
        """
        from open_agent_kit.features.codebase_intelligence.constants import (
            CI_CORS_HOST_LOCALHOST,
            CI_CORS_ORIGIN_TEMPLATE,
            CI_CORS_SCHEME_HTTP,
            CI_SHARED_PORT_DIR,
            CI_SHARED_PORT_FILE,
        )
        from open_agent_kit.features.codebase_intelligence.daemon.manager import (
            PORT_RANGE_START,
        )

        monkeypatch.setenv(CI_AUTH_ENV_VAR, TEST_TOKEN)

        # Set up a port file so CORS allows the right origin
        project_root = tmp_path / "project"
        project_root.mkdir()
        shared_port_dir = project_root / CI_SHARED_PORT_DIR
        shared_port_dir.mkdir(parents=True)
        port = PORT_RANGE_START
        (shared_port_dir / CI_SHARED_PORT_FILE).write_text(str(port))

        app = create_app(project_root=project_root)
        client = TestClient(app)

        allowed_origin = CI_CORS_ORIGIN_TEMPLATE.format(
            scheme=CI_CORS_SCHEME_HTTP,
            host=CI_CORS_HOST_LOCALHOST,
            port=port,
        )

        response = client.options(
            "/api/status",
            headers={
                "Origin": allowed_origin,
                "Access-Control-Request-Method": "GET",
            },
        )
        # CORS middleware should return 200 without hitting auth
        assert response.status_code == HTTPStatus.OK


# =============================================================================
# RequestSizeLimitMiddleware Tests
# =============================================================================


class TestRequestSizeLimit:
    """Test request body size limit enforcement."""

    def test_small_request_passes(self, authed_client):
        """Test that small requests pass the size check."""
        response = authed_client.get(
            "/api/health",
            headers={"Content-Length": "100"},
        )
        assert response.status_code == HTTPStatus.OK

    def test_oversized_request_returns_413(self, authed_client):
        """Test that oversized requests return 413."""
        oversized = str(CI_MAX_REQUEST_BODY_BYTES + 1)
        response = authed_client.get(
            "/api/health",
            headers={"Content-Length": oversized},
        )
        assert response.status_code == HTTPStatus.REQUEST_ENTITY_TOO_LARGE
        assert response.json()["detail"] == CI_AUTH_ERROR_PAYLOAD_TOO_LARGE

    def test_exact_limit_passes(self, authed_client):
        """Test that a request at exactly the limit passes."""
        exact = str(CI_MAX_REQUEST_BODY_BYTES)
        response = authed_client.get(
            "/api/health",
            headers={"Content-Length": exact},
        )
        # Should pass size check (at limit, not over)
        assert response.status_code != HTTPStatus.REQUEST_ENTITY_TOO_LARGE

    def test_no_content_length_passes(self, authed_client):
        """Test that requests without Content-Length pass through."""
        response = authed_client.get("/api/health")
        assert response.status_code == HTTPStatus.OK
