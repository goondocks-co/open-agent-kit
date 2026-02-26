"""Tests for TeamPullWorker."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from open_agent_kit.features.codebase_intelligence.activity.store.core import ActivityStore
from open_agent_kit.features.codebase_intelligence.config.team import TeamConfig
from open_agent_kit.features.codebase_intelligence.constants.team import (
    TEAM_EVENT_OBSERVATION_UPSERT,
)
from open_agent_kit.features.codebase_intelligence.team.protocol import (
    TeamEvent,
    TeamEventBatch,
)
from open_agent_kit.features.codebase_intelligence.team.pull.worker import TeamPullWorker

TEST_MACHINE_ID = "test-machine-pull"
REMOTE_MACHINE_ID = "remote-machine-002"
TEST_PROJECT_ID = "myproject:abc12345"
TEST_SERVER_URL = "http://localhost:8600"


@pytest.fixture
def store(tmp_path):
    """Create a real ActivityStore with a temp database."""
    db_path = tmp_path / ".oak" / "ci" / "activities.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return ActivityStore(db_path, machine_id=TEST_MACHINE_ID)


@pytest.fixture
def team_config():
    """Create a minimal TeamConfig for testing."""
    return TeamConfig(
        server_url=TEST_SERVER_URL,
        auto_sync=True,
        sync_interval_seconds=1,
        pull_interval_seconds=5,
    )


@pytest.fixture
def worker(store, team_config):
    """Create a TeamPullWorker (not started)."""
    return TeamPullWorker(
        store=store,
        config=team_config,
        project_id=TEST_PROJECT_ID,
        machine_id=TEST_MACHINE_ID,
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
# Start/Stop lifecycle
# --------------------------------------------------------------------------


def test_start_stop_lifecycle(worker):
    """Worker should start and stop cleanly."""
    worker.start()
    assert worker._thread is not None
    assert worker._thread.is_alive()

    worker.stop()
    assert worker._thread is None


def test_start_is_idempotent(worker):
    """Calling start() twice should not create a second thread."""
    worker.start()
    thread1 = worker._thread

    worker.start()
    thread2 = worker._thread

    assert thread1 is thread2
    worker.stop()


# --------------------------------------------------------------------------
# Cursor persistence
# --------------------------------------------------------------------------


def test_read_cursor_returns_none_initially(worker):
    """No cursor should exist before first pull."""
    cursor = worker._read_cursor()
    assert cursor is None


def test_save_and_read_cursor_roundtrip(worker):
    """Saved cursor should be readable."""
    worker._save_cursor("cursor-abc-123")
    cursor = worker._read_cursor()
    assert cursor == "cursor-abc-123"


def test_save_cursor_overwrites(worker):
    """Saving a new cursor should overwrite the old one."""
    worker._save_cursor("cursor-old")
    worker._save_cursor("cursor-new")
    cursor = worker._read_cursor()
    assert cursor == "cursor-new"


# --------------------------------------------------------------------------
# Pull and apply
# --------------------------------------------------------------------------


def test_pull_no_transport_returns_zero(worker):
    """Pull should return 0 when no transport is set."""
    result = worker._pull_and_apply()
    assert result == 0


def test_pull_and_apply_with_events(worker, store):
    """Pull should apply events from transport and save cursor."""
    _insert_session(store, "sess-remote-1")

    obs_event = TeamEvent(
        event_type=TEAM_EVENT_OBSERVATION_UPSERT,
        payload={
            "id": "obs-pulled-1",
            "session_id": "sess-remote-1",
            "observation": "Pulled from server",
            "memory_type": "pattern",
            "created_at": "2026-02-26T10:00:00",
            "created_at_epoch": 1740000000,
            "content_hash": "pull-hash-001",
            "source_machine_id": REMOTE_MACHINE_ID,
        },
        source_machine_id=REMOTE_MACHINE_ID,
        content_hash="pull-hash-001",
        schema_version=9,
        timestamp="2026-02-26T10:00:00+00:00",
        project_id=TEST_PROJECT_ID,
    )
    batch = TeamEventBatch(events=[obs_event], cursor="cursor-after-pull")

    mock_transport = MagicMock()
    mock_transport.pull_events = AsyncMock(return_value=batch)
    worker.set_transport(mock_transport)

    applied = worker._pull_and_apply()
    assert applied == 1

    # Verify event was applied to store
    conn = store._get_connection()
    row = conn.execute(
        "SELECT observation FROM memory_observations WHERE id = ?", ("obs-pulled-1",)
    ).fetchone()
    assert row is not None
    assert row[0] == "Pulled from server"

    # Verify cursor was saved
    cursor = worker._read_cursor()
    assert cursor == "cursor-after-pull"


def test_pull_empty_batch_returns_zero(worker, store):
    """Pull with no events should return 0 and not save cursor."""
    batch = TeamEventBatch(events=[], cursor="cursor-empty")

    mock_transport = MagicMock()
    mock_transport.pull_events = AsyncMock(return_value=batch)
    worker.set_transport(mock_transport)

    applied = worker._pull_and_apply()
    assert applied == 0

    # Cursor should not be saved for empty batches
    cursor = worker._read_cursor()
    assert cursor is None


def test_pull_transport_error_propagates(worker, store):
    """Transport errors should propagate and set last_error."""
    mock_transport = MagicMock()
    mock_transport.pull_events = AsyncMock(side_effect=ConnectionError("server unreachable"))
    worker.set_transport(mock_transport)

    with pytest.raises(ConnectionError, match="server unreachable"):
        worker._pull_and_apply()

    assert worker._last_error == "server unreachable"


def test_pull_sends_exclude_machine_id(worker, store):
    """Pull request should exclude the local machine's events."""
    batch = TeamEventBatch(events=[], cursor=None)

    mock_transport = MagicMock()
    mock_transport.pull_events = AsyncMock(return_value=batch)
    worker.set_transport(mock_transport)

    worker._pull_and_apply()

    # Check the request passed to transport
    mock_transport.pull_events.assert_called_once()
    request = mock_transport.pull_events.call_args[0][0]
    assert request.exclude_machine_id == TEST_MACHINE_ID


