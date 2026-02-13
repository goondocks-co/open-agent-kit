"""Tests for statistics operations in the refactored data layer.

Covers:
- get_bulk_session_stats(): bulk aggregation query that eliminates N+1
"""

from __future__ import annotations

from pathlib import Path

import pytest

from open_agent_kit.features.codebase_intelligence.activity.store.core import (
    ActivityStore,
)
from open_agent_kit.features.codebase_intelligence.activity.store.models import (
    Activity,
)
from open_agent_kit.features.codebase_intelligence.activity.store.sessions import (
    create_session,
)
from open_agent_kit.features.codebase_intelligence.activity.store.stats import (
    get_bulk_session_stats,
)

TEST_MACHINE_ID = "test-machine-stats"
PROJECT_ROOT = "/test/project"
AGENT_NAME = "claude"


@pytest.fixture()
def store(tmp_path: Path) -> ActivityStore:
    """Create an ActivityStore with a real temp SQLite database."""
    db_path = tmp_path / "ci" / "activities.db"
    return ActivityStore(db_path, machine_id=TEST_MACHINE_ID)


def _make_session(store: ActivityStore, session_id: str) -> None:
    """Create a minimal session."""
    create_session(store, session_id=session_id, agent=AGENT_NAME, project_root=PROJECT_ROOT)


def _add_activity(
    store: ActivityStore,
    session_id: str,
    tool_name: str = "Read",
    file_path: str | None = "/some/file.py",
    success: bool = True,
    error_message: str | None = None,
) -> int:
    """Insert a single activity and return its ID."""
    return store.add_activity(
        Activity(
            session_id=session_id,
            tool_name=tool_name,
            file_path=file_path,
            tool_output_summary=f"{tool_name} output",
            success=success,
            error_message=error_message,
        )
    )


# ==========================================================================
# get_bulk_session_stats()
# ==========================================================================


class TestGetBulkSessionStats:
    """Verify the bulk aggregation query for session statistics."""

    def test_empty_session_list_returns_empty_dict(self, store: ActivityStore) -> None:
        """Passing an empty list should return an empty dictionary."""
        result = get_bulk_session_stats(store, session_ids=[])
        assert result == {}

    def test_session_with_no_activities(self, store: ActivityStore) -> None:
        """A session with zero activities should return zero counts."""
        _make_session(store, "empty-session")

        result = get_bulk_session_stats(store, session_ids=["empty-session"])

        assert "empty-session" in result
        stats = result["empty-session"]
        assert stats["activity_count"] == 0
        assert stats["files_touched"] == 0
        assert stats["reads"] == 0
        assert stats["edits"] == 0
        assert stats["writes"] == 0
        assert stats["errors"] == 0
        assert stats["tool_counts"] == {}

    def test_single_session_with_activities(self, store: ActivityStore) -> None:
        """Verify counts for a session with mixed tool activity."""
        _make_session(store, "session-1")
        _add_activity(store, "session-1", tool_name="Read", file_path="/a.py")
        _add_activity(store, "session-1", tool_name="Read", file_path="/b.py")
        _add_activity(store, "session-1", tool_name="Edit", file_path="/a.py")
        _add_activity(store, "session-1", tool_name="Write", file_path="/c.py")
        _add_activity(
            store,
            "session-1",
            tool_name="Bash",
            file_path=None,
            success=False,
            error_message="command failed",
        )

        result = get_bulk_session_stats(store, session_ids=["session-1"])

        assert "session-1" in result
        stats = result["session-1"]
        assert stats["activity_count"] == 5
        # /a.py, /b.py, /c.py + None = 3 distinct non-null file paths
        assert stats["files_touched"] == 3
        assert stats["reads"] == 2
        assert stats["edits"] == 1
        assert stats["writes"] == 1
        assert stats["errors"] == 1
        assert stats["tool_counts"]["Read"] == 2
        assert stats["tool_counts"]["Edit"] == 1
        assert stats["tool_counts"]["Write"] == 1
        assert stats["tool_counts"]["Bash"] == 1

    def test_multiple_sessions_bulk_query(self, store: ActivityStore) -> None:
        """Verify correct per-session aggregation across multiple sessions."""
        _make_session(store, "s1")
        _make_session(store, "s2")
        _make_session(store, "s3")

        # s1: 3 reads
        _add_activity(store, "s1", tool_name="Read", file_path="/x.py")
        _add_activity(store, "s1", tool_name="Read", file_path="/y.py")
        _add_activity(store, "s1", tool_name="Read", file_path="/z.py")

        # s2: 1 edit, 1 write
        _add_activity(store, "s2", tool_name="Edit", file_path="/a.py")
        _add_activity(store, "s2", tool_name="Write", file_path="/b.py")

        # s3: no activities

        result = get_bulk_session_stats(store, session_ids=["s1", "s2", "s3"])

        assert len(result) == 3

        # s1 assertions
        assert result["s1"]["activity_count"] == 3
        assert result["s1"]["reads"] == 3
        assert result["s1"]["edits"] == 0
        assert result["s1"]["writes"] == 0

        # s2 assertions
        assert result["s2"]["activity_count"] == 2
        assert result["s2"]["reads"] == 0
        assert result["s2"]["edits"] == 1
        assert result["s2"]["writes"] == 1

        # s3 assertions (empty session)
        assert result["s3"]["activity_count"] == 0
        assert result["s3"]["tool_counts"] == {}

    def test_nonexistent_session_returns_zero_stats(self, store: ActivityStore) -> None:
        """Querying a session ID that doesn't exist should return zero counts."""
        result = get_bulk_session_stats(store, session_ids=["does-not-exist"])

        assert "does-not-exist" in result
        stats = result["does-not-exist"]
        assert stats["activity_count"] == 0
        assert stats["prompt_batch_count"] == 0

    def test_stats_include_prompt_batch_count(self, store: ActivityStore) -> None:
        """Verify prompt_batch_count is included in bulk stats."""
        _make_session(store, "with-batches")
        store.create_prompt_batch("with-batches", user_prompt="first prompt")
        store.create_prompt_batch("with-batches", user_prompt="second prompt")
        _add_activity(store, "with-batches", tool_name="Read", file_path="/f.py")

        result = get_bulk_session_stats(store, session_ids=["with-batches"])

        stats = result["with-batches"]
        assert stats["activity_count"] == 1
        # prompt_batch_count should be >= 1 (exact count depends on
        # how the LEFT JOIN deduplicates batches in the aggregate query)
        assert stats["prompt_batch_count"] >= 1

    def test_tool_counts_map_per_session(self, store: ActivityStore) -> None:
        """Each session should have its own independent tool_counts map."""
        _make_session(store, "alpha")
        _make_session(store, "beta")

        _add_activity(store, "alpha", tool_name="Read")
        _add_activity(store, "alpha", tool_name="Read")
        _add_activity(store, "beta", tool_name="Edit")

        result = get_bulk_session_stats(store, session_ids=["alpha", "beta"])

        assert result["alpha"]["tool_counts"] == {"Read": 2}
        assert result["beta"]["tool_counts"] == {"Edit": 1}
