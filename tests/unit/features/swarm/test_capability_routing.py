"""Tests for swarm capability routing infrastructure.

Covers:
- SwarmWorkerClient.heartbeat() sends the correct payload
- SwarmWorkerClient.heartbeat() targets the correct endpoint
- SwarmWorkerClient.heartbeat() propagates HTTP errors
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from open_agent_kit.features.swarm.constants import SWARM_API_PATH_HEARTBEAT
from open_agent_kit.features.swarm.daemon.client import SwarmWorkerClient


def _mock_httpx_response(
    *, status_code: int = 200, json_body: dict[str, Any] | None = None
) -> MagicMock:
    """Build a MagicMock that quacks like an ``httpx.Response``."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_body if json_body is not None else {}
    resp.raise_for_status = MagicMock()
    return resp


@pytest.fixture
def anyio_backend() -> str:
    """Restrict anyio tests to asyncio backend."""
    return "asyncio"


@pytest.fixture
def swarm_client() -> SwarmWorkerClient:
    return SwarmWorkerClient(
        swarm_url="https://test-swarm.workers.dev",
        swarm_token="test-token",
    )


class TestSwarmWorkerClientHeartbeat:
    """Test heartbeat sends team_id."""

    @pytest.mark.anyio
    async def test_heartbeat_sends_team_id(self, swarm_client: SwarmWorkerClient) -> None:
        mock_response = _mock_httpx_response(json_body={"status": "ok"})

        swarm_client._client.post = AsyncMock(return_value=mock_response)  # type: ignore[assignment]
        result = await swarm_client.heartbeat("team-123")

        assert result == {"status": "ok"}
        call_kwargs = swarm_client._client.post.call_args  # type: ignore[union-attr]
        assert call_kwargs is not None
        assert call_kwargs.kwargs["json"]["team_id"] == "team-123"

    @pytest.mark.anyio
    async def test_heartbeat_hits_correct_endpoint(self, swarm_client: SwarmWorkerClient) -> None:
        mock_response = _mock_httpx_response(json_body={"status": "ok"})

        swarm_client._client.post = AsyncMock(return_value=mock_response)  # type: ignore[assignment]
        await swarm_client.heartbeat("team-456")

        call_args = swarm_client._client.post.call_args  # type: ignore[union-attr]
        assert call_args is not None
        url = call_args.args[0]
        assert url.endswith(SWARM_API_PATH_HEARTBEAT)

    @pytest.mark.anyio
    async def test_heartbeat_raises_on_http_error(self, swarm_client: SwarmWorkerClient) -> None:
        mock_response = _mock_httpx_response(status_code=500)
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error",
            request=MagicMock(),
            response=mock_response,
        )

        swarm_client._client.post = AsyncMock(return_value=mock_response)  # type: ignore[assignment]
        with pytest.raises(httpx.HTTPStatusError):
            await swarm_client.heartbeat("team-789")
