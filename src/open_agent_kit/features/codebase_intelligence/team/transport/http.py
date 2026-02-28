"""Direct HTTPS transport for team event sync.

Used in reverse-proxy / direct-connection deployments where the team
server is reachable over HTTP(S).
"""

import logging
from datetime import UTC, datetime

import httpx

from open_agent_kit.features.codebase_intelligence.constants.team import (
    TEAM_AUTH_SCHEME_BEARER,
    TEAM_HTTP_HEARTBEAT_PATH,
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
        """Push events via POST to /api/team/events/push.

        Raises:
            httpx.TransportError: On network-level failures (server unreachable,
                connection refused, timeout). The caller should treat these as
                transient and NOT increment retry counts — events must stay pending.
        Returns:
            PushResult with accepted/rejected counts when the server responds,
            including error responses (4xx/5xx) which are treated as explicit
            server rejections and DO count against the retry limit.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self._url(TEAM_HTTP_PUSH_PATH),
                    json=batch.model_dump(),
                    headers=self._auth_headers(),
                )
                response.raise_for_status()
                self._connected = True
                self._last_error = None
                return PushResult.model_validate(response.json())
        except httpx.TransportError as e:
            # Network-level failure: server is unreachable, connection refused,
            # or timed out. Re-raise so the outbox worker knows this is transient
            # and must NOT increment retry_count on pending events.
            self._last_error = str(e)
            self._connected = False
            raise
        except httpx.HTTPError as e:
            # Server responded with an error (4xx/5xx). This is an explicit
            # server rejection — the caller may count this against the retry limit.
            self._last_error = str(e)
            self._connected = False
            logger.warning(TEAM_TRANSPORT_ERROR_PUSH.format(error=e))
            return PushResult(accepted=0, rejected=len(batch.events))

    async def pull_events(self, request: TeamPullRequest) -> TeamEventBatch:
        """Pull events via POST to /api/team/events/pull."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self._url(TEAM_HTTP_PULL_PATH),
                    json=request.model_dump(),
                    headers=self._auth_headers(),
                )
                response.raise_for_status()
                self._connected = True
                self._last_error = None
                return TeamEventBatch.model_validate(response.json())
        except httpx.HTTPError as e:
            self._last_error = str(e)
            self._connected = False
            logger.warning(TEAM_TRANSPORT_ERROR_PULL.format(error=e))
            return TeamEventBatch()

    async def connect(self) -> None:
        """Verify server reachable via GET /api/team/status."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
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
        """No-op — clients are not cached."""
        self._connected = False

    async def send_heartbeat(self) -> None:
        """Update member presence via POST /members/heartbeat."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self._url(TEAM_HTTP_HEARTBEAT_PATH),
                    headers=self._auth_headers(),
                )
                response.raise_for_status()
                self._connected = True
                self._last_error = None
        except httpx.HTTPError as e:
            self._last_error = str(e)
            self._connected = False
            logger.debug("Heartbeat failed: %s", e)

    def get_status(self) -> TransportStatus:
        """Return current transport status."""
        return TransportStatus(
            connected=self._connected,
            server_url=self._server_url,
            last_error=self._last_error,
            last_connected_at=self._last_connected_at,
        )
