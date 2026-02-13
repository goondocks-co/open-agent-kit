"""Unit tests for transcript parsing utilities.

Tests cover:
- Claude Code transcript format: {"type": "assistant", "message": {"role": "assistant", "content": ...}}
- VS Code Copilot transcript format: {"type": "assistant.message", "data": {"content": ...}}
- Simple format: {"role": "assistant", "content": ...}
- Edge cases: empty files, missing content, tool-only messages
"""

import json

import pytest

from open_agent_kit.features.codebase_intelligence.constants import (
    RESPONSE_SUMMARY_MAX_LENGTH,
)
from open_agent_kit.features.codebase_intelligence.transcript import (
    parse_transcript_response,
)


@pytest.fixture
def transcript_file(tmp_path):
    """Create a temporary transcript JSONL file from a list of dicts."""

    def _create(lines: list[dict], filename: str = "transcript.jsonl") -> str:
        path = tmp_path / filename
        path.write_text(
            "\n".join(json.dumps(line) for line in lines),
            encoding="utf-8",
        )
        return str(path)

    return _create


class TestClaudeCodeFormat:
    """Tests for Claude Code transcript format."""

    def test_extracts_assistant_text(self, transcript_file):
        """Extracts text from Claude Code assistant message."""
        path = transcript_file(
            [
                {"type": "assistant", "message": {"role": "assistant", "content": "Hello world"}},
            ]
        )
        result = parse_transcript_response(path)
        assert result == "Hello world"

    def test_extracts_from_content_blocks(self, transcript_file):
        """Extracts text from content block list format."""
        path = transcript_file(
            [
                {
                    "type": "assistant",
                    "message": {
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": "Part one"},
                            {"type": "tool_use", "name": "Read"},
                            {"type": "text", "text": "Part two"},
                        ],
                    },
                },
            ]
        )
        result = parse_transcript_response(path)
        assert result == "Part one\nPart two"

    def test_returns_last_assistant_message(self, transcript_file):
        """Returns the last assistant message, not the first."""
        path = transcript_file(
            [
                {
                    "type": "assistant",
                    "message": {"role": "assistant", "content": "First response"},
                },
                {
                    "type": "assistant",
                    "message": {"role": "assistant", "content": "Final response"},
                },
            ]
        )
        result = parse_transcript_response(path)
        assert result == "Final response"


class TestVSCodeCopilotFormat:
    """Tests for VS Code Copilot transcript format."""

    def test_extracts_assistant_message(self, transcript_file):
        """Extracts content from VS Code Copilot assistant.message."""
        path = transcript_file(
            [
                {"type": "session.start", "data": {"sessionId": "test-123"}},
                {"type": "user.message", "data": {"content": "What is this?"}},
                {"type": "assistant.turn_start", "data": {"turnId": "0"}},
                {
                    "type": "assistant.message",
                    "data": {
                        "messageId": "msg-1",
                        "content": "Here is the explanation.",
                        "toolRequests": [],
                        "reasoningText": "Thinking about this...",
                    },
                },
                {"type": "assistant.turn_end", "data": {"turnId": "0"}},
            ]
        )
        result = parse_transcript_response(path)
        assert result == "Here is the explanation."

    def test_returns_last_message_across_turns(self, transcript_file):
        """Returns the last assistant.message when multiple turns exist."""
        path = transcript_file(
            [
                {"type": "user.message", "data": {"content": "Question"}},
                {
                    "type": "assistant.message",
                    "data": {"content": "First turn response", "toolRequests": []},
                },
                {"type": "assistant.turn_end", "data": {"turnId": "0"}},
                {"type": "assistant.turn_start", "data": {"turnId": "1"}},
                {
                    "type": "assistant.message",
                    "data": {"content": "Final turn response", "toolRequests": []},
                },
                {"type": "assistant.turn_end", "data": {"turnId": "1"}},
            ]
        )
        result = parse_transcript_response(path)
        assert result == "Final turn response"

    def test_skips_tool_only_messages(self, transcript_file):
        """Skips assistant.message entries that have no text content (tool-only)."""
        path = transcript_file(
            [
                {
                    "type": "assistant.message",
                    "data": {
                        "content": "",
                        "toolRequests": [{"name": "read_file"}],
                    },
                },
                {"type": "assistant.turn_end", "data": {"turnId": "0"}},
                {"type": "assistant.turn_start", "data": {"turnId": "1"}},
                {
                    "type": "assistant.message",
                    "data": {"content": "After reading files.", "toolRequests": []},
                },
                {"type": "assistant.turn_end", "data": {"turnId": "1"}},
            ]
        )
        result = parse_transcript_response(path)
        assert result == "After reading files."

    def test_handles_missing_data_field(self, transcript_file):
        """Handles assistant.message with missing data field gracefully."""
        path = transcript_file(
            [
                {"type": "assistant.message"},
                {"type": "assistant.message", "data": {"content": "Fallback"}},
            ]
        )
        result = parse_transcript_response(path)
        assert result == "Fallback"


class TestSimpleFormat:
    """Tests for simple transcript format."""

    def test_extracts_role_based_message(self, transcript_file):
        """Extracts content from simple role-based format."""
        path = transcript_file(
            [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
            ]
        )
        result = parse_transcript_response(path)
        assert result == "Hi there!"


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_nonexistent_file_returns_none(self):
        """Returns None for nonexistent transcript file."""
        result = parse_transcript_response("/nonexistent/path/transcript.jsonl")
        assert result is None

    def test_empty_file_returns_none(self, transcript_file, tmp_path):
        """Returns None for empty file."""
        path = tmp_path / "empty.jsonl"
        path.write_text("", encoding="utf-8")
        result = parse_transcript_response(str(path))
        assert result is None

    def test_no_assistant_messages_returns_none(self, transcript_file):
        """Returns None when no assistant messages exist."""
        path = transcript_file(
            [
                {"type": "session.start", "data": {}},
                {"type": "user.message", "data": {"content": "Hello"}},
            ]
        )
        result = parse_transcript_response(path)
        assert result is None

    def test_truncates_to_max_length(self, transcript_file):
        """Long responses are truncated to max_length."""
        long_content = "A" * (RESPONSE_SUMMARY_MAX_LENGTH + 500)
        path = transcript_file(
            [
                {"role": "assistant", "content": long_content},
            ]
        )
        result = parse_transcript_response(path)
        assert result is not None
        assert len(result) == RESPONSE_SUMMARY_MAX_LENGTH

    def test_custom_max_length(self, transcript_file):
        """Custom max_length is respected."""
        path = transcript_file(
            [
                {"role": "assistant", "content": "A" * 200},
            ]
        )
        result = parse_transcript_response(path, max_length=50)
        assert result is not None
        assert len(result) == 50

    def test_invalid_json_lines_skipped(self, transcript_file, tmp_path):
        """Invalid JSON lines are skipped without error."""
        path = tmp_path / "mixed.jsonl"
        path.write_text(
            'not valid json\n{"role": "assistant", "content": "Valid"}\n',
            encoding="utf-8",
        )
        result = parse_transcript_response(str(path))
        assert result == "Valid"
