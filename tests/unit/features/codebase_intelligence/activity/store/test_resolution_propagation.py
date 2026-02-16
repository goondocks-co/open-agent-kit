"""Integration tests for cross-machine resolution propagation.

Uses two ActivityStore instances sharing a database to simulate
multi-machine backup/restore scenarios. Verifies the full cycle:
create observation → resolve → export → import → replay.
"""

import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from open_agent_kit.features.codebase_intelligence.activity.store import (
    ActivityStore,
    StoredObservation,
)
from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
    export_to_sql,
    import_from_sql_with_dedup,
)
from open_agent_kit.features.codebase_intelligence.activity.store.resolution_events import (
    count_unapplied_events,
    replay_unapplied_events,
    store_resolution_event,
)
from open_agent_kit.features.codebase_intelligence.constants import (
    OBSERVATION_STATUS_ACTIVE,
    OBSERVATION_STATUS_RESOLVED,
    OBSERVATION_STATUS_SUPERSEDED,
    RESOLUTION_EVENT_ACTION_RESOLVED,
    RESOLUTION_EVENT_ACTION_SUPERSEDED,
)

MACHINE_A = "machine_aaa111"
MACHINE_B = "machine_bbb222"
PROJECT_ROOT = "/test/project"


@pytest.fixture
def tmp_dir():
    """Shared temp dir for databases and backups."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def store_a(tmp_dir):
    """ActivityStore for machine A."""
    s = ActivityStore(tmp_dir / "test.db", machine_id=MACHINE_A)
    yield s
    s.close()


@pytest.fixture
def store_b(tmp_dir):
    """ActivityStore for machine B (same DB file)."""
    s = ActivityStore(tmp_dir / "test.db", machine_id=MACHINE_B)
    yield s
    s.close()


def _create_observation(store, obs_id=None, session_id=None):
    """Helper to create an active observation."""
    obs_id = obs_id or str(uuid.uuid4())
    session_id = session_id or str(uuid.uuid4())

    store.create_session(session_id, "claude", PROJECT_ROOT)
    obs = StoredObservation(
        id=obs_id,
        session_id=session_id,
        observation="Test gotcha: API fails on empty input",
        memory_type="gotcha",
        context="api/handler.py",
        importance=7,
        source_machine_id=store.machine_id,
    )
    store.store_observation(obs)
    return obs_id, session_id


class TestFullPropagationCycle:
    """End-to-end test: A creates obs, B resolves, A imports from B → obs resolved on A."""

    def test_resolution_propagates_via_backup(self, store_a, store_b, tmp_dir):
        """Full cycle: create → resolve → export → import → replay."""
        # 1. Machine A creates an observation
        obs_id, session_a = _create_observation(store_a)

        # 2. Machine B also has the observation (simulating prior backup import)
        #    It already exists in the shared DB since they share the same file

        # 3. Machine B resolves the observation
        session_b = str(uuid.uuid4())
        store_b.create_session(session_b, "claude", PROJECT_ROOT)

        resolved_at = datetime.now(UTC).isoformat()
        store_b.update_observation_status(
            obs_id,
            OBSERVATION_STATUS_RESOLVED,
            resolved_by_session_id=session_b,
            resolved_at=resolved_at,
        )

        # Machine B emits a resolution event (as the hook would)
        store_resolution_event(
            store_b,
            observation_id=obs_id,
            action=RESOLUTION_EVENT_ACTION_RESOLVED,
            resolved_by_session_id=session_b,
        )

        # 4. Machine B exports backup
        backup_path = tmp_dir / f"{MACHINE_B}.sql"
        export_to_sql(store_b, backup_path)

        # 5. Verify the export contains resolution_events
        content = backup_path.read_text()
        assert "resolution_events" in content

        # 6. Create a fresh DB for machine A to simulate separate machine
        db_a_path = tmp_dir / "machine_a.db"
        fresh_store_a = ActivityStore(db_a_path, machine_id=MACHINE_A)
        try:
            # Re-create the observation on A (it was originally A's)
            _create_observation(fresh_store_a, obs_id=obs_id, session_id=session_a)

            # Verify it's still active
            obs = fresh_store_a.get_observation(obs_id)
            assert obs is not None
            assert obs.status == OBSERVATION_STATUS_ACTIVE

            # 7. Machine A imports B's backup
            result = import_from_sql_with_dedup(fresh_store_a, backup_path)
            assert result.resolution_events_imported >= 1

            # 8. Replay unapplied events
            applied = replay_unapplied_events(fresh_store_a)
            assert applied >= 1

            # 9. Verify observation is now resolved on A
            obs = fresh_store_a.get_observation(obs_id)
            assert obs is not None
            assert obs.status == OBSERVATION_STATUS_RESOLVED
        finally:
            fresh_store_a.close()


class TestAutoResolvePropagation:
    """B auto-supersedes A's observation, propagates back to A."""

    def test_supersede_propagates(self, store_a, store_b, tmp_dir):
        """Auto-supersede on B creates event that propagates to A."""
        # A creates gotcha
        obs_id_old, session_a = _create_observation(store_a)

        # B creates new observation that supersedes A's
        new_obs_id, session_b = _create_observation(store_b)

        # B supersedes A's observation (as auto_resolve would do)
        resolved_at = datetime.now(UTC).isoformat()
        store_b.update_observation_status(
            obs_id_old,
            OBSERVATION_STATUS_SUPERSEDED,
            resolved_by_session_id=session_b,
            resolved_at=resolved_at,
            superseded_by=new_obs_id,
        )
        store_resolution_event(
            store_b,
            observation_id=obs_id_old,
            action=RESOLUTION_EVENT_ACTION_SUPERSEDED,
            resolved_by_session_id=session_b,
            superseded_by=new_obs_id,
        )

        # Export B, import into fresh A
        backup_path = tmp_dir / f"{MACHINE_B}.sql"
        export_to_sql(store_b, backup_path)

        db_a_path = tmp_dir / "machine_a_fresh.db"
        fresh_a = ActivityStore(db_a_path, machine_id=MACHINE_A)
        try:
            _create_observation(fresh_a, obs_id=obs_id_old, session_id=session_a)

            import_from_sql_with_dedup(fresh_a, backup_path)
            replay_unapplied_events(fresh_a)

            obs = fresh_a.get_observation(obs_id_old)
            assert obs is not None
            assert obs.status == OBSERVATION_STATUS_SUPERSEDED
            assert obs.superseded_by == new_obs_id
        finally:
            fresh_a.close()


