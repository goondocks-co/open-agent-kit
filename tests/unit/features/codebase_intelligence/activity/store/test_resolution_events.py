"""Tests for resolution event store operations, backfill, and replay.

Covers:
- Store/model round-trips
- Content hash computation and dedup
- Backfill of existing resolutions
- Replay of unapplied events (last-writer-wins)
"""

import tempfile
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from open_agent_kit.features.codebase_intelligence.activity.store import (
    ActivityStore,
    StoredObservation,
)
from open_agent_kit.features.codebase_intelligence.activity.store.models import (
    ResolutionEvent,
)
from open_agent_kit.features.codebase_intelligence.activity.store.resolution_events import (
    backfill_resolution_events,
    count_unapplied_events,
    get_all_resolution_event_hashes,
    replay_unapplied_events,
    store_resolution_event,
)
from open_agent_kit.features.codebase_intelligence.constants import (
    OBSERVATION_STATUS_ACTIVE,
    OBSERVATION_STATUS_RESOLVED,
    OBSERVATION_STATUS_SUPERSEDED,
    RESOLUTION_EVENT_ACTION_REACTIVATED,
    RESOLUTION_EVENT_ACTION_RESOLVED,
    RESOLUTION_EVENT_ACTION_SUPERSEDED,
)

MACHINE_A = "machine_aaa111"
MACHINE_B = "machine_bbb222"
PROJECT_ROOT = "/test/project"


