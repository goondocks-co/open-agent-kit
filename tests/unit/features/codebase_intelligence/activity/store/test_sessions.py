"""Tests for session operations in the refactored data layer.

Covers:
- would_create_cycle(): recursive CTE cycle detection
- cleanup_low_quality_sessions(): batch deletion of low-quality sessions
- find_linkable_parent_session(): tiered parent session discovery
"""

from __future__ import annotations

from datetime import datetime, timedelta
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
    find_linkable_parent_session,
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


# ==========================================================================
# find_linkable_parent_session()
# ==========================================================================


def _set_session_timestamps(
    store: ActivityStore,
    session_id: str,
    created_at_epoch: float,
    ended_at: datetime | None = None,
    status: str = "active",
) -> None:
    """Override session timestamps directly in the DB for controlled testing."""
    conn = store._get_connection()
    started_at = datetime.fromtimestamp(created_at_epoch).isoformat()
    conn.execute(
        """
        UPDATE sessions
        SET created_at_epoch = ?, started_at = ?, status = ?,
            ended_at = ?
        WHERE id = ?
        """,
        (
            created_at_epoch,
            started_at,
            status,
            ended_at.isoformat() if ended_at else None,
            session_id,
        ),
    )
    conn.commit()


class TestFindLinkableParentSession:
    """Verify tiered parent session discovery for auto-linking."""

    def test_tier1_picks_most_recently_ended_not_created(self, store: ActivityStore) -> None:
        """Regression: Tier 1 must order by ended_at, not created_at_epoch.

        Scenario (the actual bug):
        - Session A created at T+0, ended at T+120min (plan session, long-running)
        - Session B created at T+10min, ended at T+15min (unrelated, short-lived)
        - Session C starts at T+120min (continuation after clearing A)

        Old behavior: picked B (newer created_at_epoch) -> wrong parent
        Fixed behavior: picks A (most recently ended_at) -> correct parent
        """
        now = datetime.now()
        t0 = now - timedelta(minutes=120)
        t10 = now - timedelta(minutes=110)
        t15 = now - timedelta(minutes=105)
        t120 = now  # session A ends, session C starts

        # Create both sessions
        _make_session(store, "plan-session-A")
        _make_session(store, "unrelated-session-B")
        _make_session(store, "continuation-C")

        # A: created first, ended last (the real parent)
        _set_session_timestamps(
            store,
            "plan-session-A",
            created_at_epoch=t0.timestamp(),
            ended_at=t120,
            status="completed",
        )
        # B: created second, ended much earlier (not the parent)
        _set_session_timestamps(
            store,
            "unrelated-session-B",
            created_at_epoch=t10.timestamp(),
            ended_at=t15,
            status="completed",
        )
        # C: the new continuation session (not yet ended)
        _set_session_timestamps(
            store,
            "continuation-C",
            created_at_epoch=t120.timestamp(),
        )

        result = find_linkable_parent_session(
            store=store,
            agent=AGENT_NAME,
            project_root=PROJECT_ROOT,
            exclude_session_id="continuation-C",
            new_session_started_at=t120,
            max_gap_seconds=5,
        )

        assert result is not None
        parent_id, reason = result
        assert parent_id == "plan-session-A", (
            f"Expected plan-session-A (most recently ended) "
            f"but got {parent_id} — Tier 1 is still ordering by created_at_epoch"
        )
        assert reason == "clear"  # SESSION_LINK_REASON_CLEAR (within 5s gap)

    def test_tier2_finds_active_session_race_condition(self, store: ActivityStore) -> None:
        """Tier 2 should find an active session when SessionEnd hasn't fired yet."""
        now = datetime.now()
        t0 = now - timedelta(minutes=60)

        _make_session(store, "active-parent")
        _add_activities(store, "active-parent", count=3)
        # Tier 2 checks prompt_count > 0; _add_activities doesn't touch it
        conn = store._get_connection()
        conn.execute("UPDATE sessions SET prompt_count = 3 WHERE id = 'active-parent'")
        conn.commit()
        _set_session_timestamps(
            store,
            "active-parent",
            created_at_epoch=t0.timestamp(),
            status="active",  # Not yet ended
        )

        _make_session(store, "new-child")
        _set_session_timestamps(store, "new-child", created_at_epoch=now.timestamp())

        result = find_linkable_parent_session(
            store=store,
            agent=AGENT_NAME,
            project_root=PROJECT_ROOT,
            exclude_session_id="new-child",
            new_session_started_at=now,
        )

        assert result is not None
        parent_id, reason = result
        assert parent_id == "active-parent"
        assert reason == "clear_active"

    def test_tier3_fallback_picks_most_recently_ended(self, store: ActivityStore) -> None:
        """Tier 3 fallback must independently find the most recently ended session.

        Regression: Tier 3 previously reused the wrong candidate from Tier 1.
        """
        now = datetime.now()
        t0 = now - timedelta(hours=2)
        t30 = now - timedelta(hours=1, minutes=30)
        t60 = now - timedelta(hours=1)

        # A: created first, ended more recently (correct parent)
        _make_session(store, "correct-parent-A")
        _set_session_timestamps(
            store,
            "correct-parent-A",
            created_at_epoch=t0.timestamp(),
            ended_at=t60,  # ended 1 hour ago
            status="completed",
        )
        # B: created later, ended earlier (wrong parent)
        _make_session(store, "wrong-parent-B")
        _set_session_timestamps(
            store,
            "wrong-parent-B",
            created_at_epoch=t30.timestamp(),
            ended_at=t30,  # ended 1.5 hours ago
            status="completed",
        )

        _make_session(store, "new-session")
        _set_session_timestamps(store, "new-session", created_at_epoch=now.timestamp())

        # Both sessions ended >5s ago, so Tier 1 won't match.
        # Tier 2 won't match (no active sessions).
        # Tier 3 should pick A (most recently ended).
        result = find_linkable_parent_session(
            store=store,
            agent=AGENT_NAME,
            project_root=PROJECT_ROOT,
            exclude_session_id="new-session",
            new_session_started_at=now,
            max_gap_seconds=5,
        )

        assert result is not None
        parent_id, reason = result
        assert parent_id == "correct-parent-A", (
            f"Expected correct-parent-A (ended more recently) "
            f"but got {parent_id} — Tier 3 is reusing wrong Tier 1 candidate"
        )
        assert reason == "inferred"

    def test_no_match_when_all_sessions_too_old(self, store: ActivityStore) -> None:
        """No link should be returned when all candidates exceed the fallback window."""
        now = datetime.now()
        old = now - timedelta(hours=48)

        _make_session(store, "ancient")
        _set_session_timestamps(
            store,
            "ancient",
            created_at_epoch=old.timestamp(),
            ended_at=old,
            status="completed",
        )

        _make_session(store, "new-session")
        _set_session_timestamps(store, "new-session", created_at_epoch=now.timestamp())

        result = find_linkable_parent_session(
            store=store,
            agent=AGENT_NAME,
            project_root=PROJECT_ROOT,
            exclude_session_id="new-session",
            new_session_started_at=now,
            fallback_max_hours=24,
        )

        assert result is None

    def test_different_agent_not_linked(self, store: ActivityStore) -> None:
        """Sessions from a different agent should never be linked."""
        now = datetime.now()

        # Create a session for a different agent
        create_session(
            store,
            session_id="cursor-session",
            agent="cursor",
            project_root=PROJECT_ROOT,
        )
        _set_session_timestamps(
            store,
            "cursor-session",
            created_at_epoch=(now - timedelta(seconds=1)).timestamp(),
            ended_at=now - timedelta(seconds=1),
            status="completed",
        )

        _make_session(store, "claude-new")
        _set_session_timestamps(store, "claude-new", created_at_epoch=now.timestamp())

        result = find_linkable_parent_session(
            store=store,
            agent=AGENT_NAME,  # "claude"
            project_root=PROJECT_ROOT,
            exclude_session_id="claude-new",
            new_session_started_at=now,
        )

        assert result is None
