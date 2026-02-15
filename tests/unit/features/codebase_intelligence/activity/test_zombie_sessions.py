"""Tests for zombie session prevention.

Covers:
- process_session marks empty sessions as processed (A1)
- recover_stale_sessions marks empty recovered sessions as processed (A2)
- count_session_activities helper (A2)
"""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from open_agent_kit.features.codebase_intelligence.activity.processor.core import (
    ActivityProcessor,
)
from open_agent_kit.features.codebase_intelligence.activity.store.core import (
    ActivityStore,
)
from open_agent_kit.features.codebase_intelligence.activity.store.models import (
    Activity,
)
from open_agent_kit.features.codebase_intelligence.activity.store.sessions import (
    count_session_activities,
    create_session,
    end_session,
    recover_stale_sessions,
)
from open_agent_kit.features.codebase_intelligence.constants import (
    MIN_SESSION_ACTIVITIES,
    SESSION_STATUS_COMPLETED,
)

TEST_MACHINE_ID = "test-machine-zombie"
PROJECT_ROOT = "/test/project"
AGENT_NAME = "claude"


@pytest.fixture()
def store(tmp_path: Path) -> ActivityStore:
    """Create an ActivityStore with a real temp SQLite database."""
    db_path = tmp_path / "ci" / "activities.db"
    return ActivityStore(db_path, machine_id=TEST_MACHINE_ID)


