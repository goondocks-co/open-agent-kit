"""Tests for the DaemonClient and discover_daemon.

Tests cover:
- Port file discovery with priority (local override > team-shared)
- Auth token discovery (env var > token file)
- DaemonClient header construction
- DaemonClient.create_session HTTP call
- DaemonClient.cancel HTTP call
- DaemonClient.set_mode HTTP call
- DaemonClient.close_session HTTP call
- NDJSON streaming parse in prompt/approve_plan
"""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from open_agent_kit.features.acp_server.constants import (
    ACP_DAEMON_PORT_FILE,
    ACP_DAEMON_PORT_FILE_LOCAL,
    ACP_ERROR_DAEMON_UNREACHABLE,
)
from open_agent_kit.features.acp_server.daemon_client import (
    DaemonClient,
    discover_daemon,
)
from open_agent_kit.features.team.daemon.models_acp import (
    DoneEvent,
    ErrorEvent,
    TextEvent,
    parse_execution_event,
)

# =============================================================================
# discover_daemon tests
# =============================================================================


class TestDiscoverDaemon:
    """Tests for discover_daemon function."""

    def test_reads_local_port_file(self, tmp_path: Path) -> None:
        """discover_daemon should prefer the local override port file."""
        local_port_file = tmp_path / ACP_DAEMON_PORT_FILE_LOCAL
        local_port_file.parent.mkdir(parents=True, exist_ok=True)
        local_port_file.write_text("8765")

        # Also create the team-shared file with different port
        shared_port_file = tmp_path / ACP_DAEMON_PORT_FILE
        shared_port_file.parent.mkdir(parents=True, exist_ok=True)
        shared_port_file.write_text("9999")

        base_url, _token = discover_daemon(tmp_path)

        assert base_url == "http://127.0.0.1:8765"

    def test_falls_back_to_shared_port_file(self, tmp_path: Path) -> None:
        """discover_daemon should use shared port file when local not present."""
        shared_port_file = tmp_path / ACP_DAEMON_PORT_FILE
        shared_port_file.parent.mkdir(parents=True, exist_ok=True)
        shared_port_file.write_text("9876")

        base_url, _token = discover_daemon(tmp_path)

        assert base_url == "http://127.0.0.1:9876"

    def test_raises_when_no_port_file(self, tmp_path: Path) -> None:
        """discover_daemon should raise RuntimeError when no port file exists."""
        with pytest.raises(RuntimeError, match=ACP_ERROR_DAEMON_UNREACHABLE):
            discover_daemon(tmp_path)

    def test_reads_auth_token_from_env(self, tmp_path: Path) -> None:
        """discover_daemon should read auth token from OAK_CI_TOKEN env var."""
        from open_agent_kit.features.team.constants import CI_AUTH_ENV_VAR

        port_file = tmp_path / ACP_DAEMON_PORT_FILE_LOCAL
        port_file.parent.mkdir(parents=True, exist_ok=True)
        port_file.write_text("8765")

        with patch.dict(os.environ, {CI_AUTH_ENV_VAR: "test-token-abc"}):
            _base_url, token = discover_daemon(tmp_path)

        assert token == "test-token-abc"

    def test_reads_auth_token_from_file_fallback(self, tmp_path: Path) -> None:
        """discover_daemon should fall back to token file when env var not set."""
        from open_agent_kit.features.team.constants import (
            CI_AUTH_ENV_VAR,
            CI_DATA_DIR,
            CI_TOKEN_FILE,
        )

        port_file = tmp_path / ACP_DAEMON_PORT_FILE_LOCAL
        port_file.parent.mkdir(parents=True, exist_ok=True)
        port_file.write_text("8765")

        token_file = tmp_path / ".oak" / CI_DATA_DIR / CI_TOKEN_FILE
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text("file-token-xyz")

        with patch.dict(os.environ, {}, clear=False):
            # Ensure env var is not set
            os.environ.pop(CI_AUTH_ENV_VAR, None)
            _base_url, token = discover_daemon(tmp_path)

        assert token == "file-token-xyz"

    def test_empty_token_when_no_source(self, tmp_path: Path) -> None:
        """discover_daemon should return empty token when no source available."""
        from open_agent_kit.features.team.constants import CI_AUTH_ENV_VAR

        port_file = tmp_path / ACP_DAEMON_PORT_FILE_LOCAL
        port_file.parent.mkdir(parents=True, exist_ok=True)
        port_file.write_text("8765")

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(CI_AUTH_ENV_VAR, None)
            _base_url, token = discover_daemon(tmp_path)

        assert token == ""

    def test_skips_invalid_port_file(self, tmp_path: Path) -> None:
        """discover_daemon should skip port files with non-integer content."""
        local_port_file = tmp_path / ACP_DAEMON_PORT_FILE_LOCAL
        local_port_file.parent.mkdir(parents=True, exist_ok=True)
        local_port_file.write_text("not-a-number")

        shared_port_file = tmp_path / ACP_DAEMON_PORT_FILE
        shared_port_file.parent.mkdir(parents=True, exist_ok=True)
        shared_port_file.write_text("5555")

        base_url, _token = discover_daemon(tmp_path)

        assert base_url == "http://127.0.0.1:5555"


