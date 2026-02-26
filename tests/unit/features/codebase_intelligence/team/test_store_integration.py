"""Tests for team outbox integration with the activity store.

Verifies that store operations (observations, sessions, resolution events)
correctly enqueue outbox events when team_outbox_enabled is True.
"""

import json

import pytest

from open_agent_kit.features.codebase_intelligence.activity.store.core import ActivityStore
from open_agent_kit.features.codebase_intelligence.activity.store.models import (
    StoredObservation,
)
from open_agent_kit.features.codebase_intelligence.constants.team import (
    TEAM_EVENT_OBSERVATION_RESOLVED,
    TEAM_EVENT_OBSERVATION_UPSERT,
    TEAM_EVENT_SESSION_SUMMARY_UPDATE,
    TEAM_EVENT_SESSION_UPSERT,
    TEAM_OUTBOX_STATUS_PENDING,
)

TEST_MACHINE_ID = "test-machine-integration"
TEST_PROJECT_ROOT = "/tmp/test-project"
TEST_SESSION_ID = "session-integration-001"
TEST_AGENT = "claude"


@pytest.fixture
def store(tmp_path):
    """Create a real ActivityStore for integration testing."""
    db_path = tmp_path / ".oak" / "ci" / "activities.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return ActivityStore(db_path, machine_id=TEST_MACHINE_ID)


def _get_outbox_rows(store):
    """Helper to fetch all outbox rows."""
    conn = store._get_connection()
    cursor = conn.execute("SELECT * FROM team_outbox ORDER BY id")
    return cursor.fetchall()


def _make_observation(session_id=TEST_SESSION_ID, obs_id="obs-int-1"):
    """Create a test StoredObservation."""
    return StoredObservation(
        id=obs_id,
        session_id=session_id,
        observation="Test observation for integration",
        memory_type="pattern",
        context="test context",
        tags=["test"],
        importance=5,
    )


# ---- Observation tests ----


def test_store_observation_with_outbox_enabled(store):
    """store_observation should create an outbox row when team_outbox_enabled=True."""
    # First create a session so foreign key doesn't fail
    from open_agent_kit.features.codebase_intelligence.activity.store.sessions.crud import (
        create_session,
    )

    create_session(store, TEST_SESSION_ID, TEST_AGENT, TEST_PROJECT_ROOT)

    store.team_outbox_enabled = True
    obs = _make_observation()
    store.store_observation(obs)

    rows = _get_outbox_rows(store)
    assert len(rows) >= 1  # At least observation event (session event may also exist)

    # Find the observation event
    obs_rows = [r for r in rows if r["event_type"] == TEAM_EVENT_OBSERVATION_UPSERT]
    assert len(obs_rows) == 1

    row = obs_rows[0]
    assert row["status"] == TEAM_OUTBOX_STATUS_PENDING
    assert row["source_machine_id"] == TEST_MACHINE_ID

    payload = json.loads(row["payload"])
    assert payload["id"] == obs.id
    assert payload["memory_type"] == "pattern"


def test_store_observation_with_outbox_disabled(store):
    """store_observation should NOT create an outbox row when team_outbox_enabled=False."""
    from open_agent_kit.features.codebase_intelligence.activity.store.sessions.crud import (
        create_session,
    )

    create_session(store, TEST_SESSION_ID, TEST_AGENT, TEST_PROJECT_ROOT)

    store.team_outbox_enabled = False
    obs = _make_observation()
    store.store_observation(obs)

    rows = _get_outbox_rows(store)
    obs_rows = [r for r in rows if r["event_type"] == TEAM_EVENT_OBSERVATION_UPSERT]
    assert len(obs_rows) == 0


# ---- Session tests ----


def test_create_session_with_outbox_enabled(store):
    """create_session should enqueue a session_upsert event when outbox is enabled."""
    from open_agent_kit.features.codebase_intelligence.activity.store.sessions.crud import (
        create_session,
    )

    store.team_outbox_enabled = True
    create_session(store, "session-outbox-1", TEST_AGENT, TEST_PROJECT_ROOT)

    rows = _get_outbox_rows(store)
    session_rows = [r for r in rows if r["event_type"] == TEAM_EVENT_SESSION_UPSERT]
    assert len(session_rows) == 1

    payload = json.loads(session_rows[0]["payload"])
    assert payload["id"] == "session-outbox-1"
    assert payload["agent"] == TEST_AGENT


