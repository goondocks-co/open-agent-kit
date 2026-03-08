"""HTTP client for Swarm Worker API."""

from __future__ import annotations

import logging
from types import TracebackType
from typing import Any, cast

import httpx

from open_agent_kit.features.swarm.constants import (
    SWARM_API_PATH_BROADCAST,
    SWARM_API_PATH_CONFIG_MIN_OAK_VERSION,
    SWARM_API_PATH_FETCH,
    SWARM_API_PATH_HEALTH_CHECK,
    SWARM_API_PATH_HEARTBEAT,
    SWARM_API_PATH_NODES,
    SWARM_API_PATH_REGISTER,
    SWARM_API_PATH_SEARCH,
    SWARM_API_PATH_UNREGISTER,
    SWARM_DEFAULT_FETCH_TIMEOUT_SECONDS,
    SWARM_DEFAULT_SEARCH_TIMEOUT_SECONDS,
    SWARM_DEFAULT_TOOL_TIMEOUT_SECONDS,
    SWARM_HEALTH_CHECK_TIMEOUT_SECONDS,
    SWARM_MCP_TIMEOUT_PADDING_SECONDS,
)

logger = logging.getLogger(__name__)


class SwarmWorkerClient:
    """HTTP client for communicating with the Swarm Worker DO."""

    def __init__(self, swarm_url: str, swarm_token: str) -> None:
        self._swarm_url = swarm_url.rstrip("/")
        self._swarm_token = swarm_token
        self._auth_headers = {"Authorization": f"Bearer {swarm_token}"}
        self._client = httpx.AsyncClient(headers=self._auth_headers)

    def _url(self, path: str) -> str:
        return f"{self._swarm_url}{path}"

    async def search(self, query: str, search_type: str = "all", limit: int = 10) -> dict[str, Any]:
        """Search across swarm nodes.

        Args:
            query: Search query string.
            search_type: Type of search: "all", "memory", "sessions", or "plans".
            limit: Maximum number of results.

        Returns:
            Search results from the swarm worker.
        """
        logger.debug(
            "HTTP POST %s query=%r type=%s limit=%d",
            SWARM_API_PATH_SEARCH,
            query,
            search_type,
            limit,
        )
        resp = await self._client.post(
            self._url(SWARM_API_PATH_SEARCH),
            json={"query": query, "search_type": search_type, "limit": limit},
            timeout=SWARM_DEFAULT_SEARCH_TIMEOUT_SECONDS + SWARM_MCP_TIMEOUT_PADDING_SECONDS,
        )
        resp.raise_for_status()
        logger.debug(
            "HTTP POST %s -> %d (%d bytes)",
            SWARM_API_PATH_SEARCH,
            resp.status_code,
            len(resp.content),
        )
        return cast(dict[str, Any], resp.json())

    async def fetch(
        self,
        ids: list[str],
        project_slug: str | None = None,
        timeout: float = SWARM_DEFAULT_FETCH_TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        """Fetch full content for chunk IDs via the swarm DO.

        Uses the same ``/api/swarm/fetch`` path that the MCP ``swarm_fetch``
        tool uses, ensuring a single code-path for fetch operations.

        Args:
            ids: Chunk IDs to fetch.
            project_slug: Optional project to scope the fetch to.
            timeout: Request timeout in seconds.

        Returns:
            ``{results: [...], total_tokens: N}`` from the swarm DO.
        """
        body: dict[str, Any] = {"ids": ids}
        if project_slug:
            body["project_slug"] = project_slug
        logger.debug(
            "HTTP POST %s ids=%d project=%s",
            SWARM_API_PATH_FETCH,
            len(ids),
            project_slug,
        )
        resp = await self._client.post(
            self._url(SWARM_API_PATH_FETCH),
            json=body,
            timeout=timeout + SWARM_MCP_TIMEOUT_PADDING_SECONDS,
        )
        resp.raise_for_status()
        logger.debug(
            "HTTP POST %s -> %d (%d bytes)",
            SWARM_API_PATH_FETCH,
            resp.status_code,
            len(resp.content),
        )
        return cast(dict[str, Any], resp.json())

    async def broadcast(
        self, tool_name: str, arguments: dict, timeout: float = 30.0
    ) -> dict[str, Any]:
        """Broadcast a tool call to all swarm nodes.

        Args:
            tool_name: Name of the tool to invoke.
            arguments: Tool arguments.
            timeout: Request timeout in seconds.

        Returns:
            Aggregated results from all nodes.
        """
        logger.debug(
            "HTTP POST %s tool=%s timeout=%.1f", SWARM_API_PATH_BROADCAST, tool_name, timeout
        )
        resp = await self._client.post(
            self._url(SWARM_API_PATH_BROADCAST),
            json={"tool_name": tool_name, "arguments": arguments},
            timeout=timeout + SWARM_MCP_TIMEOUT_PADDING_SECONDS,
        )
        resp.raise_for_status()
        logger.debug(
            "HTTP POST %s -> %d (%d bytes)",
            SWARM_API_PATH_BROADCAST,
            resp.status_code,
            len(resp.content),
        )
        return cast(dict[str, Any], resp.json())

    async def nodes(self) -> dict[str, Any]:
        """List all nodes in the swarm.

        Returns:
            Node list from the swarm worker.
        """
        logger.debug("HTTP GET %s", SWARM_API_PATH_NODES)
        resp = await self._client.get(
            self._url(SWARM_API_PATH_NODES),
            timeout=SWARM_HEALTH_CHECK_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        logger.debug(
            "HTTP GET %s -> %d (%d bytes)",
            SWARM_API_PATH_NODES,
            resp.status_code,
            len(resp.content),
        )
        return cast(dict[str, Any], resp.json())

    async def heartbeat(
        self,
        team_id: str,
        *,
        capabilities: list[str] | None = None,
        node_count: int | None = None,
        oak_version: str | None = None,
        tool_names: list[str] | None = None,
    ) -> dict[str, Any]:
        """Send a heartbeat to the swarm worker.

        Args:
            team_id: Team identifier for the heartbeat.
            capabilities: Optional updated capability list.
            node_count: Optional updated node count.
            oak_version: Optional updated OAK version string.
            tool_names: Optional updated list of tool names.

        Returns:
            Heartbeat acknowledgement.
        """
        body: dict[str, Any] = {"team_id": team_id}
        if capabilities is not None:
            body["capabilities"] = capabilities
        if node_count is not None:
            body["node_count"] = node_count
        if oak_version is not None:
            body["oak_version"] = oak_version
        if tool_names is not None:
            body["tool_names"] = tool_names
        resp = await self._client.post(
            self._url(SWARM_API_PATH_HEARTBEAT),
            json=body,
            timeout=SWARM_HEALTH_CHECK_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        logger.debug("Heartbeat sent: team_id=%s", team_id)
        return cast(dict[str, Any], resp.json())

    async def register(
        self,
        team_id: str,
        project_slug: str,
        callback_url: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Register this node with the swarm worker.

        Args:
            team_id: Team identifier.
            project_slug: Slug identifying this project.
            callback_url: URL the worker can reach this node at.
            **kwargs: Additional registration fields.

        Returns:
            Registration confirmation.
        """
        body = {
            "token": self._swarm_token,
            "team_id": team_id,
            "project_slug": project_slug,
            "callback_url": callback_url,
            **kwargs,
        }
        resp = await self._client.post(
            self._url(SWARM_API_PATH_REGISTER),
            json=body,
            timeout=SWARM_HEALTH_CHECK_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        logger.info("Registered with swarm: team_id=%s project=%s", team_id, project_slug)
        return cast(dict[str, Any], resp.json())

    async def unregister(self, team_id: str) -> dict[str, Any]:
        """Unregister this node from the swarm worker.

        Args:
            team_id: Team identifier to unregister.

        Returns:
            Unregistration confirmation.
        """
        resp = await self._client.post(
            self._url(SWARM_API_PATH_UNREGISTER),
            json={"team_id": team_id},
            timeout=SWARM_HEALTH_CHECK_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        logger.info("Unregistered from swarm: team_id=%s", team_id)
        return cast(dict[str, Any], resp.json())

    async def health_check(self, team_slug: str) -> dict[str, Any]:
        """Request a health check for a specific team.

        Args:
            team_slug: Project slug of the team to check.

        Returns:
            Health check data including per-node status.
        """
        logger.debug(
            "HTTP POST %s team_slug=%s",
            SWARM_API_PATH_HEALTH_CHECK,
            team_slug,
        )
        resp = await self._client.post(
            self._url(SWARM_API_PATH_HEALTH_CHECK),
            json={"team_slug": team_slug},
            timeout=SWARM_DEFAULT_TOOL_TIMEOUT_SECONDS + SWARM_MCP_TIMEOUT_PADDING_SECONDS,
        )
        resp.raise_for_status()
        logger.debug(
            "HTTP POST %s -> %d (%d bytes)",
            SWARM_API_PATH_HEALTH_CHECK,
            resp.status_code,
            len(resp.content),
        )
        return cast(dict[str, Any], resp.json())

    async def get_min_oak_version(self) -> dict[str, Any]:
        """Get the minimum OAK version configured on the swarm DO.

        Returns:
            Dict with ``min_oak_version`` key.
        """
        resp = await self._client.get(
            self._url(SWARM_API_PATH_CONFIG_MIN_OAK_VERSION),
            timeout=SWARM_HEALTH_CHECK_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return cast(dict[str, Any], resp.json())

    async def set_min_oak_version(self, data: dict[str, Any]) -> dict[str, Any]:
        """Set the minimum OAK version on the swarm DO.

        Args:
            data: Dict with ``min_oak_version`` key.

        Returns:
            Updated config from the swarm DO.
        """
        resp = await self._client.put(
            self._url(SWARM_API_PATH_CONFIG_MIN_OAK_VERSION),
            json=data,
            timeout=SWARM_HEALTH_CHECK_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return cast(dict[str, Any], resp.json())

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self) -> SwarmWorkerClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.close()
