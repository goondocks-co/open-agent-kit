"""Unit tests for RemoteObsApplier."""

import pytest

from open_agent_kit.features.codebase_intelligence.activity.store.core import ActivityStore
from open_agent_kit.features.codebase_intelligence.team.sync.obs_applier import (
    RemoteObsApplier,
)

TEST_MACHINE_ID = "test-machine-applier"
TEST_FROM_MACHINE_ID = "remote-machine-001"
TEST_SESSION_ID = "session-applier-001"
TEST_PROJECT_ROOT = "/tmp/test-project"
TEST_AGENT = "claude"


@pytest.fixture
def store(tmp_path):
    """Create a real ActivityStore for testing."""
    db_path = tmp_path / ".oak" / "ci" / "activities.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return ActivityStore(db_path, machine_id=TEST_MACHINE_ID)


@pytest.fixture
def applier(store):
    """Create a RemoteObsApplier backed by a real store."""
    return RemoteObsApplier(store)


def _make_obs(
    obs_id="obs-1",
    session_id=TEST_SESSION_ID,
    content_hash="hash-1",
    observation="Test observation",
):
    """Create a minimal observation dict."""
    return {
        "id": obs_id,
        "session_id": session_id,
        "observation": observation,
        "memory_type": "pattern",
        "context": "test context",
        "tags": '["test"]',
        "importance": 5,
        "content_hash": content_hash,
        "created_at": "2025-01-01T00:00:00+00:00",
        "created_at_epoch": 1735689600,
    }


def test_apply_batch_inserts_observations(applier, store):
    """apply_batch should insert observations into the database."""
    obs = _make_obs()
    result = applier.apply_batch([obs], TEST_FROM_MACHINE_ID)

    assert result.applied == 1
    assert result.skipped == 0

    conn = store._get_connection()
    cursor = conn.execute(
        "SELECT id, observation FROM memory_observations WHERE id = ?", ("obs-1",)
    )
    row = cursor.fetchone()
    assert row is not None
    assert row["observation"] == "Test observation"


def test_dedup_same_content_hash_skipped(applier):
    """Second observation with same content_hash should be skipped."""
    obs = _make_obs()
    result1 = applier.apply_batch([obs], TEST_FROM_MACHINE_ID)
    assert result1.applied == 1

    obs2 = _make_obs(obs_id="obs-2", content_hash="hash-1")
    result2 = applier.apply_batch([obs2], TEST_FROM_MACHINE_ID)
    assert result2.applied == 0
    assert result2.skipped == 1


def test_started_at_fallback_uses_created_at(applier, store):
    """Obs without started_at should use created_at for the session stub."""
    obs = _make_obs()
    obs["created_at"] = "2025-06-15T10:00:00+00:00"
    # No started_at field
    applier.apply_batch([obs], TEST_FROM_MACHINE_ID)

    conn = store._get_connection()
    cursor = conn.execute("SELECT started_at FROM sessions WHERE id = ?", (TEST_SESSION_ID,))
    row = cursor.fetchone()
    assert row is not None
    assert row["started_at"] == "2025-06-15T10:00:00+00:00"


def test_ensure_session_uses_epoch_when_no_timestamps(applier, store):
    """_ensure_session_exists uses epoch when payload has no started_at or created_at."""
    payload = {"session_id": "session-epoch"}
    with store._transaction() as conn:
        applier._ensure_session_exists(conn, payload)

    conn = store._get_connection()
    cursor = conn.execute("SELECT started_at FROM sessions WHERE id = ?", ("session-epoch",))
    row = cursor.fetchone()
    assert row is not None
    assert row["started_at"] == "1970-01-01T00:00:00+00:00"


def test_apply_result_counts_are_accurate(applier):
    """ApplyResult should accurately report applied and skipped counts."""
    obs_list = [
        _make_obs(obs_id="obs-a", content_hash="hash-a"),
        _make_obs(obs_id="obs-b", content_hash="hash-b"),
        _make_obs(obs_id="obs-c", content_hash="hash-c"),
    ]
    result = applier.apply_batch(obs_list, TEST_FROM_MACHINE_ID)
    assert result.applied == 3
    assert result.skipped == 0

    # Apply again -- all should be skipped (dedup)
    obs_list_dup = [
        _make_obs(obs_id="obs-d", content_hash="hash-a"),
        _make_obs(obs_id="obs-e", content_hash="hash-b"),
    ]
    result2 = applier.apply_batch(obs_list_dup, TEST_FROM_MACHINE_ID)
    assert result2.applied == 0
    assert result2.skipped == 2


def test_obs_without_content_hash_skipped(applier):
    """Observations without content_hash should be skipped."""
    obs = _make_obs()
    del obs["content_hash"]
    result = applier.apply_batch([obs], TEST_FROM_MACHINE_ID)
    assert result.applied == 0
    assert result.skipped == 1


def test_exception_in_insert_counted_as_errored(applier, monkeypatch):
    """An exception during per-observation insert should be caught and counted as errored."""
    obs = _make_obs()

    def _explode(*args, **kwargs):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(applier, "_ensure_session_exists", _explode)
    result = applier.apply_batch([obs], TEST_FROM_MACHINE_ID)
    assert result.applied == 0
    assert result.errored == 1
