"""Shared helpers for the CloudRelayClient package."""

from __future__ import annotations

import httpx


def _is_auth_failure(exc: BaseException) -> bool:
    """Check whether an exception indicates an HTTP auth failure (401/403).

    Inspects typed exception attributes rather than fragile string matching.
    Handles websockets.exceptions.InvalidStatus (WS handshake rejection)
    and httpx.HTTPStatusError (HTTP response errors).
    """
    from open_agent_kit.features.team.constants import (
        CLOUD_RELAY_AUTH_FAILURE_STATUS_CODES,
    )

    # websockets raises InvalidStatus with response.status_code on handshake rejection
    try:
        from websockets.exceptions import InvalidStatus

        if isinstance(exc, InvalidStatus):
            return exc.response.status_code in CLOUD_RELAY_AUTH_FAILURE_STATUS_CODES
    except ImportError:
        pass  # websockets not installed; skip this check

    # httpx raises HTTPStatusError with response.status_code
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in CLOUD_RELAY_AUTH_FAILURE_STATUS_CODES

    # ConnectionError from _establish_connection carries the error text from the
    # relay, but we only detect auth from typed exceptions above.
    return False
