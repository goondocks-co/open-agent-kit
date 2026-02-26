"""Tests for TeamEventApplier."""

import uuid

import pytest

from open_agent_kit.features.codebase_intelligence.activity.store.core import ActivityStore
from open_agent_kit.features.codebase_intelligence.constants.team import (
    TEAM_EVENT_OBSERVATION_RESOLVED,
    TEAM_EVENT_OBSERVATION_UPSERT,
    TEAM_EVENT_SESSION_SUMMARY_UPDATE,
    TEAM_EVENT_SESSION_UPSERT,
)
from open_agent_kit.features.codebase_intelligence.team.protocol import TeamEvent
from open_agent_kit.features.codebase_intelligence.team.pull.applier import (
    ApplyResult,
    TeamEventApplier,
)

TEST_MACHINE_ID = "test-machine-applier"
REMOTE_MACHINE_ID = "remote-machine-001"
TEST_PROJECT_ID = "myproject:abc12345"


@pytest.fixture
def store(tmp_path):
    """Create a real ActivityStore with a temp database."""
    db_path = tmp_path / ".oak" / "ci" / "activities.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return ActivityStore(db_path, machine_id=TEST_MACHINE_ID)


@pytest.fixture
def applier(store):
    """Create a TeamEventApplier."""
    return TeamEventApplier(store)


def _make_event(event_type, payload, source_machine_id=REMOTE_MACHINE_ID, content_hash=None):
    """Helper to build a TeamEvent."""
    return TeamEvent(
        event_type=event_type,
        payload=payload,
        source_machine_id=source_machine_id,
        content_hash=content_hash or f"hash-{uuid.uuid4().hex[:8]}",
        schema_version=9,
        timestamp="2026-02-26T10:00:00+00:00",
        project_id=TEST_PROJECT_ID,
    )


def _insert_session(store, session_id="sess-remote-1"):
    """Insert a session directly for FK satisfaction."""
    conn = store._get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO sessions (id, agent, project_root, started_at, "
        "created_at_epoch, source_machine_id) VALUES (?, ?, ?, ?, ?, ?)",
        (session_id, "unknown", "/tmp", "2026-02-26T10:00:00", 1740000000, REMOTE_MACHINE_ID),
    )
    conn.commit()


# --------------------------------------------------------------------------
# Observation upsert tests
# --------------------------------------------------------------------------


def test_apply_observation_upsert_new(applier, store):
    """New observation should be inserted."""
    obs_id = f"obs-{uuid.uuid4().hex[:8]}"
    payload = {
        "id": obs_id,
        "session_id": "sess-remote-1",
        "observation": "Found a bug in parser",
        "memory_type": "issue",
        "context": "src/parser.py",
        "created_at": "2026-02-26T10:00:00",
        "created_at_epoch": 1740000000,
        "content_hash": "unique-hash-001",
        "source_machine_id": REMOTE_MACHINE_ID,
    }
    _insert_session(store)
    event = _make_event(TEAM_EVENT_OBSERVATION_UPSERT, payload, content_hash="unique-hash-001")

    result = applier._apply_event(event)
    assert result is True

    # Verify inserted
    conn = store._get_connection()
    row = conn.execute(
        "SELECT id, observation, embedded FROM memory_observations WHERE id = ?", (obs_id,)
    ).fetchone()
    assert row is not None
    assert row[1] == "Found a bug in parser"
    assert row[2] == 0  # embedded=False


def test_apply_observation_upsert_dedup(applier, store):
    """Duplicate content_hash should be skipped."""
    obs_id = f"obs-{uuid.uuid4().hex[:8]}"
    content_hash = "dedup-hash-001"
    payload = {
        "id": obs_id,
        "session_id": "sess-remote-1",
        "observation": "Found a bug in parser",
        "memory_type": "issue",
        "context": "src/parser.py",
        "created_at": "2026-02-26T10:00:00",
        "created_at_epoch": 1740000000,
        "content_hash": content_hash,
        "source_machine_id": REMOTE_MACHINE_ID,
    }
    _insert_session(store)

    # First insert
    event1 = _make_event(TEAM_EVENT_OBSERVATION_UPSERT, payload, content_hash=content_hash)
    result1 = applier._apply_event(event1)
    assert result1 is True

    # Second insert with same hash -- should be skipped
    payload2 = dict(payload, id=f"obs-{uuid.uuid4().hex[:8]}")
    event2 = _make_event(TEAM_EVENT_OBSERVATION_UPSERT, payload2, content_hash=content_hash)
    result2 = applier._apply_event(event2)
    assert result2 is False


