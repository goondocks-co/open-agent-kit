"""Dynamic CORS middleware for the CI daemon.

Extends Starlette's CORS handling with runtime-configurable origins
to support tunnel URLs that are only known after the tunnel starts.
"""

import logging
from collections.abc import MutableMapping
from http import HTTPStatus
from typing import Any

from starlette.datastructures import Headers, MutableHeaders
from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from open_agent_kit.features.codebase_intelligence.constants import (
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
)
from open_agent_kit.features.codebase_intelligence.daemon.state import get_state

logger = logging.getLogger(__name__)


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
