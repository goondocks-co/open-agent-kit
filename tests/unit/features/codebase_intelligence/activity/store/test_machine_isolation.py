"""Tests for machine isolation in background processing paths.

Verifies that all background processing, indexing, and state-reset operations
only touch records where source_machine_id matches the store's machine_id.
This prevents cross-machine data pollution when team backups are restored.
"""

import tempfile
import time
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from open_agent_kit.features.codebase_intelligence.activity.store import (
    Activity,
    ActivityStore,
    StoredObservation,
)
from open_agent_kit.features.codebase_intelligence.constants import (
    MIN_SESSION_ACTIVITIES,
    RECOVERY_BATCH_PROMPT,
)

MACHINE_A = "machine_aaa111"
MACHINE_B = "machine_bbb222"
PROJECT_ROOT = "/test/project"


@pytest.fixture
def shared_db():
    """Create a temporary database path shared by two stores."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir) / "isolation_test.db"


@pytest.fixture
def store_a(shared_db):
    """ActivityStore for machine A."""
    return ActivityStore(shared_db, machine_id=MACHINE_A)


@pytest.fixture
def store_b(shared_db):
    """ActivityStore for machine B (shares same DB file)."""
    return ActivityStore(shared_db, machine_id=MACHINE_B)


def _create_completed_session(
    store: ActivityStore,
    session_id: str,
    *,
    with_activities: int = 0,
    with_batch: bool = False,
    with_title: bool = False,
    with_summary_obs: bool = False,
) -> str:
    """Helper to create a completed session with optional related records."""
    store.create_session(session_id, "claude", PROJECT_ROOT)

    if with_batch:
        batch = store.create_prompt_batch(session_id, "test prompt")
        store.end_prompt_batch(batch.id)

    for i in range(with_activities):
        store.add_activity(
            Activity(
                session_id=session_id,
                tool_name="Read",
                tool_output_summary=f"activity {i}",
                source_machine_id=store.machine_id,
            )
        )

    store.end_session(session_id)

    if with_title:
        store.update_session_title(session_id, "Test Title")

    if with_summary_obs:
        store.store_observation(
            StoredObservation(
                id=str(uuid.uuid4()),
                session_id=session_id,
                observation="Summary of session",
                memory_type="session_summary",
                source_machine_id=store.machine_id,
            )
        )

    return session_id


def _create_active_session(
    store: ActivityStore,
    session_id: str,
    *,
    with_activities: int = 0,
    created_epoch: int | None = None,
) -> str:
    """Helper to create an active session, optionally backdated."""
    store.create_session(session_id, "claude", PROJECT_ROOT)

    if created_epoch is not None:
        with store._transaction() as tx:
            tx.execute(
                "UPDATE sessions SET created_at_epoch = ? WHERE id = ?",
                (created_epoch, session_id),
            )

    for i in range(with_activities):
        store.add_activity(
            Activity(
                session_id=session_id,
                tool_name="Read",
                tool_output_summary=f"activity {i}",
                source_machine_id=store.machine_id,
            )
        )

    return session_id


# =============================================================================
# Test: reset_processing_state is machine-scoped
# =============================================================================


class TestResetProcessingStateMachineScoped:
    """reset_processing_state() should only reset records from the current machine."""

    def test_only_resets_own_machine(self, store_a, store_b):
        """Records from machine B should be untouched after machine A resets."""
        sid_a = _create_completed_session(
            store_a, "sess-a", with_activities=MIN_SESSION_ACTIVITIES, with_batch=True
        )
        sid_b = _create_completed_session(
            store_b, "sess-b", with_activities=MIN_SESSION_ACTIVITIES, with_batch=True
        )

        # Mark everything processed
        store_a.mark_session_processed(sid_a)
        store_a.mark_session_processed(sid_b)

        # Reset from machine A's perspective
        counts = store_a.reset_processing_state()

        # Machine A's session should be reset
        session_a = store_a.get_session(sid_a)
        assert session_a.processed is False

        # Machine B's session should still be processed
        session_b = store_a.get_session(sid_b)
        assert session_b.processed is True

        assert counts["sessions_reset"] >= 1

    def test_delete_memories_scoped(self, store_a, store_b):
        """delete_memories=True should only delete own machine's observations."""
        sid_a = _create_completed_session(store_a, "sess-a")
        sid_b = _create_completed_session(store_b, "sess-b")

        obs_a_id = str(uuid.uuid4())
        obs_b_id = str(uuid.uuid4())
        store_a.store_observation(
            StoredObservation(
                id=obs_a_id,
                session_id=sid_a,
                observation="obs from A",
                memory_type="discovery",
                source_machine_id=MACHINE_A,
            )
        )
        store_b.store_observation(
            StoredObservation(
                id=obs_b_id,
                session_id=sid_b,
                observation="obs from B",
                memory_type="discovery",
                source_machine_id=MACHINE_B,
            )
        )

        counts = store_a.reset_processing_state(delete_memories=True)
        assert counts["observations_deleted"] == 1

        # B's observation should survive
        assert store_a.get_observation(obs_b_id) is not None
        # A's observation should be gone
        assert store_a.get_observation(obs_a_id) is None