def test_apply_observation_sets_embedded_false(applier, store):
    """Imported observations must have embedded=False for ChromaDB re-embedding."""
    obs_id = f"obs-{uuid.uuid4().hex[:8]}"
    payload = {
        "id": obs_id,
        "session_id": "sess-remote-1",
        "observation": "Needs re-embedding",
        "memory_type": "pattern",
        "created_at": "2026-02-26T10:00:00",
        "created_at_epoch": 1740000000,
        "content_hash": f"hash-{uuid.uuid4().hex[:8]}",
        "source_machine_id": REMOTE_MACHINE_ID,
    }
    _insert_session(store)
    event = _make_event(TEAM_EVENT_OBSERVATION_UPSERT, payload)
    applier._apply_event(event)

    conn = store._get_connection()
    row = conn.execute(
        "SELECT embedded FROM memory_observations WHERE id = ?", (obs_id,)
    ).fetchone()
    assert row[0] == 0


# --------------------------------------------------------------------------
# Observation resolved tests
# --------------------------------------------------------------------------


def test_apply_observation_resolved_new(applier, store):
    """Resolution event should be inserted and observation status updated."""
    obs_id = f"obs-{uuid.uuid4().hex[:8]}"
    _insert_session(store)

    # First insert the observation
    obs_payload = {
        "id": obs_id,
        "session_id": "sess-remote-1",
        "observation": "Bug to resolve",
        "memory_type": "issue",
        "created_at": "2026-02-26T10:00:00",
        "created_at_epoch": 1740000000,
        "content_hash": f"obs-hash-{uuid.uuid4().hex[:8]}",
        "source_machine_id": REMOTE_MACHINE_ID,
    }
    obs_event = _make_event(TEAM_EVENT_OBSERVATION_UPSERT, obs_payload)
    applier._apply_event(obs_event)

    # Now resolve it
    res_id = f"res-{uuid.uuid4().hex[:8]}"
    res_hash = f"res-hash-{uuid.uuid4().hex[:8]}"
    res_payload = {
        "id": res_id,
        "observation_id": obs_id,
        "action": "resolved",
        "resolved_by_session_id": "sess-resolver",
        "reason": "Fixed in latest commit",
        "created_at": "2026-02-26T11:00:00",
        "created_at_epoch": 1740003600,
        "source_machine_id": REMOTE_MACHINE_ID,
        "content_hash": res_hash,
    }
    res_event = _make_event(TEAM_EVENT_OBSERVATION_RESOLVED, res_payload, content_hash=res_hash)
    result = applier._apply_event(res_event)
    assert result is True

    # Verify resolution event inserted with applied=False
    conn = store._get_connection()
    row = conn.execute("SELECT applied FROM resolution_events WHERE id = ?", (res_id,)).fetchone()
    assert row is not None
    assert row[0] == 0  # applied=False

    # Verify observation status updated
    obs_row = conn.execute(
        "SELECT status FROM memory_observations WHERE id = ?", (obs_id,)
    ).fetchone()
    assert obs_row[0] == "resolved"


def test_apply_observation_resolved_dedup(applier, store):
    """Duplicate resolution content_hash should be skipped."""
    res_hash = "dedup-res-hash-001"
    _insert_session(store)

    res_payload = {
        "id": f"res-{uuid.uuid4().hex[:8]}",
        "observation_id": "obs-nonexistent",
        "action": "resolved",
        "created_at": "2026-02-26T11:00:00",
        "created_at_epoch": 1740003600,
        "source_machine_id": REMOTE_MACHINE_ID,
        "content_hash": res_hash,
    }

    event1 = _make_event(TEAM_EVENT_OBSERVATION_RESOLVED, res_payload, content_hash=res_hash)
    result1 = applier._apply_event(event1)
    assert result1 is True

    # Second with same hash
    res_payload2 = dict(res_payload, id=f"res-{uuid.uuid4().hex[:8]}")
    event2 = _make_event(TEAM_EVENT_OBSERVATION_RESOLVED, res_payload2, content_hash=res_hash)
    result2 = applier._apply_event(event2)
    assert result2 is False