def test_create_session_with_outbox_disabled(store):
    """create_session should NOT enqueue when outbox is disabled."""
    from open_agent_kit.features.codebase_intelligence.activity.store.sessions.crud import (
        create_session,
    )

    store.team_outbox_enabled = False
    create_session(store, "session-no-outbox", TEST_AGENT, TEST_PROJECT_ROOT)

    rows = _get_outbox_rows(store)
    session_rows = [r for r in rows if r["event_type"] == TEAM_EVENT_SESSION_UPSERT]
    assert len(session_rows) == 0


# ---- Session summary tests ----


def test_update_session_summary_with_outbox_enabled(store):
    """update_session_summary should enqueue a summary_update event."""
    from open_agent_kit.features.codebase_intelligence.activity.store.sessions.crud import (
        create_session,
        update_session_summary,
    )

    store.team_outbox_enabled = True
    create_session(store, "session-summary-1", TEST_AGENT, TEST_PROJECT_ROOT)
    update_session_summary(store, "session-summary-1", "This session fixed auth bugs")

    rows = _get_outbox_rows(store)
    summary_rows = [r for r in rows if r["event_type"] == TEAM_EVENT_SESSION_SUMMARY_UPDATE]
    assert len(summary_rows) == 1

    payload = json.loads(summary_rows[0]["payload"])
    assert payload["session_id"] == "session-summary-1"
    assert payload["summary"] == "This session fixed auth bugs"


# ---- Resolution event tests ----


def test_resolution_event_with_outbox_enabled(store):
    """store_resolution_event should enqueue an observation_resolved event."""
    from open_agent_kit.features.codebase_intelligence.activity.store.sessions.crud import (
        create_session,
    )

    store.team_outbox_enabled = True
    create_session(store, TEST_SESSION_ID, TEST_AGENT, TEST_PROJECT_ROOT)

    # Create an observation first
    obs = _make_observation()
    store.store_observation(obs)

    # Now resolve it
    from open_agent_kit.features.codebase_intelligence.activity.store.resolution_events import (
        store_resolution_event,
    )

    store_resolution_event(
        store,
        observation_id=obs.id,
        action="resolved",
        resolved_by_session_id=TEST_SESSION_ID,
        reason="Bug was fixed",
    )

    rows = _get_outbox_rows(store)
    resolved_rows = [r for r in rows if r["event_type"] == TEAM_EVENT_OBSERVATION_RESOLVED]
    assert len(resolved_rows) == 1

    payload = json.loads(resolved_rows[0]["payload"])
    assert payload["observation_id"] == obs.id
    assert payload["action"] == "resolved"


def test_resolution_event_with_outbox_disabled(store):
    """store_resolution_event should NOT enqueue when outbox is disabled."""
    from open_agent_kit.features.codebase_intelligence.activity.store.sessions.crud import (
        create_session,
    )

    store.team_outbox_enabled = False
    create_session(store, TEST_SESSION_ID, TEST_AGENT, TEST_PROJECT_ROOT)

    obs = _make_observation()
    store.store_observation(obs)

    from open_agent_kit.features.codebase_intelligence.activity.store.resolution_events import (
        store_resolution_event,
    )

    store_resolution_event(
        store,
        observation_id=obs.id,
        action="resolved",
        resolved_by_session_id=TEST_SESSION_ID,
    )

    rows = _get_outbox_rows(store)
    resolved_rows = [r for r in rows if r["event_type"] == TEAM_EVENT_OBSERVATION_RESOLVED]
    assert len(resolved_rows) == 0


# ---- Atomicity test ----


def test_outbox_and_observation_atomic(store):
    """Both observation and outbox write should succeed or fail together."""
    from open_agent_kit.features.codebase_intelligence.activity.store.sessions.crud import (
        create_session,
    )

    store.team_outbox_enabled = True
    create_session(store, TEST_SESSION_ID, TEST_AGENT, TEST_PROJECT_ROOT)

    obs = _make_observation()
    store.store_observation(obs)

    # Verify both the observation AND the outbox row exist
    conn = store._get_connection()

    obs_cursor = conn.execute("SELECT id FROM memory_observations WHERE id = ?", (obs.id,))
    assert obs_cursor.fetchone() is not None

    outbox_cursor = conn.execute(
        "SELECT id FROM team_outbox WHERE event_type = ?",
        (TEAM_EVENT_OBSERVATION_UPSERT,),
    )
    assert outbox_cursor.fetchone() is not None
