"""Tests for the swarm fetch route.

Tests cover:
- swarm_fetch() calls SwarmWorkerClient.fetch() with correct args
- swarm_fetch() returns the DO response directly (no envelope wrapping)
- swarm_fetch() handles missing http_client gracefully
- swarm_fetch() handles upstream errors gracefully
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from open_agent_kit.features.swarm.constants import (
    SWARM_ERROR_NOT_CONNECTED,
    SWARM_RESPONSE_KEY_ERROR,
)
from open_agent_kit.features.swarm.daemon.routes.fetch import (
    FetchRequest,
    swarm_fetch,
)


@pytest.fixture
def anyio_backend() -> str:
    """Restrict anyio tests to asyncio backend."""
    return "asyncio"


@pytest.fixture()
def _mock_state_connected():
    """Patch get_swarm_state to return a state with a connected http_client."""
    mock_client = AsyncMock()
    mock_state = AsyncMock()
    mock_state.http_client = mock_client

    with patch(
        "open_agent_kit.features.swarm.daemon.routes.fetch.get_swarm_state",
        return_value=mock_state,
    ):
        yield mock_client


@pytest.fixture()
def _mock_state_disconnected():
    """Patch get_swarm_state to return a state with no http_client."""
    mock_state = AsyncMock()
    mock_state.http_client = None

    with patch(
        "open_agent_kit.features.swarm.daemon.routes.fetch.get_swarm_state",
        return_value=mock_state,
    ):
        yield


class TestSwarmFetch:
    """Test the swarm_fetch route handler."""

    @pytest.mark.anyio
    async def test_calls_client_fetch_with_correct_args(
        self, _mock_state_connected: AsyncMock
    ) -> None:
        """Passes ids and project_slug to SwarmWorkerClient.fetch()."""
        client = _mock_state_connected
        client.fetch.return_value = {
            "results": [{"id": "chunk-1", "content": "hello", "tokens": 5}],
            "total_tokens": 5,
        }
        body = FetchRequest(ids=["chunk-1"], project_slug="my-project")
        await swarm_fetch(body)

        client.fetch.assert_awaited_once_with(
            ids=["chunk-1"],
            project_slug="my-project",
        )

    @pytest.mark.anyio
    async def test_returns_do_response_directly(self, _mock_state_connected: AsyncMock) -> None:
        """Returns the swarm DO response as-is (no MCP envelope wrapping)."""
        client = _mock_state_connected
        do_response = {
            "results": [
                {"id": "chunk-1", "content": "hello", "tokens": 5},
                {"id": "chunk-2", "content": "world", "tokens": 3},
            ],
            "total_tokens": 8,
        }
        client.fetch.return_value = do_response
        body = FetchRequest(ids=["chunk-1", "chunk-2"], project_slug="proj")
        result = await swarm_fetch(body)

        assert result == do_response

    @pytest.mark.anyio
    async def test_returns_error_when_disconnected(self, _mock_state_disconnected: None) -> None:
        """Returns an error dict when no http_client is available."""
        body = FetchRequest(ids=["chunk-1"], project_slug="proj")
        result = await swarm_fetch(body)

        assert result[SWARM_RESPONSE_KEY_ERROR] == SWARM_ERROR_NOT_CONNECTED

    @pytest.mark.anyio
    async def test_returns_error_on_upstream_exception(
        self, _mock_state_connected: AsyncMock
    ) -> None:
        """Returns an error dict when the upstream call raises."""
        client = _mock_state_connected
        client.fetch.side_effect = RuntimeError("connection reset")
        body = FetchRequest(ids=["chunk-1"], project_slug="proj")
        result = await swarm_fetch(body)

        assert "connection reset" in result[SWARM_RESPONSE_KEY_ERROR]

    @pytest.mark.anyio
    async def test_empty_results_returned_as_is(self, _mock_state_connected: AsyncMock) -> None:
        """Empty results from the DO are returned without error wrapping."""
        client = _mock_state_connected
        client.fetch.return_value = {"results": [], "total_tokens": 0}
        body = FetchRequest(ids=["nonexistent"], project_slug="proj")
        result = await swarm_fetch(body)

        assert result["results"] == []
        assert SWARM_RESPONSE_KEY_ERROR not in result