@pytest.fixture
def db_path():
    """Create a temporary database path."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir) / "test_resolution.db"


@pytest.fixture
def store(db_path):
    """ActivityStore for machine A."""
    s = ActivityStore(db_path, machine_id=MACHINE_A)
    yield s
    s.close()


@pytest.fixture
def store_b(db_path):
    """ActivityStore for machine B (shares same DB file)."""
    s = ActivityStore(db_path, machine_id=MACHINE_B)
    yield s
    s.close()


def _create_observation(store, obs_id=None, session_id=None, status=OBSERVATION_STATUS_ACTIVE):
    """Helper to create and store an observation."""
    obs_id = obs_id or str(uuid.uuid4())
    session_id = session_id or str(uuid.uuid4())

    # Create session first
    store.create_session(session_id, "claude", PROJECT_ROOT)

    obs = StoredObservation(
        id=obs_id,
        session_id=session_id,
        observation="Test observation",
        memory_type="gotcha",
        context="test_file.py",
        importance=5,
        source_machine_id=store.machine_id,
        status=status,
    )
    store.store_observation(obs)
    return obs_id, session_id


# =============================================================================
# Store/Model Tests
# =============================================================================


class TestStoreResolutionEvent:
    """Tests for store_resolution_event()."""

    def test_round_trip_all_fields(self, store):
        """Store an event and verify all fields via DB query."""
        obs_id, session_id = _create_observation(store)

        event_id = store_resolution_event(
            store,
            observation_id=obs_id,
            action=RESOLUTION_EVENT_ACTION_RESOLVED,
            resolved_by_session_id=session_id,
            reason="Bug was fixed",
        )

        # Query directly to verify fields
        conn = store._get_connection()
        cursor = conn.execute("SELECT * FROM resolution_events WHERE id = ?", (event_id,))
        row = cursor.fetchone()
        assert row is not None
        assert row["observation_id"] == obs_id
        assert row["action"] == RESOLUTION_EVENT_ACTION_RESOLVED
        assert row["resolved_by_session_id"] == session_id
        assert row["reason"] == "Bug was fixed"
        assert row["source_machine_id"] == MACHINE_A
        assert row["content_hash"] is not None
        assert bool(row["applied"]) is True

    def test_auto_sets_machine_id(self, store):
        """source_machine_id defaults to store.machine_id."""
        obs_id, session_id = _create_observation(store)

        event_id = store_resolution_event(
            store, observation_id=obs_id, action=RESOLUTION_EVENT_ACTION_RESOLVED
        )

        conn = store._get_connection()
        row = conn.execute(
            "SELECT source_machine_id FROM resolution_events WHERE id = ?",
            (event_id,),
        ).fetchone()
        assert row["source_machine_id"] == MACHINE_A

    def test_computes_content_hash(self, store):
        """Content hash is deterministic and non-null."""
        obs_id, _ = _create_observation(store)

        event_id = store_resolution_event(
            store, observation_id=obs_id, action=RESOLUTION_EVENT_ACTION_RESOLVED
        )

        conn = store._get_connection()
        row = conn.execute(
            "SELECT content_hash FROM resolution_events WHERE id = ?",
            (event_id,),
        ).fetchone()
        assert row["content_hash"] is not None
        assert len(row["content_hash"]) == 16  # compute_hash returns 16-char hex

    def test_duplicate_event_ignored(self, store):
        """INSERT OR IGNORE prevents duplicate event IDs."""
        obs_id, _ = _create_observation(store)

        event_id = store_resolution_event(
            store, observation_id=obs_id, action=RESOLUTION_EVENT_ACTION_RESOLVED
        )

        # Store a second event (different UUID, so won't collide on ID)
        event_id_2 = store_resolution_event(
            store, observation_id=obs_id, action=RESOLUTION_EVENT_ACTION_RESOLVED
        )

        # Both should exist (different IDs, same content_hash is fine - INSERT OR IGNORE on PK)
        assert event_id != event_id_2

    def test_get_all_hashes(self, store):
        """get_all_resolution_event_hashes returns stored hashes."""
        obs_id, _ = _create_observation(store)
        store_resolution_event(
            store, observation_id=obs_id, action=RESOLUTION_EVENT_ACTION_RESOLVED
        )

        hashes = get_all_resolution_event_hashes(store)
        assert len(hashes) >= 1

    def test_count_unapplied(self, store):
        """count_unapplied_events counts events with applied=FALSE."""
        obs_id, _ = _create_observation(store)

        # Locally-created events default to applied=TRUE
        store_resolution_event(
            store, observation_id=obs_id, action=RESOLUTION_EVENT_ACTION_RESOLVED
        )
        assert count_unapplied_events(store) == 0

        # Manually insert an unapplied event
        store_resolution_event(
            store,
            observation_id=obs_id,
            action=RESOLUTION_EVENT_ACTION_SUPERSEDED,
            applied=False,
        )
        assert count_unapplied_events(store) == 1


# =============================================================================
# Backfill Tests
# =============================================================================


class TestBackfillResolutionEvents:
    """Tests for backfill_resolution_events()."""

    def test_creates_events_for_resolved_observations(self, store):
        """Backfill creates events for already-resolved observations."""
        obs_id, session_id = _create_observation(store)

        # Resolve the observation directly (simulating pre-migration state)
        store.update_observation_status(
            obs_id,
            OBSERVATION_STATUS_RESOLVED,
            resolved_by_session_id=session_id,
            resolved_at=datetime.now(UTC).isoformat(),
        )

        count = backfill_resolution_events(store)
        assert count == 1

        hashes = get_all_resolution_event_hashes(store)
        assert len(hashes) == 1

    def test_only_creates_for_own_resolutions(self, store, store_b):
        """Each machine only backfills events for its own resolutions."""
        # Machine A creates and resolves an observation
        obs_id_a, session_a = _create_observation(store)
        store.update_observation_status(
            obs_id_a,
            OBSERVATION_STATUS_RESOLVED,
            resolved_by_session_id=session_a,
            resolved_at=datetime.now(UTC).isoformat(),
        )

        # Machine B creates and resolves its own observation
        obs_id_b, session_b = _create_observation(store_b)
        store_b.update_observation_status(
            obs_id_b,
            OBSERVATION_STATUS_RESOLVED,
            resolved_by_session_id=session_b,
            resolved_at=datetime.now(UTC).isoformat(),
        )

        # Backfill on machine A — should only create 1 event (for its own resolution)
        count_a = backfill_resolution_events(store)
        assert count_a == 1

        # Verify the event is for machine A's observation
        conn = store._get_connection()
        row = conn.execute(
            "SELECT observation_id, source_machine_id FROM resolution_events"
        ).fetchone()
        assert row["observation_id"] == obs_id_a
        assert row["source_machine_id"] == MACHINE_A

    def test_idempotent(self, store):
        """Running backfill twice is a no-op the second time."""
        obs_id, session_id = _create_observation(store)
        store.update_observation_status(
            obs_id,
            OBSERVATION_STATUS_RESOLVED,
            resolved_by_session_id=session_id,
            resolved_at=datetime.now(UTC).isoformat(),
        )

        count1 = backfill_resolution_events(store)
        count2 = backfill_resolution_events(store)

        assert count1 == 1
        assert count2 == 0

    def test_skips_active_observations(self, store):
        """Active observations produce no backfill events."""
        _create_observation(store, status=OBSERVATION_STATUS_ACTIVE)

        count = backfill_resolution_events(store)
        assert count == 0


# =============================================================================
# Replay Tests
# =============================================================================


class TestReplayUnappliedEvents:
    """Tests for replay_unapplied_events()."""

    def test_applies_to_active_observation(self, store):
        """An unapplied resolved event changes the observation status."""
        obs_id, session_id = _create_observation(store)

        # Insert an unapplied event (simulating import)
        store_resolution_event(
            store,
            observation_id=obs_id,
            action=RESOLUTION_EVENT_ACTION_RESOLVED,
            resolved_by_session_id=session_id,
            applied=False,
        )

        applied = replay_unapplied_events(store)
        assert applied == 1

        # Verify observation status changed
        obs = store.get_observation(obs_id)
        assert obs is not None
        assert obs.status == OBSERVATION_STATUS_RESOLVED

    def test_skips_missing_observation(self, store):
        """Events targeting non-existent observations stay unapplied."""
        missing_obs_id = str(uuid.uuid4())

        store_resolution_event(
            store,
            observation_id=missing_obs_id,
            action=RESOLUTION_EVENT_ACTION_RESOLVED,
            applied=False,
        )

        applied = replay_unapplied_events(store)
        assert applied == 0
        assert count_unapplied_events(store) == 1

    def test_last_writer_wins_newer(self, store):
        """A newer event overwrites the current observation state."""
        obs_id, session_id = _create_observation(store)

        # Resolve the observation with an old timestamp
        old_time = datetime.now(UTC) - timedelta(hours=1)
        store.update_observation_status(
            obs_id,
            OBSERVATION_STATUS_RESOLVED,
            resolved_by_session_id=session_id,
            resolved_at=old_time.isoformat(),
        )

        # Insert a newer supersede event (unapplied)
        new_supersede_id = str(uuid.uuid4())
        store_resolution_event(
            store,
            observation_id=obs_id,
            action=RESOLUTION_EVENT_ACTION_SUPERSEDED,
            superseded_by=new_supersede_id,
            applied=False,
            created_at=datetime.now(UTC),
        )

        applied = replay_unapplied_events(store)
        assert applied == 1

        obs = store.get_observation(obs_id)
        assert obs is not None
        assert obs.status == OBSERVATION_STATUS_SUPERSEDED

    def test_last_writer_wins_stale(self, store):
        """An older event is skipped when observation has newer resolution."""
        obs_id, session_id = _create_observation(store)

        # Resolve the observation with a recent timestamp
        recent_time = datetime.now(UTC)
        store.update_observation_status(
            obs_id,
            OBSERVATION_STATUS_RESOLVED,
            resolved_by_session_id=session_id,
            resolved_at=recent_time.isoformat(),
        )

        # Insert an older event (unapplied) — should be skipped
        old_time = datetime.now(UTC) - timedelta(hours=2)
        store_resolution_event(
            store,
            observation_id=obs_id,
            action=RESOLUTION_EVENT_ACTION_SUPERSEDED,
            applied=False,
            created_at=old_time,
        )

        applied = replay_unapplied_events(store)
        # Should still be marked applied (skipped but acknowledged)
        assert applied == 1

        # Status should remain resolved (not overwritten to superseded)
        obs = store.get_observation(obs_id)
        assert obs is not None
        assert obs.status == OBSERVATION_STATUS_RESOLVED

    def test_updates_chromadb(self, store):
        """Replay updates ChromaDB when vector_store is provided."""
        obs_id, session_id = _create_observation(store)

        # Mark observation as embedded
        store.mark_observation_embedded(obs_id)

        store_resolution_event(
            store,
            observation_id=obs_id,
            action=RESOLUTION_EVENT_ACTION_RESOLVED,
            resolved_by_session_id=session_id,
            applied=False,
        )

        mock_vector_store = MagicMock()
        applied = replay_unapplied_events(store, vector_store=mock_vector_store)
        assert applied == 1
        mock_vector_store.update_memory_status.assert_called_once_with(
            obs_id, OBSERVATION_STATUS_RESOLVED
        )

    def test_marks_events_applied(self, store):
        """After replay, events are marked applied=TRUE."""
        obs_id, _ = _create_observation(store)

        store_resolution_event(
            store,
            observation_id=obs_id,
            action=RESOLUTION_EVENT_ACTION_RESOLVED,
            applied=False,
        )
        assert count_unapplied_events(store) == 1

        replay_unapplied_events(store)
        assert count_unapplied_events(store) == 0

    def test_idempotent(self, store):
        """Second replay is a no-op."""
        obs_id, _ = _create_observation(store)

        store_resolution_event(
            store,
            observation_id=obs_id,
            action=RESOLUTION_EVENT_ACTION_RESOLVED,
            applied=False,
        )

        applied1 = replay_unapplied_events(store)
        applied2 = replay_unapplied_events(store)

        assert applied1 == 1
        assert applied2 == 0

    def test_reactivation_clears_resolution(self, store):
        """A reactivated event sets status back to active."""
        obs_id, session_id = _create_observation(store)

        # First resolve it
        store.update_observation_status(
            obs_id,
            OBSERVATION_STATUS_RESOLVED,
            resolved_by_session_id=session_id,
            resolved_at=(datetime.now(UTC) - timedelta(hours=1)).isoformat(),
        )

        # Then reactivate via unapplied event
        store_resolution_event(
            store,
            observation_id=obs_id,
            action=RESOLUTION_EVENT_ACTION_REACTIVATED,
            applied=False,
        )

        applied = replay_unapplied_events(store)
        assert applied == 1

        obs = store.get_observation(obs_id)
        assert obs is not None
        assert obs.status == OBSERVATION_STATUS_ACTIVE


# =============================================================================
# ResolutionEvent Model Tests
# =============================================================================


class TestResolutionEventModel:
    """Tests for the ResolutionEvent dataclass."""

    def test_to_row_from_row_roundtrip(self, store):
        """to_row() and from_row() preserve all fields."""
        event = ResolutionEvent(
            id=str(uuid.uuid4()),
            observation_id=str(uuid.uuid4()),
            action=RESOLUTION_EVENT_ACTION_SUPERSEDED,
            resolved_by_session_id="session-123",
            superseded_by="obs-456",
            reason="Newer implementation",
            created_at=datetime.now(UTC),
            source_machine_id=MACHINE_A,
            applied=True,
        )

        row = event.to_row()
        assert row["content_hash"] is not None

        # Store and retrieve via DB to test from_row with sqlite3.Row
        conn = store._get_connection()
        conn.execute(
            """
            INSERT INTO resolution_events
            (id, observation_id, action, resolved_by_session_id, superseded_by,
             reason, created_at, created_at_epoch, source_machine_id, content_hash, applied)
            VALUES (:id, :observation_id, :action, :resolved_by_session_id, :superseded_by,
                    :reason, :created_at, :created_at_epoch, :source_machine_id,
                    :content_hash, :applied)
            """,
            row,
        )
        conn.commit()

        cursor = conn.execute("SELECT * FROM resolution_events WHERE id = ?", (event.id,))
        db_row = cursor.fetchone()
        restored = ResolutionEvent.from_row(db_row)

        assert restored.id == event.id
        assert restored.observation_id == event.observation_id
        assert restored.action == event.action
        assert restored.resolved_by_session_id == event.resolved_by_session_id
        assert restored.superseded_by == event.superseded_by
        assert restored.reason == event.reason
        assert restored.source_machine_id == event.source_machine_id
        assert restored.applied == event.applied
        assert restored.content_hash == event.content_hash