# =============================================================================
# Test: get_unembedded_observations is machine-scoped
# =============================================================================


class TestGetUnembeddedObservationsIncludesAllMachines:
    """get_unembedded_observations() should return observations from ALL machines.

    Embedding is a read/index path — imported team observations should be
    embedded into local ChromaDB so agents can search collective wisdom.
    """

    def test_returns_all_machines(self, store_a, store_b):
        sid_a = _create_completed_session(store_a, "sess-a")
        sid_b = _create_completed_session(store_b, "sess-b")

        store_a.store_observation(
            StoredObservation(
                id=str(uuid.uuid4()),
                session_id=sid_a,
                observation="obs A",
                memory_type="discovery",
                embedded=False,
                source_machine_id=MACHINE_A,
            )
        )
        store_b.store_observation(
            StoredObservation(
                id=str(uuid.uuid4()),
                session_id=sid_b,
                observation="obs B",
                memory_type="discovery",
                embedded=False,
                source_machine_id=MACHINE_B,
            )
        )

        # Either store should see BOTH unembedded observations
        unembedded = store_a.get_unembedded_observations()
        assert len(unembedded) == 2
        machines = {o.source_machine_id for o in unembedded}
        assert machines == {MACHINE_A, MACHINE_B}


# =============================================================================
# Test: get_sessions_needing_titles is machine-scoped
# =============================================================================


class TestGetSessionsNeedingTitlesMachineScoped:
    """get_sessions_needing_titles() should only return own machine's sessions."""

    def test_only_returns_own_machine(self, store_a, store_b):
        # Create sessions without titles but with batches
        _create_completed_session(store_a, "sess-a", with_batch=True)
        _create_completed_session(store_b, "sess-b", with_batch=True)

        needing_a = store_a.get_sessions_needing_titles()
        assert len(needing_a) == 1
        assert needing_a[0].id == "sess-a"

        needing_b = store_b.get_sessions_needing_titles()
        assert len(needing_b) == 1
        assert needing_b[0].id == "sess-b"


# =============================================================================
# Test: get_sessions_missing_summaries is machine-scoped
# =============================================================================


class TestGetSessionsMissingSummariesMachineScoped:
    """get_sessions_missing_summaries() should only return own machine's sessions."""

    def test_only_returns_own_machine(self, store_a, store_b):
        _create_completed_session(store_a, "sess-a", with_activities=MIN_SESSION_ACTIVITIES)
        _create_completed_session(store_b, "sess-b", with_activities=MIN_SESSION_ACTIVITIES)

        missing_a = store_a.get_sessions_missing_summaries()
        assert len(missing_a) == 1
        assert missing_a[0].id == "sess-a"

        missing_b = store_b.get_sessions_missing_summaries()
        assert len(missing_b) == 1
        assert missing_b[0].id == "sess-b"


# =============================================================================
# Test: recovery batch INSERT includes source_machine_id
# =============================================================================