def _make_session(
    store: ActivityStore,
    session_id: str,
) -> None:
    """Create a session."""
    create_session(
        store,
        session_id=session_id,
        agent=AGENT_NAME,
        project_root=PROJECT_ROOT,
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


def _is_session_processed(store: ActivityStore, session_id: str) -> bool:
    """Check whether a session is marked as processed."""
    conn = store._get_connection()
    cursor = conn.execute(
        "SELECT processed FROM sessions WHERE id = ?",
        (session_id,),
    )
    row = cursor.fetchone()
    return bool(row and row[0])


# ==========================================================================
# A1: process_session marks empty sessions as processed
# ==========================================================================


class TestProcessSessionEmptyMarking:
    """Verify that process_session marks empty sessions as processed."""

    def test_process_session_marks_empty_session_processed(self, store: ActivityStore) -> None:
        """A completed session with 0 unprocessed activities should be
        marked as processed after process_session returns."""
        _make_session(store, "empty-session")
        end_session(store, "empty-session")

        processor = ActivityProcessor(
            activity_store=store,
            vector_store=MagicMock(),
            summarizer=MagicMock(),
            prompt_config=MagicMock(),
            project_root=PROJECT_ROOT,
        )

        result = processor.process_session("empty-session")

        assert result.success is True
        assert result.activities_processed == 0
        assert _is_session_processed(store, "empty-session")

    def test_process_session_does_not_mark_when_activities_exist(
        self, store: ActivityStore
    ) -> None:
        """A session with unprocessed activities should follow the normal
        processing path (mark_session_processed is called at the end of
        the full processing pipeline, not the early return)."""
        _make_session(store, "active-session")
        _add_activities(store, "active-session", count=MIN_SESSION_ACTIVITIES)
        end_session(store, "active-session")

        # The processor needs a summarizer that returns a valid result
        # for the full processing path. We mock _call_llm to avoid
        # needing a real LLM.
        processor = ActivityProcessor(
            activity_store=store,
            vector_store=MagicMock(),
            summarizer=MagicMock(),
            prompt_config=MagicMock(),
            project_root=PROJECT_ROOT,
        )

        # Mock the LLM call to return a successful result with observations
        processor._call_llm = MagicMock(  # type: ignore[method-assign]
            return_value={
                "success": True,
                "observations": [
                    {
                        "observation": "test observation",
                        "memory_type": "discovery",
                        "context": "/test.py",
                    }
                ],
                "summary": "test summary",
            }
        )
        # Mock classify to avoid needing real prompts
        processor._classify_session = MagicMock(  # type: ignore[method-assign]
            return_value="feature_development"
        )
        processor._select_template_by_classification = MagicMock(  # type: ignore[method-assign]
            return_value=MagicMock(name="test_template"),
        )
        processor._get_oak_ci_context = MagicMock(return_value="")  # type: ignore[method-assign]

        result = processor.process_session("active-session")

        assert result.success is True
        assert result.activities_processed == MIN_SESSION_ACTIVITIES
        # Session should be processed via the normal path (end of pipeline)
        assert _is_session_processed(store, "active-session")


# ==========================================================================
# A2: recover_stale_sessions marks empty recovered sessions as processed
# ==========================================================================


class TestRecoverStaleSessionZombieGuard:
    """Verify that recover_stale_sessions marks empty recovered sessions
    as processed to prevent zombie sessions."""

    def test_recover_stale_session_marks_empty_processed(self, store: ActivityStore) -> None:
        """A stale session with 0 activities that meets the quality threshold
        (via activity_count from the recovery query) should be marked as
        both completed AND processed.

        Note: recover_stale_sessions deletes sessions below min_activities.
        To test the 'recovered but empty' path, we need a session with
        enough activities to pass the recovery threshold but 0 unprocessed
        activities. However, the simpler case is: create a session with
        activities >= min_activities, then ensure count_session_activities
        returns 0 for the guard check. Actually, the guard checks
        count_session_activities which counts ALL activities. So we test
        with a session that has >= min_activities activities to get it
        recovered (not deleted), then verify it's processed.

        Actually, looking more carefully: the guard in recover_stale_sessions
        checks count_session_activities == 0. Sessions with 0 activities
        are deleted (< min_activities). So the guard fires for sessions
        that have activities >= min_activities but count_session_activities
        returns 0 -- which can't happen naturally. The real scenario is:
        a session has activities, gets recovered (completed), but all
        activities were already processed. The process_session early return
        (A1) handles that case. The guard in A2 is defense-in-depth.

        For this test, we use min_activities=0 so the session with 0
        activities gets recovered (not deleted), triggering the guard.
        """
        _make_session(store, "stale-empty")

        # Backdate the session creation so it appears stale
        conn = store._get_connection()
        stale_epoch = int(time.time()) - 7200  # 2 hours ago
        conn.execute(
            "UPDATE sessions SET created_at_epoch = ? WHERE id = ?",
            (stale_epoch, "stale-empty"),
        )
        conn.commit()

        recovered_ids, deleted_ids = recover_stale_sessions(
            store,
            timeout_seconds=3600,
            min_activities=0,  # Allow 0-activity sessions to be recovered
        )

        assert "stale-empty" in recovered_ids
        assert "stale-empty" not in deleted_ids

        # Session should be completed
        session = store.get_session("stale-empty")
        assert session is not None
        assert session.status == SESSION_STATUS_COMPLETED

        # Session should be marked as processed (zombie guard)
        assert _is_session_processed(store, "stale-empty")

    def test_recover_stale_session_preserves_nonempty(self, store: ActivityStore) -> None:
        """A stale session with activities should be recovered (completed)
        but NOT marked as processed -- it still has work to do."""
        _make_session(store, "stale-nonempty")
        _add_activities(store, "stale-nonempty", count=MIN_SESSION_ACTIVITIES)

        # Backdate the session and activities so they appear stale
        conn = store._get_connection()
        stale_epoch = int(time.time()) - 7200  # 2 hours ago
        conn.execute(
            "UPDATE sessions SET created_at_epoch = ? WHERE id = ?",
            (stale_epoch, "stale-nonempty"),
        )
        conn.execute(
            "UPDATE activities SET timestamp_epoch = ? WHERE session_id = ?",
            (stale_epoch, "stale-nonempty"),
        )
        conn.commit()

        recovered_ids, deleted_ids = recover_stale_sessions(
            store,
            timeout_seconds=3600,
            min_activities=MIN_SESSION_ACTIVITIES,
        )

        assert "stale-nonempty" in recovered_ids
        assert "stale-nonempty" not in deleted_ids

        # Session should be completed
        session = store.get_session("stale-nonempty")
        assert session is not None
        assert session.status == SESSION_STATUS_COMPLETED

        # Session should NOT be marked as processed (has activities to process)
        assert not _is_session_processed(store, "stale-nonempty")


# ==========================================================================
# count_session_activities()
# ==========================================================================


class TestCountSessionActivities:
    """Verify the count_session_activities helper."""

    def test_count_session_activities(self, store: ActivityStore) -> None:
        """Should return the exact number of activities for a session."""
        _make_session(store, "counted")
        activity_count = 5
        _add_activities(store, "counted", count=activity_count)

        assert count_session_activities(store, "counted") == activity_count

    def test_count_session_activities_empty(self, store: ActivityStore) -> None:
        """Should return 0 for a session with no activities."""
        _make_session(store, "empty")

        assert count_session_activities(store, "empty") == 0