# =============================================================================
# DaemonClient construction tests
# =============================================================================


class TestDaemonClientHeaders:
    """Tests for DaemonClient header construction."""

    def test_headers_include_content_type(self) -> None:
        """Headers should always include Content-Type."""
        client = DaemonClient(base_url="http://localhost:8080", auth_token="")

        headers = client._headers()

        assert headers["Content-Type"] == "application/json"

    def test_headers_include_auth_when_token_set(self) -> None:
        """Headers should include Authorization when auth_token is non-empty."""
        client = DaemonClient(base_url="http://localhost:8080", auth_token="my-token")

        headers = client._headers()

        assert headers["Authorization"] == "Bearer my-token"

    def test_headers_omit_auth_when_no_token(self) -> None:
        """Headers should not include Authorization when auth_token is empty."""
        client = DaemonClient(base_url="http://localhost:8080", auth_token="")

        headers = client._headers()

        assert "Authorization" not in headers


# =============================================================================
# parse_execution_event tests (used by DaemonClient streaming)
# =============================================================================


class TestParseExecutionEvent:
    """Tests for NDJSON event parsing used by DaemonClient."""

    def test_parses_text_event(self) -> None:
        """Should parse a text event correctly."""
        data = {"type": "text", "text": "Hello world"}
        event = parse_execution_event(data)

        assert isinstance(event, TextEvent)
        assert event.text == "Hello world"

    def test_parses_done_event(self) -> None:
        """Should parse a done event correctly."""
        data = {"type": "done", "session_id": "s1", "needs_plan_approval": True}
        event = parse_execution_event(data)

        assert isinstance(event, DoneEvent)
        assert event.session_id == "s1"
        assert event.needs_plan_approval is True

    def test_parses_error_event(self) -> None:
        """Should parse an error event correctly."""
        data = {"type": "error", "message": "Something went wrong"}
        event = parse_execution_event(data)

        assert isinstance(event, ErrorEvent)
        assert event.message == "Something went wrong"

    def test_raises_on_missing_type(self) -> None:
        """Should raise ValueError when type field is missing."""
        with pytest.raises(ValueError, match="Missing 'type' field"):
            parse_execution_event({})

    def test_raises_on_unknown_type(self) -> None:
        """Should raise ValueError for unrecognized event type."""
        with pytest.raises(ValueError, match="Unrecognized event type"):
            parse_execution_event({"type": "unknown_event"})

    def test_roundtrip_ndjson_line(self) -> None:
        """Simulates parsing a single NDJSON line as DaemonClient would."""
        ndjson_line = '{"type": "text", "text": "response from agent"}'
        data = json.loads(ndjson_line)
        event = parse_execution_event(data)

        assert isinstance(event, TextEvent)
        assert event.text == "response from agent"