class TestRecoveryBatchGetsMachineId:
    """recover_orphaned_activities() should set source_machine_id on created batches."""

    def test_recovery_batch_has_machine_id(self, store_a):
        sid = "sess-recovery"
        store_a.create_session(sid, "claude", PROJECT_ROOT)

        # Insert an orphaned activity (no batch)
        store_a.add_activity(
            Activity(
                session_id=sid,
                tool_name="Read",
                tool_output_summary="orphan",
                source_machine_id=MACHINE_A,
            )
        )
        # Null out the batch assignment to simulate orphan
        with store_a._transaction() as tx:
            tx.execute(
                "UPDATE activities SET prompt_batch_id = NULL WHERE session_id = ?",
                (sid,),
            )

        recovered = store_a.recover_orphaned_activities()
        assert recovered == 1

        # Find the recovery batch
        batches = store_a.get_session_prompt_batches(sid)
        recovery_batches = [b for b in batches if b.user_prompt == RECOVERY_BATCH_PROMPT]
        assert len(recovery_batches) == 1
        assert recovery_batches[0].source_machine_id == MACHINE_A


# =============================================================================
# Test: recover_stale_sessions is machine-scoped
# =============================================================================


class TestRecoverStaleSessionsMachineScoped:
    """recover_stale_sessions() should only recover own machine's sessions."""

    def test_only_recovers_own_machine(self, store_a, store_b):
        old_epoch = int(time.time()) - 7200  # 2 hours ago

        _create_active_session(
            store_a,
            "stale-a",
            with_activities=MIN_SESSION_ACTIVITIES,
            created_epoch=old_epoch,
        )
        _create_active_session(
            store_b,
            "stale-b",
            with_activities=MIN_SESSION_ACTIVITIES,
            created_epoch=old_epoch,
        )

        # Backdate activity timestamps so COALESCE picks up the old epoch
        with store_a._transaction() as tx:
            tx.execute(
                "UPDATE activities SET timestamp_epoch = ? WHERE session_id IN ('stale-a', 'stale-b')",
                (old_epoch,),
            )

        recovered_ids, deleted_ids = store_a.recover_stale_sessions(timeout_seconds=3600)

        # Only machine A's session should be recovered
        assert "stale-a" in recovered_ids
        assert "stale-b" not in recovered_ids
        assert "stale-b" not in deleted_ids

        # Machine B's session should still be active
        session_b = store_a.get_session("stale-b")
        assert session_b.status == "active"


# =============================================================================
# Test: get_unembedded_plans is machine-scoped
# =============================================================================


class TestGetUnembeddedPlansIncludesAllMachines:
    """get_unembedded_plans() should return plan batches from ALL machines.

    Embedding is a read/index path — imported team plans should be
    embedded into local ChromaDB so agents can search collective wisdom.
    """

    def test_returns_all_machines(self, store_a, store_b):
        sid_a = "sess-plan-a"
        sid_b = "sess-plan-b"
        store_a.create_session(sid_a, "claude", PROJECT_ROOT)
        store_b.create_session(sid_b, "claude", PROJECT_ROOT)

        # Create plan batches for each machine
        batch_a = store_a.create_prompt_batch(
            sid_a,
            "plan prompt A",
            source_type="plan",
            plan_content="Plan A content",
            plan_file_path="/tmp/plan-a.md",
        )
        batch_b = store_b.create_prompt_batch(
            sid_b,
            "plan prompt B",
            source_type="plan",
            plan_content="Plan B content",
            plan_file_path="/tmp/plan-b.md",
        )

        # Either store should see BOTH unembedded plans
        plans = store_a.get_unembedded_plans()
        plan_ids = {p.id for p in plans}
        assert batch_a.id in plan_ids
        assert batch_b.id in plan_ids


# =============================================================================
# Test: get_completed_sessions is machine-scoped
# =============================================================================


