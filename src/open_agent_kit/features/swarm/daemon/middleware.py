"""Authentication middleware for the swarm daemon.

Provides Bearer token authentication for ``/api/*`` routes, exempting
the health endpoint so liveness probes work without credentials.
"""

import hmac
import json
import logging
import secrets
from http import HTTPStatus

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

from open_agent_kit.features.swarm.constants import (
    SWARM_AUTH_EPHEMERAL_TOKEN_BYTES,
    SWARM_AUTH_ERROR_INVALID_SCHEME,
    SWARM_AUTH_ERROR_INVALID_TOKEN,
    SWARM_AUTH_ERROR_MISSING,
    SWARM_AUTH_HEADER_NAME,
    SWARM_AUTH_SCHEME_BEARER,
    SWARM_AUTH_WARNING_NO_TOKEN,
    SWARM_DAEMON_API_PATH_HEALTH,
)
from open_agent_kit.features.swarm.daemon.state import get_swarm_state

logger = logging.getLogger(__name__)

# ASGI message types
_SCOPE_HTTP = "http"
_RESPONSE_START = "http.response.start"
_RESPONSE_BODY = "http.response.body"

# Paths exempt from authentication.
_AUTH_EXEMPT_PREFIXES: tuple[str, ...] = (
    "/static/",
    "/favicon.png",
    "/logo.png",
)

# High-frequency polling paths — suppress "Auth OK" debug noise.
_AUTH_QUIET_PATHS: tuple[str, ...] = (
    "/api/swarm/status",
    "/api/logs",
    "/api/config",
)

# Dashboard HTML routes served without auth (SPA shell).
_DASHBOARD_ROUTES: tuple[str, ...] = (
    "/",
    "/ui",
)


def _is_auth_exempt(path: str, method: str) -> bool:
    """Check if a request path is exempt from token authentication.

    Args:
        path: The request URL path.
        method: The HTTP method.

    Returns:
        True if the request should bypass authentication.
    """
    # Health endpoint is always accessible (liveness probes)
    if path == SWARM_DAEMON_API_PATH_HEALTH and method == "GET":
        return True

    # Static assets
    for prefix in _AUTH_EXEMPT_PREFIXES:
        if path.startswith(prefix):
            return True

    # Dashboard HTML routes (exact or prefix with /)
    for route in _DASHBOARD_ROUTES:
        if path == route or path.startswith(route + "/"):
            return True

    # Only /api/* paths require auth; anything else passes through
    if not path.startswith("/api/"):
        return True

    return False


async def _send_json_error(send: Send, status: int, detail: str) -> None:
    """Send a JSON error response via raw ASGI.

    Args:
        send: The ASGI send callable.
        status: HTTP status code.
        detail: Error detail message.
    """
    body = json.dumps({"detail": detail}).encode()
    await send(
        {
            "type": _RESPONSE_START,
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": _RESPONSE_BODY, "body": body})


class TokenAuthMiddleware:
    """ASGI middleware that validates Bearer token on /api/* routes.

    If ``auth_token`` is None (env var unset), an ephemeral token is
    generated. This enables graceful degradation for manual ``uvicorn``
    dev starts where the manager isn't generating tokens.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != _SCOPE_HTTP:
            await self.app(scope, receive, send)
            return

        state = get_swarm_state()

        # No token configured -- generate ephemeral token
        if state.auth_token is None:
            state.auth_token = secrets.token_hex(SWARM_AUTH_EPHEMERAL_TOKEN_BYTES)
            logger.warning(SWARM_AUTH_WARNING_NO_TOKEN)

        path: str = scope.get("path", "")
        method: str = scope.get("method", "GET")

        # Exempt paths bypass auth
        if _is_auth_exempt(path, method):
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        auth_value = headers.get(SWARM_AUTH_HEADER_NAME)

        if not auth_value:
            logger.debug("Auth rejected: missing header for %s %s", method, path)
            await _send_json_error(send, HTTPStatus.UNAUTHORIZED, SWARM_AUTH_ERROR_MISSING)
            return

        # Expect "Bearer <token>"
        parts = auth_value.split(None, 1)
        if len(parts) != 2 or parts[0] != SWARM_AUTH_SCHEME_BEARER:
            await _send_json_error(send, HTTPStatus.UNAUTHORIZED, SWARM_AUTH_ERROR_INVALID_SCHEME)
            return

        if not hmac.compare_digest(parts[1], state.auth_token):
            logger.debug("Auth rejected: invalid token for %s %s", method, path)
            await _send_json_error(send, HTTPStatus.UNAUTHORIZED, SWARM_AUTH_ERROR_INVALID_TOKEN)
            return

        # Token valid -- proceed (suppress debug noise for polling paths)
        if path not in _AUTH_QUIET_PATHS:
            logger.debug("Auth OK: %s %s", method, path)
        await self.app(scope, receive, send)
