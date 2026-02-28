"""Tests for HTTP transport.

Tests cover:
- HttpTransport push_events (mock httpx)
- HttpTransport pull_events (mock httpx)
- HttpTransport connect/disconnect
"""

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from open_agent_kit.features.codebase_intelligence.constants.team import (
    TEAM_EVENT_OBSERVATION_UPSERT,
)
from open_agent_kit.features.codebase_intelligence.team.protocol import (
    TeamEvent,
    TeamEventBatch,
    TeamPullRequest,
)
from open_agent_kit.features.codebase_intelligence.team.transport.http import (
    HttpTransport,
)

_TEST_SERVER_URL = "https://team.example.com"
_TEST_TOKEN = "oak_team_testtoken"


def _make_event(content_hash: str = "h1") -> TeamEvent:
    """Create a test event."""
    return TeamEvent(
        event_type=TEAM_EVENT_OBSERVATION_UPSERT,
        payload={"test": True},
        source_machine_id="machine-1",
        content_hash=content_hash,
        schema_version=9,
        timestamp="2026-02-26T10:00:00Z",
        project_id="proj:abcd1234",
    )


def _run(coro):
    """Run an async coroutine synchronously."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _mock_async_client(**kwargs):
    """Create a mock that works with ``async with httpx.AsyncClient() as client:``."""
    mock_client = AsyncMock(**kwargs)

    @asynccontextmanager
    async def _ctx_mgr():
        yield mock_client

    mock_cls = MagicMock(return_value=_ctx_mgr())
    return mock_cls, mock_client


# =============================================================================
# connect / disconnect
# =============================================================================


class TestHttpTransportConnect:
    """Test connect and disconnect."""

    def test_connect_success(self):
        """connect() sets connected=True on successful status check."""
        transport = HttpTransport(_TEST_SERVER_URL, _TEST_TOKEN)

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_cls, mock_client = _mock_async_client()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", mock_cls):
            _run(transport.connect())

        status = transport.get_status()
        assert status.connected is True
        assert status.server_url == _TEST_SERVER_URL
        assert status.last_error is None

    def test_connect_failure(self):
        """connect() sets connected=False on HTTP error."""
        import httpx

        transport = HttpTransport(_TEST_SERVER_URL, _TEST_TOKEN)

        mock_cls, mock_client = _mock_async_client()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

        with patch("httpx.AsyncClient", mock_cls):
            _run(transport.connect())

        status = transport.get_status()
        assert status.connected is False
        assert status.last_error is not None

    def test_disconnect(self):
        """disconnect() sets connected=False."""
        transport = HttpTransport(_TEST_SERVER_URL, _TEST_TOKEN)

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_cls, mock_client = _mock_async_client()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", mock_cls):
            _run(transport.connect())

        _run(transport.disconnect())
        status = transport.get_status()
        assert status.connected is False


# =============================================================================
# push_events
# =============================================================================


class TestHttpTransportPush:
    """Test push_events."""

    def test_push_success(self):
        """push_events returns PushResult from server response."""
        transport = HttpTransport(_TEST_SERVER_URL, _TEST_TOKEN)

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"accepted": 2, "rejected": 0, "cursor": "5"})

        mock_cls, mock_client = _mock_async_client()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", mock_cls):
            batch = TeamEventBatch(events=[_make_event("h1"), _make_event("h2")])
            result = _run(transport.push_events(batch))

        assert result.accepted == 2
        assert result.rejected == 0

    def test_push_failure(self):
        """push_events returns rejected count on HTTP error."""
        import httpx

        transport = HttpTransport(_TEST_SERVER_URL, _TEST_TOKEN)

        mock_cls, mock_client = _mock_async_client()
        mock_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError("500", request=MagicMock(), response=MagicMock())
        )

        with patch("httpx.AsyncClient", mock_cls):
            batch = TeamEventBatch(events=[_make_event()])
            result = _run(transport.push_events(batch))

        assert result.accepted == 0
        assert result.rejected == 1


# =============================================================================
# pull_events
# =============================================================================


class TestHttpTransportPull:
    """Test pull_events."""

    def test_pull_success(self):
        """pull_events returns TeamEventBatch from server response."""
        transport = HttpTransport(_TEST_SERVER_URL, _TEST_TOKEN)

        event_data = _make_event("h1").model_dump()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"events": [event_data], "cursor": "1"})

        mock_cls, mock_client = _mock_async_client()
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", mock_cls):
            request = TeamPullRequest(since_cursor=None, limit=50)
            batch = _run(transport.pull_events(request))

        assert len(batch.events) == 1
        assert batch.cursor == "1"

    def test_pull_failure(self):
        """pull_events returns empty batch on HTTP error."""
        import httpx

        transport = HttpTransport(_TEST_SERVER_URL, _TEST_TOKEN)

        mock_cls, mock_client = _mock_async_client()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))

        with patch("httpx.AsyncClient", mock_cls):
            request = TeamPullRequest()
            batch = _run(transport.pull_events(request))

        assert len(batch.events) == 0
        assert batch.cursor is None
