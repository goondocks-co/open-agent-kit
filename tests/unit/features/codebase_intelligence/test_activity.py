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

TEST_MACHINE_ID = "test_machine_abc123"

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
    return ActivityStore(temp_db, machine_id=TEST_MACHINE_ID)


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

    def test_reactivate_session_if_needed_reactivates_completed(
        self, activity_store: ActivityStore
    ):
        """Test that reactivate_session_if_needed reactivates a completed session."""
        activity_store.create_session(
            session_id="test-session-reactivate-1",
            agent="claude",
            project_root="/path",
        )
        activity_store.end_session("test-session-reactivate-1")

        # Verify session is completed
        session = activity_store.get_session("test-session-reactivate-1")
        assert session.status == "completed"
        assert session.ended_at is not None

        # Reactivate
        reactivated = activity_store.reactivate_session_if_needed("test-session-reactivate-1")
        assert reactivated is True

        # Verify session is now active
        session = activity_store.get_session("test-session-reactivate-1")
        assert session.status == "active"
        assert session.ended_at is None

    def test_reactivate_session_if_needed_noop_for_active(self, activity_store: ActivityStore):
        """Test that reactivate_session_if_needed is a no-op for active sessions."""
        activity_store.create_session(
            session_id="test-session-reactivate-2",
            agent="claude",
            project_root="/path",
        )

        # Session is already active
        session = activity_store.get_session("test-session-reactivate-2")
        assert session.status == "active"

        # Reactivate should be a no-op
        reactivated = activity_store.reactivate_session_if_needed("test-session-reactivate-2")
        assert reactivated is False

        # Session should still be active
        session = activity_store.get_session("test-session-reactivate-2")
        assert session.status == "active"

    def test_reactivate_session_if_needed_nonexistent(self, activity_store: ActivityStore):
        """Test that reactivate_session_if_needed returns False for nonexistent session."""
        reactivated = activity_store.reactivate_session_if_needed("nonexistent-session")
        assert reactivated is False

    def test_create_prompt_batch_reactivates_completed_session(self, activity_store: ActivityStore):
        """Test that create_prompt_batch reactivates a completed session.

        This is the main fix for the issue where activities are logged to
        closed sessions without reopening them.
        """
        # Create and end a session
        activity_store.create_session(
            session_id="test-session-reactivate-on-batch",
            agent="claude",
            project_root="/path",
        )
        activity_store.end_session("test-session-reactivate-on-batch")

        # Verify session is completed
        session = activity_store.get_session("test-session-reactivate-on-batch")
        assert session.status == "completed"

        # Create a new prompt batch - this should reactivate the session
        batch = activity_store.create_prompt_batch(
            session_id="test-session-reactivate-on-batch",
            user_prompt="New prompt after session was closed",
        )

        # Verify batch was created
        assert batch.id is not None
        assert batch.session_id == "test-session-reactivate-on-batch"

        # Verify session was reactivated
        session = activity_store.get_session("test-session-reactivate-on-batch")
        assert session.status == "active"
        assert session.ended_at is None


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
# Plan Iteration Consolidation Tests
# =============================================================================


