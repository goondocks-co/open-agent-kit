"""Tests for session summary generation and formatting.

Tests cover:
- Session summary prompt template loading
- _format_session_summaries helper function
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
    """Test the _format_session_summaries helper function."""

    def test_format_empty_summaries(self):
        """Test formatting with empty list returns empty string."""
        from open_agent_kit.features.codebase_intelligence.daemon.routes.hooks import (
            _format_session_summaries,
        )

        result = _format_session_summaries([])
        assert result == ""

    def test_format_single_summary(self):
        """Test formatting a single session summary."""
        from open_agent_kit.features.codebase_intelligence.daemon.routes.hooks import (
            _format_session_summaries,
        )

        summaries = [
            {
                "observation": "Implemented user authentication with JWT",
                "tags": ["session-summary", "claude"],
            }
        ]

        result = _format_session_summaries(summaries)

        assert "Recent Session History" in result
        assert "Session 1" in result
        assert "claude" in result
        assert "Implemented user authentication with JWT" in result

    def test_format_multiple_summaries(self):
        """Test formatting multiple session summaries."""
        from open_agent_kit.features.codebase_intelligence.daemon.routes.hooks import (
            _format_session_summaries,
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

        result = _format_session_summaries(summaries)

        assert "Session 1" in result
        assert "Session 2" in result
        assert "claude" in result
        assert "cursor" in result

    def test_format_truncates_long_summaries(self):
        """Test that long summaries are truncated."""
        from open_agent_kit.features.codebase_intelligence.daemon.routes.hooks import (
            _format_session_summaries,
        )

        long_text = "A" * 250  # Over 200 char limit
        summaries = [
            {
                "observation": long_text,
                "tags": ["session-summary", "claude"],
            }
        ]

        result = _format_session_summaries(summaries)

        assert "..." in result
        assert len(long_text) > 200  # Original is long
        # The truncated version should appear

    def test_format_respects_max_items(self):
        """Test that max_items parameter is respected."""
        from open_agent_kit.features.codebase_intelligence.daemon.routes.hooks import (
            _format_session_summaries,
        )

        summaries = [
            {"observation": f"Session {i}", "tags": ["session-summary", "claude"]}
            for i in range(10)
        ]

        result = _format_session_summaries(summaries, max_items=3)

        assert "Session 1" in result
        assert "Session 2" in result
        assert "Session 3" in result
        assert "Session 4" not in result

    def test_format_filters_system_tags(self):
        """Test that system tags are filtered when extracting agent name."""
        from open_agent_kit.features.codebase_intelligence.daemon.routes.hooks import (
            _format_session_summaries,
        )

        summaries = [
            {
                "observation": "Test work",
                "tags": ["session-summary", "auto-extracted", "gemini"],
            }
        ]

        result = _format_session_summaries(summaries)

        # Should show gemini, not the system tags
        assert "gemini" in result
        assert "(session-summary)" not in result
        assert "(auto-extracted)" not in result

    def test_format_handles_missing_tags(self):
        """Test formatting when tags are missing."""
        from open_agent_kit.features.codebase_intelligence.daemon.routes.hooks import (
            _format_session_summaries,
        )

        summaries = [
            {
                "observation": "Work without tags",
                "tags": [],
            }
        ]

        result = _format_session_summaries(summaries)

        assert "unknown" in result
        assert "Work without tags" in result


class TestProcessSessionSummary:
    """Test the ActivityProcessor.process_session_summary method."""

    @pytest.fixture
    def mock_activity_store(self):
        """Create a mock activity store."""
        mock = MagicMock()
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

        result = processor.process_session_summary("session-123")

        assert result is None

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

        result = processor.process_session_summary("nonexistent-session")

        assert result is None
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

        result = processor.process_session_summary("session-123")

        assert result is None

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
            "total_activities": 2,  # Less than 3
            "files_read": [],
            "files_modified": [],
            "files_created": [],
        }

        processor = ActivityProcessor(
            activity_store=mock_activity_store,
            vector_store=mock_vector_store,
            summarizer=mock_summarizer,
        )

        result = processor.process_session_summary("session-123")

        assert result is None

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
            "total_activities": 50,
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

            result = processor.process_session_summary("session-123")

        assert result == "Implemented JWT authentication and fixed login bug"
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
            "total_activities": 10,
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

            result = processor.process_session_summary("session-123")

        assert result is None
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
            "total_activities": 10,
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

            result = processor.process_session_summary("session-123")

        assert result == "Summary with surrounding quotes"
        assert not result.startswith('"')
        assert not result.endswith('"')
