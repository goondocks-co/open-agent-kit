"""Remote team gateway — client mode: HTTP proxy to remote server."""

import logging
from typing import Any

import httpx
from fastapi import HTTPException

from open_agent_kit.features.codebase_intelligence.constants.team import (
    TEAM_HTTP_JOIN_STATUS_PATH,
    TEAM_HTTP_MEMBERS_PATH,
    TEAM_ROUTER_PREFIX,
)
from open_agent_kit.features.codebase_intelligence.team.gateway.base import TeamGateway

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT: int = 10


class RemoteTeamGateway(TeamGateway):
    """Gateway that proxies requests to a remote team server.

    Used in client mode where the daemon connects to an external server.
    """

    def __init__(self, server_url: str, api_key: str | None) -> None:
        self._server_url = server_url.rstrip("/")
        self._api_key = api_key

    def _auth_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def get_members(self) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self._server_url}{TEAM_ROUTER_PREFIX}{TEAM_HTTP_MEMBERS_PATH}",
                    headers=self._auth_headers(),
                    timeout=_HTTP_TIMEOUT,
                )
                resp.raise_for_status()
                # Server returns list[TeamMemberInfo]; wrap for dashboard
                members: list[Any] = resp.json()
                return {"members": members}
        except Exception as exc:
            logger.warning("Failed to fetch team members: %s", exc)
            return {"members": [], "error": str(exc)}

    async def get_join_status(self, key_id: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self._server_url}{TEAM_ROUTER_PREFIX}{TEAM_HTTP_JOIN_STATUS_PATH}/{key_id}",
                    timeout=_HTTP_TIMEOUT,
                )
                resp.raise_for_status()
                result = resp.json()
        except Exception as exc:
            logger.warning("Failed to poll join status: %s", exc)
            return {"status": "error", "error": str(exc), "pending_approval": True}

        status = result.get("status", "pending")
        return {"status": status, "pending_approval": status == "pending"}

    async def get_pending_joins(self) -> list[dict[str, Any]]:
        raise HTTPException(status_code=403, detail="Server mode only")

    async def approve_join(self, key_id: str) -> dict[str, bool]:
        raise HTTPException(status_code=403, detail="Server mode only")

    async def reject_join(self, key_id: str) -> dict[str, bool]:
        raise HTTPException(status_code=403, detail="Server mode only")

    def is_server(self) -> bool:
        return False