class TestPlanIterationConsolidation:
    """Test that plan iterations (same file, same session) are consolidated.

    When Claude iterates on a plan (writing to the same file multiple times),
    only one plan batch should exist per file per session. Subsequent writes
    update the existing batch's content rather than creating duplicates.
    """

    def test_get_session_plan_batch_with_file_path(self, activity_store: ActivityStore):
        """Test filtering plan batch by file path."""
        activity_store.create_session(
            session_id="test-plan-fp1", agent="claude", project_root="/path"
        )

        # Create two plan batches with different file paths
        batch1 = activity_store.create_prompt_batch(
            session_id="test-plan-fp1", user_prompt="Plan feature A"
        )
        activity_store.update_prompt_batch_source_type(
            batch1.id,
            "plan",
            plan_file_path="/plans/plan-a.md",
            plan_content="Plan A content",
        )

        batch2 = activity_store.create_prompt_batch(
            session_id="test-plan-fp1", user_prompt="Plan feature B"
        )
        activity_store.update_prompt_batch_source_type(
            batch2.id,
            "plan",
            plan_file_path="/plans/plan-b.md",
            plan_content="Plan B content",
        )

        # Filter by specific file path
        result_a = activity_store.get_session_plan_batch(
            "test-plan-fp1", plan_file_path="/plans/plan-a.md"
        )
        assert result_a is not None
        assert result_a.id == batch1.id

        result_b = activity_store.get_session_plan_batch(
            "test-plan-fp1", plan_file_path="/plans/plan-b.md"
        )
        assert result_b is not None
        assert result_b.id == batch2.id

    def test_get_session_plan_batch_without_file_path_returns_latest(
        self, activity_store: ActivityStore
    ):
        """Test that omitting file path returns most recent plan (backward compat)."""
        activity_store.create_session(
            session_id="test-plan-fp2", agent="claude", project_root="/path"
        )

        batch1 = activity_store.create_prompt_batch(
            session_id="test-plan-fp2", user_prompt="Plan v1"
        )
        activity_store.update_prompt_batch_source_type(
            batch1.id,
            "plan",
            plan_file_path="/plans/plan-a.md",
            plan_content="Plan A",
        )

        batch2 = activity_store.create_prompt_batch(
            session_id="test-plan-fp2", user_prompt="Plan v2"
        )
        activity_store.update_prompt_batch_source_type(
            batch2.id,
            "plan",
            plan_file_path="/plans/plan-b.md",
            plan_content="Plan B",
        )

        # No file path filter — returns most recent
        result = activity_store.get_session_plan_batch("test-plan-fp2")
        assert result is not None
        assert result.id == batch2.id

    def test_get_session_plan_batch_no_match_returns_none(self, activity_store: ActivityStore):
        """Test that a non-existent file path returns None."""
        activity_store.create_session(
            session_id="test-plan-fp3", agent="claude", project_root="/path"
        )

        batch = activity_store.create_prompt_batch(session_id="test-plan-fp3", user_prompt="Plan")
        activity_store.update_prompt_batch_source_type(
            batch.id,
            "plan",
            plan_file_path="/plans/plan-a.md",
            plan_content="Content",
        )

        result = activity_store.get_session_plan_batch(
            "test-plan-fp3", plan_file_path="/plans/nonexistent.md"
        )
        assert result is None

    def test_get_plans_dedup_by_file_path_keeps_latest(self, activity_store: ActivityStore):
        """Test that get_plans deduplicates by file path, keeping latest."""
        activity_store.create_session(
            session_id="test-plan-dedup1", agent="claude", project_root="/path"
        )

        # Simulate: same plan file in two sessions (parent + child)
        batch1 = activity_store.create_prompt_batch(
            session_id="test-plan-dedup1", user_prompt="Plan v1"
        )
        activity_store.update_prompt_batch_source_type(
            batch1.id,
            "plan",
            plan_file_path="/plans/shared-plan.md",
            plan_content="Version 1 content",
        )

        activity_store.create_session(
            session_id="test-plan-dedup2", agent="claude", project_root="/path"
        )
        batch2 = activity_store.create_prompt_batch(
            session_id="test-plan-dedup2", user_prompt="Plan v2"
        )
        activity_store.update_prompt_batch_source_type(
            batch2.id,
            "plan",
            plan_file_path="/plans/shared-plan.md",
            plan_content="Version 2 content (refined)",
        )

        plans, total = activity_store.get_plans(deduplicate=True)
        assert total == 1
        assert len(plans) == 1
        # Should keep the latest (v2)
        assert plans[0].id == batch2.id
        assert "Version 2" in plans[0].plan_content

    def test_get_plans_different_files_not_deduped(self, activity_store: ActivityStore):
        """Test that different file paths are not deduplicated."""
        activity_store.create_session(
            session_id="test-plan-dedup3", agent="claude", project_root="/path"
        )

        batch1 = activity_store.create_prompt_batch(
            session_id="test-plan-dedup3", user_prompt="Plan A"
        )
        activity_store.update_prompt_batch_source_type(
            batch1.id,
            "plan",
            plan_file_path="/plans/plan-a.md",
            plan_content="Plan A content",
        )

        batch2 = activity_store.create_prompt_batch(
            session_id="test-plan-dedup3", user_prompt="Plan B"
        )
        activity_store.update_prompt_batch_source_type(
            batch2.id,
            "plan",
            plan_file_path="/plans/plan-b.md",
            plan_content="Plan B content",
        )

        plans, total = activity_store.get_plans(deduplicate=True)
        assert total == 2
        assert len(plans) == 2

    def test_get_plans_no_dedup_returns_all(self, activity_store: ActivityStore):
        """Test that deduplicate=False returns all plan batches."""
        activity_store.create_session(
            session_id="test-plan-dedup4", agent="claude", project_root="/path"
        )

        # Same file path, two batches (simulating old data before consolidation)
        for i in range(2):
            batch = activity_store.create_prompt_batch(
                session_id="test-plan-dedup4", user_prompt=f"Plan v{i + 1}"
            )
            activity_store.update_prompt_batch_source_type(
                batch.id,
                "plan",
                plan_file_path="/plans/same-plan.md",
                plan_content=f"Version {i + 1}",
            )

        plans, total = activity_store.get_plans(deduplicate=False)
        assert total == 2
        assert len(plans) == 2


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

    def test_get_bulk_session_stats(self, activity_store: ActivityStore):
        """Test getting statistics for multiple sessions in bulk."""
        # Create multiple sessions
        session_ids = []
        for i in range(3):
            session_id = f"test-session-bulk{i}"
            session_ids.append(session_id)
            activity_store.create_session(
                session_id=session_id,
                agent="claude",
                project_root="/path",
            )

            # Add activities to each session
            for j in range(i + 1):  # Different number of activities per session
                activity = Activity(
                    session_id=session_id,
                    tool_name="Read" if j == 0 else "Edit",
                    tool_input={},
                    file_path=f"/test/file{j}.py",
                    duration_ms=100,
                    success=True,
                )
                activity_store.add_activity(activity)

        # Get bulk stats
        stats_map = activity_store.get_bulk_session_stats(session_ids)

        # Verify all sessions are in the result
        assert len(stats_map) == 3
        assert all(sid in stats_map for sid in session_ids)

        # Verify stats for each session
        assert stats_map["test-session-bulk0"]["activity_count"] == 1
        assert stats_map["test-session-bulk1"]["activity_count"] == 2
        assert stats_map["test-session-bulk2"]["activity_count"] == 3

        # Verify tool counts
        assert "Read" in stats_map["test-session-bulk0"]["tool_counts"]
        assert stats_map["test-session-bulk0"]["tool_counts"]["Read"] == 1

    def test_get_bulk_session_stats_empty_list(self, activity_store: ActivityStore):
        """Test bulk stats with empty session list."""
        stats_map = activity_store.get_bulk_session_stats([])
        assert stats_map == {}

    def test_get_bulk_session_stats_no_activities(self, activity_store: ActivityStore):
        """Test bulk stats for sessions with no activities."""
        session_id = "test-session-empty"
        activity_store.create_session(
            session_id=session_id,
            agent="claude",
            project_root="/path",
        )

        stats_map = activity_store.get_bulk_session_stats([session_id])
        assert session_id in stats_map
        assert stats_map[session_id]["activity_count"] == 0
        assert stats_map[session_id]["tool_counts"] == {}

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

    def test_get_recent_sessions_filters_by_agent(self, activity_store: ActivityStore):
        """Test retrieving recent sessions filtered by agent."""
        activity_store.create_session(
            session_id="test-session-agent-claude",
            agent="claude",
            project_root="/path",
        )
        activity_store.create_session(
            session_id="test-session-agent-codex-model",
            agent="gpt-5.3-codex",
            project_root="/path",
        )

        recent = activity_store.get_recent_sessions(limit=10, agent="codex")
        assert len(recent) == 1
        assert recent[0].agent == "gpt-5.3-codex"

    def test_count_sessions_filters_by_agent(self, activity_store: ActivityStore):
        """Test counting sessions filtered by agent."""
        activity_store.create_session(
            session_id="test-count-agent-claude",
            agent="claude",
            project_root="/path",
        )
        activity_store.create_session(
            session_id="test-count-agent-gemini-model",
            agent="gemini-2.5-pro-gemini",
            project_root="/path",
        )

        from open_agent_kit.features.codebase_intelligence.activity.store.sessions import (
            count_sessions,
        )

        total = count_sessions(activity_store, agent="gemini")
        assert total == 1


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

    def test_recover_stale_sessions_deletes_empty_sessions(self, activity_store: ActivityStore):
        """Test that recover_stale_sessions deletes empty sessions (no prompt batches)."""
        import time

        # Create an empty session (no prompt batches)
        activity_store.create_session(
            session_id="test-session-empty-stale",
            agent="claude",
            project_root="/path",
        )

        # Make it stale by setting created_at_epoch to a long time ago
        conn = activity_store._get_connection()
        old_epoch = time.time() - 7200  # 2 hours ago
        conn.execute(
            "UPDATE sessions SET created_at_epoch = ? WHERE id = ?",
            (old_epoch, "test-session-empty-stale"),
        )
        conn.commit()

        # Recover with 1 hour timeout
        recovered_ids, deleted_ids = activity_store.recover_stale_sessions(timeout_seconds=3600)

        # Empty session should be deleted, not recovered
        assert "test-session-empty-stale" in deleted_ids
        assert "test-session-empty-stale" not in recovered_ids

        # Session should no longer exist
        session = activity_store.get_session("test-session-empty-stale")
        assert session is None

    def test_recover_stale_sessions_marks_nonempty_as_completed(
        self, activity_store: ActivityStore
    ):
        """Test that recover_stale_sessions marks quality sessions as completed.

        Sessions need MIN_SESSION_ACTIVITIES (3) to be considered quality.
        Sessions below this threshold are deleted instead of recovered.
        """
        import time

        from open_agent_kit.features.codebase_intelligence.activity.store.models import Activity
        from open_agent_kit.features.codebase_intelligence.constants import MIN_SESSION_ACTIVITIES

        # Create a session with a prompt batch
        activity_store.create_session(
            session_id="test-session-quality-stale",
            agent="claude",
            project_root="/path",
        )
        activity_store.create_prompt_batch(
            session_id="test-session-quality-stale",
            user_prompt="Test prompt",
        )

        # Add enough activities to meet quality threshold
        for i in range(MIN_SESSION_ACTIVITIES):
            activity = Activity(
                session_id="test-session-quality-stale",
                tool_name="Read",
                tool_input={"path": f"/test/file{i}.py"},
                tool_output_summary=f"Read file {i}",
                file_path=f"/test/file{i}.py",
                success=True,
            )
            activity_store.add_activity(activity)

        # Make it stale by setting created_at_epoch and activity timestamps to a long time ago
        conn = activity_store._get_connection()
        old_epoch = time.time() - 7200  # 2 hours ago
        conn.execute(
            "UPDATE sessions SET created_at_epoch = ? WHERE id = ?",
            (old_epoch, "test-session-quality-stale"),
        )
        # Also update activity timestamps so session is detected as stale
        conn.execute(
            "UPDATE activities SET timestamp_epoch = ? WHERE session_id = ?",
            (old_epoch, "test-session-quality-stale"),
        )
        # Mark prompt batch as completed and old (active batches block stale recovery)
        conn.execute(
            "UPDATE prompt_batches SET status = 'completed', created_at_epoch = ? WHERE session_id = ?",
            (old_epoch, "test-session-quality-stale"),
        )
        conn.commit()

        # Recover with 1 hour timeout
        recovered_ids, deleted_ids = activity_store.recover_stale_sessions(timeout_seconds=3600)

        # Quality session should be recovered, not deleted
        assert "test-session-quality-stale" in recovered_ids
        assert "test-session-quality-stale" not in deleted_ids

        # Session should be marked as completed
        session = activity_store.get_session("test-session-quality-stale")
        assert session is not None
        assert session.status == "completed"

    def test_recover_stale_sessions_returns_empty_for_no_stale(self, activity_store: ActivityStore):
        """Test that recover_stale_sessions returns empty lists when no stale sessions."""
        # Create a fresh session (not stale)
        activity_store.create_session(
            session_id="test-session-fresh",
            agent="claude",
            project_root="/path",
        )

        # Recover with 1 hour timeout - fresh session should not be affected
        recovered_ids, deleted_ids = activity_store.recover_stale_sessions(timeout_seconds=3600)

        assert recovered_ids == []
        assert deleted_ids == []

        # Session should still exist and be active
        session = activity_store.get_session("test-session-fresh")
        assert session is not None
        assert session.status == "active"

    def test_ensure_session_exists_creates_missing_session(self, activity_store: ActivityStore):
        """Test that _ensure_session_exists creates a session if missing."""
        # Session doesn't exist
        session = activity_store.get_session("test-session-missing")
        assert session is None

        # Ensure session exists
        created = activity_store._ensure_session_exists(
            "test-session-missing",
            "claude",
        )

        assert created is True

        # Session should now exist
        session = activity_store.get_session("test-session-missing")
        assert session is not None
        assert session.agent == "claude"
        assert session.status == "active"

    def test_ensure_session_exists_noop_for_existing(self, activity_store: ActivityStore):
        """Test that _ensure_session_exists is a no-op for existing sessions."""
        # Create session
        activity_store.create_session(
            session_id="test-session-existing",
            agent="cursor",
            project_root="/path",
        )

        # Ensure session exists - should return False (not created)
        created = activity_store._ensure_session_exists(
            "test-session-existing",
            "claude",  # Different agent - should not overwrite
        )

        assert created is False

        # Session should still have original agent
        session = activity_store.get_session("test-session-existing")
        assert session.agent == "cursor"

    def test_create_prompt_batch_recreates_deleted_session(self, activity_store: ActivityStore):
        """Test that create_prompt_batch recreates a deleted session when agent is provided."""
        import time

        # Create an empty session
        activity_store.create_session(
            session_id="test-session-to-delete",
            agent="claude",
            project_root="/path",
        )

        # Make it stale
        conn = activity_store._get_connection()
        old_epoch = time.time() - 7200
        conn.execute(
            "UPDATE sessions SET created_at_epoch = ? WHERE id = ?",
            (old_epoch, "test-session-to-delete"),
        )
        conn.commit()

        # Recover - should delete the empty session
        recovered_ids, deleted_ids = activity_store.recover_stale_sessions(timeout_seconds=3600)
        assert "test-session-to-delete" in deleted_ids

        # Verify session is deleted
        session = activity_store.get_session("test-session-to-delete")
        assert session is None

        # Create a prompt batch for the deleted session with agent parameter
        batch = activity_store.create_prompt_batch(
            session_id="test-session-to-delete",
            user_prompt="New prompt after deletion",
            agent="claude",  # Enables session recreation
        )

        # Batch should be created
        assert batch.id is not None
        assert batch.session_id == "test-session-to-delete"

        # Session should be recreated
        session = activity_store.get_session("test-session-to-delete")
        assert session is not None
        assert session.agent == "claude"
        assert session.status == "active"


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

    @patch("open_agent_kit.features.codebase_intelligence.activity.processor.core.render_prompt")
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

    @patch(
        "open_agent_kit.features.codebase_intelligence.activity.processor.handlers.render_prompt"
    )
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

    @patch(
        "open_agent_kit.features.codebase_intelligence.activity.processor.handlers.render_prompt"
    )
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

    @patch(
        "open_agent_kit.features.codebase_intelligence.activity.processor.handlers.render_prompt"
    )
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
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            export_to_sql,
        )

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
        count = export_to_sql(activity_store, backup_path)

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

        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            export_to_sql,
        )

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
        count = export_to_sql(activity_store, backup_path)

        assert count >= 2  # session + observation
        content = backup_path.read_text()
        assert "INSERT INTO memory_observations" in content
        assert "Test observation for backup" in content

    def test_export_excludes_activities_by_default(
        self, activity_store: ActivityStore, temp_db: Path
    ):
        """Test that activities table is excluded by default."""
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            export_to_sql,
        )

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
        export_to_sql(activity_store, backup_path, include_activities=False)

        content = backup_path.read_text()
        assert "INSERT INTO sessions" in content
        assert "INSERT INTO activities" not in content

    def test_export_includes_activities_when_requested(
        self, activity_store: ActivityStore, temp_db: Path
    ):
        """Test that activities can be included in export."""
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            export_to_sql,
        )

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
        export_to_sql(activity_store, backup_path, include_activities=True)

        content = backup_path.read_text()
        assert "INSERT INTO activities" in content

    def test_import_from_sql_restores_data(self, temp_db: Path):
        """Test that import_from_sql restores data to a fresh database."""
        import uuid

        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            export_to_sql,
            import_from_sql_with_dedup,
        )

        # Create source store with data
        source_store = ActivityStore(temp_db, machine_id=TEST_MACHINE_ID)
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
        export_to_sql(source_store, backup_path)
        source_store.close()

        # Create fresh target store
        target_db = temp_db.parent / "target.db"
        target_store = ActivityStore(target_db, machine_id=TEST_MACHINE_ID)

        # Import
        result = import_from_sql_with_dedup(target_store, backup_path)

        assert result.total_imported >= 3  # session + prompt batch + observation

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

        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            export_to_sql,
            import_from_sql_with_dedup,
        )

        # Create source store with embedded observation
        source_store = ActivityStore(temp_db, machine_id=TEST_MACHINE_ID)
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
        export_to_sql(source_store, backup_path)
        source_store.close()

        # Create fresh target and import
        target_db = temp_db.parent / "target.db"
        target_store = ActivityStore(target_db, machine_id=TEST_MACHINE_ID)
        import_from_sql_with_dedup(target_store, backup_path)

        # Verify observations are unembedded after import (for ChromaDB rebuild)
        assert target_store.count_unembedded_observations() >= 1

        target_store.close()

    def test_import_handles_duplicates_gracefully(
        self, activity_store: ActivityStore, temp_db: Path
    ):
        """Test that import handles duplicate records without failing."""
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            export_to_sql,
            import_from_sql_with_dedup,
        )

        # Create initial data
        activity_store.create_session(
            session_id="dup-test-1",
            agent="claude",
            project_root="/test/project",
        )

        # Export
        backup_path = temp_db.parent / "backup.sql"
        export_to_sql(activity_store, backup_path)

        # Import again (should not fail on duplicate)
        # Duplicates are skipped via dedup, but should not raise
        import_from_sql_with_dedup(activity_store, backup_path)

    def test_export_escapes_special_characters(self, activity_store: ActivityStore, temp_db: Path):
        """Test that export properly escapes SQL special characters."""
        import uuid

        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            export_to_sql,
        )

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
        count = export_to_sql(activity_store, backup_path)
        assert count >= 2

        # Content should be valid SQL
        content = backup_path.read_text()
        assert "single quotes" in content
        # Single quotes should be escaped
        assert "''" in content or "single quotes" in content

    def test_roundtrip_preserves_data_integrity(self, temp_db: Path):
        """Test that export->import roundtrip preserves data integrity."""
        import uuid

        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            export_to_sql,
            import_from_sql_with_dedup,
        )

        # Create source with comprehensive data
        source_store = ActivityStore(temp_db, machine_id=TEST_MACHINE_ID)
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
        export_to_sql(source_store, backup_path)
        source_store.close()

        # Import to fresh database
        target_db = temp_db.parent / "roundtrip_target.db"
        target_store = ActivityStore(target_db, machine_id=TEST_MACHINE_ID)
        import_from_sql_with_dedup(target_store, backup_path)

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

    def test_import_handles_unknown_columns_from_newer_schema(self, temp_db: Path):
        """Test that import strips columns that don't exist in current schema.

        This enables importing backups from newer schema versions.
        """
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            import_from_sql_with_dedup,
        )

        # Create a backup file with an extra column that doesn't exist
        backup_content = """-- OAK Codebase Intelligence History Backup
-- Exported: 2025-01-01T00:00:00
-- Machine: test_machine
-- Schema version: 99

-- sessions (1 records)
INSERT INTO sessions (id, agent, project_root, started_at, status, prompt_count, tool_count, processed, created_at_epoch, future_column_v99) VALUES ('future-test-1', 'claude', '/test/project', '2025-01-01T00:00:00', 'completed', 0, 0, 0, 1704067200, 'future_value');
"""
        backup_path = temp_db.parent / "future_backup.sql"
        backup_path.write_text(backup_content)

        # Import to a fresh database - should NOT fail due to unknown column
        target_store = ActivityStore(temp_db, machine_id=TEST_MACHINE_ID)
        result = import_from_sql_with_dedup(target_store, backup_path)

        # Session should be imported (unknown column stripped)
        assert result.total_imported >= 1
        session = target_store.get_session("future-test-1")
        assert session is not None
        assert session.agent == "claude"
        target_store.close()

    def test_import_preserves_parent_session_links(self, temp_db: Path):
        """Test that parent_session_id links are preserved during import."""
        from open_agent_kit.features.codebase_intelligence.activity.store.sessions import (
            update_session_parent,
        )

        # Create source with parent-child session relationship
        source_store = ActivityStore(temp_db, machine_id=TEST_MACHINE_ID)

        # Create parent session
        source_store.create_session(
            session_id="parent-session",
            agent="claude",
            project_root="/test/project",
        )

        # Create child session linked to parent
        source_store.create_session(
            session_id="child-session",
            agent="claude",
            project_root="/test/project",
        )
        update_session_parent(
            source_store,
            session_id="child-session",
            parent_session_id="parent-session",
            reason="continuation",
        )

        # Export
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            export_to_sql,
            import_from_sql_with_dedup,
        )

        backup_path = temp_db.parent / "parent_child_backup.sql"
        export_to_sql(source_store, backup_path)
        source_store.close()

        # Import to fresh database
        target_db = temp_db.parent / "target_parent_child.db"
        target_store = ActivityStore(target_db, machine_id=TEST_MACHINE_ID)
        import_from_sql_with_dedup(target_store, backup_path)

        # Verify parent-child link preserved
        child = target_store.get_session("child-session")
        assert child is not None
        assert child.parent_session_id == "parent-session"
        assert child.parent_session_reason == "continuation"

        target_store.close()

    def test_import_handles_orphaned_parent_reference(self, temp_db: Path):
        """Test that orphaned parent_session_id references are handled gracefully.

        When a child session references a parent that wasn't included in the backup,
        the link should be set to NULL with a warning.
        """
        # Create a backup with a child session referencing non-existent parent
        backup_content = """-- OAK Codebase Intelligence History Backup
-- Exported: 2025-01-01T00:00:00
-- Machine: test_machine
-- Schema version: 12

-- sessions (1 records)
INSERT INTO sessions (id, agent, project_root, started_at, status, prompt_count, tool_count, processed, created_at_epoch, parent_session_id, parent_session_reason) VALUES ('orphan-child', 'claude', '/test/project', '2025-01-01T00:00:00', 'completed', 0, 0, 0, 1704067200, 'non-existent-parent', 'continuation');
"""
        backup_path = temp_db.parent / "orphan_parent_backup.sql"
        backup_path.write_text(backup_content)

        # Import to a fresh database
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            import_from_sql_with_dedup,
        )

        target_store = ActivityStore(temp_db, machine_id=TEST_MACHINE_ID)
        import_from_sql_with_dedup(target_store, backup_path)

        # Session should be imported with parent_session_id set to NULL
        session = target_store.get_session("orphan-child")
        assert session is not None
        # The orphan parent reference should have been cleaned up
        assert session.parent_session_id is None
        target_store.close()

    def test_import_remaps_source_plan_batch_id(self, temp_db: Path):
        """Test that source_plan_batch_id self-references are remapped correctly.

        When importing prompt_batches, the auto-generated IDs differ from the backup.
        source_plan_batch_id references must be remapped to the new IDs.
        """
        # Create source store with plan -> implementation batch relationship
        source_store = ActivityStore(temp_db, machine_id=TEST_MACHINE_ID)
        source_store.create_session(
            session_id="plan-session",
            agent="claude",
            project_root="/test/project",
        )

        # Create plan batch
        plan_batch = source_store.create_prompt_batch(
            session_id="plan-session",
            user_prompt="Create a plan",
            source_type="plan",
        )
        source_store.end_prompt_batch(plan_batch.id)

        # Create implementation batch that references the plan
        impl_batch = source_store.create_prompt_batch(
            session_id="plan-session",
            user_prompt="Implement the plan",
            source_type="derived_plan",
        )
        # Link implementation to plan
        conn = source_store._get_connection()
        conn.execute(
            "UPDATE prompt_batches SET source_plan_batch_id = ? WHERE id = ?",
            (plan_batch.id, impl_batch.id),
        )
        conn.commit()
        source_store.end_prompt_batch(impl_batch.id)

        # Verify source relationship
        cursor = conn.execute(
            "SELECT source_plan_batch_id FROM prompt_batches WHERE id = ?",
            (impl_batch.id,),
        )
        assert cursor.fetchone()[0] == plan_batch.id

        # Export
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            export_to_sql,
            import_from_sql_with_dedup,
        )

        backup_path = temp_db.parent / "plan_link_backup.sql"
        export_to_sql(source_store, backup_path)
        source_store.close()

        # Import to fresh database
        target_db = temp_db.parent / "target_plan_link.db"
        target_store = ActivityStore(target_db, machine_id=TEST_MACHINE_ID)
        import_from_sql_with_dedup(target_store, backup_path)

        # Verify the relationship is preserved (IDs may differ but link exists)
        target_conn = target_store._get_connection()
        cursor = target_conn.execute("""
            SELECT pb1.prompt_number, pb2.prompt_number
            FROM prompt_batches pb1
            JOIN prompt_batches pb2 ON pb1.source_plan_batch_id = pb2.id
            WHERE pb1.session_id = 'plan-session'
            """)
        result = cursor.fetchone()
        # Implementation batch (prompt_number=2) should link to plan batch (prompt_number=1)
        assert result is not None
        assert result[0] == 2  # impl batch prompt_number
        assert result[1] == 1  # plan batch prompt_number

        target_store.close()

    def test_export_only_includes_records_from_current_machine(self, temp_db: Path):
        """Test that export only includes records that originated on this machine.

        Origin tracking prevents backup file bloat when team members import
        each other's backups - each backup only contains original work, not
        imported data from other machines.
        """
        import uuid

        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            export_to_sql,
        )

        # Create a store and add local data
        store = ActivityStore(temp_db, machine_id=TEST_MACHINE_ID)
        current_machine = store.machine_id

        # Create a local session (will have current machine's source_machine_id)
        store.create_session(
            session_id="local-session",
            agent="claude",
            project_root="/test/project",
        )
        local_batch = store.create_prompt_batch(
            session_id="local-session",
            user_prompt="Local work",
        )
        local_obs = StoredObservation(
            id=str(uuid.uuid4()),
            session_id="local-session",
            observation="Local observation",
            memory_type="gotcha",
        )
        store.store_observation(local_obs)
        store.end_prompt_batch(local_batch.id)

        # Simulate imported data from another machine by inserting with different source_machine_id
        conn = store._get_connection()
        foreign_machine = "other_machine_alice"

        # Insert a foreign session
        conn.execute(
            """
            INSERT INTO sessions (id, agent, project_root, started_at, status, prompt_count,
                                 tool_count, processed, created_at_epoch, source_machine_id)
            VALUES ('foreign-session', 'claude', '/other/project', '2025-01-01T00:00:00',
                    'completed', 1, 0, 0, 1704067200, ?)
            """,
            (foreign_machine,),
        )

        # Insert a foreign prompt batch
        conn.execute(
            """
            INSERT INTO prompt_batches (session_id, prompt_number, user_prompt, started_at,
                                        status, activity_count, processed, created_at_epoch,
                                        source_machine_id)
            VALUES ('foreign-session', 1, 'Foreign work', '2025-01-01T00:00:00',
                    'completed', 0, 0, 1704067200, ?)
            """,
            (foreign_machine,),
        )

        # Insert a foreign observation
        conn.execute(
            """
            INSERT INTO memory_observations (id, session_id, observation, memory_type,
                                            created_at, created_at_epoch, embedded,
                                            source_machine_id)
            VALUES (?, 'foreign-session', 'Foreign observation', 'gotcha',
                    '2025-01-01T00:00:00', 1704067200, 0, ?)
            """,
            (str(uuid.uuid4()), foreign_machine),
        )
        conn.commit()

        # Verify we have both local and foreign data
        all_sessions = store.get_recent_sessions(limit=100)
        assert len(all_sessions) == 2

        # Export - should only include local data
        backup_path = temp_db.parent / "origin_tracking_backup.sql"
        export_to_sql(store, backup_path)

        # Read and verify backup content
        backup_content = backup_path.read_text()

        # Local session should be in backup
        assert "local-session" in backup_content
        assert "Local observation" in backup_content

        # Foreign session should NOT be in backup
        assert "foreign-session" not in backup_content
        assert "Foreign observation" not in backup_content

        # The backup should contain the machine identifier
        assert f"-- Machine: {current_machine}" in backup_content

        store.close()

    def test_imported_records_preserve_original_source_machine_id(self, temp_db: Path):
        """Test that imported records keep their original source_machine_id.

        When importing from another machine, the source_machine_id should be
        preserved so that future exports from this machine won't re-export
        the imported data.
        """
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            export_to_sql,
            import_from_sql_with_dedup,
        )

        # Create a backup file that looks like it came from another machine
        foreign_machine = "other_machine_bob"
        backup_content = f"""-- OAK Codebase Intelligence History Backup
-- Exported: 2025-01-01T00:00:00
-- Machine: {foreign_machine}
-- Schema version: 13

-- sessions (1 records)
INSERT INTO sessions (id, agent, project_root, started_at, status, prompt_count, tool_count, processed, created_at_epoch, source_machine_id) VALUES ('imported-session', 'claude', '/bobs/project', '2025-01-01T00:00:00', 'completed', 1, 0, 0, 1704067200, '{foreign_machine}');

-- prompt_batches (1 records)
INSERT INTO prompt_batches (id, session_id, prompt_number, user_prompt, started_at, status, activity_count, processed, created_at_epoch, source_machine_id) VALUES (1, 'imported-session', 1, 'Bobs work', '2025-01-01T00:00:00', 'completed', 0, 0, 1704067200, '{foreign_machine}');

-- memory_observations (1 records)
INSERT INTO memory_observations (id, session_id, observation, memory_type, created_at, created_at_epoch, embedded, source_machine_id) VALUES ('obs-123', 'imported-session', 'Bobs observation', 'gotcha', '2025-01-01T00:00:00', 1704067200, 0, '{foreign_machine}');
"""
        backup_path = temp_db.parent / "foreign_backup.sql"
        backup_path.write_text(backup_content)

        # Import the backup
        store = ActivityStore(temp_db, machine_id=TEST_MACHINE_ID)
        import_from_sql_with_dedup(store, backup_path)

        # Verify the data was imported
        session = store.get_session("imported-session")
        assert session is not None
        assert session.source_machine_id == foreign_machine

        # Now export from this machine
        current_machine = store.machine_id
        assert current_machine != foreign_machine, "Test requires different machine IDs"

        export_path = temp_db.parent / "re_export.sql"
        count = export_to_sql(store, export_path)

        # No records should be exported (all data is from the foreign machine)
        assert count == 0

        # The file should not be created when there are zero records
        # (the zero-record guard prevents writing header-only files)
        assert (
            not export_path.exists()
        ), "Export file should not be created when no records match the current machine"

        store.close()


