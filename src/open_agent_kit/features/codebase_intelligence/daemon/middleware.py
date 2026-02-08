"""Middleware for the CI daemon.

Includes:
- DynamicCORSMiddleware: Runtime-configurable CORS for tunnel URLs.
- TokenAuthMiddleware: Bearer token authentication for /api/* routes.
- RequestSizeLimitMiddleware: Content-Length enforcement to prevent memory exhaustion.
"""

import logging
from collections.abc import MutableMapping
from http import HTTPStatus
from typing import Any

from starlette.datastructures import Headers, MutableHeaders
from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from open_agent_kit.features.codebase_intelligence.constants import (
    CI_AUTH_ERROR_INVALID_SCHEME,
    CI_AUTH_ERROR_INVALID_TOKEN,
    CI_AUTH_ERROR_MISSING,
    CI_AUTH_ERROR_PAYLOAD_TOO_LARGE,
    CI_AUTH_HEADER_NAME,
    CI_AUTH_SCHEME_BEARER,
    CI_CORS_EMPTY_BODY,
    CI_CORS_HEADER_ALLOW_HEADERS,
    CI_CORS_HEADER_ALLOW_METHODS,
    CI_CORS_HEADER_ALLOW_ORIGIN,
    CI_CORS_HEADER_MAX_AGE,
    CI_CORS_HEADER_ORIGIN,
    CI_CORS_HEADER_ORIGIN_CAP,
    CI_CORS_HEADER_VARY,
    CI_CORS_MAX_AGE_SECONDS,
    CI_CORS_METHOD_OPTIONS,
    CI_CORS_RESPONSE_BODY_TYPE,
    CI_CORS_RESPONSE_START_TYPE,
    CI_CORS_SCOPE_HTTP,
    CI_CORS_WILDCARD,
    CI_MAX_REQUEST_BODY_BYTES,
)
from open_agent_kit.features.codebase_intelligence.daemon.state import get_state

logger = logging.getLogger(__name__)

# Paths that are exempt from token authentication.
# These are served without auth: static assets, favicon, dashboard HTML routes.
_AUTH_EXEMPT_PREFIXES: tuple[str, ...] = (
    "/static/",
    "/favicon.png",
    "/logo.png",
)

# Dashboard HTML routes (exact match or prefix match with /).
# These serve the SPA shell and must be accessible without auth.
_DASHBOARD_ROUTES: tuple[str, ...] = (
    "/",
    "/ui",
    "/search",
    "/logs",
    "/config",
    "/help",
    "/activity",
    "/devtools",
    "/team",
    "/agents",
)


