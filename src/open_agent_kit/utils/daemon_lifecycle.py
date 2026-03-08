"""Shared daemon lifecycle helpers used by team and swarm daemon routes.

Centralises the ``delayed_shutdown`` coroutine that is duplicated across
release-channel and restart route modules.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal

logger = logging.getLogger(__name__)


async def delayed_shutdown(delay_seconds: float, *, log_message: str | None = None) -> None:
    """Wait *delay_seconds* then send SIGTERM to trigger a graceful shutdown.

    Args:
        delay_seconds: How long to wait before sending the signal.
        log_message: Optional message logged at INFO level just before the
            signal is sent.  Falls back to a generic message when ``None``.
    """
    await asyncio.sleep(delay_seconds)
    logger.info(log_message or "Shutting down daemon (SIGTERM).")
    os.kill(os.getpid(), signal.SIGTERM)