class TestDeferredReplay:
    """Event imported before observation, replay deferred."""

    def test_deferred_then_successful(self, store_a, tmp_dir):
        """Event stays unapplied when observation missing, succeeds after observation arrives."""
        obs_id = str(uuid.uuid4())

        # Insert unapplied event for an observation that doesn't exist yet
        store_resolution_event(
            store_a,
            observation_id=obs_id,
            action=RESOLUTION_EVENT_ACTION_RESOLVED,
            applied=False,
        )

        # First replay — observation doesn't exist, event stays unapplied
        applied = replay_unapplied_events(store_a)
        assert applied == 0
        assert count_unapplied_events(store_a) == 1

        # Now create the observation
        _create_observation(store_a, obs_id=obs_id)

        # Second replay — should succeed
        applied = replay_unapplied_events(store_a)
        assert applied == 1
        assert count_unapplied_events(store_a) == 0

        obs = store_a.get_observation(obs_id)
        assert obs is not None
        assert obs.status == OBSERVATION_STATUS_RESOLVED


class TestBackupExportImport:
    """Tests for resolution_events in backup export/import."""

    def test_export_includes_resolution_events(self, store_a, tmp_dir):
        """Exported SQL file contains resolution_events INSERT statements."""
        obs_id, session_id = _create_observation(store_a)
        store_resolution_event(
            store_a,
            observation_id=obs_id,
            action=RESOLUTION_EVENT_ACTION_RESOLVED,
            resolved_by_session_id=session_id,
        )

        backup_path = tmp_dir / f"{MACHINE_A}.sql"
        count = export_to_sql(store_a, backup_path)
        assert count > 0

        content = backup_path.read_text()
        assert "INSERT INTO resolution_events" in content

    def test_export_only_own_events(self, store_a, store_b, tmp_dir):
        """Each machine only exports its own resolution events."""
        obs_id, _ = _create_observation(store_a)

        # Machine A creates an event
        store_resolution_event(
            store_a,
            observation_id=obs_id,
            action=RESOLUTION_EVENT_ACTION_RESOLVED,
        )

        # Machine B creates an event for the same observation
        store_resolution_event(
            store_b,
            observation_id=obs_id,
            action=RESOLUTION_EVENT_ACTION_SUPERSEDED,
        )

        # Export from A should only have A's event
        backup_a = tmp_dir / f"{MACHINE_A}.sql"
        export_to_sql(store_a, backup_a)

        content = backup_a.read_text()
        assert MACHINE_A in content
        # Count INSERT INTO resolution_events lines
        re_lines = [
            line for line in content.split("\n") if line.startswith("INSERT INTO resolution_events")
        ]
        assert len(re_lines) == 1

    def test_import_marks_events_unapplied(self, store_a, tmp_dir):
        """Imported resolution events have applied=FALSE."""
        # Create and export from A
        obs_id, session_id = _create_observation(store_a)
        store_resolution_event(
            store_a,
            observation_id=obs_id,
            action=RESOLUTION_EVENT_ACTION_RESOLVED,
            resolved_by_session_id=session_id,
        )

        backup_path = tmp_dir / f"{MACHINE_A}.sql"
        export_to_sql(store_a, backup_path)

        # Import into a fresh store (machine B)
        db_b_path = tmp_dir / "fresh_b.db"
        fresh_b = ActivityStore(db_b_path, machine_id=MACHINE_B)
        try:
            result = import_from_sql_with_dedup(fresh_b, backup_path)
            assert result.resolution_events_imported >= 1

            # Verify they're marked unapplied
            assert count_unapplied_events(fresh_b) >= 1
        finally:
            fresh_b.close()

    def test_import_dedup_by_content_hash(self, store_a, tmp_dir):
        """Duplicate resolution events are skipped on re-import."""
        obs_id, session_id = _create_observation(store_a)
        store_resolution_event(
            store_a,
            observation_id=obs_id,
            action=RESOLUTION_EVENT_ACTION_RESOLVED,
        )

        backup_path = tmp_dir / f"{MACHINE_A}.sql"
        export_to_sql(store_a, backup_path)

        db_b_path = tmp_dir / "fresh_b.db"
        fresh_b = ActivityStore(db_b_path, machine_id=MACHINE_B)
        try:
            # First import
            result1 = import_from_sql_with_dedup(fresh_b, backup_path)
            imported1 = result1.resolution_events_imported

            # Second import — should skip
            result2 = import_from_sql_with_dedup(fresh_b, backup_path)
            assert result2.resolution_events_skipped >= imported1
            assert result2.resolution_events_imported == 0
        finally:
            fresh_b.close()
