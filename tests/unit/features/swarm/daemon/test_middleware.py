"""Tests for the swarm daemon TokenAuthMiddleware.

Tests cover:
- Health endpoint is exempt from auth
- Static assets are exempt from auth
- Dashboard routes are exempt from auth
- Non-API paths bypass auth
- Missing Authorization header returns 401
- Invalid Bearer scheme returns 401
- Invalid token returns 401
- Valid token passes through
- Ephemeral token generation when no token is configured
"""

import json
from http import HTTPStatus
from unittest.mock import AsyncMock

import pytest

from open_agent_kit.features.swarm.constants import (
    SWARM_AUTH_ERROR_INVALID_SCHEME,
    SWARM_AUTH_ERROR_INVALID_TOKEN,
    SWARM_AUTH_ERROR_MISSING,
    SWARM_DAEMON_API_PATH_HEALTH,
)
from open_agent_kit.features.swarm.daemon.middleware import (
    TokenAuthMiddleware,
    _is_auth_exempt,
)
from open_agent_kit.features.swarm.daemon.state import get_swarm_state, reset_swarm_state


@pytest.fixture()
def anyio_backend() -> str:
    """Restrict anyio tests to asyncio backend."""
    return "asyncio"


@pytest.fixture(autouse=True)
def _clean_state() -> None:
    """Reset singleton state before each test."""
    reset_swarm_state()
    yield  # type: ignore[misc]
    reset_swarm_state()


# =========================================================================
# _is_auth_exempt() tests
# =========================================================================


class TestIsAuthExempt:
    """Test auth exemption logic."""

    def test_health_get_is_exempt(self) -> None:
        assert _is_auth_exempt(SWARM_DAEMON_API_PATH_HEALTH, "GET") is True

    def test_health_post_is_not_exempt(self) -> None:
        assert _is_auth_exempt(SWARM_DAEMON_API_PATH_HEALTH, "POST") is False

    def test_static_assets_are_exempt(self) -> None:
        assert _is_auth_exempt("/static/app.js", "GET") is True
        assert _is_auth_exempt("/favicon.png", "GET") is True

    def test_dashboard_root_is_exempt(self) -> None:
        assert _is_auth_exempt("/", "GET") is True
        assert _is_auth_exempt("/ui", "GET") is True
        assert _is_auth_exempt("/ui/config", "GET") is True

    def test_api_routes_require_auth(self) -> None:
        assert _is_auth_exempt("/api/swarm/search", "POST") is False
        assert _is_auth_exempt("/api/config", "GET") is False

    def test_non_api_paths_are_exempt(self) -> None:
        assert _is_auth_exempt("/some/other/path", "GET") is True


# =========================================================================
# TokenAuthMiddleware integration tests
# =========================================================================


def _make_scope(path: str, method: str = "GET", headers: list | None = None) -> dict:
    """Build a minimal ASGI HTTP scope."""
    raw_headers = []
    for name, value in headers or []:
        raw_headers.append((name.lower().encode(), value.encode()))
    return {
        "type": "http",
        "path": path,
        "method": method,
        "headers": raw_headers,
    }


class TestTokenAuthMiddleware:
    """Test the ASGI middleware."""

    @pytest.fixture()
    def middleware(self) -> TokenAuthMiddleware:
        app = AsyncMock()
        return TokenAuthMiddleware(app)

    @pytest.mark.anyio
    async def test_exempt_path_passes_through(self, middleware: TokenAuthMiddleware) -> None:
        """Health endpoint bypasses auth entirely."""
        scope = _make_scope(SWARM_DAEMON_API_PATH_HEALTH, "GET")
        receive = AsyncMock()
        send = AsyncMock()
        await middleware(scope, receive, send)
        middleware.app.assert_awaited_once_with(scope, receive, send)

    @pytest.mark.anyio
    async def test_missing_header_returns_401(self, middleware: TokenAuthMiddleware) -> None:
        """API request without Authorization header gets 401."""
        state = get_swarm_state()
        state.auth_token = "test-token"

        scope = _make_scope("/api/swarm/search", "POST")
        receive = AsyncMock()
        send = AsyncMock()
        await middleware(scope, receive, send)

        # Should have sent a response, not passed through
        middleware.app.assert_not_awaited()
        # Check the response status
        start_call = send.call_args_list[0]
        response_start = start_call[0][0]
        assert response_start["status"] == HTTPStatus.UNAUTHORIZED

        body_call = send.call_args_list[1]
        body = json.loads(body_call[0][0]["body"])
        assert body["detail"] == SWARM_AUTH_ERROR_MISSING

    @pytest.mark.anyio
    async def test_invalid_scheme_returns_401(self, middleware: TokenAuthMiddleware) -> None:
        """Non-Bearer auth scheme gets 401."""
        state = get_swarm_state()
        state.auth_token = "test-token"

        scope = _make_scope("/api/swarm/nodes", "GET", headers=[("Authorization", "Basic abc123")])
        receive = AsyncMock()
        send = AsyncMock()
        await middleware(scope, receive, send)

        middleware.app.assert_not_awaited()
        body_call = send.call_args_list[1]
        body = json.loads(body_call[0][0]["body"])
        assert body["detail"] == SWARM_AUTH_ERROR_INVALID_SCHEME

    @pytest.mark.anyio
    async def test_invalid_token_returns_401(self, middleware: TokenAuthMiddleware) -> None:
        """Wrong Bearer token gets 401."""
        state = get_swarm_state()
        state.auth_token = "correct-token"

        scope = _make_scope(
            "/api/swarm/nodes", "GET", headers=[("Authorization", "Bearer wrong-token")]
        )
        receive = AsyncMock()
        send = AsyncMock()
        await middleware(scope, receive, send)

        middleware.app.assert_not_awaited()
        body_call = send.call_args_list[1]
        body = json.loads(body_call[0][0]["body"])
        assert body["detail"] == SWARM_AUTH_ERROR_INVALID_TOKEN

    @pytest.mark.anyio
    async def test_valid_token_passes_through(self, middleware: TokenAuthMiddleware) -> None:
        """Correct Bearer token allows the request through."""
        state = get_swarm_state()
        state.auth_token = "correct-token"

        scope = _make_scope(
            "/api/swarm/search", "POST", headers=[("Authorization", "Bearer correct-token")]
        )
        receive = AsyncMock()
        send = AsyncMock()
        await middleware(scope, receive, send)

        middleware.app.assert_awaited_once_with(scope, receive, send)

    @pytest.mark.anyio
    async def test_generates_ephemeral_token_when_none(
        self, middleware: TokenAuthMiddleware
    ) -> None:
        """When auth_token is None, an ephemeral token is generated."""
        state = get_swarm_state()
        assert state.auth_token is None

        scope = _make_scope("/api/swarm/nodes", "GET")
        receive = AsyncMock()
        send = AsyncMock()
        await middleware(scope, receive, send)

        # Token should have been generated
        assert state.auth_token is not None
        assert len(state.auth_token) > 0

    @pytest.mark.anyio
    async def test_non_http_scope_passes_through(self, middleware: TokenAuthMiddleware) -> None:
        """Non-HTTP scopes (e.g. websocket) bypass auth."""
        scope = {"type": "websocket", "path": "/api/ws"}
        receive = AsyncMock()
        send = AsyncMock()
        await middleware(scope, receive, send)
        middleware.app.assert_awaited_once_with(scope, receive, send)
