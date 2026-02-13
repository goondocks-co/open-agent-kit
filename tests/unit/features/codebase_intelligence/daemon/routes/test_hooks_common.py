"""Tests for shared hook route infrastructure.

Tests cover:
- parse_hook_body() -- valid JSON, invalid JSON fallback, tool_input normalization
- handle_hook_errors decorator -- fire-and-forget returns {"status": "ok"}
- parse_tool_output() -- valid JSON, invalid JSON, empty input
- hash_value() -- deterministic output, consistent algorithm
- normalize_file_path() -- relative path computation, edge cases
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from open_agent_kit.features.codebase_intelligence.constants import (
    AGENT_UNKNOWN,
    HOOK_DEDUP_HASH_ALGORITHM,
    HOOK_FIELD_AGENT,
    HOOK_FIELD_CONVERSATION_ID,
    HOOK_FIELD_GENERATION_ID,
    HOOK_FIELD_HOOK_ORIGIN,
    HOOK_FIELD_SESSION_ID,
    HOOK_FIELD_TOOL_INPUT,
    HOOK_FIELD_TOOL_NAME,
    HOOK_FIELD_TOOL_USE_ID,
)
from open_agent_kit.features.codebase_intelligence.daemon.routes.hooks_common import (
    HookBody,
    handle_hook_errors,
    hash_value,
    normalize_file_path,
    parse_hook_body,
    parse_tool_output,
)


@pytest.fixture
def anyio_backend():
    """Restrict anyio tests to asyncio backend (trio is not installed)."""
    return "asyncio"


# =============================================================================
# Helpers
# =============================================================================


def _make_request(body: dict | None = None, *, raise_on_json: bool = False) -> MagicMock:
    """Create a mock FastAPI Request whose .json() returns the given body.

    Args:
        body: The JSON body to return.  If None, defaults to empty dict.
        raise_on_json: If True, .json() raises ValueError (simulating bad JSON).
    """
    request = MagicMock()
    if raise_on_json:
        request.json = AsyncMock(side_effect=ValueError("Invalid JSON"))
    else:
        request.json = AsyncMock(return_value=body if body is not None else {})
    return request


# =============================================================================
# parse_hook_body()
# =============================================================================


class TestParseHookBody:
    """Test parse_hook_body() async helper."""

    @pytest.mark.anyio
    async def test_valid_json_extracts_fields(self) -> None:
        """All standard fields are extracted from a well-formed request body."""
        body = {
            HOOK_FIELD_SESSION_ID: "sess-123",
            HOOK_FIELD_AGENT: "claude",
            HOOK_FIELD_TOOL_NAME: "Read",
            HOOK_FIELD_TOOL_INPUT: {"file_path": "/tmp/test.py"},
            HOOK_FIELD_HOOK_ORIGIN: "post-tool-use",
            HOOK_FIELD_TOOL_USE_ID: "tu-456",
            HOOK_FIELD_GENERATION_ID: "gen-789",
        }
        request = _make_request(body)
        result = await parse_hook_body(request)

        assert isinstance(result, HookBody)
        assert result.session_id == "sess-123"
        assert result.agent == "claude"
        assert result.tool_name == "Read"
        assert result.tool_input == {"file_path": "/tmp/test.py"}
        assert result.hook_origin == "post-tool-use"
        assert result.tool_use_id == "tu-456"
        assert result.generation_id == "gen-789"
        assert result.raw == body

    @pytest.mark.anyio
    async def test_invalid_json_returns_empty_hookbody(self) -> None:
        """Malformed JSON body returns HookBody with defaults."""
        request = _make_request(raise_on_json=True)
        result = await parse_hook_body(request)

        assert result.raw == {}
        assert result.session_id is None
        assert result.agent == AGENT_UNKNOWN
        assert result.tool_name == ""
        assert result.tool_input == {}

    @pytest.mark.anyio
    async def test_session_id_falls_back_to_conversation_id(self) -> None:
        """When session_id is absent, conversation_id is used."""
        body = {HOOK_FIELD_CONVERSATION_ID: "conv-abc"}
        request = _make_request(body)
        result = await parse_hook_body(request)

        assert result.session_id == "conv-abc"

    @pytest.mark.anyio
    async def test_session_id_prefers_session_id_over_conversation_id(self) -> None:
        """session_id takes priority over conversation_id when both present."""
        body = {
            HOOK_FIELD_SESSION_ID: "sess-primary",
            HOOK_FIELD_CONVERSATION_ID: "conv-fallback",
        }
        request = _make_request(body)
        result = await parse_hook_body(request)

        assert result.session_id == "sess-primary"

    @pytest.mark.anyio
    async def test_tool_input_string_parsed_as_json(self) -> None:
        """String tool_input is parsed as JSON."""
        input_dict = {"command": "ls"}
        body = {HOOK_FIELD_TOOL_INPUT: json.dumps(input_dict)}
        request = _make_request(body)
        result = await parse_hook_body(request)

        assert result.tool_input == input_dict

    @pytest.mark.anyio
    async def test_tool_input_unparseable_string_wrapped(self) -> None:
        """Unparseable string tool_input is wrapped in {"raw": ...}."""
        body = {HOOK_FIELD_TOOL_INPUT: "not json at all"}
        request = _make_request(body)
        result = await parse_hook_body(request)

        assert result.tool_input == {"raw": "not json at all"}

    @pytest.mark.anyio
    async def test_tool_input_none_becomes_empty_dict(self) -> None:
        """None tool_input is normalised to empty dict."""
        body = {HOOK_FIELD_TOOL_INPUT: None}
        request = _make_request(body)
        result = await parse_hook_body(request)

        assert result.tool_input == {}

    @pytest.mark.anyio
    async def test_tool_input_dict_passed_through(self) -> None:
        """Dict tool_input is used as-is."""
        input_dict = {"file": "main.py", "line": 42}
        body = {HOOK_FIELD_TOOL_INPUT: input_dict}
        request = _make_request(body)
        result = await parse_hook_body(request)

        assert result.tool_input == input_dict

    @pytest.mark.anyio
    async def test_missing_optional_fields_use_defaults(self) -> None:
        """Missing optional fields default to empty strings or AGENT_UNKNOWN."""
        body = {HOOK_FIELD_SESSION_ID: "sess-only"}
        request = _make_request(body)
        result = await parse_hook_body(request)

        assert result.agent == AGENT_UNKNOWN
        assert result.tool_name == ""
        assert result.hook_origin == ""
        assert result.tool_use_id == ""
        assert result.generation_id == ""


# =============================================================================
# handle_hook_errors decorator
# =============================================================================


class TestHandleHookErrors:
    """Test @handle_hook_errors decorator."""

    @pytest.mark.anyio
    async def test_successful_handler_returns_its_result(self) -> None:
        """Decorated handler returns its own result on success."""

        @handle_hook_errors("test-hook")
        async def handler() -> dict:
            return {"status": "ok", "extra": "data"}

        result = await handler()
        assert result == {"status": "ok", "extra": "data"}

    @pytest.mark.anyio
    async def test_exception_returns_ok_status(self) -> None:
        """Any exception is swallowed and {"status": "ok"} is returned."""

        @handle_hook_errors("test-hook")
        async def handler() -> dict:
            raise RuntimeError("Something broke")

        result = await handler()
        assert result == {"status": "ok"}

    @pytest.mark.anyio
    async def test_value_error_returns_ok_status(self) -> None:
        """ValueError is also swallowed (fire-and-forget)."""

        @handle_hook_errors("test-hook")
        async def handler() -> dict:
            raise ValueError("Bad data")

        result = await handler()
        assert result == {"status": "ok"}

    @pytest.mark.anyio
    async def test_preserves_function_name(self) -> None:
        """functools.wraps preserves the original function name."""

        @handle_hook_errors("test-hook")
        async def my_special_handler() -> dict:
            return {"status": "ok"}

        assert my_special_handler.__name__ == "my_special_handler"


# =============================================================================
# parse_tool_output()
# =============================================================================


class TestParseToolOutput:
    """Test parse_tool_output() utility."""

    def test_valid_json_dict(self) -> None:
        """Valid JSON dict string is parsed and returned."""
        result = parse_tool_output('{"key": "value", "count": 42}')
        assert result == {"key": "value", "count": 42}

    def test_valid_json_non_dict_returns_none(self) -> None:
        """Valid JSON that is not a dict (e.g. list) returns None."""
        assert parse_tool_output("[1, 2, 3]") is None

    def test_valid_json_string_returns_none(self) -> None:
        """Valid JSON string primitive returns None."""
        assert parse_tool_output('"just a string"') is None

    def test_invalid_json_returns_none(self) -> None:
        """Invalid JSON returns None."""
        assert parse_tool_output("not json at all") is None

    def test_empty_string_returns_none(self) -> None:
        """Empty string returns None."""
        assert parse_tool_output("") is None

    def test_nested_dict(self) -> None:
        """Nested JSON dict is correctly parsed."""
        data = {"outer": {"inner": "value"}}
        result = parse_tool_output(json.dumps(data))
        assert result == data


# =============================================================================
# hash_value()
# =============================================================================


class TestHashValue:
    """Test hash_value() utility."""

    def test_deterministic_output(self) -> None:
        """Same input always produces the same hash."""
        assert hash_value("test-input") == hash_value("test-input")

    def test_different_inputs_different_hashes(self) -> None:
        """Different inputs produce different hashes."""
        assert hash_value("input-a") != hash_value("input-b")

    def test_uses_configured_algorithm(self) -> None:
        """hash_value uses the HOOK_DEDUP_HASH_ALGORITHM from constants."""
        import hashlib

        expected = hashlib.new(HOOK_DEDUP_HASH_ALGORITHM)
        expected.update(b"test-value")
        assert hash_value("test-value") == expected.hexdigest()

    def test_empty_string(self) -> None:
        """Empty string produces a valid hash (not empty or None)."""
        result = hash_value("")
        assert isinstance(result, str)
        assert len(result) > 0


# =============================================================================
# normalize_file_path()
# =============================================================================


class TestNormalizeFilePath:
    """Test normalize_file_path() utility."""

    def test_absolute_path_within_project(self, tmp_path: Path) -> None:
        """Absolute path under project root is converted to relative posix path."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        file_path = project_root / "src" / "main.py"
        file_path.parent.mkdir(parents=True)
        file_path.touch()

        result = normalize_file_path(str(file_path), project_root)
        assert result == "src/main.py"

    def test_relative_path_resolved_against_project(self, tmp_path: Path) -> None:
        """Relative path is resolved against project root."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        file_path = project_root / "lib" / "utils.py"
        file_path.parent.mkdir(parents=True)
        file_path.touch()

        result = normalize_file_path("lib/utils.py", project_root)
        assert result == "lib/utils.py"

    def test_empty_path_returns_empty(self) -> None:
        """Empty file path is returned as-is."""
        assert normalize_file_path("", Path("/some/root")) == ""

    def test_none_project_root_returns_original(self) -> None:
        """When project_root is None, the original path is returned."""
        assert normalize_file_path("/some/file.py", None) == "/some/file.py"

    def test_path_outside_project_returns_original(self, tmp_path: Path) -> None:
        """Path outside the project root is returned as-is."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        outside_path = "/completely/different/path.py"

        result = normalize_file_path(outside_path, project_root)
        assert result == outside_path

    def test_project_root_itself(self, tmp_path: Path) -> None:
        """Project root path itself returns empty relative path."""
        project_root = tmp_path / "project"
        project_root.mkdir()

        result = normalize_file_path(str(project_root), project_root)
        # Path(".").as_posix() == "."
        assert result == "."