def test_pull_sends_cursor(worker, store):
    """Pull request should include the saved cursor."""
    worker._save_cursor("saved-cursor-xyz")

    batch = TeamEventBatch(events=[], cursor=None)
    mock_transport = MagicMock()
    mock_transport.pull_events = AsyncMock(return_value=batch)
    worker.set_transport(mock_transport)

    worker._pull_and_apply()

    request = mock_transport.pull_events.call_args[0][0]
    assert request.since_cursor == "saved-cursor-xyz"


# --------------------------------------------------------------------------
# Status
# --------------------------------------------------------------------------


def test_get_status_initial(worker):
    """Initial status should show enabled with zero counts."""
    status = worker.get_status()
    assert status.enabled is True
    assert status.events_applied_total == 0
    assert status.last_pull is None
    assert status.cursor is None


def test_get_status_after_pull(worker, store):
    """Status should reflect applied events after a pull."""
    _insert_session(store, "sess-remote-1")

    obs_event = TeamEvent(
        event_type=TEAM_EVENT_OBSERVATION_UPSERT,
        payload={
            "id": "obs-status-1",
            "session_id": "sess-remote-1",
            "observation": "Status test",
            "memory_type": "pattern",
            "created_at": "2026-02-26T10:00:00",
            "created_at_epoch": 1740000000,
            "content_hash": "status-hash-001",
            "source_machine_id": REMOTE_MACHINE_ID,
        },
        source_machine_id=REMOTE_MACHINE_ID,
        content_hash="status-hash-001",
        schema_version=9,
        timestamp="2026-02-26T10:00:00+00:00",
        project_id=TEST_PROJECT_ID,
    )
    batch = TeamEventBatch(events=[obs_event], cursor="status-cursor")

    mock_transport = MagicMock()
    mock_transport.pull_events = AsyncMock(return_value=batch)
    worker.set_transport(mock_transport)
    worker._pull_and_apply()

    status = worker.get_status()
    assert status.events_applied_total == 1
    assert status.last_pull is not None
    assert status.cursor == "status-cursor"
