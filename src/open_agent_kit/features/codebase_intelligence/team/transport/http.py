"""Direct HTTPS transport for team event sync.

Used in reverse-proxy / direct-connection deployments where the team
server is reachable over HTTP(S).
"""

import logging
from datetime import UTC, datetime

import httpx

from open_agent_kit.features.codebase_intelligence.constants.team import (
    TEAM_AUTH_SCHEME_BEARER,
    TEAM_HTTP_PULL_PATH,
    TEAM_HTTP_PUSH_PATH,
    TEAM_HTTP_STATUS_PATH,
    TEAM_ROUTER_PREFIX,
    TEAM_TRANSPORT_ERROR_CONNECTION,
    TEAM_TRANSPORT_ERROR_PULL,
    TEAM_TRANSPORT_ERROR_PUSH,
)
from open_agent_kit.features.codebase_intelligence.team.protocol import (
    PushResult,
    TeamEventBatch,
    TeamPullRequest,
    TransportStatus,
)
from open_agent_kit.features.codebase_intelligence.team.transport.base import (
    TeamTransport,
)

logger = logging.getLogger(__name__)


class HttpTransport(TeamTransport):
    """Direct HTTPS transport for reverse proxy deployments.

    Uses httpx.AsyncClient with Bearer token authentication to
    communicate with the team server's REST API.

    Args:
        server_url: Base URL of the team server (e.g. "https://team.example.com").
        token: API key for authentication.
    """

    def __init__(self, server_url: str, token: str) -> None:
        self._server_url = server_url.rstrip("/")
        self._token = token
        self._client: httpx.AsyncClient | None = None
        self._connected = False
        self._last_error: str | None = None
        self._last_connected_at: str | None = None

    def _auth_headers(self) -> dict[str, str]:
        """Build authorization headers."""
        return {"Authorization": f"{TEAM_AUTH_SCHEME_BEARER} {self._token}"}

    def _url(self, path: str) -> str:
        """Build full URL from relative path."""
        return f"{self._server_url}{TEAM_ROUTER_PREFIX}{path}"

    async def push_events(self, batch: TeamEventBatch) -> PushResult:
        """Push events via POST to /api/team/events/push."""
        if self._client is None:
            await self.connect()

        assert self._client is not None
        try:
            response = await self._client.post(
                self._url(TEAM_HTTP_PUSH_PATH),
                json=batch.model_dump(),
                headers=self._auth_headers(),
            )
            response.raise_for_status()
            return PushResult.model_validate(response.json())
        except httpx.HTTPError as e:
            self._last_error = str(e)
            self._connected = False
            logger.warning(TEAM_TRANSPORT_ERROR_PUSH.format(error=e))
            return PushResult(accepted=0, rejected=len(batch.events))

    async def pull_events(self, request: TeamPullRequest) -> TeamEventBatch:
        """Pull events via POST to /api/team/events/pull."""
        if self._client is None:
            await self.connect()

        assert self._client is not None
        try:
            response = await self._client.post(
                self._url(TEAM_HTTP_PULL_PATH),
                json=request.model_dump(),
                headers=self._auth_headers(),
            )
            response.raise_for_status()
            return TeamEventBatch.model_validate(response.json())
        except httpx.HTTPError as e:
            self._last_error = str(e)
            self._connected = False
            logger.warning(TEAM_TRANSPORT_ERROR_PULL.format(error=e))
            return TeamEventBatch()

    async def connect(self) -> None:
        """Verify server reachable via GET /api/team/status."""
        self._client = httpx.AsyncClient()
        try:
            response = await self._client.get(
                self._url(TEAM_HTTP_STATUS_PATH),
            )
            response.raise_for_status()
            self._connected = True
            self._last_error = None
            self._last_connected_at = datetime.now(UTC).isoformat()
        except httpx.HTTPError as e:
            self._connected = False
            self._last_error = str(e)
            logger.warning(TEAM_TRANSPORT_ERROR_CONNECTION.format(error=e))

    async def disconnect(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        self._connected = False

    def get_status(self) -> TransportStatus:
        """Return current transport status."""
        return TransportStatus(
            connected=self._connected,
            server_url=self._server_url,
            last_error=self._last_error,
            last_connected_at=self._last_connected_at,
        )
