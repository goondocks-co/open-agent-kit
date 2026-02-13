"""Tests for session operations in the refactored data layer.

Covers:
- would_create_cycle(): recursive CTE cycle detection
- cleanup_low_quality_sessions(): batch deletion of low-quality sessions
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from open_agent_kit.features.codebase_intelligence.activity.store.core import (
    ActivityStore,
)
from open_agent_kit.features.codebase_intelligence.activity.store.models import (
    Activity,
)
from open_agent_kit.features.codebase_intelligence.activity.store.sessions import (
    cleanup_low_quality_sessions,
    create_session,
    end_session,
    would_create_cycle,
)

TEST_MACHINE_ID = "test-machine-sessions"
PROJECT_ROOT = "/test/project"
AGENT_NAME = "claude"


@pytest.fixture()
def store(tmp_path: Path) -> ActivityStore:
    """Create an ActivityStore with a real temp SQLite database."""
    db_path = tmp_path / "ci" / "activities.db"
    return ActivityStore(db_path, machine_id=TEST_MACHINE_ID)


# ---------------------------------------------------------------------------
# Helper: create a session + link it to a parent in one call
# ---------------------------------------------------------------------------


def _make_session(
    store: ActivityStore,
    session_id: str,
    parent_id: str | None = None,
    parent_reason: str | None = None,
) -> None:
    """Create a session and optionally set its parent link."""
    create_session(
        store,
        session_id=session_id,
        agent=AGENT_NAME,
        project_root=PROJECT_ROOT,
        parent_session_id=parent_id,
        parent_session_reason=parent_reason,
    )


def _add_activities(store: ActivityStore, session_id: str, count: int) -> None:
    """Insert *count* dummy activities for a session."""
    for i in range(count):
        store.add_activity(
            Activity(
                session_id=session_id,
                tool_name="Read",
                file_path=f"/file_{i}.py",
                tool_output_summary=f"Read file {i}",
            )
        )


# ==========================================================================
# would_create_cycle()
# ==========================================================================


class TestWouldCreateCycle:
    """Verify the recursive CTE cycle-detection query."""

    def test_no_cycle_linear_chain(self, store: ActivityStore) -> None:
        """A -> B -> C; proposing D as parent of A should be safe."""
        _make_session(store, "A")
        _make_session(store, "B", parent_id="A")
        _make_session(store, "C", parent_id="B")
        _make_session(store, "D")

        assert would_create_cycle(store, session_id="A", proposed_parent_id="D") is False

    def test_direct_cycle(self, store: ActivityStore) -> None:
        """A -> B; proposing A as parent of B creates a direct cycle."""
        _make_session(store, "A")
        _make_session(store, "B", parent_id="A")

        assert would_create_cycle(store, session_id="A", proposed_parent_id="B") is True

    def test_indirect_cycle(self, store: ActivityStore) -> None:
        """A -> B -> C; proposing A as parent of C creates an indirect cycle."""
        _make_session(store, "A")
        _make_session(store, "B", parent_id="A")
        _make_session(store, "C", parent_id="B")

        assert would_create_cycle(store, session_id="A", proposed_parent_id="C") is True

    def test_self_reference(self, store: ActivityStore) -> None:
        """Proposing A as parent of A is always a cycle."""
        _make_session(store, "A")

        assert would_create_cycle(store, session_id="A", proposed_parent_id="A") is True

    def test_none_parent_is_safe(self, store: ActivityStore) -> None:
        """When parent is None the check is not needed but the function
        should not raise if called with a non-existent session ID."""
        _make_session(store, "A")

        # A session that doesn't exist as parent -- no cycle possible
        assert would_create_cycle(store, session_id="A", proposed_parent_id="nonexistent") is False

    def test_longer_chain_no_cycle(self, store: ActivityStore) -> None:
        """A -> B -> C -> D -> E; proposing F as parent of A is safe."""
        _make_session(store, "A")
        _make_session(store, "B", parent_id="A")
        _make_session(store, "C", parent_id="B")
        _make_session(store, "D", parent_id="C")
        _make_session(store, "E", parent_id="D")
        _make_session(store, "F")

        assert would_create_cycle(store, session_id="A", proposed_parent_id="F") is False

    def test_longer_chain_cycle_at_depth(self, store: ActivityStore) -> None:
        """A -> B -> C -> D; proposing A as parent of D creates a deep cycle."""
        _make_session(store, "A")
        _make_session(store, "B", parent_id="A")
        _make_session(store, "C", parent_id="B")
        _make_session(store, "D", parent_id="C")

        assert would_create_cycle(store, session_id="A", proposed_parent_id="D") is True

    def test_disjoint_chains_no_cycle(self, store: ActivityStore) -> None:
        """Two independent chains should not interfere with each other."""
        # Chain 1: A -> B
        _make_session(store, "A")
        _make_session(store, "B", parent_id="A")
        # Chain 2: X -> Y
        _make_session(store, "X")
        _make_session(store, "Y", parent_id="X")

        # Linking Y as parent of A should be safe (disjoint chains)
        assert would_create_cycle(store, session_id="A", proposed_parent_id="Y") is False


# ==========================================================================
# cleanup_low_quality_sessions()
# ==========================================================================


class TestCleanupLowQualitySessions:
    """Verify batch deletion of completed sessions below the quality threshold."""

    def test_deletes_low_quality_completed_sessions(self, store: ActivityStore) -> None:
        """Completed sessions with fewer than min_activities should be deleted."""
        # Session with 1 activity (below threshold of 3)
        _make_session(store, "low-quality-1")
        _add_activities(store, "low-quality-1", count=1)
        end_session(store, "low-quality-1")

        # Session with 0 activities (below threshold)
        _make_session(store, "low-quality-2")
        end_session(store, "low-quality-2")

        deleted = cleanup_low_quality_sessions(store, min_activities=3)

        assert sorted(deleted) == ["low-quality-1", "low-quality-2"]
        # Verify sessions are actually gone from the database
        assert store.get_session("low-quality-1") is None
        assert store.get_session("low-quality-2") is None

    def test_preserves_high_quality_sessions(self, store: ActivityStore) -> None:
        """Completed sessions meeting the threshold should NOT be deleted."""
        _make_session(store, "high-quality")
        _add_activities(store, "high-quality", count=5)
        end_session(store, "high-quality")

        deleted = cleanup_low_quality_sessions(store, min_activities=3)

        assert deleted == []
        assert store.get_session("high-quality") is not None

    def test_does_not_delete_active_sessions(self, store: ActivityStore) -> None:
        """Active sessions should never be deleted, even if low quality."""
        _make_session(store, "active-low")
        _add_activities(store, "active-low", count=1)
        # Do NOT call end_session -- session stays active

        deleted = cleanup_low_quality_sessions(store, min_activities=3)

        assert deleted == []
        assert store.get_session("active-low") is not None

    def test_returns_empty_when_no_low_quality(self, store: ActivityStore) -> None:
        """No deletions when all sessions meet the threshold."""
        _make_session(store, "good-1")
        _add_activities(store, "good-1", count=10)
        end_session(store, "good-1")

        _make_session(store, "good-2")
        _add_activities(store, "good-2", count=5)
        end_session(store, "good-2")

        deleted = cleanup_low_quality_sessions(store, min_activities=3)

        assert deleted == []

    def test_chromadb_cleanup_called(self, store: ActivityStore) -> None:
        """Vector store cleanup should be called when observations exist."""
        _make_session(store, "with-obs")
        _add_activities(store, "with-obs", count=1)
        end_session(store, "with-obs")

        mock_vector_store = MagicMock()

        cleanup_low_quality_sessions(
            store,
            vector_store=mock_vector_store,
            min_activities=3,
        )

        # The function attempts ChromaDB cleanup; with no observations
        # the delete_memories call should NOT be made (no IDs to delete)
        mock_vector_store.delete_memories.assert_not_called()

    def test_chromadb_cleanup_with_observations(self, store: ActivityStore) -> None:
        """When sessions have observations, ChromaDB cleanup should be called."""
        from open_agent_kit.features.codebase_intelligence.activity.store.models import (
            StoredObservation,
        )

        _make_session(store, "with-obs")
        _add_activities(store, "with-obs", count=1)
        end_session(store, "with-obs")

        # Insert a memory observation for this session
        store.store_observation(
            StoredObservation(
                id="obs-1",
                session_id="with-obs",
                observation="test observation",
                memory_type="gotcha",
                context="test context",
            )
        )

        mock_vector_store = MagicMock()

        cleanup_low_quality_sessions(
            store,
            vector_store=mock_vector_store,
            min_activities=3,
        )

        # ChromaDB cleanup should have been called with the observation ID
        mock_vector_store.delete_memories.assert_called_once_with(["obs-1"])

    def test_chromadb_failure_does_not_prevent_deletion(self, store: ActivityStore) -> None:
        """ChromaDB failure should not prevent SQLite deletion (best-effort)."""
        from open_agent_kit.features.codebase_intelligence.activity.store.models import (
            StoredObservation,
        )

        _make_session(store, "chroma-fail")
        _add_activities(store, "chroma-fail", count=1)
        end_session(store, "chroma-fail")

        store.store_observation(
            StoredObservation(
                id="obs-fail",
                session_id="chroma-fail",
                observation="test observation",
                memory_type="gotcha",
            )
        )

        mock_vector_store = MagicMock()
        mock_vector_store.delete_memories.side_effect = RuntimeError("ChromaDB down")

        deleted = cleanup_low_quality_sessions(
            store,
            vector_store=mock_vector_store,
            min_activities=3,
        )

        # SQLite deletion should still succeed despite ChromaDB failure
        assert "chroma-fail" in deleted
        assert store.get_session("chroma-fail") is None

    def test_mixed_quality_sessions(self, store: ActivityStore) -> None:
        """Only low-quality sessions should be deleted in a mixed set."""
        # Low quality (1 activity, threshold is 3)
        _make_session(store, "low")
        _add_activities(store, "low", count=1)
        end_session(store, "low")

        # Exactly at threshold (3 activities)
        _make_session(store, "borderline")
        _add_activities(store, "borderline", count=3)
        end_session(store, "borderline")

        # High quality (10 activities)
        _make_session(store, "high")
        _add_activities(store, "high", count=10)
        end_session(store, "high")

        deleted = cleanup_low_quality_sessions(store, min_activities=3)

        assert deleted == ["low"]
        assert store.get_session("borderline") is not None
        assert store.get_session("high") is not None
