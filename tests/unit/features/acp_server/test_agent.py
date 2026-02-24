"""Tests for the OAK ACP Agent (daemon bridge)."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from open_agent_kit.features.acp_server.agent import OakAcpAgent
from open_agent_kit.features.acp_server.constants import (
    ACP_AGENT_NAME,
    ACP_SESSION_MODE_ARCHITECT,
    ACP_SESSION_MODE_ASK,
    ACP_SESSION_MODE_CODE,
)


@pytest.fixture
def anyio_backend():
    """Restrict anyio tests to asyncio backend."""
    return "asyncio"


@pytest.fixture
def agent(tmp_path: Path) -> OakAcpAgent:
    """Create an agent with a temporary project root."""
    return OakAcpAgent(project_root=tmp_path)


class TestInitialize:
    @pytest.mark.anyio
    async def test_returns_protocol_version(self, agent: OakAcpAgent):
        response = await agent.initialize(protocol_version=1)
        assert response.protocol_version is not None

    @pytest.mark.anyio
    async def test_returns_agent_info(self, agent: OakAcpAgent):
        response = await agent.initialize(protocol_version=1)
        assert response.agent_info is not None
        assert response.agent_info.name == ACP_AGENT_NAME


class TestNewSession:
    @pytest.mark.anyio
    async def test_creates_session_via_daemon(self, agent: OakAcpAgent, tmp_path: Path):
        """When daemon is reachable, session_id comes from daemon."""
        mock_client = AsyncMock()
        mock_client.create_session.return_value = "daemon-session-123"

        with patch.object(agent, "_ensure_daemon_client", return_value=mock_client):
            response = await agent.new_session(cwd=str(tmp_path))

        assert response.session_id == "daemon-session-123"
        mock_client.create_session.assert_called_once_with(str(tmp_path))

    @pytest.mark.anyio
    async def test_fallback_on_daemon_error(self, agent: OakAcpAgent, tmp_path: Path):
        """When daemon is unreachable, falls back to local UUID."""
        with patch.object(agent, "_ensure_daemon_client", side_effect=RuntimeError("no daemon")):
            response = await agent.new_session(cwd=str(tmp_path))

        assert response.session_id is not None
        assert len(response.session_id) > 0

    @pytest.mark.anyio
    async def test_session_modes_advertised(self, agent: OakAcpAgent, tmp_path: Path):
        """New session response includes available modes."""
        mock_client = AsyncMock()
        mock_client.create_session.return_value = "s1"

        with patch.object(agent, "_ensure_daemon_client", return_value=mock_client):
            response = await agent.new_session(cwd=str(tmp_path))

        assert response.modes is not None
        mode_ids = [m.id for m in response.modes.available_modes]
        assert ACP_SESSION_MODE_CODE in mode_ids
        assert ACP_SESSION_MODE_ARCHITECT in mode_ids
        assert ACP_SESSION_MODE_ASK in mode_ids
        assert response.modes.current_mode_id == ACP_SESSION_MODE_CODE


class TestCancel:
    @pytest.mark.anyio
    async def test_delegates_to_daemon(self, agent: OakAcpAgent):
        """Cancel delegates to daemon client."""
        mock_client = AsyncMock()
        with patch.object(agent, "_ensure_daemon_client", return_value=mock_client):
            await agent.cancel(session_id="s1")
        mock_client.cancel.assert_called_once_with("s1")

    @pytest.mark.anyio
    async def test_cancel_daemon_error_noop(self, agent: OakAcpAgent):
        """Cancel gracefully handles daemon errors."""
        mock_client = AsyncMock()
        mock_client.cancel.side_effect = RuntimeError("connection refused")
        with patch.object(agent, "_ensure_daemon_client", return_value=mock_client):
            # Should not raise
            await agent.cancel(session_id="s1")


class TestPrompt:
    @pytest.mark.anyio
    async def test_daemon_error_sends_error_update(self, agent: OakAcpAgent):
        """When daemon prompt fails, sends error update to client."""
        conn = AsyncMock()
        agent.on_connect(conn)

        with patch.object(agent, "_ensure_daemon_client", side_effect=RuntimeError("no daemon")):
            response = await agent.prompt(
                prompt=[{"type": "text", "text": "hello"}],
                session_id="s1",
            )

        assert response.stop_reason == "end_turn"
        conn.session_update.assert_called()


class TestSetSessionMode:
    @pytest.mark.anyio
    async def test_maps_code_to_accept_edits(self, agent: OakAcpAgent):
        """Code mode maps to acceptEdits permission mode."""
        mock_client = AsyncMock()
        with patch.object(agent, "_ensure_daemon_client", return_value=mock_client):
            await agent.set_session_mode(mode_id=ACP_SESSION_MODE_CODE, session_id="s1")
        mock_client.set_mode.assert_called_once_with("s1", "acceptEdits")

    @pytest.mark.anyio
    async def test_maps_architect_to_plan(self, agent: OakAcpAgent):
        """Architect mode maps to plan permission mode."""
        mock_client = AsyncMock()
        with patch.object(agent, "_ensure_daemon_client", return_value=mock_client):
            await agent.set_session_mode(mode_id=ACP_SESSION_MODE_ARCHITECT, session_id="s1")
        mock_client.set_mode.assert_called_once_with("s1", "plan")

    @pytest.mark.anyio
    async def test_unknown_mode_returns_none(self, agent: OakAcpAgent):
        """Unknown mode_id returns None without calling daemon."""
        mock_client = AsyncMock()
        with patch.object(agent, "_ensure_daemon_client", return_value=mock_client):
            result = await agent.set_session_mode(mode_id="unknown", session_id="s1")
        assert result is None
        mock_client.set_mode.assert_not_called()
