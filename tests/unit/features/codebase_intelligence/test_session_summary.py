"""Tests for session summary generation and formatting.

Tests cover:
- Session summary prompt template loading
- format_session_summaries helper function (in injection.py)
- process_session_summary method in ActivityProcessor
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest


class TestSessionSummaryPromptTemplate:
    """Test that the session-summary prompt template loads correctly."""

    def test_session_summary_template_exists(self):
        """Test that session-summary.md template file exists."""
        from open_agent_kit.features.codebase_intelligence.activity.prompts import (
            PromptTemplateConfig,
        )

        config = PromptTemplateConfig.load_from_directory()
        template = config.get_template("session-summary")

        assert template is not None
        assert template.name == "session-summary"

    def test_session_summary_template_has_required_placeholders(self):
        """Test that template contains required placeholders."""
        from open_agent_kit.features.codebase_intelligence.activity.prompts import (
            PromptTemplateConfig,
        )

        config = PromptTemplateConfig.load_from_directory()
        template = config.get_template("session-summary")

        assert template is not None
        assert "{{session_duration}}" in template.prompt
        assert "{{prompt_batch_count}}" in template.prompt
        assert "{{files_read_count}}" in template.prompt
        assert "{{files_modified_count}}" in template.prompt
        assert "{{files_created_count}}" in template.prompt
        assert "{{tool_calls}}" in template.prompt
        assert "{{prompt_batches}}" in template.prompt

    def test_session_summary_template_has_examples(self):
        """Test that template contains good and bad examples."""
        from open_agent_kit.features.codebase_intelligence.activity.prompts import (
            PromptTemplateConfig,
        )

        config = PromptTemplateConfig.load_from_directory()
        template = config.get_template("session-summary")

        assert template is not None
        assert "Good" in template.prompt
        assert "Bad" in template.prompt


class TestFormatSessionSummaries:
    """Test the format_session_summaries helper function."""

    def test_format_empty_summaries(self):
        """Test formatting with empty list returns empty string."""
        from open_agent_kit.features.codebase_intelligence.daemon.routes.injection import (
            format_session_summaries,
        )

        result = format_session_summaries([])
        assert result == ""

    def test_format_single_summary(self):
        """Test formatting a single session summary."""
        from open_agent_kit.features.codebase_intelligence.daemon.routes.injection import (
            format_session_summaries,
        )

        summaries = [
            {
                "observation": "Implemented user authentication with JWT",
                "tags": ["session-summary", "claude"],
            }
        ]

        result = format_session_summaries(summaries)

        from open_agent_kit.features.codebase_intelligence.constants import (
            INJECTION_SESSION_SUMMARIES_TITLE,
        )

        assert INJECTION_SESSION_SUMMARIES_TITLE in result
        assert "Session 1" in result
        assert "claude" in result
        assert "Implemented user authentication with JWT" in result

    def test_format_multiple_summaries(self):
        """Test formatting multiple session summaries."""
        from open_agent_kit.features.codebase_intelligence.daemon.routes.injection import (
            format_session_summaries,
        )

        summaries = [
            {
                "observation": "First session work",
                "tags": ["session-summary", "claude"],
            },
            {
                "observation": "Second session work",
                "tags": ["session-summary", "cursor"],
            },
        ]

        result = format_session_summaries(summaries)

        assert "Session 1" in result
        assert "Session 2" in result
        assert "claude" in result
        assert "cursor" in result

    def test_format_truncates_long_summaries(self):
        """Test that long summaries are truncated."""
        from open_agent_kit.features.codebase_intelligence.daemon.routes.injection import (
            format_session_summaries,
        )

        long_text = "A" * 250  # Over 200 char limit
        summaries = [
            {
                "observation": long_text,
                "tags": ["session-summary", "claude"],
            }
        ]

        result = format_session_summaries(summaries)

        assert "..." in result
        assert len(long_text) > 200  # Original is long
        # The truncated version should appear

    def test_format_respects_max_items(self):
        """Test that max_items parameter is respected."""
        from open_agent_kit.features.codebase_intelligence.daemon.routes.injection import (
            format_session_summaries,
        )

        summaries = [
            {"observation": f"Session {i}", "tags": ["session-summary", "claude"]}
            for i in range(10)
        ]

        result = format_session_summaries(summaries, max_items=3)

        assert "Session 1" in result
        assert "Session 2" in result
        assert "Session 3" in result
        assert "Session 4" not in result

    def test_format_filters_system_tags(self):
        """Test that system tags are filtered when extracting agent name."""
        from open_agent_kit.features.codebase_intelligence.daemon.routes.injection import (
            format_session_summaries,
        )

        summaries = [
            {
                "observation": "Test work",
                "tags": ["session-summary", "auto-extracted", "gemini"],
            }
        ]

        result = format_session_summaries(summaries)

        # Should show gemini, not the system tags
        assert "gemini" in result
        assert "(session-summary)" not in result
        assert "(auto-extracted)" not in result

    def test_format_handles_missing_tags(self):
        """Test formatting when tags are missing."""
        from open_agent_kit.features.codebase_intelligence.daemon.routes.injection import (
            format_session_summaries,
        )

        summaries = [
            {
                "observation": "Work without tags",
                "tags": [],
            }
        ]

        result = format_session_summaries(summaries)

        assert "unknown" in result
        assert "Work without tags" in result


class TestUnwrapJsonSummary:
    """Test _unwrap_json_summary defensive parsing for misbehaving models."""

    def test_plain_text_passthrough(self):
        """Plain text is returned unchanged."""
        from open_agent_kit.features.codebase_intelligence.activity.processor.summaries import (
            _unwrap_json_summary,
        )

        text = "Chris implemented JWT authentication and fixed the login bug."
        assert _unwrap_json_summary(text) == text

    def test_json_with_string_summary(self):
        """JSON with a string summary field is unwrapped."""
        from open_agent_kit.features.codebase_intelligence.activity.processor.summaries import (
            _unwrap_json_summary,
        )

        text = '{"summary": "Implemented dark mode support."}'
        assert _unwrap_json_summary(text) == "Implemented dark mode support."

    def test_json_with_array_summary(self):
        """JSON with an array summary field is joined into a string."""
        from open_agent_kit.features.codebase_intelligence.activity.processor.summaries import (
            _unwrap_json_summary,
        )

        text = '{"summary": ["First paragraph.", "Second paragraph."]}'
        assert _unwrap_json_summary(text) == "First paragraph. Second paragraph."

    def test_json_with_observations_and_summary(self):
        """JSON with both observations and summary extracts just the summary."""
        from open_agent_kit.features.codebase_intelligence.activity.processor.summaries import (
            _unwrap_json_summary,
        )

        text = '{"observations": [], "summary": "Fixed the auth bug."}'
        assert _unwrap_json_summary(text) == "Fixed the auth bug."

    def test_json_without_summary_key_returns_original(self):
        """JSON without a summary key returns original text."""
        from open_agent_kit.features.codebase_intelligence.activity.processor.summaries import (
            _unwrap_json_summary,
        )

        text = '{"observations": [{"type": "gotcha"}]}'
        assert _unwrap_json_summary(text) == text

    def test_json_with_empty_summary_returns_original(self):
        """JSON with empty summary returns original text."""
        from open_agent_kit.features.codebase_intelligence.activity.processor.summaries import (
            _unwrap_json_summary,
        )

        text = '{"summary": ""}'
        assert _unwrap_json_summary(text) == text

    def test_invalid_json_passthrough(self):
        """Text that starts with { but isn't valid JSON passes through."""
        from open_agent_kit.features.codebase_intelligence.activity.processor.summaries import (
            _unwrap_json_summary,
        )

        text = "{not valid json at all"
        assert _unwrap_json_summary(text) == text

    def test_json_with_whitespace(self):
        """JSON with leading/trailing whitespace is still detected."""
        from open_agent_kit.features.codebase_intelligence.activity.processor.summaries import (
            _unwrap_json_summary,
        )

        text = '  \n{"summary": "Cleaned up tests."}\n  '
        assert _unwrap_json_summary(text) == "Cleaned up tests."


class TestParseLlmResponseSummaryNormalization:
    """Test that _parse_llm_response normalizes summary to string."""

    def test_summary_as_list_is_joined(self):
        """When model returns summary as a list, it should be joined."""
        from open_agent_kit.features.codebase_intelligence.summarization.providers import (
            _parse_llm_response,
        )

        raw = '{"observations": [], "summary": ["Part one.", "Part two."]}'
        result = _parse_llm_response(raw)
        assert result.success is True
        assert result.session_summary == "Part one. Part two."

    def test_summary_as_string_unchanged(self):
        """When model returns summary as a string, it stays as-is."""
        from open_agent_kit.features.codebase_intelligence.summarization.providers import (
            _parse_llm_response,
        )

        raw = '{"observations": [], "summary": "Simple summary."}'
        result = _parse_llm_response(raw)
        assert result.success is True
        assert result.session_summary == "Simple summary."


class TestProcessSessionSummary:
    """Test the ActivityProcessor.process_session_summary method."""

    @pytest.fixture
    def mock_activity_store(self):
        """Create a mock activity store."""
        mock = MagicMock()
        # Default: no existing session summary (handles resumed session logic)
        mock.get_latest_session_summary.return_value = None
        return mock

    @pytest.fixture
    def mock_vector_store(self):
        """Create a mock vector store."""
        mock = MagicMock()
        mock.add_memory.return_value = "memory-id-123"
        return mock

    @pytest.fixture
    def mock_summarizer(self):
        """Create a mock summarizer."""
        mock = MagicMock()
        return mock

    def test_process_session_summary_no_summarizer(self, mock_activity_store, mock_vector_store):
        """Test that process_session_summary returns None without summarizer."""
        from open_agent_kit.features.codebase_intelligence.activity.processor import (
            ActivityProcessor,
        )

        processor = ActivityProcessor(
            activity_store=mock_activity_store,
            vector_store=mock_vector_store,
            summarizer=None,
        )

        summary, title = processor.process_session_summary_with_title("session-123")

        assert summary is None
        assert title is None

    def test_process_session_summary_session_not_found(
        self, mock_activity_store, mock_vector_store, mock_summarizer
    ):
        """Test handling when session is not found."""
        from open_agent_kit.features.codebase_intelligence.activity.processor import (
            ActivityProcessor,
        )

        mock_activity_store.get_session.return_value = None

        processor = ActivityProcessor(
            activity_store=mock_activity_store,
            vector_store=mock_vector_store,
            summarizer=mock_summarizer,
        )

        summary, title = processor.process_session_summary_with_title("nonexistent-session")

        assert summary is None
        assert title is None
        mock_activity_store.get_session.assert_called_once_with("nonexistent-session")

    def test_process_session_summary_no_batches(
        self, mock_activity_store, mock_vector_store, mock_summarizer
    ):
        """Test handling when session has no prompt batches."""
        from open_agent_kit.features.codebase_intelligence.activity.processor import (
            ActivityProcessor,
        )
        from open_agent_kit.features.codebase_intelligence.activity.store import (
            Session,
        )

        mock_session = Session(
            id="session-123",
            agent="claude",
            project_root="/test/project",
            started_at=datetime.now(),
        )
        mock_activity_store.get_session.return_value = mock_session
        mock_activity_store.get_session_prompt_batches.return_value = []

        processor = ActivityProcessor(
            activity_store=mock_activity_store,
            vector_store=mock_vector_store,
            summarizer=mock_summarizer,
        )

        summary, title = processor.process_session_summary_with_title("session-123")

        assert summary is None
        assert title is None

    def test_process_session_summary_too_short(
        self, mock_activity_store, mock_vector_store, mock_summarizer
    ):
        """Test that sessions with few tool calls are skipped."""
        from open_agent_kit.features.codebase_intelligence.activity.processor import (
            ActivityProcessor,
        )
        from open_agent_kit.features.codebase_intelligence.activity.store import (
            PromptBatch,
            Session,
        )

        mock_session = Session(
            id="session-123",
            agent="claude",
            project_root="/test/project",
            started_at=datetime.now(),
        )
        mock_activity_store.get_session.return_value = mock_session
        mock_activity_store.get_session_prompt_batches.return_value = [
            PromptBatch(
                id=1,
                session_id="session-123",
                prompt_number=1,
                user_prompt="test",
                started_at=datetime.now(),
            )
        ]
        mock_activity_store.get_session_stats.return_value = {
            "activity_count": 2,  # Less than 3
            "files_read": [],
            "files_modified": [],
            "files_created": [],
        }

        processor = ActivityProcessor(
            activity_store=mock_activity_store,
            vector_store=mock_vector_store,
            summarizer=mock_summarizer,
        )

        summary, title = processor.process_session_summary_with_title("session-123")

        assert summary is None
        assert title is None

    def test_process_session_summary_success(
        self, mock_activity_store, mock_vector_store, mock_summarizer
    ):
        """Test successful session summary generation."""
        from open_agent_kit.features.codebase_intelligence.activity.processor import (
            ActivityProcessor,
        )
        from open_agent_kit.features.codebase_intelligence.activity.store import (
            PromptBatch,
            Session,
        )

        now = datetime.now()
        mock_session = Session(
            id="session-123",
            agent="claude",
            project_root="/test/project",
            started_at=now - timedelta(minutes=30),
            ended_at=now,
        )
        mock_activity_store.get_session.return_value = mock_session
        mock_activity_store.get_session_prompt_batches.return_value = [
            PromptBatch(
                id=1,
                session_id="session-123",
                prompt_number=1,
                user_prompt="Add user authentication",
                classification="implementation",
                started_at=now - timedelta(minutes=25),
            ),
            PromptBatch(
                id=2,
                session_id="session-123",
                prompt_number=2,
                user_prompt="Fix the login bug",
                classification="debugging",
                started_at=now - timedelta(minutes=10),
            ),
        ]
        mock_activity_store.get_session_stats.return_value = {
            "activity_count": 50,
            "files_read": ["auth.py", "config.py"],
            "files_modified": ["auth.py"],
            "files_created": [],
        }

        # Mock the _call_llm method to return a summary
        with patch.object(
            ActivityProcessor,
            "_call_llm",
            return_value={
                "success": True,
                "raw_response": "Implemented JWT authentication and fixed login bug",
            },
        ):
            processor = ActivityProcessor(
                activity_store=mock_activity_store,
                vector_store=mock_vector_store,
                summarizer=mock_summarizer,
            )

            summary, _title = processor.process_session_summary_with_title("session-123")

        assert summary == "Implemented JWT authentication and fixed login bug"
        mock_vector_store.add_memory.assert_called_once()

        # Verify the memory was created with correct type
        call_args = mock_vector_store.add_memory.call_args
        memory = call_args[0][0]
        assert memory.memory_type == "session_summary"
        assert "session-summary" in memory.tags
        assert "claude" in memory.tags

    def test_process_session_summary_llm_failure(
        self, mock_activity_store, mock_vector_store, mock_summarizer
    ):
        """Test handling when LLM call fails."""
        from open_agent_kit.features.codebase_intelligence.activity.processor import (
            ActivityProcessor,
        )
        from open_agent_kit.features.codebase_intelligence.activity.store import (
            PromptBatch,
            Session,
        )

        now = datetime.now()
        mock_session = Session(
            id="session-123",
            agent="claude",
            project_root="/test/project",
            started_at=now - timedelta(minutes=30),
            ended_at=now,
        )
        mock_activity_store.get_session.return_value = mock_session
        mock_activity_store.get_session_prompt_batches.return_value = [
            PromptBatch(
                id=1,
                session_id="session-123",
                prompt_number=1,
                user_prompt="Test",
                started_at=now,
            )
        ]
        mock_activity_store.get_session_stats.return_value = {
            "activity_count": 10,
            "files_read": [],
            "files_modified": [],
            "files_created": [],
        }

        with patch.object(
            ActivityProcessor,
            "_call_llm",
            return_value={"success": False, "error": "LLM unavailable"},
        ):
            processor = ActivityProcessor(
                activity_store=mock_activity_store,
                vector_store=mock_vector_store,
                summarizer=mock_summarizer,
            )

            summary, title = processor.process_session_summary_with_title("session-123")

        assert summary is None
        assert title is None
        mock_vector_store.add_memory.assert_not_called()

    def test_process_session_summary_strips_quotes(
        self, mock_activity_store, mock_vector_store, mock_summarizer
    ):
        """Test that surrounding quotes are stripped from LLM response."""
        from open_agent_kit.features.codebase_intelligence.activity.processor import (
            ActivityProcessor,
        )
        from open_agent_kit.features.codebase_intelligence.activity.store import (
            PromptBatch,
            Session,
        )

        now = datetime.now()
        mock_session = Session(
            id="session-123",
            agent="claude",
            project_root="/test/project",
            started_at=now - timedelta(minutes=30),
            ended_at=now,
        )
        mock_activity_store.get_session.return_value = mock_session
        mock_activity_store.get_session_prompt_batches.return_value = [
            PromptBatch(
                id=1,
                session_id="session-123",
                prompt_number=1,
                user_prompt="Test",
                started_at=now,
            )
        ]
        mock_activity_store.get_session_stats.return_value = {
            "activity_count": 10,
            "files_read": [],
            "files_modified": [],
            "files_created": [],
        }

        # LLM sometimes wraps response in quotes
        with patch.object(
            ActivityProcessor,
            "_call_llm",
            return_value={
                "success": True,
                "raw_response": '"Summary with surrounding quotes"',
            },
        ):
            processor = ActivityProcessor(
                activity_store=mock_activity_store,
                vector_store=mock_vector_store,
                summarizer=mock_summarizer,
            )

            summary, _title = processor.process_session_summary_with_title("session-123")

        assert summary == "Summary with surrounding quotes"
        assert not summary.startswith('"')
        assert not summary.endswith('"')

    def test_process_session_summary_skips_if_already_summarized_no_new_batches(
        self, mock_activity_store, mock_vector_store, mock_summarizer
    ):
        """Test that resumed sessions with no new activity skip summarization."""
        from open_agent_kit.features.codebase_intelligence.activity.processor import (
            ActivityProcessor,
        )
        from open_agent_kit.features.codebase_intelligence.activity.store import (
            PromptBatch,
            Session,
            StoredObservation,
        )

        now = datetime.now()
        summary_time = now - timedelta(minutes=10)  # Summary was created 10 mins ago

        mock_session = Session(
            id="session-123",
            agent="claude",
            project_root="/test/project",
            started_at=now - timedelta(hours=2),
            ended_at=now,
        )

        # Existing summary from before
        existing_summary = StoredObservation(
            id="summary-old",
            session_id="session-123",
            observation="Previous session summary",
            memory_type="session_summary",
            created_at=summary_time,
        )

        # Batch that's older than the summary (already covered)
        old_batch = PromptBatch(
            id=1,
            session_id="session-123",
            prompt_number=1,
            user_prompt="Old work",
            started_at=now - timedelta(hours=1),  # Before summary_time
        )

        mock_activity_store.get_session.return_value = mock_session
        mock_activity_store.get_session_prompt_batches.return_value = [old_batch]
        mock_activity_store.get_latest_session_summary.return_value = existing_summary

        processor = ActivityProcessor(
            activity_store=mock_activity_store,
            vector_store=mock_vector_store,
            summarizer=mock_summarizer,
        )

        summary, title = processor.process_session_summary_with_title("session-123")

        # Should skip - no new batches since last summary
        assert summary is None
        assert title is None
        mock_summarizer.summarize.assert_not_called()

    def test_process_session_summary_includes_all_batches_on_resume(
        self, mock_activity_store, mock_vector_store, mock_summarizer
    ):
        """Test that resumed sessions re-summarize ALL batches for full context.

        When a session is resumed and completed again, the new summary should
        include all batches (not just new ones) so that the replacement summary
        has full session context. The deterministic ID ensures upsert behavior.
        """
        from unittest.mock import patch

        from open_agent_kit.features.codebase_intelligence.activity.processor import (
            ActivityProcessor,
        )
        from open_agent_kit.features.codebase_intelligence.activity.store import (
            PromptBatch,
            Session,
            StoredObservation,
        )

        now = datetime.now()
        summary_time = now - timedelta(minutes=30)  # Summary was created 30 mins ago

        mock_session = Session(
            id="session-123",
            agent="claude",
            project_root="/test/project",
            started_at=now - timedelta(hours=2),
            ended_at=now,
        )

        # Existing summary from first session leg
        existing_summary = StoredObservation(
            id="summary-old",
            session_id="session-123",
            observation="Previous session summary",
            memory_type="session_summary",
            created_at=summary_time,
        )

        # Old batch (before summary - from first session leg)
        old_batch = PromptBatch(
            id=1,
            session_id="session-123",
            prompt_number=1,
            user_prompt="Old work from first leg",
            started_at=now - timedelta(hours=1),
            classification="implementation",
        )

        # New batch (after summary - from resumed session)
        new_batch = PromptBatch(
            id=2,
            session_id="session-123",
            prompt_number=2,
            user_prompt="New work after resume",
            started_at=now - timedelta(minutes=5),  # After summary_time
            classification="debugging",
        )

        mock_activity_store.get_session.return_value = mock_session
        mock_activity_store.get_session_prompt_batches.return_value = [old_batch, new_batch]
        mock_activity_store.get_latest_session_summary.return_value = existing_summary
        mock_activity_store.get_session_stats.return_value = {
            "activity_count": 10,
            "files_read": ["test.py"],
            "files_modified": ["test.py"],
            "files_created": [],
        }

        llm_calls = []

        def capture_llm_call(prompt):
            llm_calls.append(prompt)
            return {
                "success": True,
                "raw_response": "Full session: implemented feature and fixed bugs",
            }

        with patch.object(ActivityProcessor, "_call_llm", side_effect=capture_llm_call):
            processor = ActivityProcessor(
                activity_store=mock_activity_store,
                vector_store=mock_vector_store,
                summarizer=mock_summarizer,
            )

            summary, _title = processor.process_session_summary_with_title("session-123")

        # Should generate summary
        assert summary == "Full session: implemented feature and fixed bugs"
        # Verify it was stored
        mock_activity_store.store_observation.assert_called_once()

        # Verify LLM received ALL batches in the SUMMARY call (first call)
        # Note: There may be 2 calls total (summary + title generation)
        assert len(llm_calls) >= 1
        summary_prompt = llm_calls[0]  # First call is for summary
        assert "Old work from first leg" in summary_prompt  # Old batch included
        assert "New work after resume" in summary_prompt  # New batch included
