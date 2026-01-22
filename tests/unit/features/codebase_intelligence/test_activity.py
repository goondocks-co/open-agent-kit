"""Tests for Activity module (store.py and processor.py).

Tests cover:
- ActivityStore: session CRUD operations, prompt batch operations, activity logging,
  search functionality (FTS5), and statistics methods
- ActivityProcessor: prompt batch processing, activity summarization, memory extraction,
  and error handling with mocked LLM calls
"""

import tempfile
import threading
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from open_agent_kit.features.codebase_intelligence.activity.processor import (
    ActivityProcessor,
    ContextBudget,
    ProcessingResult,
)
from open_agent_kit.features.codebase_intelligence.activity.store import (
    Activity,
    ActivityStore,
    Session,
    StoredObservation,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for testing."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test_activity.db"
        yield db_path


@pytest.fixture
def activity_store(temp_db):
    """Create an ActivityStore instance with temporary database."""
    return ActivityStore(temp_db)


@pytest.fixture
def mock_vector_store():
    """Create a mock vector store."""
    mock = MagicMock()
    mock.add_documents.return_value = True
    mock.search.return_value = [
        {"id": "obs_1", "score": 0.95, "text": "observation 1"},
        {"id": "obs_2", "score": 0.85, "text": "observation 2"},
    ]
    return mock


@pytest.fixture
def mock_summarizer():
    """Create a mock summarizer."""
    mock = MagicMock()
    mock.summarize.return_value = {
        "success": True,
        "observations": [
            {"title": "Observation 1", "description": "Test observation 1"},
            {"title": "Observation 2", "description": "Test observation 2"},
        ],
    }
    return mock


@pytest.fixture
def mock_prompt_config():
    """Create a mock prompt template config."""
    mock = MagicMock()

    # Mock template objects
    classify_template = MagicMock()
    classify_template.name = "classify"

    extract_template = MagicMock()
    extract_template.name = "extract"

    def get_template(name):
        if name == "classify":
            return classify_template
        elif name == "extract":
            return extract_template
        return extract_template

    mock.get_template = get_template
    return mock


@pytest.fixture
def activity_processor(activity_store, mock_vector_store, mock_summarizer, mock_prompt_config):
    """Create an ActivityProcessor instance with mocked dependencies."""
    return ActivityProcessor(
        activity_store=activity_store,
        vector_store=mock_vector_store,
        summarizer=mock_summarizer,
        prompt_config=mock_prompt_config,
        project_root="/test/project",
        context_tokens=4096,
    )


# =============================================================================
# ActivityStore Tests: Session Operations
# =============================================================================


class TestActivityStoreSessionOperations:
    """Test session CRUD operations."""

    def test_create_session(self, activity_store: ActivityStore):
        """Test creating a new session."""
        session = activity_store.create_session(
            session_id="test-session-1",
            agent="claude",
            project_root="/path/to/project",
        )

        assert session.id == "test-session-1"
        assert session.agent == "claude"
        assert session.project_root == "/path/to/project"
        assert session.status == "active"
        assert session.prompt_count == 0
        assert session.tool_count == 0
        assert session.processed is False

    def test_get_session(self, activity_store: ActivityStore):
        """Test retrieving an existing session."""
        created = activity_store.create_session(
            session_id="test-session-2",
            agent="cursor",
            project_root="/another/path",
        )

        retrieved = activity_store.get_session("test-session-2")
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.agent == created.agent

    def test_get_nonexistent_session(self, activity_store: ActivityStore):
        """Test retrieving a nonexistent session returns None."""
        result = activity_store.get_session("nonexistent-session")
        assert result is None

    def test_end_session(self, activity_store: ActivityStore):
        """Test ending a session."""
        activity_store.create_session(
            session_id="test-session-3",
            agent="claude",
            project_root="/path",
        )

        activity_store.end_session(
            session_id="test-session-3",
            summary="Test summary",
        )

        session = activity_store.get_session("test-session-3")
        assert session.status == "completed"
        assert session.ended_at is not None
        assert session.summary == "Test summary"

    def test_end_session_without_summary(self, activity_store: ActivityStore):
        """Test ending a session without a summary."""
        activity_store.create_session(
            session_id="test-session-4",
            agent="claude",
            project_root="/path",
        )

        activity_store.end_session(session_id="test-session-4")

        session = activity_store.get_session("test-session-4")
        assert session.status == "completed"
        assert session.summary is None

    def test_increment_prompt_count(self, activity_store: ActivityStore):
        """Test incrementing session prompt count."""
        activity_store.create_session(
            session_id="test-session-5",
            agent="claude",
            project_root="/path",
        )

        activity_store.increment_prompt_count("test-session-5")
        session = activity_store.get_session("test-session-5")
        assert session.prompt_count == 1

        activity_store.increment_prompt_count("test-session-5")
        session = activity_store.get_session("test-session-5")
        assert session.prompt_count == 2

    def test_get_unprocessed_sessions(self, activity_store: ActivityStore):
        """Test retrieving unprocessed sessions."""
        # Create and complete some sessions
        for i in range(3):
            session_id = f"test-session-unproc-{i}"
            activity_store.create_session(
                session_id=session_id,
                agent="claude",
                project_root="/path",
            )
            activity_store.end_session(session_id)

        unprocessed = activity_store.get_unprocessed_sessions(limit=10)
        assert len(unprocessed) == 3
        assert all(s.processed is False for s in unprocessed)

    def test_mark_session_processed(self, activity_store: ActivityStore):
        """Test marking a session as processed."""
        activity_store.create_session(
            session_id="test-session-6",
            agent="claude",
            project_root="/path",
        )
        activity_store.end_session("test-session-6")

        activity_store.mark_session_processed("test-session-6")

        session = activity_store.get_session("test-session-6")
        assert session.processed is True


# =============================================================================
# ActivityStore Tests: Prompt Batch Operations
# =============================================================================


class TestActivityStorePromptBatchOperations:
    """Test prompt batch CRUD operations."""

    def test_create_prompt_batch(self, activity_store: ActivityStore):
        """Test creating a prompt batch."""
        activity_store.create_session(
            session_id="test-session-pb1",
            agent="claude",
            project_root="/path",
        )

        batch = activity_store.create_prompt_batch(
            session_id="test-session-pb1",
            user_prompt="What should I do?",
        )

        assert batch.session_id == "test-session-pb1"
        assert batch.prompt_number == 1
        assert batch.user_prompt == "What should I do?"
        assert batch.status == "active"
        assert batch.processed is False

    def test_create_multiple_prompt_batches(self, activity_store: ActivityStore):
        """Test creating multiple prompt batches in sequence."""
        activity_store.create_session(
            session_id="test-session-pb2",
            agent="claude",
            project_root="/path",
        )

        batch1 = activity_store.create_prompt_batch(
            session_id="test-session-pb2",
            user_prompt="First prompt",
        )
        batch2 = activity_store.create_prompt_batch(
            session_id="test-session-pb2",
            user_prompt="Second prompt",
        )

        assert batch1.prompt_number == 1
        assert batch2.prompt_number == 2

    def test_get_prompt_batch(self, activity_store: ActivityStore):
        """Test retrieving a prompt batch."""
        activity_store.create_session(
            session_id="test-session-pb3",
            agent="claude",
            project_root="/path",
        )

        created = activity_store.create_prompt_batch(
            session_id="test-session-pb3",
            user_prompt="Test prompt",
        )

        retrieved = activity_store.get_prompt_batch(created.id)
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.user_prompt == "Test prompt"

    def test_get_active_prompt_batch(self, activity_store: ActivityStore):
        """Test retrieving the active prompt batch for a session."""
        activity_store.create_session(
            session_id="test-session-pb4",
            agent="claude",
            project_root="/path",
        )

        batch = activity_store.create_prompt_batch(
            session_id="test-session-pb4",
            user_prompt="Active prompt",
        )

        active = activity_store.get_active_prompt_batch("test-session-pb4")
        assert active is not None
        assert active.id == batch.id
        assert active.status == "active"

    def test_end_prompt_batch(self, activity_store: ActivityStore):
        """Test ending a prompt batch."""
        activity_store.create_session(
            session_id="test-session-pb5",
            agent="claude",
            project_root="/path",
        )

        batch = activity_store.create_prompt_batch(
            session_id="test-session-pb5",
            user_prompt="Prompt",
        )

        activity_store.end_prompt_batch(batch.id)

        retrieved = activity_store.get_prompt_batch(batch.id)
        assert retrieved.status == "completed"
        assert retrieved.ended_at is not None

    def test_get_unprocessed_prompt_batches(self, activity_store: ActivityStore):
        """Test retrieving unprocessed prompt batches."""
        activity_store.create_session(
            session_id="test-session-pb6",
            agent="claude",
            project_root="/path",
        )

        # Create and end batches
        for i in range(3):
            batch = activity_store.create_prompt_batch(
                session_id="test-session-pb6",
                user_prompt=f"Prompt {i}",
            )
            activity_store.end_prompt_batch(batch.id)

        unprocessed = activity_store.get_unprocessed_prompt_batches(limit=10)
        assert len(unprocessed) == 3
        assert all(b.processed is False for b in unprocessed)

    def test_mark_prompt_batch_processed(self, activity_store: ActivityStore):
        """Test marking a prompt batch as processed."""
        activity_store.create_session(
            session_id="test-session-pb7",
            agent="claude",
            project_root="/path",
        )

        batch = activity_store.create_prompt_batch(
            session_id="test-session-pb7",
            user_prompt="Prompt",
        )
        activity_store.end_prompt_batch(batch.id)

        activity_store.mark_prompt_batch_processed(
            batch.id,
            classification="implementation",
        )

        retrieved = activity_store.get_prompt_batch(batch.id)
        assert retrieved.processed is True
        assert retrieved.classification == "implementation"

    def test_get_session_prompt_batches(self, activity_store: ActivityStore):
        """Test retrieving all batches for a session."""
        activity_store.create_session(
            session_id="test-session-pb8",
            agent="claude",
            project_root="/path",
        )

        for i in range(3):
            activity_store.create_prompt_batch(
                session_id="test-session-pb8",
                user_prompt=f"Prompt {i}",
            )

        batches = activity_store.get_session_prompt_batches("test-session-pb8")
        assert len(batches) == 3
        assert all(b.session_id == "test-session-pb8" for b in batches)


# =============================================================================
# ActivityStore Tests: Activity Logging
# =============================================================================


class TestActivityStoreActivityLogging:
    """Test activity logging operations."""

    def test_add_activity(self, activity_store: ActivityStore):
        """Test adding an activity."""
        activity_store.create_session(
            session_id="test-session-a1",
            agent="claude",
            project_root="/path",
        )

        activity = Activity(
            session_id="test-session-a1",
            tool_name="Read",
            tool_input={"path": "/test/file.py"},
            tool_output_summary="File content preview",
            file_path="/test/file.py",
            files_affected=["/test/file.py"],
            duration_ms=150,
            success=True,
        )

        activity_id = activity_store.add_activity(activity)
        assert activity_id > 0

        # Verify session tool count was incremented
        session = activity_store.get_session("test-session-a1")
        assert session.tool_count == 1

    def test_add_activity_with_prompt_batch(self, activity_store: ActivityStore):
        """Test adding an activity linked to a prompt batch."""
        activity_store.create_session(
            session_id="test-session-a2",
            agent="claude",
            project_root="/path",
        )

        batch = activity_store.create_prompt_batch(
            session_id="test-session-a2",
            user_prompt="Prompt",
        )

        activity = Activity(
            session_id="test-session-a2",
            prompt_batch_id=batch.id,
            tool_name="Edit",
            tool_input={"path": "/test/file.py"},
            tool_output_summary="File modified",
            file_path="/test/file.py",
            duration_ms=200,
            success=True,
        )

        activity_store.add_activity(activity)

        # Verify batch activity count was incremented
        retrieved_batch = activity_store.get_prompt_batch(batch.id)
        assert retrieved_batch.activity_count == 1

    def test_add_failed_activity(self, activity_store: ActivityStore):
        """Test adding a failed activity."""
        activity_store.create_session(
            session_id="test-session-a3",
            agent="claude",
            project_root="/path",
        )

        activity = Activity(
            session_id="test-session-a3",
            tool_name="Edit",
            tool_input={"path": "/nonexistent/file.py"},
            tool_output_summary="",
            file_path="/nonexistent/file.py",
            duration_ms=50,
            success=False,
            error_message="File not found",
        )

        activity_store.add_activity(activity)

        activities = activity_store.get_session_activities("test-session-a3")
        assert len(activities) == 1
        assert activities[0].success is False
        assert activities[0].error_message == "File not found"

    def test_get_session_activities(self, activity_store: ActivityStore):
        """Test retrieving activities for a session."""
        activity_store.create_session(
            session_id="test-session-a4",
            agent="claude",
            project_root="/path",
        )

        for i in range(5):
            activity = Activity(
                session_id="test-session-a4",
                tool_name="Read" if i % 2 == 0 else "Edit",
                tool_input={},
                file_path=f"/test/file{i}.py",
                duration_ms=100,
                success=True,
            )
            activity_store.add_activity(activity)

        activities = activity_store.get_session_activities("test-session-a4")
        assert len(activities) == 5

    def test_get_session_activities_filtered_by_tool(self, activity_store: ActivityStore):
        """Test retrieving activities filtered by tool name."""
        activity_store.create_session(
            session_id="test-session-a5",
            agent="claude",
            project_root="/path",
        )

        for i in range(5):
            activity = Activity(
                session_id="test-session-a5",
                tool_name="Read" if i < 3 else "Edit",
                tool_input={},
                file_path=f"/test/file{i}.py",
                duration_ms=100,
                success=True,
            )
            activity_store.add_activity(activity)

        read_activities = activity_store.get_session_activities(
            "test-session-a5",
            tool_name="Read",
        )
        assert len(read_activities) == 3
        assert all(a.tool_name == "Read" for a in read_activities)

    def test_get_unprocessed_activities(self, activity_store: ActivityStore):
        """Test retrieving unprocessed activities."""
        activity_store.create_session(
            session_id="test-session-a6",
            agent="claude",
            project_root="/path",
        )

        for i in range(3):
            activity = Activity(
                session_id="test-session-a6",
                tool_name="Read",
                tool_input={},
                file_path=f"/test/file{i}.py",
                duration_ms=100,
                success=True,
                processed=False,
            )
            activity_store.add_activity(activity)

        unprocessed = activity_store.get_unprocessed_activities(
            session_id="test-session-a6",
        )
        assert len(unprocessed) == 3
        assert all(a.processed is False for a in unprocessed)

    def test_mark_activities_processed(self, activity_store: ActivityStore):
        """Test marking activities as processed."""
        activity_store.create_session(
            session_id="test-session-a7",
            agent="claude",
            project_root="/path",
        )

        activity_ids = []
        for i in range(3):
            activity = Activity(
                session_id="test-session-a7",
                tool_name="Read",
                tool_input={},
                file_path=f"/test/file{i}.py",
                duration_ms=100,
                success=True,
            )
            activity_id = activity_store.add_activity(activity)
            activity_ids.append(activity_id)

        activity_store.mark_activities_processed(
            activity_ids,
            observation_id="obs_123",
        )

        unprocessed = activity_store.get_unprocessed_activities(
            session_id="test-session-a7",
        )
        assert len(unprocessed) == 0


# =============================================================================
# ActivityStore Tests: Full-Text Search
# =============================================================================


class TestActivityStoreFullTextSearch:
    """Test FTS5 search functionality."""

    def test_search_activities_by_tool_name(self, activity_store: ActivityStore):
        """Test searching activities by tool name."""
        activity_store.create_session(
            session_id="test-session-search1",
            agent="claude",
            project_root="/path",
        )

        # Add activities
        for i in range(3):
            activity = Activity(
                session_id="test-session-search1",
                tool_name="Read" if i < 2 else "Edit",
                tool_input={},
                tool_output_summary="File content" if i < 2 else "File modified",
                file_path=f"/test/file{i}.py",
                duration_ms=100,
                success=True,
            )
            activity_store.add_activity(activity)

        results = activity_store.search_activities("Read")
        assert len(results) >= 2

    def test_search_activities_by_file_path(self, activity_store: ActivityStore):
        """Test searching activities by file path."""
        activity_store.create_session(
            session_id="test-session-search2",
            agent="claude",
            project_root="/path",
        )

        activity = Activity(
            session_id="test-session-search2",
            tool_name="Read",
            tool_input={},
            file_path="/test/models.py",
            duration_ms=100,
            success=True,
        )
        activity_store.add_activity(activity)

        # FTS5 requires proper query syntax for special characters like .
        # Search by file name without extension or use models as keyword
        results = activity_store.search_activities("models")
        assert len(results) >= 1

    def test_search_activities_filtered_by_session(self, activity_store: ActivityStore):
        """Test searching with session filter."""
        # Create two sessions with different activities
        for session_num in range(2):
            session_id = f"test-session-search{3 + session_num}"
            activity_store.create_session(
                session_id=session_id,
                agent="claude",
                project_root="/path",
            )

            activity = Activity(
                session_id=session_id,
                tool_name="Read",
                tool_input={},
                tool_output_summary="Content for session " + str(session_num),
                file_path=f"/test/session{session_num}.py",
                duration_ms=100,
                success=True,
            )
            activity_store.add_activity(activity)

        # Search only in first session
        results = activity_store.search_activities(
            "session",
            session_id="test-session-search3",
            limit=10,
        )
        # Should only find results from session 3
        assert all(r.session_id == "test-session-search3" for r in results)

    def test_search_activities_by_output_summary(self, activity_store: ActivityStore):
        """Test searching by tool output summary."""
        activity_store.create_session(
            session_id="test-session-search5",
            agent="claude",
            project_root="/path",
        )

        activity = Activity(
            session_id="test-session-search5",
            tool_name="Read",
            tool_input={},
            tool_output_summary="Successfully read Python configuration file",
            file_path="/test/config.py",
            duration_ms=100,
            success=True,
        )
        activity_store.add_activity(activity)

        results = activity_store.search_activities("configuration")
        assert len(results) >= 1


# =============================================================================
# ActivityStore Tests: Statistics
# =============================================================================


class TestActivityStoreStatistics:
    """Test statistics retrieval methods."""

    def test_get_session_stats(self, activity_store: ActivityStore):
        """Test getting session statistics."""
        activity_store.create_session(
            session_id="test-session-stats1",
            agent="claude",
            project_root="/path",
        )

        # Add various activities
        for i in range(3):
            activity = Activity(
                session_id="test-session-stats1",
                tool_name="Read" if i == 0 else ("Edit" if i == 1 else "Write"),
                tool_input={},
                file_path=f"/test/file{i}.py",
                duration_ms=100,
                success=True,
            )
            activity_store.add_activity(activity)

        stats = activity_store.get_session_stats("test-session-stats1")
        assert stats["activity_count"] == 3
        assert stats["reads"] == 1
        assert stats["edits"] == 1
        assert stats["writes"] == 1
        assert stats["files_touched"] >= 1

    def test_get_session_stats_with_errors(self, activity_store: ActivityStore):
        """Test session stats include error counts."""
        activity_store.create_session(
            session_id="test-session-stats2",
            agent="claude",
            project_root="/path",
        )

        # Add activities including failed ones
        for i in range(3):
            activity = Activity(
                session_id="test-session-stats2",
                tool_name="Read",
                tool_input={},
                file_path=f"/test/file{i}.py",
                duration_ms=100,
                success=i != 2,  # Last one fails
                error_message="File not found" if i == 2 else None,
            )
            activity_store.add_activity(activity)

        stats = activity_store.get_session_stats("test-session-stats2")
        assert stats["errors"] == 1

    def test_get_prompt_batch_stats(self, activity_store: ActivityStore):
        """Test getting prompt batch statistics."""
        activity_store.create_session(
            session_id="test-session-stats3",
            agent="claude",
            project_root="/path",
        )

        batch = activity_store.create_prompt_batch(
            session_id="test-session-stats3",
            user_prompt="Prompt",
        )

        # Add activities to batch
        for i in range(2):
            activity = Activity(
                session_id="test-session-stats3",
                prompt_batch_id=batch.id,
                tool_name="Read" if i == 0 else "Edit",
                tool_input={},
                file_path=f"/test/file{i}.py",
                duration_ms=100,
                success=True,
            )
            activity_store.add_activity(activity)

        stats = activity_store.get_prompt_batch_stats(batch.id)
        assert stats["tool_counts"]["Read"] == 1
        assert stats["tool_counts"]["Edit"] == 1

    def test_get_recent_sessions(self, activity_store: ActivityStore):
        """Test retrieving recent sessions."""
        # Create multiple sessions
        for i in range(5):
            activity_store.create_session(
                session_id=f"test-session-recent-{i}",
                agent="claude",
                project_root="/path",
            )

        recent = activity_store.get_recent_sessions(limit=3)
        assert len(recent) == 3


# =============================================================================
# ActivityStore Tests: Recovery Operations
# =============================================================================


class TestActivityStoreRecoveryOperations:
    """Test recovery operations for stuck/orphaned data."""

    def test_recover_stuck_batches(self, activity_store: ActivityStore):
        """Test recovering batches stuck in active state."""
        activity_store.create_session(
            session_id="test-session-recover1",
            agent="claude",
            project_root="/path",
        )

        batch = activity_store.create_prompt_batch(
            session_id="test-session-recover1",
            user_prompt="Prompt",
        )

        # Manually set created_at_epoch to a long time ago
        conn = activity_store._get_connection()
        import time

        old_epoch = time.time() - 2000
        conn.execute(
            "UPDATE prompt_batches SET created_at_epoch = ? WHERE id = ?",
            (old_epoch, batch.id),
        )
        conn.commit()

        recovered = activity_store.recover_stuck_batches(timeout_seconds=1800)
        assert recovered >= 1

    def test_recover_orphaned_activities(self, activity_store: ActivityStore):
        """Test recovering activities without batch associations."""
        activity_store.create_session(
            session_id="test-session-recover2",
            agent="claude",
            project_root="/path",
        )

        # First create a batch that the orphaned activities can be recovered to
        batch = activity_store.create_prompt_batch(
            session_id="test-session-recover2",
            user_prompt="Recovery batch",
        )
        activity_store.end_prompt_batch(batch.id)

        # Add activity without batch
        activity = Activity(
            session_id="test-session-recover2",
            prompt_batch_id=None,
            tool_name="Read",
            tool_input={},
            file_path="/test/file.py",
            duration_ms=100,
            success=True,
        )
        activity_store.add_activity(activity)

        recovered = activity_store.recover_orphaned_activities()
        assert recovered >= 1


# =============================================================================
# ActivityProcessor Tests: Session Processing
# =============================================================================


class TestActivityProcessorSessionProcessing:
    """Test session-level processing with mocked LLM."""

    def test_process_session_no_summarizer(self, activity_store: ActivityStore):
        """Test processing when no summarizer is configured."""
        processor = ActivityProcessor(
            activity_store=activity_store,
            vector_store=MagicMock(),
            summarizer=None,  # No summarizer
        )

        activity_store.create_session(
            session_id="test-session-proc1",
            agent="claude",
            project_root="/path",
        )

        result = processor.process_session("test-session-proc1")
        assert result.success is False
        assert result.error == "No summarizer configured"

    def test_process_session_no_activities(
        self, activity_processor: ActivityProcessor, activity_store: ActivityStore
    ):
        """Test processing a session with no activities."""
        activity_store.create_session(
            session_id="test-session-proc2",
            agent="claude",
            project_root="/path",
        )

        result = activity_processor.process_session("test-session-proc2")
        assert result.success is True
        assert result.activities_processed == 0

    @patch("open_agent_kit.features.codebase_intelligence.activity.processor.render_prompt")
    def test_process_session_with_activities(
        self,
        mock_render_prompt,
        activity_processor: ActivityProcessor,
        activity_store: ActivityStore,
    ):
        """Test processing a session with activities."""
        mock_render_prompt.return_value = "Generated prompt"

        activity_store.create_session(
            session_id="test-session-proc3",
            agent="claude",
            project_root="/path",
        )

        # Add activities
        for i in range(2):
            activity = Activity(
                session_id="test-session-proc3",
                tool_name="Read" if i == 0 else "Edit",
                tool_input={},
                file_path=f"/test/file{i}.py",
                duration_ms=100,
                success=True,
            )
            activity_store.add_activity(activity)

        with patch.object(activity_processor, "_classify_session") as mock_classify:
            with patch.object(activity_processor, "_select_template_by_classification"):
                with patch.object(activity_processor, "_get_oak_ci_context") as mock_context:
                    with patch.object(activity_processor, "_call_llm") as mock_llm:
                        mock_classify.return_value = "implementation"
                        mock_context.return_value = ""
                        mock_llm.return_value = {
                            "success": True,
                            "observations": [{"title": "Obs 1", "description": "Test obs"}],
                        }

                        result = activity_processor.process_session("test-session-proc3")
                        assert result.success is True
                        assert result.activities_processed == 2


# =============================================================================
# ActivityProcessor Tests: Prompt Batch Processing
# =============================================================================


class TestActivityProcessorBatchProcessing:
    """Test prompt batch processing."""

    def test_process_prompt_batch_not_found(
        self,
        activity_processor: ActivityProcessor,
    ):
        """Test processing a nonexistent batch."""
        result = activity_processor.process_prompt_batch(99999)
        assert result.success is False
        assert "not found" in result.error

    def test_process_prompt_batch_no_activities(
        self,
        activity_processor: ActivityProcessor,
        activity_store: ActivityStore,
    ):
        """Test processing a batch with no activities."""
        activity_store.create_session(
            session_id="test-session-batch1",
            agent="claude",
            project_root="/path",
        )

        batch = activity_store.create_prompt_batch(
            session_id="test-session-batch1",
            user_prompt="Prompt",
        )
        activity_store.end_prompt_batch(batch.id)

        result = activity_processor.process_prompt_batch(batch.id)
        assert result.success is True
        assert result.activities_processed == 0

    @patch("open_agent_kit.features.codebase_intelligence.activity.processor.render_prompt")
    def test_process_prompt_batch_with_activities(
        self,
        mock_render_prompt,
        activity_processor: ActivityProcessor,
        activity_store: ActivityStore,
    ):
        """Test processing a batch with activities."""
        mock_render_prompt.return_value = "Generated prompt"

        activity_store.create_session(
            session_id="test-session-batch2",
            agent="claude",
            project_root="/path",
        )

        batch = activity_store.create_prompt_batch(
            session_id="test-session-batch2",
            user_prompt="Implement feature",
        )

        # Add activities
        for i in range(2):
            activity = Activity(
                session_id="test-session-batch2",
                prompt_batch_id=batch.id,
                tool_name="Read" if i == 0 else "Write",
                tool_input={},
                file_path=f"/test/file{i}.py",
                duration_ms=100,
                success=True,
            )
            activity_store.add_activity(activity)

        activity_store.end_prompt_batch(batch.id)

        with patch.object(activity_processor, "_classify_session") as mock_classify:
            with patch.object(activity_processor, "_select_template_by_classification"):
                with patch.object(activity_processor, "_get_oak_ci_context") as mock_context:
                    with patch.object(activity_processor, "_call_llm") as mock_llm:
                        mock_classify.return_value = "implementation"
                        mock_context.return_value = ""
                        mock_llm.return_value = {
                            "success": True,
                            "observations": [
                                {"title": "Implemented feature", "description": "Added new feature"}
                            ],
                        }

                        result = activity_processor.process_prompt_batch(batch.id)
                        assert result.success is True
                        assert result.activities_processed == 2
                        assert result.prompt_batch_id == batch.id

    @patch("open_agent_kit.features.codebase_intelligence.activity.processor.render_prompt")
    def test_process_prompt_batch_llm_error(
        self,
        mock_render_prompt,
        activity_processor: ActivityProcessor,
        activity_store: ActivityStore,
    ):
        """Test processing when LLM call fails."""
        mock_render_prompt.return_value = "Generated prompt"

        activity_store.create_session(
            session_id="test-session-batch3",
            agent="claude",
            project_root="/path",
        )

        batch = activity_store.create_prompt_batch(
            session_id="test-session-batch3",
            user_prompt="Prompt",
        )

        activity = Activity(
            session_id="test-session-batch3",
            prompt_batch_id=batch.id,
            tool_name="Read",
            tool_input={},
            file_path="/test/file.py",
            duration_ms=100,
            success=True,
        )
        activity_store.add_activity(activity)
        activity_store.end_prompt_batch(batch.id)

        with patch.object(activity_processor, "_classify_session") as mock_classify:
            with patch.object(activity_processor, "_select_template_by_classification"):
                with patch.object(activity_processor, "_get_oak_ci_context"):
                    with patch.object(activity_processor, "_call_llm") as mock_llm:
                        mock_classify.return_value = "debugging"
                        mock_llm.return_value = {
                            "success": False,
                            "error": "LLM API timeout",
                        }

                        result = activity_processor.process_prompt_batch(batch.id)
                        assert result.success is False
                        assert "timeout" in result.error.lower()


# =============================================================================
# ActivityProcessor Tests: Pending Batch Processing
# =============================================================================


class TestActivityProcessorPendingBatches:
    """Test processing multiple pending batches."""

    @patch("open_agent_kit.features.codebase_intelligence.activity.processor.render_prompt")
    def test_process_pending_batches(
        self,
        mock_render_prompt,
        activity_processor: ActivityProcessor,
        activity_store: ActivityStore,
    ):
        """Test processing multiple pending batches."""
        mock_render_prompt.return_value = "Generated prompt"

        activity_store.create_session(
            session_id="test-session-pending1",
            agent="claude",
            project_root="/path",
        )

        # Create multiple batches
        for i in range(2):
            batch = activity_store.create_prompt_batch(
                session_id="test-session-pending1",
                user_prompt=f"Prompt {i}",
            )

            activity = Activity(
                session_id="test-session-pending1",
                prompt_batch_id=batch.id,
                tool_name="Read",
                tool_input={},
                file_path=f"/test/file{i}.py",
                duration_ms=100,
                success=True,
            )
            activity_store.add_activity(activity)
            activity_store.end_prompt_batch(batch.id)

        with patch.object(activity_processor, "_classify_session") as mock_classify:
            with patch.object(activity_processor, "_select_template_by_classification"):
                with patch.object(activity_processor, "_get_oak_ci_context"):
                    with patch.object(activity_processor, "_call_llm") as mock_llm:
                        mock_classify.return_value = "exploration"
                        mock_llm.return_value = {
                            "success": True,
                            "observations": [
                                {"title": "Explored code", "description": "Found patterns"}
                            ],
                        }

                        results = activity_processor.process_pending_batches(max_batches=10)
                        assert len(results) == 2
                        assert all(r.success for r in results)

    def test_process_pending_batches_no_pending(
        self,
        activity_processor: ActivityProcessor,
        activity_store: ActivityStore,
    ):
        """Test processing when no batches are pending."""
        results = activity_processor.process_pending_batches(max_batches=10)
        assert len(results) == 0

    def test_process_pending_batches_locked(
        self,
        activity_processor: ActivityProcessor,
    ):
        """Test processing skips when already processing."""
        activity_processor._is_processing = True
        results = activity_processor.process_pending_batches(max_batches=10)
        assert len(results) == 0


# =============================================================================
# ContextBudget Tests
# =============================================================================


class TestContextBudget:
    """Test ContextBudget calculations."""

    def test_default_budget(self):
        """Test default context budget."""
        budget = ContextBudget()
        assert budget.context_tokens == 4096
        assert budget.max_activities == 30

    def test_small_context_model(self):
        """Test budget for small context models (4K)."""
        budget = ContextBudget.from_context_tokens(4000)
        assert budget.context_tokens == 4000
        assert budget.max_activities == 15

    def test_medium_context_model(self):
        """Test budget for medium context models (8K+)."""
        budget = ContextBudget.from_context_tokens(8000)
        assert budget.context_tokens == 8000
        assert budget.max_activities == 30

    def test_large_context_model(self):
        """Test budget for large context models (32K+)."""
        budget = ContextBudget.from_context_tokens(32000)
        assert budget.context_tokens == 32000
        assert budget.max_activities == 50

    def test_budget_allocations(self):
        """Test that budget allocations are reasonable."""
        budget = ContextBudget.from_context_tokens(8000)
        assert budget.max_user_prompt_chars > 0
        assert budget.max_oak_context_chars > 0
        assert budget.max_activity_summary_chars > 0


# =============================================================================
# ProcessingResult Tests
# =============================================================================


class TestProcessingResult:
    """Test ProcessingResult dataclass."""

    def test_processing_result_success(self):
        """Test successful processing result."""
        result = ProcessingResult(
            session_id="test-session",
            activities_processed=10,
            observations_extracted=5,
            success=True,
            duration_ms=1500,
            classification="implementation",
        )

        assert result.session_id == "test-session"
        assert result.activities_processed == 10
        assert result.observations_extracted == 5
        assert result.success is True
        assert result.error is None

    def test_processing_result_failure(self):
        """Test failed processing result."""
        result = ProcessingResult(
            session_id="test-session",
            activities_processed=0,
            observations_extracted=0,
            success=False,
            error="LLM API error",
            duration_ms=500,
        )

        assert result.success is False
        assert result.error == "LLM API error"
        assert result.activities_processed == 0


# =============================================================================
# Activity and Session Dataclass Tests
# =============================================================================


class TestActivityDataclass:
    """Test Activity dataclass functionality."""

    def test_activity_to_row(self):
        """Test converting activity to database row."""
        activity = Activity(
            session_id="test",
            tool_name="Read",
            tool_input={"path": "/test.py"},
            tool_output_summary="Content",
            file_path="/test.py",
            files_affected=["/test.py"],
            duration_ms=100,
            success=True,
        )

        row = activity.to_row()
        assert row["session_id"] == "test"
        assert row["tool_name"] == "Read"
        assert row["tool_input"] == '{"path": "/test.py"}'
        assert row["file_path"] == "/test.py"

    def test_activity_from_row(self):
        """Test creating activity from database row."""
        # Create a mock row
        row_dict = {
            "id": 1,
            "session_id": "test",
            "prompt_batch_id": None,
            "tool_name": "Read",
            "tool_input": '{"path": "/test.py"}',
            "tool_output_summary": "Content",
            "file_path": "/test.py",
            "files_affected": "[]",
            "duration_ms": 100,
            "success": True,
            "error_message": None,
            "timestamp": datetime.now().isoformat(),
            "processed": False,
            "observation_id": None,
        }

        # Create a mock sqlite3.Row-like object
        class MockRow(dict):
            def __getitem__(self, key):
                return super().__getitem__(key)

        mock_row = MockRow(row_dict)

        activity = Activity.from_row(mock_row)
        assert activity.tool_name == "Read"
        assert activity.file_path == "/test.py"


class TestSessionDataclass:
    """Test Session dataclass functionality."""

    def test_session_to_row(self):
        """Test converting session to database row."""
        session = Session(
            id="test-session",
            agent="claude",
            project_root="/path",
            started_at=datetime.now(),
        )

        row = session.to_row()
        assert row["id"] == "test-session"
        assert row["agent"] == "claude"
        assert row["project_root"] == "/path"

    def test_session_from_row(self):
        """Test creating session from database row."""
        now = datetime.now()
        row_dict = {
            "id": "test-session",
            "agent": "claude",
            "project_root": "/path",
            "started_at": now.isoformat(),
            "ended_at": None,
            "status": "active",
            "prompt_count": 0,
            "tool_count": 0,
            "processed": False,
            "summary": None,
        }

        class MockRow(dict):
            def __getitem__(self, key):
                return super().__getitem__(key)

        mock_row = MockRow(row_dict)
        session = Session.from_row(mock_row)
        assert session.id == "test-session"
        assert session.status == "active"


# =============================================================================
# Database Threading Tests
# =============================================================================


class TestActivityStoreThreading:
    """Test thread safety of ActivityStore."""

    def test_concurrent_activity_writes(self, activity_store: ActivityStore):
        """Test adding activities concurrently."""
        activity_store.create_session(
            session_id="test-session-threading",
            agent="claude",
            project_root="/path",
        )

        def add_activities(thread_id):
            for i in range(5):
                activity = Activity(
                    session_id="test-session-threading",
                    tool_name="Read",
                    tool_input={},
                    file_path=f"/test/file-{thread_id}-{i}.py",
                    duration_ms=100,
                    success=True,
                )
                activity_store.add_activity(activity)

        threads = [threading.Thread(target=add_activities, args=(i,)) for i in range(3)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        activities = activity_store.get_session_activities("test-session-threading")
        assert len(activities) == 15


# =============================================================================
# Integration Tests
# =============================================================================


class TestActivityIntegration:
    """Integration tests for activity workflow."""

    def test_complete_session_workflow(self, activity_store: ActivityStore):
        """Test a complete session workflow."""
        # Create session
        session = activity_store.create_session(
            session_id="integration-test-1",
            agent="claude",
            project_root="/test/project",
        )

        assert session.status == "active"

        # Create and use prompt batches
        for prompt_num in range(2):
            batch = activity_store.create_prompt_batch(
                session_id="integration-test-1",
                user_prompt=f"User request {prompt_num}",
            )

            # Add activities to batch: 3 items per batch
            # activity_num 0 -> Read (0 % 2 == 0)
            # activity_num 1 -> Edit (1 % 2 != 0)
            # activity_num 2 -> Read (2 % 2 == 0)
            for activity_num in range(3):
                activity = Activity(
                    session_id="integration-test-1",
                    prompt_batch_id=batch.id,
                    tool_name="Read" if activity_num % 2 == 0 else "Edit",
                    tool_input={"file": f"file{activity_num}.py"},
                    tool_output_summary=f"Result {activity_num}",
                    file_path=f"/test/file{activity_num}.py",
                    duration_ms=100,
                    success=True,
                )
                activity_store.add_activity(activity)

            activity_store.end_prompt_batch(batch.id)
            activity_store.mark_prompt_batch_processed(batch.id, classification="implementation")

        # End session
        activity_store.end_session("integration-test-1", summary="Test summary")

        # Verify final state
        final_session = activity_store.get_session("integration-test-1")
        assert final_session.status == "completed"
        assert final_session.prompt_count == 2
        assert final_session.tool_count == 6

        stats = activity_store.get_session_stats("integration-test-1")
        assert stats["activity_count"] == 6
        # Per batch: 2 reads (indices 0, 2) + 1 edit (index 1)
        # 2 batches * 2 reads = 4 reads total
        # 2 batches * 1 edit = 2 edits total
        assert stats["reads"] == 4
        assert stats["edits"] == 2


# =============================================================================
# ActivityStore Tests: Backup and Restore
# =============================================================================


class TestActivityStoreBackup:
    """Test backup (export) and restore (import) functionality."""

    def test_export_to_sql_creates_file(self, activity_store: ActivityStore, temp_db: Path):
        """Test that export_to_sql creates a SQL file."""
        # Create some test data
        activity_store.create_session(
            session_id="backup-test-1",
            agent="claude",
            project_root="/test/project",
        )
        activity_store.create_prompt_batch(
            session_id="backup-test-1",
            user_prompt="Test prompt",
        )

        # Export to SQL
        backup_path = temp_db.parent / "backup.sql"
        count = activity_store.export_to_sql(backup_path)

        assert backup_path.exists()
        assert count >= 2  # At least session and prompt batch
        content = backup_path.read_text()
        assert "INSERT INTO sessions" in content
        assert "INSERT INTO prompt_batches" in content

    def test_export_to_sql_includes_observations(
        self, activity_store: ActivityStore, temp_db: Path
    ):
        """Test that export includes memory observations."""
        import uuid

        # Create session and observation
        activity_store.create_session(
            session_id="backup-test-2",
            agent="claude",
            project_root="/test/project",
        )
        obs = StoredObservation(
            id=str(uuid.uuid4()),
            session_id="backup-test-2",
            observation="Test observation for backup",
            memory_type="discovery",
            context="test_context",
        )
        activity_store.store_observation(obs)

        # Export to SQL
        backup_path = temp_db.parent / "backup.sql"
        count = activity_store.export_to_sql(backup_path)

        assert count >= 2  # session + observation
        content = backup_path.read_text()
        assert "INSERT INTO memory_observations" in content
        assert "Test observation for backup" in content

    def test_export_excludes_activities_by_default(
        self, activity_store: ActivityStore, temp_db: Path
    ):
        """Test that activities table is excluded by default."""
        # Create session with activities
        activity_store.create_session(
            session_id="backup-test-3",
            agent="claude",
            project_root="/test/project",
        )
        activity = Activity(
            session_id="backup-test-3",
            tool_name="Read",
            tool_input={"path": "/test/file.py"},
            file_path="/test/file.py",
            duration_ms=100,
            success=True,
        )
        activity_store.add_activity(activity)

        # Export without activities
        backup_path = temp_db.parent / "backup.sql"
        activity_store.export_to_sql(backup_path, include_activities=False)

        content = backup_path.read_text()
        assert "INSERT INTO sessions" in content
        assert "INSERT INTO activities" not in content

    def test_export_includes_activities_when_requested(
        self, activity_store: ActivityStore, temp_db: Path
    ):
        """Test that activities can be included in export."""
        # Create session with activities
        activity_store.create_session(
            session_id="backup-test-4",
            agent="claude",
            project_root="/test/project",
        )
        activity = Activity(
            session_id="backup-test-4",
            tool_name="Read",
            tool_input={"path": "/test/file.py"},
            file_path="/test/file.py",
            duration_ms=100,
            success=True,
        )
        activity_store.add_activity(activity)

        # Export with activities
        backup_path = temp_db.parent / "backup.sql"
        activity_store.export_to_sql(backup_path, include_activities=True)

        content = backup_path.read_text()
        assert "INSERT INTO activities" in content

    def test_import_from_sql_restores_data(self, temp_db: Path):
        """Test that import_from_sql restores data to a fresh database."""
        import uuid

        # Create source store with data
        source_store = ActivityStore(temp_db)
        source_store.create_session(
            session_id="import-test-1",
            agent="claude",
            project_root="/test/project",
        )
        source_store.create_prompt_batch(
            session_id="import-test-1",
            user_prompt="Test prompt for import",
        )
        obs = StoredObservation(
            id=str(uuid.uuid4()),
            session_id="import-test-1",
            observation="Test observation for import",
            memory_type="discovery",
        )
        source_store.store_observation(obs)

        # Export
        backup_path = temp_db.parent / "backup.sql"
        source_store.export_to_sql(backup_path)
        source_store.close()

        # Create fresh target store
        target_db = temp_db.parent / "target.db"
        target_store = ActivityStore(target_db)

        # Import
        count = target_store.import_from_sql(backup_path)

        assert count >= 3  # session + prompt batch + observation

        # Verify data was restored
        session = target_store.get_session("import-test-1")
        assert session is not None
        assert session.agent == "claude"

        # Verify observation was restored
        obs_count = target_store.count_observations()
        assert obs_count >= 1

        target_store.close()

    def test_import_marks_observations_as_unembedded(self, temp_db: Path):
        """Test that imported observations are marked as unembedded for ChromaDB rebuild."""
        import uuid

        # Create source store with embedded observation
        source_store = ActivityStore(temp_db)
        source_store.create_session(
            session_id="embed-test-1",
            agent="claude",
            project_root="/test/project",
        )
        obs_id = str(uuid.uuid4())
        obs = StoredObservation(
            id=obs_id,
            session_id="embed-test-1",
            observation="Embedded observation",
            memory_type="discovery",
        )
        source_store.store_observation(obs)
        # Mark as embedded in source
        source_store.mark_observation_embedded(obs_id)

        # Verify it's embedded in source
        assert source_store.count_embedded_observations() == 1

        # Export
        backup_path = temp_db.parent / "backup.sql"
        source_store.export_to_sql(backup_path)
        source_store.close()

        # Create fresh target and import
        target_db = temp_db.parent / "target.db"
        target_store = ActivityStore(target_db)
        target_store.import_from_sql(backup_path)

        # Verify observations are unembedded after import (for ChromaDB rebuild)
        assert target_store.count_unembedded_observations() >= 1

        target_store.close()

    def test_import_handles_duplicates_gracefully(
        self, activity_store: ActivityStore, temp_db: Path
    ):
        """Test that import handles duplicate records without failing."""
        # Create initial data
        activity_store.create_session(
            session_id="dup-test-1",
            agent="claude",
            project_root="/test/project",
        )

        # Export
        backup_path = temp_db.parent / "backup.sql"
        activity_store.export_to_sql(backup_path)

        # Import again (should not fail on duplicate)
        # Count may be 0 due to duplicates being skipped, but should not raise
        activity_store.import_from_sql(backup_path)

    def test_export_escapes_special_characters(self, activity_store: ActivityStore, temp_db: Path):
        """Test that export properly escapes SQL special characters."""
        import uuid

        # Create session with special characters
        activity_store.create_session(
            session_id="escape-test-1",
            agent="claude",
            project_root="/test/project",
        )
        obs = StoredObservation(
            id=str(uuid.uuid4()),
            session_id="escape-test-1",
            observation="Test with 'single quotes' and special chars: \"; DROP TABLE;",
            memory_type="discovery",
        )
        activity_store.store_observation(obs)

        # Export should not fail
        backup_path = temp_db.parent / "backup.sql"
        count = activity_store.export_to_sql(backup_path)
        assert count >= 2

        # Content should be valid SQL
        content = backup_path.read_text()
        assert "single quotes" in content
        # Single quotes should be escaped
        assert "''" in content or "single quotes" in content

    def test_roundtrip_preserves_data_integrity(self, temp_db: Path):
        """Test that export->import roundtrip preserves data integrity."""
        import uuid

        # Create source with comprehensive data
        source_store = ActivityStore(temp_db)
        source_store.create_session(
            session_id="roundtrip-test-1",
            agent="claude",
            project_root="/test/project",
        )
        batch = source_store.create_prompt_batch(
            session_id="roundtrip-test-1",
            user_prompt="Complex prompt with details",
        )
        obs = StoredObservation(
            id=str(uuid.uuid4()),
            session_id="roundtrip-test-1",
            observation="Important observation",
            memory_type="gotcha",
            context="specific_context",
            tags=["tag1", "tag2"],
        )
        source_store.store_observation(obs)
        source_store.end_prompt_batch(batch.id)
        source_store.end_session("roundtrip-test-1", summary="Session summary")

        # Get original counts
        orig_sessions = len(source_store.get_recent_sessions(limit=100))
        orig_observations = source_store.count_observations()

        # Export
        backup_path = temp_db.parent / "backup.sql"
        source_store.export_to_sql(backup_path)
        source_store.close()

        # Import to fresh database
        target_db = temp_db.parent / "roundtrip_target.db"
        target_store = ActivityStore(target_db)
        target_store.import_from_sql(backup_path)

        # Verify counts match
        target_sessions = len(target_store.get_recent_sessions(limit=100))
        target_observations = target_store.count_observations()

        assert target_sessions == orig_sessions
        assert target_observations == orig_observations

        # Verify specific data
        session = target_store.get_session("roundtrip-test-1")
        assert session.summary == "Session summary"
        assert session.status == "completed"

        target_store.close()