class DynamicCORSMiddleware(CORSMiddleware):
    """CORS middleware that checks both static and dynamic origins.

    Static origins (localhost) are configured at startup via the parent class.
    Dynamic origins (tunnel URLs) are read from DaemonState at request time.
    """

    def __init__(
        self,
        app: ASGIApp,
        allow_origins: list[str] | None = None,
        allow_methods: list[str] | None = None,
        allow_headers: list[str] | None = None,
        allow_credentials: bool = False,
    ) -> None:
        # Store static origins for our own checking
        self._static_origins: set[str] = set(allow_origins or [])

        # Initialize parent with allow_origins=[] so it doesn't do its own
        # origin matching. We handle origin checking ourselves.
        super().__init__(
            app,
            allow_origins=[],
            allow_methods=allow_methods or [CI_CORS_WILDCARD],
            allow_headers=allow_headers or [CI_CORS_WILDCARD],
            allow_credentials=allow_credentials,
        )

    def is_allowed_origin(self, origin: str) -> bool:
        """Check if origin is allowed (static or dynamic).

        Args:
            origin: The Origin header value from the request.

        Returns:
            True if the origin is in static or dynamic allowed origins.
        """
        if not origin:
            return False

        # Check static origins (localhost)
        if origin in self._static_origins:
            return True

        # Check dynamic origins (tunnel URLs)
        dynamic_origins = get_state().get_dynamic_cors_origins()
        return origin in dynamic_origins

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle CORS for both static and dynamic origins."""
        if scope["type"] != CI_CORS_SCOPE_HTTP:
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        origin = headers.get(CI_CORS_HEADER_ORIGIN)

        # No origin header — not a CORS request, pass through
        if not origin:
            await self.app(scope, receive, send)
            return

        if not self.is_allowed_origin(origin):
            # Origin not allowed — pass through without CORS headers
            # (browser will block the response)
            await self.app(scope, receive, send)
            return

        # Handle preflight (OPTIONS) requests
        if scope["method"] == CI_CORS_METHOD_OPTIONS:
            preflight_headers = {
                CI_CORS_HEADER_ALLOW_ORIGIN: origin,
                CI_CORS_HEADER_ALLOW_METHODS: ", ".join(self.allow_methods),
                CI_CORS_HEADER_ALLOW_HEADERS: ", ".join(self.allow_headers),
                CI_CORS_HEADER_MAX_AGE: str(CI_CORS_MAX_AGE_SECONDS),
                CI_CORS_HEADER_VARY: CI_CORS_HEADER_ORIGIN_CAP,
            }

            await send(
                {
                    "type": CI_CORS_RESPONSE_START_TYPE,
                    "status": HTTPStatus.OK,
                    "headers": [(k.encode(), v.encode()) for k, v in preflight_headers.items()],
                }
            )
            await send({"type": CI_CORS_RESPONSE_BODY_TYPE, "body": CI_CORS_EMPTY_BODY})
            return

        # For actual requests, inject CORS headers into the response
        async def send_with_cors(message: MutableMapping[str, Any]) -> None:
            if message["type"] == CI_CORS_RESPONSE_START_TYPE:
                headers = MutableHeaders(raw=list(message.get("headers", [])))
                headers[CI_CORS_HEADER_ALLOW_ORIGIN] = origin
                headers[CI_CORS_HEADER_VARY] = CI_CORS_HEADER_ORIGIN_CAP
                message["headers"] = headers.raw
            await send(message)

        await self.app(scope, receive, send_with_cors)


def _is_auth_exempt(path: str, method: str) -> bool:
    """Check if a request path is exempt from token authentication.

    Exempt paths include:
    - GET /api/health (liveness probe)
    - Static assets (/static/*, /favicon.png, /logo.png)
    - Dashboard HTML routes (/, /ui, /search, etc. and their sub-routes)
    - Any non-/api/ path not covered above (future-proof)

    Args:
        path: The request URL path.
        method: The HTTP method (GET, POST, etc.).

    Returns:
        True if the request should bypass authentication.
    """
    # Health endpoint is always accessible (liveness probes, CLI health checks)
    if path == "/api/health" and method == "GET":
        return True

    # Non-API paths: static assets, favicon, logo
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
    import json

    body = json.dumps({"detail": detail}).encode()
    await send(
        {
            "type": CI_CORS_RESPONSE_START_TYPE,
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": CI_CORS_RESPONSE_BODY_TYPE, "body": body})


class TokenAuthMiddleware:
    """ASGI middleware that validates Bearer token on /api/* routes.

    If ``auth_token`` is None (env var unset), all requests pass through.
    This enables graceful degradation for manual ``uvicorn`` dev starts
    where the manager isn't generating tokens.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != CI_CORS_SCOPE_HTTP:
            await self.app(scope, receive, send)
            return

        state = get_state()

        # No token configured — pass all requests through (dev mode)
        if state.auth_token is None:
            await self.app(scope, receive, send)
            return

        path: str = scope.get("path", "")
        method: str = scope.get("method", "GET")

        # Exempt paths bypass auth
        if _is_auth_exempt(path, method):
            await self.app(scope, receive, send)
            return

        # Extract and validate Authorization header
        headers = Headers(scope=scope)
        auth_value = headers.get(CI_AUTH_HEADER_NAME)

        if not auth_value:
            await _send_json_error(send, HTTPStatus.UNAUTHORIZED, CI_AUTH_ERROR_MISSING)
            return

        # Expect "Bearer <token>"
        parts = auth_value.split(None, 1)
        if len(parts) != 2 or parts[0] != CI_AUTH_SCHEME_BEARER:
            await _send_json_error(send, HTTPStatus.UNAUTHORIZED, CI_AUTH_ERROR_INVALID_SCHEME)
            return

        if parts[1] != state.auth_token:
            await _send_json_error(send, HTTPStatus.UNAUTHORIZED, CI_AUTH_ERROR_INVALID_TOKEN)
            return

        # Token valid — proceed
        await self.app(scope, receive, send)


class RequestSizeLimitMiddleware:
    """ASGI middleware that enforces a maximum request body size.

    Checks the ``Content-Length`` header and returns 413 if the declared
    size exceeds ``CI_MAX_REQUEST_BODY_BYTES``.  Requests without a
    ``Content-Length`` header pass through (chunked transfers are bounded
    by uvicorn's own limits).
    """

    def __init__(self, app: ASGIApp, max_bytes: int = CI_MAX_REQUEST_BODY_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != CI_CORS_SCOPE_HTTP:
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        content_length = headers.get("content-length")

        if content_length is not None:
            try:
                if int(content_length) > self.max_bytes:
                    await _send_json_error(
                        send,
                        HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                        CI_AUTH_ERROR_PAYLOAD_TOO_LARGE,
                    )
                    return
            except ValueError:
                pass  # Non-numeric Content-Length — let downstream handle it

        await self.app(scope, receive, send)