# --------------------------------------------------------------------------
# Session upsert tests
# --------------------------------------------------------------------------


def test_apply_session_upsert(applier, store):
    """Session upsert should insert a new session."""
    session_id = f"sess-{uuid.uuid4().hex[:8]}"
    payload = {
        "id": session_id,
        "agent": "claude",
        "project_root": "/home/user/project",
        "started_at": "2026-02-26T10:00:00",
        "status": "completed",
        "prompt_count": 5,
        "created_at_epoch": 1740000000,
        "source_machine_id": REMOTE_MACHINE_ID,
        "summary": "Refactored the parser module",
    }
    event = _make_event(TEAM_EVENT_SESSION_UPSERT, payload)
    result = applier._apply_event(event)
    assert result is True

    conn = store._get_connection()
    row = conn.execute(
        "SELECT id, agent, summary, summary_embedded FROM sessions WHERE id = ?",
        (session_id,),
    ).fetchone()
    assert row is not None
    assert row[1] == "claude"
    assert row[2] == "Refactored the parser module"
    assert row[3] == 0  # summary_embedded=0


def test_apply_session_upsert_missing_id(applier, store):
    """Session upsert without ID should be skipped."""
    payload = {
        "agent": "claude",
        "project_root": "/home/user/project",
        "started_at": "2026-02-26T10:00:00",
        "created_at_epoch": 1740000000,
    }
    event = _make_event(TEAM_EVENT_SESSION_UPSERT, payload)
    result = applier._apply_event(event)
    assert result is False


# --------------------------------------------------------------------------
# Session summary update tests
# --------------------------------------------------------------------------


def test_apply_session_summary_update(applier, store):
    """Session summary update should update existing session."""
    session_id = f"sess-{uuid.uuid4().hex[:8]}"
    # First create the session
    sess_payload = {
        "id": session_id,
        "agent": "claude",
        "project_root": "/tmp",
        "started_at": "2026-02-26T10:00:00",
        "created_at_epoch": 1740000000,
        "source_machine_id": REMOTE_MACHINE_ID,
    }
    sess_event = _make_event(TEAM_EVENT_SESSION_UPSERT, sess_payload)
    applier._apply_event(sess_event)

    # Update summary
    summary_payload = {
        "session_id": session_id,
        "summary": "New summary after analysis",
        "summary_updated_at": 1740007200,
    }
    summary_event = _make_event(TEAM_EVENT_SESSION_SUMMARY_UPDATE, summary_payload)
    result = applier._apply_event(summary_event)
    assert result is True

    conn = store._get_connection()
    row = conn.execute(
        "SELECT summary, summary_embedded FROM sessions WHERE id = ?",
        (session_id,),
    ).fetchone()
    assert row[0] == "New summary after analysis"
    assert row[1] == 0  # summary_embedded=0


def test_apply_session_summary_update_missing_session_id(applier, store):
    """Summary update without session_id should be skipped."""
    payload = {"summary": "orphan summary"}
    event = _make_event(TEAM_EVENT_SESSION_SUMMARY_UPDATE, payload)
    result = applier._apply_event(event)
    assert result is False


def test_apply_session_summary_update_none_summary(applier, store):
    """Summary update with None summary should be skipped."""
    payload = {"session_id": "sess-exists", "summary": None}
    event = _make_event(TEAM_EVENT_SESSION_SUMMARY_UPDATE, payload)
    result = applier._apply_event(event)
    assert result is False


# --------------------------------------------------------------------------
# Batch tests
# --------------------------------------------------------------------------


def test_apply_batch_mixed_events(applier, store):
    """apply_batch should handle a mix of event types."""
    _insert_session(store)

    obs_id = f"obs-{uuid.uuid4().hex[:8]}"
    session_id = f"sess-{uuid.uuid4().hex[:8]}"

    events = [
        _make_event(
            TEAM_EVENT_OBSERVATION_UPSERT,
            {
                "id": obs_id,
                "session_id": "sess-remote-1",
                "observation": "Pattern found",
                "memory_type": "pattern",
                "created_at": "2026-02-26T10:00:00",
                "created_at_epoch": 1740000000,
                "content_hash": "batch-hash-001",
                "source_machine_id": REMOTE_MACHINE_ID,
            },
        ),
        _make_event(
            TEAM_EVENT_SESSION_UPSERT,
            {
                "id": session_id,
                "agent": "claude",
                "project_root": "/tmp",
                "started_at": "2026-02-26T10:00:00",
                "created_at_epoch": 1740000000,
                "source_machine_id": REMOTE_MACHINE_ID,
            },
        ),
    ]

    result = applier.apply_batch(events)
    assert isinstance(result, ApplyResult)
    assert result.applied == 2
    assert result.skipped == 0
    assert result.errors == 0


