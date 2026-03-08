"""Swarm operations mixin for CloudRelayClient.

Handles cross-project federation via WebSocket: swarm search, node listing,
status, and advisory fetching.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import uuid4

from open_agent_kit.features.team.cloud_relay.protocol import (
    SwarmNodesMessage,
    SwarmSearchMessage,
)
from open_agent_kit.features.team.constants import (
    SWARM_DEFAULT_SEARCH_TIMEOUT_SECONDS,
)

logger = logging.getLogger(__name__)


class SwarmMixin:
    """Mixin providing swarm (cross-project) operations."""

    # Attributes set by CloudRelayClient.__init__
    _ws: Any
    _connected: bool
    _worker_url: str | None
    _token: str | None
    _machine_id: str
    _swarm_connected: bool
    _swarm_id: str | None
    _pending_swarm: dict[str, asyncio.Future[dict[str, Any]]]

    # Methods provided by other mixins / core (declared for mypy)
    _get_http_client: Any
    _relay_auth_headers: Any

    async def _send_swarm_request(
        self,
        message: str,
        request_id: str,
        timeout: float,
    ) -> dict[str, Any]:
        """Send a swarm WS message and await the response.

        Creates a Future keyed by request_id, sends the message, and awaits
        the response with a timeout. The _handle_message loop resolves the
        Future when the corresponding result message arrives.
        """
        if not self._ws or not self._connected:
            return {"error": "Not connected to relay"}

        loop = asyncio.get_running_loop()
        fut: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._pending_swarm[request_id] = fut

        try:
            await self._ws.send(message)
            return await asyncio.wait_for(fut, timeout=timeout)
        except TimeoutError:
            self._pending_swarm.pop(request_id, None)
            return {"error": "Swarm request timed out"}
        except Exception as exc:
            self._pending_swarm.pop(request_id, None)
            return {"error": str(exc)}

    async def swarm_search(
        self,
        query: str,
        search_type: str = "all",
        limit: int = 10,
    ) -> dict[str, Any]:
        """Search across all projects in the swarm."""
        request_id = str(uuid4())
        msg = SwarmSearchMessage(
            request_id=request_id,
            query=query,
            search_type=search_type,
            limit=limit,
        )
        return await self._send_swarm_request(
            msg.model_dump_json(),
            request_id,
            timeout=SWARM_DEFAULT_SEARCH_TIMEOUT_SECONDS + 1.0,
        )

    async def swarm_nodes(self) -> dict[str, Any]:
        """List all teams in the swarm."""
        request_id = str(uuid4())
        msg = SwarmNodesMessage(request_id=request_id)
        return await self._send_swarm_request(
            msg.model_dump_json(),
            request_id,
            timeout=SWARM_DEFAULT_SEARCH_TIMEOUT_SECONDS + 1.0,
        )

    async def swarm_status(self) -> dict[str, Any]:
        """Get swarm connection status from the node_list broadcast."""
        return {
            "connected": self._swarm_connected,
            "swarm_connected": self._swarm_connected,
            "swarm_id": self._swarm_id,
            "relay_connected": self._connected,
            "worker_url": self._worker_url,
        }

    async def get_swarm_advisories(self) -> list[dict[str, Any]]:
        """Fetch swarm advisories from the relay Worker via HTTP.

        Returns:
            List of advisory dicts, or empty list on failure.
        """
        if not self._worker_url or not self._token:
            return []
        try:
            client = self._get_http_client()
            resp = await client.get(
                f"{self._worker_url}/swarm/advisories",
                headers=self._relay_auth_headers(),
                timeout=10.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                return list(data.get("advisories", []))
        except Exception as exc:
            logger.debug("Failed to fetch swarm advisories: %s", exc)
        return []
