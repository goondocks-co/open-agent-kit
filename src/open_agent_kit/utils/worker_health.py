"""Cached health probe for deployed Cloudflare Workers.

Shared by both the swarm and team (cloud relay) daemon status endpoints.
The probe hits the worker's ``/health`` endpoint and caches the result
for ``WORKER_HEALTH_PROBE_TTL_SECONDS`` to avoid excessive outbound calls
when the UI polls status every few seconds.
"""

import logging
import time

import httpx

from open_agent_kit.utils.worker_scaffold_shared import (
    WORKER_HEALTH_PROBE_PATH,
    WORKER_HEALTH_PROBE_TIMEOUT_SECONDS,
    WORKER_HEALTH_PROBE_TTL_SECONDS,
)

logger = logging.getLogger(__name__)

_cache: dict[str, tuple[bool, float]] = {}
_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    """Return a module-level reusable async HTTP client."""
    global _http_client  # noqa: PLW0603
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient()
    return _http_client


def invalidate_health_cache(url: str | None = None) -> None:
    """Clear cached health results.

    Args:
        url: If given, clear only that URL's cache entry.
             If ``None``, clear all entries.
    """
    if url is None:
        _cache.clear()
    else:
        _cache.pop(url, None)


async def probe_worker_health(url: str) -> bool:
    """Probe a deployed worker's health endpoint with TTL caching.

    Args:
        url: Base URL of the worker (e.g. ``https://oak-swarm-foo.workers.dev``).

    Returns:
        ``True`` if the worker responded 200 within the timeout,
        ``False`` otherwise.
    """
    now = time.monotonic()
    cached = _cache.get(url)
    if cached is not None:
        result, cached_at = cached
        if now - cached_at < WORKER_HEALTH_PROBE_TTL_SECONDS:
            return result

    health_url = f"{url.rstrip('/')}{WORKER_HEALTH_PROBE_PATH}"
    try:
        client = _get_http_client()
        resp = await client.get(health_url, timeout=WORKER_HEALTH_PROBE_TIMEOUT_SECONDS)
        reachable = resp.status_code == 200
    except Exception:
        logger.debug("Health probe failed for %s", url, exc_info=True)
        reachable = False

    _cache[url] = (reachable, now)
    return reachable