def test_apply_batch_with_dedup(applier, store):
    """apply_batch should count skipped (dedup) events correctly."""
    _insert_session(store)
    content_hash = "batch-dedup-hash"

    obs_payload = {
        "id": f"obs-{uuid.uuid4().hex[:8]}",
        "session_id": "sess-remote-1",
        "observation": "Duplicate obs",
        "memory_type": "issue",
        "created_at": "2026-02-26T10:00:00",
        "created_at_epoch": 1740000000,
        "content_hash": content_hash,
        "source_machine_id": REMOTE_MACHINE_ID,
    }
    event1 = _make_event(TEAM_EVENT_OBSERVATION_UPSERT, obs_payload, content_hash=content_hash)
    event2 = _make_event(
        TEAM_EVENT_OBSERVATION_UPSERT,
        dict(obs_payload, id=f"obs-{uuid.uuid4().hex[:8]}"),
        content_hash=content_hash,
    )

    result = applier.apply_batch([event1, event2])
    assert result.applied == 1
    assert result.skipped == 1


def test_apply_batch_counts_errors(applier, store):
    """apply_batch should count events that raise exceptions as errors."""
    # Create an event with unknown type -- should count as skipped, not error
    unknown_event = _make_event("unknown_event_type", {"data": "test"})

    # A malformed observation (will fail because session_id is NOT NULL but missing)
    # However the applier catches exceptions and counts them
    bad_payload = {
        "id": f"obs-{uuid.uuid4().hex[:8]}",
        # Missing session_id -- will cause NOT NULL violation
        "observation": "Will fail",
        "memory_type": "issue",
        "created_at": "2026-02-26T10:00:00",
        "created_at_epoch": 1740000000,
        "content_hash": f"hash-{uuid.uuid4().hex[:8]}",
    }
    bad_event = _make_event(TEAM_EVENT_OBSERVATION_UPSERT, bad_payload)

    result = applier.apply_batch([unknown_event, bad_event])
    # unknown type returns False (skipped), bad insert raises exception (error)
    assert result.skipped == 1
    assert result.errors == 1
    assert result.applied == 0


def test_apply_observation_superseded(applier, store):
    """Superseded resolution should update observation status to superseded."""
    obs_id = f"obs-{uuid.uuid4().hex[:8]}"
    superseder_id = f"obs-{uuid.uuid4().hex[:8]}"
    _insert_session(store)

    # Insert observation
    obs_payload = {
        "id": obs_id,
        "session_id": "sess-remote-1",
        "observation": "Old pattern",
        "memory_type": "pattern",
        "created_at": "2026-02-26T10:00:00",
        "created_at_epoch": 1740000000,
        "content_hash": f"hash-{uuid.uuid4().hex[:8]}",
        "source_machine_id": REMOTE_MACHINE_ID,
    }
    applier._apply_event(_make_event(TEAM_EVENT_OBSERVATION_UPSERT, obs_payload))

    # Supersede it
    res_hash = f"res-hash-{uuid.uuid4().hex[:8]}"
    res_payload = {
        "id": f"res-{uuid.uuid4().hex[:8]}",
        "observation_id": obs_id,
        "action": "superseded",
        "superseded_by": superseder_id,
        "created_at": "2026-02-26T11:00:00",
        "created_at_epoch": 1740003600,
        "source_machine_id": REMOTE_MACHINE_ID,
        "content_hash": res_hash,
    }
    result = applier._apply_event(
        _make_event(TEAM_EVENT_OBSERVATION_RESOLVED, res_payload, content_hash=res_hash)
    )
    assert result is True

    conn = store._get_connection()
    obs_row = conn.execute(
        "SELECT status, superseded_by FROM memory_observations WHERE id = ?", (obs_id,)
    ).fetchone()
    assert obs_row[0] == "superseded"
    assert obs_row[1] == superseder_id