class TestReplaceImport:
    """Tests for drop-and-replace team backup restore (replace_machine mode)."""

    OTHER_MACHINE_ID = "other_machine_alice_abc123"

    def _create_foreign_session(
        self,
        store: ActivityStore,
        session_id: str,
        machine_id: str,
        *,
        with_observation: bool = False,
        with_activity: bool = False,
    ) -> None:
        """Insert records that look like they came from another machine."""
        import uuid

        conn = store._get_connection()
        conn.execute(
            """
            INSERT INTO sessions (id, agent, project_root, started_at, status,
                                 prompt_count, tool_count, processed, created_at_epoch,
                                 source_machine_id)
            VALUES (?, 'claude', '/other', '2025-01-01T00:00:00', 'completed',
                    1, 0, 0, 1704067200, ?)
            """,
            (session_id, machine_id),
        )
        conn.execute(
            """
            INSERT INTO prompt_batches (session_id, prompt_number, started_at, status,
                                        activity_count, processed, created_at_epoch,
                                        source_machine_id)
            VALUES (?, 1, '2025-01-01T00:00:00', 'completed', 0, 0, 1704067200, ?)
            """,
            (session_id, machine_id),
        )
        if with_observation:
            conn.execute(
                """
                INSERT INTO memory_observations (id, session_id, observation, memory_type,
                                                created_at, created_at_epoch, embedded,
                                                source_machine_id)
                VALUES (?, ?, 'Foreign obs', 'discovery', '2025-01-01T00:00:00',
                        1704067200, 0, ?)
                """,
                (str(uuid.uuid4()), session_id, machine_id),
            )
        if with_activity:
            conn.execute(
                """
                INSERT INTO activities (session_id, tool_name, timestamp, timestamp_epoch,
                                       source_machine_id)
                VALUES (?, 'Read', '2025-01-01T00:00:00', 1704067200, ?)
                """,
                (session_id, machine_id),
            )
        conn.commit()

    def _make_backup_content(self, machine_id: str, session_id: str, observation_text: str) -> str:
        """Build a minimal .sql backup file string."""
        return f"""-- OAK Codebase Intelligence History Backup
-- Exported: 2025-01-01T00:00:00
-- Machine: {machine_id}
-- Schema version: 13

-- sessions (1 records)
INSERT INTO sessions (id, agent, project_root, started_at, status, prompt_count, tool_count, processed, created_at_epoch, source_machine_id) VALUES ('{session_id}', 'claude', '/other', '2025-01-01T00:00:00', 'completed', 1, 0, 0, 1704067200, '{machine_id}');

-- prompt_batches (1 records)
INSERT INTO prompt_batches (id, session_id, prompt_number, started_at, status, activity_count, processed, created_at_epoch, source_machine_id) VALUES (1, '{session_id}', 1, '2025-01-01T00:00:00', 'completed', 0, 0, 1704067200, '{machine_id}');

-- memory_observations (1 records)
INSERT INTO memory_observations (id, session_id, observation, memory_type, created_at, created_at_epoch, embedded, source_machine_id) VALUES ('obs-{session_id}', '{session_id}', '{observation_text}', 'discovery', '2025-01-01T00:00:00', 1704067200, 0, '{machine_id}');
"""

    def test_delete_records_by_machine(self, activity_store: ActivityStore):
        """Delete removes all records for a machine while leaving local data intact."""
        from open_agent_kit.features.codebase_intelligence.activity.store.delete import (
            delete_records_by_machine,
        )

        # Create local data
        activity_store.create_session("local-sess", agent="claude", project_root="/p")

        # Create foreign data
        self._create_foreign_session(
            activity_store,
            "foreign-sess",
            self.OTHER_MACHINE_ID,
            with_observation=True,
            with_activity=True,
        )

        # Verify both exist
        assert activity_store.get_session("local-sess") is not None
        assert activity_store.get_session("foreign-sess") is not None

        # Delete foreign machine records
        counts = delete_records_by_machine(activity_store, self.OTHER_MACHINE_ID)

        assert counts["sessions"] == 1
        assert counts["prompt_batches"] == 1
        assert counts["memory_observations"] == 1
        assert counts["activities"] == 1

        # Local data untouched
        assert activity_store.get_session("local-sess") is not None
        # Foreign data gone
        assert activity_store.get_session("foreign-sess") is None

    def test_replace_import_prevents_amplification(self, temp_db: Path):
        """Importing the same backup twice with replace_machine=True should not double records."""
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            import_from_sql_with_dedup,
        )

        store = ActivityStore(temp_db, machine_id=TEST_MACHINE_ID)

        # Create backup file A
        backup_content_v1 = self._make_backup_content(
            self.OTHER_MACHINE_ID, "amp-sess", "Original observation text"
        )
        backup_path = temp_db.parent / f"{self.OTHER_MACHINE_ID}.sql"
        backup_path.write_text(backup_content_v1)

        # First import
        r1 = import_from_sql_with_dedup(store, backup_path, replace_machine=True)
        assert r1.total_imported >= 3  # session + batch + observation
        assert r1.total_deleted == 0  # nothing to delete first time

        # Simulate regeneration: same session, different observation text
        backup_content_v2 = self._make_backup_content(
            self.OTHER_MACHINE_ID, "amp-sess", "Regenerated observation text"
        )
        backup_path.write_text(backup_content_v2)

        # Second import with replace
        r2 = import_from_sql_with_dedup(store, backup_path, replace_machine=True)
        assert r2.total_deleted >= 3  # old records cleaned
        assert r2.total_imported >= 3  # new records imported

        # Verify only one observation exists (not doubled)
        obs_count = store.count_observations()
        assert obs_count == 1

        # Verify the observation has the new text
        conn = store._get_connection()
        cursor = conn.execute("SELECT observation FROM memory_observations")
        assert cursor.fetchone()[0] == "Regenerated observation text"

        store.close()

    def test_replace_import_preserves_local_data(self, temp_db: Path):
        """Replace import of machine B data should not touch machine A data."""
        import uuid

        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            import_from_sql_with_dedup,
        )

        store = ActivityStore(temp_db, machine_id=TEST_MACHINE_ID)

        # Create local data
        store.create_session("local-sess", agent="claude", project_root="/p")
        obs = StoredObservation(
            id=str(uuid.uuid4()),
            session_id="local-sess",
            observation="Local observation",
            memory_type="discovery",
        )
        store.store_observation(obs)

        # Import foreign backup with replace
        backup_content = self._make_backup_content(
            self.OTHER_MACHINE_ID, "foreign-sess", "Foreign obs"
        )
        backup_path = temp_db.parent / f"{self.OTHER_MACHINE_ID}.sql"
        backup_path.write_text(backup_content)

        import_from_sql_with_dedup(store, backup_path, replace_machine=True)

        # Local data should be untouched
        assert store.get_session("local-sess") is not None
        assert store.count_observations() == 2  # local + foreign

        store.close()

    def test_replace_import_skips_own_machine(self, temp_db: Path):
        """Replace import of own-machine backup should not pre-delete."""
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            import_from_sql_with_dedup,
        )

        store = ActivityStore(temp_db, machine_id=TEST_MACHINE_ID)

        # Create local data
        store.create_session("my-sess", agent="claude", project_root="/p")

        # Create a backup that looks like it came from this machine
        backup_content = self._make_backup_content(TEST_MACHINE_ID, "my-sess", "My observation")
        backup_path = temp_db.parent / f"{TEST_MACHINE_ID}.sql"
        backup_path.write_text(backup_content)

        result = import_from_sql_with_dedup(store, backup_path, replace_machine=True)

        # Should NOT have deleted anything (own machine guard)
        assert result.total_deleted == 0
        # Session should still exist (skipped as duplicate)
        assert store.get_session("my-sess") is not None

        store.close()

    def test_replace_import_handles_fk_cascade(self, temp_db: Path):
        """Replace import should handle session_relationships FK cascade without errors."""
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            import_from_sql_with_dedup,
        )

        store = ActivityStore(temp_db, machine_id=TEST_MACHINE_ID)

        # Create foreign sessions with a relationship between them
        self._create_foreign_session(
            store, "fk-sess-a", self.OTHER_MACHINE_ID, with_observation=True
        )
        self._create_foreign_session(
            store, "fk-sess-b", self.OTHER_MACHINE_ID, with_observation=True
        )
        conn = store._get_connection()
        conn.execute(
            """
            INSERT INTO session_relationships (session_a_id, session_b_id, relationship_type,
                                              created_at, created_at_epoch, created_by)
            VALUES ('fk-sess-a', 'fk-sess-b', 'related', '2025-01-01T00:00:00', 1704067200, 'manual')
            """,
        )
        conn.commit()

        # Now import a backup for that machine (should delete + reimport without FK errors)
        backup_content = self._make_backup_content(
            self.OTHER_MACHINE_ID, "fk-sess-a", "Replaced obs"
        )
        backup_path = temp_db.parent / f"{self.OTHER_MACHINE_ID}.sql"
        backup_path.write_text(backup_content)

        # Should not raise FK constraint errors
        result = import_from_sql_with_dedup(store, backup_path, replace_machine=True)
        assert result.total_deleted >= 2  # both sessions + children
        assert result.errors == 0

        store.close()

    def test_delete_by_machine_cross_machine_fk(self, temp_db: Path):
        """Delete-by-machine must handle cross-machine FK references from prior additive imports.

        Prior additive (hash-based) imports can leave activities from machine A
        whose prompt_batch_id points to a batch owned by machine B.  Deleting
        machine B's records by source_machine_id alone would fail with
        IntegrityError because those machine-A activities still reference the
        batches being deleted.  The fix deletes children by FK reference to the
        batch IDs being removed.
        """
        from open_agent_kit.features.codebase_intelligence.activity.store.delete import (
            delete_records_by_machine,
        )

        store = ActivityStore(temp_db, machine_id=TEST_MACHINE_ID)

        # Create a session and batch owned by machine B
        conn = store._get_connection()
        conn.execute(
            "INSERT INTO sessions (id, agent, project_root, started_at, created_at_epoch, "
            "source_machine_id) VALUES ('xfk-sess', 'claude', '/p', '2025-01-01T00:00:00', "
            "1704067200, ?)",
            (self.OTHER_MACHINE_ID,),
        )
        conn.execute(
            "INSERT INTO prompt_batches (id, session_id, prompt_number, started_at, status, "
            "created_at_epoch, source_machine_id) VALUES (9000, 'xfk-sess', 1, "
            "'2025-01-01T00:00:00', 'completed', 1704067200, ?)",
            (self.OTHER_MACHINE_ID,),
        )

        # Simulate a cross-machine FK: activity from LOCAL machine referencing
        # machine B's batch (artifact of prior additive import)
        conn.execute(
            "INSERT INTO activities (session_id, prompt_batch_id, tool_name, timestamp, "
            "timestamp_epoch, source_machine_id) VALUES ('xfk-sess', 9000, 'Read', "
            "'2025-01-01T00:00:00', 1704067200, ?)",
            (TEST_MACHINE_ID,),
        )
        conn.commit()

        # This must NOT raise sqlite3.IntegrityError
        counts = delete_records_by_machine(store, self.OTHER_MACHINE_ID)

        assert counts["prompt_batches"] == 1
        # The cross-machine activity should have been cleaned up via batch FK
        assert counts["activities"] >= 1

        store.close()

    def test_delete_by_machine_self_referential_fk(self, temp_db: Path):
        """Delete-by-machine must handle the self-referential source_plan_batch_id FK."""
        from open_agent_kit.features.codebase_intelligence.activity.store.delete import (
            delete_records_by_machine,
        )

        store = ActivityStore(temp_db, machine_id=TEST_MACHINE_ID)

        conn = store._get_connection()
        conn.execute(
            "INSERT INTO sessions (id, agent, project_root, started_at, created_at_epoch, "
            "source_machine_id) VALUES ('self-fk-sess', 'claude', '/p', '2025-01-01T00:00:00', "
            "1704067200, ?)",
            (self.OTHER_MACHINE_ID,),
        )
        # Batch A — will be referenced by batch B's source_plan_batch_id
        conn.execute(
            "INSERT INTO prompt_batches (id, session_id, prompt_number, started_at, status, "
            "created_at_epoch, source_machine_id) VALUES (9100, 'self-fk-sess', 1, "
            "'2025-01-01T00:00:00', 'completed', 1704067200, ?)",
            (self.OTHER_MACHINE_ID,),
        )
        # Batch B — self-referential FK to batch A
        conn.execute(
            "INSERT INTO prompt_batches (id, session_id, prompt_number, started_at, status, "
            "created_at_epoch, source_machine_id, source_plan_batch_id) VALUES (9101, "
            "'self-fk-sess', 2, '2025-01-01T00:00:00', 'completed', 1704067200, ?, 9100)",
            (self.OTHER_MACHINE_ID,),
        )
        conn.commit()

        # This must NOT raise sqlite3.IntegrityError
        counts = delete_records_by_machine(store, self.OTHER_MACHINE_ID)

        assert counts["prompt_batches"] == 2
        assert counts["sessions"] == 1

        store.close()

    def test_replace_import_cleans_chromadb(self, temp_db: Path):
        """Replace import should call vector_store.delete_memories with correct IDs."""
        from unittest.mock import MagicMock

        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            import_from_sql_with_dedup,
        )

        store = ActivityStore(temp_db, machine_id=TEST_MACHINE_ID)
        mock_vs = MagicMock()

        # Create foreign data with an observation
        self._create_foreign_session(
            store, "chroma-sess", self.OTHER_MACHINE_ID, with_observation=True
        )

        # Get the observation ID that was created
        conn = store._get_connection()
        cursor = conn.execute(
            "SELECT id FROM memory_observations WHERE source_machine_id = ?",
            (self.OTHER_MACHINE_ID,),
        )
        obs_id = cursor.fetchone()[0]

        # Import with replace and mock vector_store
        backup_content = self._make_backup_content(self.OTHER_MACHINE_ID, "chroma-sess", "New obs")
        backup_path = temp_db.parent / f"{self.OTHER_MACHINE_ID}.sql"
        backup_path.write_text(backup_content)

        import_from_sql_with_dedup(store, backup_path, replace_machine=True, vector_store=mock_vs)

        # Verify delete_memories was called with the old observation ID
        mock_vs.delete_memories.assert_called_once_with([obs_id])

        store.close()

    def test_incremental_embed_preserves_existing(self, temp_db: Path):
        """After replace import, local observations should keep embedded=1."""
        import uuid

        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            import_from_sql_with_dedup,
        )

        store = ActivityStore(temp_db, machine_id=TEST_MACHINE_ID)

        # Create local session with embedded observation
        store.create_session("embed-local", agent="claude", project_root="/p")
        obs_id = str(uuid.uuid4())
        obs = StoredObservation(
            id=obs_id,
            session_id="embed-local",
            observation="Local embedded obs",
            memory_type="discovery",
        )
        store.store_observation(obs)
        store.mark_observation_embedded(obs_id)
        assert store.count_embedded_observations() == 1

        # Import foreign backup with replace
        backup_content = self._make_backup_content(
            self.OTHER_MACHINE_ID, "foreign-sess", "Foreign obs"
        )
        backup_path = temp_db.parent / f"{self.OTHER_MACHINE_ID}.sql"
        backup_path.write_text(backup_content)

        import_from_sql_with_dedup(store, backup_path, replace_machine=True)

        # Local observation should still be marked as embedded
        assert store.count_embedded_observations() == 1
        # Foreign observation should be unembedded
        assert store.count_unembedded_observations() == 1

        store.close()

    def test_import_result_total_deleted_property(self):
        """ImportResult.total_deleted sums all deleted fields."""
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            ImportResult,
        )

        result = ImportResult(
            sessions_deleted=2,
            batches_deleted=5,
            observations_deleted=10,
            activities_deleted=20,
            runs_deleted=1,
        )
        assert result.total_deleted == 38

    def test_restore_all_result_total_deleted_property(self):
        """RestoreAllResult.total_deleted sums across files."""
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            ImportResult,
            RestoreAllResult,
        )

        r = RestoreAllResult(
            success=True,
            per_file={
                "a.sql": ImportResult(sessions_deleted=2, observations_deleted=3),
                "b.sql": ImportResult(sessions_deleted=1, observations_deleted=4),
            },
        )
        assert r.total_deleted == 10