class TestGetCompletedSessionsMachineScoped:
    """get_completed_sessions() should only return own machine's sessions."""

    def test_only_returns_own_machine(self, store_a, store_b):
        _create_completed_session(store_a, "completed-a", with_activities=MIN_SESSION_ACTIVITIES)
        _create_completed_session(store_b, "completed-b", with_activities=MIN_SESSION_ACTIVITIES)

        completed_a = store_a.get_completed_sessions(min_activities=MIN_SESSION_ACTIVITIES)
        ids_a = {s.id for s in completed_a}
        assert "completed-a" in ids_a
        assert "completed-b" not in ids_a

    def test_without_min_activities_filter(self, store_a, store_b):
        _create_completed_session(store_a, "completed-a2")
        _create_completed_session(store_b, "completed-b2")

        completed_a = store_a.get_completed_sessions()
        ids_a = {s.id for s in completed_a}
        assert "completed-a2" in ids_a
        assert "completed-b2" not in ids_a


# =============================================================================
# Test: cleanup_cross_machine_pollution
# =============================================================================


class TestCleanupCrossMachinePollution:
    """cleanup_cross_machine_pollution() should remove cross-machine observations."""

    def test_removes_cross_machine_observations(self, store_a, store_b):
        """Observations referencing another machine's sessions should be deleted."""
        sid_b = _create_completed_session(store_b, "sess-b")

        # Create a "polluted" observation: machine A created an observation
        # for machine B's session (this is the bug we're cleaning up)
        polluted_id = str(uuid.uuid4())
        store_a.store_observation(
            StoredObservation(
                id=polluted_id,
                session_id=sid_b,  # B's session
                observation="cross-machine pollution",
                memory_type="discovery",
                source_machine_id=MACHINE_A,  # A created it
            )
        )

        # Create a legitimate observation: machine A's observation for A's session
        sid_a = _create_completed_session(store_a, "sess-a")
        legit_id = str(uuid.uuid4())
        store_a.store_observation(
            StoredObservation(
                id=legit_id,
                session_id=sid_a,
                observation="legitimate observation",
                memory_type="discovery",
                source_machine_id=MACHINE_A,
            )
        )

        counts = store_a.cleanup_cross_machine_pollution()

        assert counts["observations_deleted"] == 1
        # Polluted observation should be gone
        assert store_a.get_observation(polluted_id) is None
        # Legitimate observation should survive
        assert store_a.get_observation(legit_id) is not None

    def test_chromadb_cleanup(self, store_a, store_b):
        """ChromaDB entries should also be cleaned up when vector_store is provided."""
        sid_b = _create_completed_session(store_b, "sess-b-chroma")
        polluted_id = str(uuid.uuid4())
        store_a.store_observation(
            StoredObservation(
                id=polluted_id,
                session_id=sid_b,
                observation="polluted",
                memory_type="discovery",
                source_machine_id=MACHINE_A,
            )
        )

        mock_vs = MagicMock()
        counts = store_a.cleanup_cross_machine_pollution(vector_store=mock_vs)

        assert counts["observations_deleted"] == 1
        assert counts["chromadb_deleted"] == 1
        mock_vs.delete_memories.assert_called_once_with([polluted_id])

    def test_idempotent(self, store_a, store_b):
        """Running cleanup twice should be a no-op on the second run."""
        sid_b = _create_completed_session(store_b, "sess-b-idem")
        store_a.store_observation(
            StoredObservation(
                id=str(uuid.uuid4()),
                session_id=sid_b,
                observation="polluted",
                memory_type="discovery",
                source_machine_id=MACHINE_A,
            )
        )

        first = store_a.cleanup_cross_machine_pollution()
        assert first["observations_deleted"] == 1

        second = store_a.cleanup_cross_machine_pollution()
        assert second["observations_deleted"] == 0

    def test_no_pollution_is_noop(self, store_a):
        """When there's no pollution, cleanup returns zeros."""
        sid = _create_completed_session(store_a, "clean-sess")
        store_a.store_observation(
            StoredObservation(
                id=str(uuid.uuid4()),
                session_id=sid,
                observation="clean",
                memory_type="discovery",
                source_machine_id=MACHINE_A,
            )
        )

        counts = store_a.cleanup_cross_machine_pollution()
        assert counts["observations_deleted"] == 0
        assert counts["chromadb_deleted"] == 0