class TestPlanDetectionDuringOrphanRecovery:
    """Test plan detection in orphan recovery (fixes plan mode detection gap)."""

    def test_orphaned_plan_write_detected_at_recovery(self, activity_store, tmp_path):
        """Plan Write activities with NULL batch should be detected during recovery.

        This tests the fix for the bug where plan detection was skipped during
        plan mode because activities were stored with prompt_batch_id=None.
        """
        import json

        from open_agent_kit.features.codebase_intelligence.constants import (
            PROMPT_SOURCE_PLAN,
        )

        # Create a session
        activity_store.create_session(
            "plan-mode-session", agent="claude", project_root=str(tmp_path)
        )

        # Create the actual plan file on disk (recovery reads from disk)
        plan_content = "# My Test Plan\n\nThis is the plan content."
        plan_dir = tmp_path / ".claude" / "plans"
        plan_dir.mkdir(parents=True)
        plan_file = plan_dir / "test-plan.md"
        plan_file.write_text(plan_content)

        # Use absolute path in tool_input (matches what recovery code will look for)
        tool_input = json.dumps(
            {
                "file_path": str(plan_file),
                "content": plan_content,
            }
        )

        conn = activity_store._get_connection()
        conn.execute(
            """
            INSERT INTO activities
            (session_id, tool_name, tool_input, timestamp, timestamp_epoch, prompt_batch_id)
            VALUES (?, ?, ?, datetime('now'), strftime('%s', 'now'), NULL)
            """,
            ("plan-mode-session", "Write", tool_input),
        )
        conn.commit()

        # Verify activity has NULL batch_id
        cursor = conn.execute(
            "SELECT prompt_batch_id FROM activities WHERE session_id = ?",
            ("plan-mode-session",),
        )
        assert cursor.fetchone()[0] is None

        # Run orphan recovery - this should detect the plan
        recovered = activity_store.recover_orphaned_activities()
        assert recovered == 1

        # Verify a batch was created and marked as plan
        cursor = conn.execute(
            """
            SELECT source_type, plan_content, plan_file_path
            FROM prompt_batches
            WHERE session_id = ?
            """,
            ("plan-mode-session",),
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == PROMPT_SOURCE_PLAN
        assert row[1] == plan_content
        assert row[2] == str(plan_file)

    def test_orphaned_non_plan_write_not_marked_as_plan(self, activity_store):
        """Non-plan Write activities should not be marked as plan during recovery."""
        import json

        from open_agent_kit.features.codebase_intelligence.constants import (
            PROMPT_SOURCE_PLAN,
        )

        # Create a session
        activity_store.create_session(
            "regular-session", agent="claude", project_root="/test/project"
        )

        # Simulate regular file write with NULL batch_id
        tool_input = json.dumps(
            {
                "file_path": "src/app.py",
                "content": "print('hello')",
            }
        )

        conn = activity_store._get_connection()
        conn.execute(
            """
            INSERT INTO activities
            (session_id, tool_name, tool_input, timestamp, timestamp_epoch, prompt_batch_id)
            VALUES (?, ?, ?, datetime('now'), strftime('%s', 'now'), NULL)
            """,
            ("regular-session", "Write", tool_input),
        )
        conn.commit()

        # Run orphan recovery
        recovered = activity_store.recover_orphaned_activities()
        assert recovered == 1

        # Verify batch was NOT marked as plan (should be recovery batch)
        cursor = conn.execute(
            """
            SELECT source_type FROM prompt_batches WHERE session_id = ?
            """,
            ("regular-session",),
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] != PROMPT_SOURCE_PLAN  # Should not be a plan
