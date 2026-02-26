"""Tests for TeamSyncWorker."""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from open_agent_kit.features.codebase_intelligence.activity.store.core import ActivityStore
from open_agent_kit.features.codebase_intelligence.config.team import TeamConfig
from open_agent_kit.features.codebase_intelligence.constants.team import (
    TEAM_EVENT_OBSERVATION_UPSERT,
    TEAM_OUTBOX_MAX_RETRY_COUNT,
    TEAM_OUTBOX_STATUS_FAILED,
    TEAM_OUTBOX_STATUS_PENDING,
    TEAM_OUTBOX_STATUS_SENT,
)
from open_agent_kit.features.codebase_intelligence.team.outbox.worker import TeamSyncWorker
from open_agent_kit.features.codebase_intelligence.team.protocol import TeamEventBatch

TEST_MACHINE_ID = "test-machine-worker"
TEST_PROJECT_ID = "myproject:abc12345"
TEST_SCHEMA_VERSION = 9


@pytest.fixture
def store(tmp_path):
    """Create a real ActivityStore with an in-memory-like temp database."""
    db_path = tmp_path / ".oak" / "ci" / "activities.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return ActivityStore(db_path, machine_id=TEST_MACHINE_ID)


@pytest.fixture
def team_config():
    """Create a minimal TeamConfig for testing."""
    return TeamConfig(
        server_url="http://localhost:8600",
        auto_sync=True,
        sync_interval_seconds=1,
    )


@pytest.fixture
def worker(store, team_config):
    """Create a TeamSyncWorker (not started)."""
    return TeamSyncWorker(
        store=store,
        config=team_config,
        project_id=TEST_PROJECT_ID,
    )


def _insert_pending_event(store, event_type=TEAM_EVENT_OBSERVATION_UPSERT, payload=None):
    """Helper to insert a pending outbox event directly."""
    if payload is None:
        payload = {"id": "obs-1", "observation": "test"}
    conn = store._get_connection()
    conn.execute(
        """
        INSERT INTO team_outbox (event_type, payload, source_machine_id, content_hash,
                                 schema_version, created_at, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_type,
            json.dumps(payload),
            TEST_MACHINE_ID,
            "hash-001",
            TEST_SCHEMA_VERSION,
            datetime.now(UTC).isoformat(),
            TEAM_OUTBOX_STATUS_PENDING,
        ),
    )
    conn.commit()


def test_flush_no_transport_is_noop(worker, store):
    """Flush should return 0 when no transport is set."""
    _insert_pending_event(store)
    result = worker._flush_outbox()
    assert result == 0


def test_flush_reads_pending_events(worker, store):
    """Flush should read pending events and push them via transport."""
    _insert_pending_event(store)

    mock_transport = MagicMock()
    mock_transport.push_events.return_value = 1
    worker.set_transport(mock_transport)

    result = worker._flush_outbox()
    assert result == 1

    # Transport should have been called with a batch
    mock_transport.push_events.assert_called_once()
    batch = mock_transport.push_events.call_args[0][0]
    assert isinstance(batch, TeamEventBatch)
    assert len(batch.events) == 1
    assert batch.events[0].event_type == TEAM_EVENT_OBSERVATION_UPSERT
    assert batch.events[0].project_id == TEST_PROJECT_ID


def test_flush_marks_events_sent(worker, store):
    """Flushed events should be marked as sent in the outbox."""
    _insert_pending_event(store)

    mock_transport = MagicMock()
    mock_transport.push_events.return_value = 1
    worker.set_transport(mock_transport)

    worker._flush_outbox()

    conn = store._get_connection()
    cursor = conn.execute("SELECT status FROM team_outbox")
    row = cursor.fetchone()
    assert row[0] == TEAM_OUTBOX_STATUS_SENT


def test_flush_retries_on_failure(worker, store):
    """Transport failure should increment retry_count and not mark as sent."""
    _insert_pending_event(store)

    mock_transport = MagicMock()
    mock_transport.push_events.side_effect = ConnectionError("network down")
    worker.set_transport(mock_transport)

    with pytest.raises(ConnectionError):
        worker._flush_outbox()

    conn = store._get_connection()
    cursor = conn.execute("SELECT status, retry_count, error_message FROM team_outbox")
    row = cursor.fetchone()
    assert row[0] == TEAM_OUTBOX_STATUS_PENDING  # still pending (retry_count < max)
    assert row[1] == 1
    assert "network down" in row[2]


def test_flush_marks_failed_after_max_retries(worker, store):
    """Events exceeding max retry count should be marked as failed."""
    # Insert event with retry_count just below the max
    conn = store._get_connection()
    conn.execute(
        """
        INSERT INTO team_outbox (event_type, payload, source_machine_id, content_hash,
                                 schema_version, created_at, status, retry_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            TEAM_EVENT_OBSERVATION_UPSERT,
            json.dumps({"id": "obs-retry"}),
            TEST_MACHINE_ID,
            "hash-retry",
            TEST_SCHEMA_VERSION,
            datetime.now(UTC).isoformat(),
            TEAM_OUTBOX_STATUS_PENDING,
            TEAM_OUTBOX_MAX_RETRY_COUNT - 1,
        ),
    )
    conn.commit()

    mock_transport = MagicMock()
    mock_transport.push_events.side_effect = ConnectionError("still down")
    worker.set_transport(mock_transport)

    with pytest.raises(ConnectionError):
        worker._flush_outbox()

    cursor = conn.execute("SELECT status, retry_count FROM team_outbox")
    row = cursor.fetchone()
    assert row[0] == TEAM_OUTBOX_STATUS_FAILED
    assert row[1] == TEAM_OUTBOX_MAX_RETRY_COUNT


def test_flush_skips_events_at_max_retry(worker, store):
    """Events already at max retry count should not be selected for flushing."""
    conn = store._get_connection()
    conn.execute(
        """
        INSERT INTO team_outbox (event_type, payload, source_machine_id, content_hash,
                                 schema_version, created_at, status, retry_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            TEAM_EVENT_OBSERVATION_UPSERT,
            json.dumps({"id": "obs-maxed"}),
            TEST_MACHINE_ID,
            "hash-maxed",
            TEST_SCHEMA_VERSION,
            datetime.now(UTC).isoformat(),
            TEAM_OUTBOX_STATUS_PENDING,
            TEAM_OUTBOX_MAX_RETRY_COUNT,
        ),
    )
    conn.commit()

    mock_transport = MagicMock()
    worker.set_transport(mock_transport)

    result = worker._flush_outbox()
    assert result == 0
    mock_transport.push_events.assert_not_called()


def test_prune_removes_old_sent_events(worker, store):
    """Sent events older than 24h should be pruned."""
    old_time = (datetime.now(UTC) - timedelta(hours=25)).isoformat()
    recent_time = datetime.now(UTC).isoformat()

    conn = store._get_connection()
    # Old sent event (should be pruned)
    conn.execute(
        """
        INSERT INTO team_outbox (event_type, payload, source_machine_id, content_hash,
                                 schema_version, created_at, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            TEAM_EVENT_OBSERVATION_UPSERT,
            "{}",
            TEST_MACHINE_ID,
            "old-hash",
            TEST_SCHEMA_VERSION,
            old_time,
            TEAM_OUTBOX_STATUS_SENT,
        ),
    )
    # Recent sent event (should be kept)
    conn.execute(
        """
        INSERT INTO team_outbox (event_type, payload, source_machine_id, content_hash,
                                 schema_version, created_at, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            TEAM_EVENT_OBSERVATION_UPSERT,
            "{}",
            TEST_MACHINE_ID,
            "recent-hash",
            TEST_SCHEMA_VERSION,
            recent_time,
            TEAM_OUTBOX_STATUS_SENT,
        ),
    )
    conn.commit()

    worker._prune_sent_events(conn)

    cursor = conn.execute("SELECT COUNT(*) FROM team_outbox")
    assert cursor.fetchone()[0] == 1

    cursor = conn.execute("SELECT content_hash FROM team_outbox")
    assert cursor.fetchone()[0] == "recent-hash"


def test_get_status_returns_queue_depth(worker, store):
    """get_status should return correct queue depth."""
    # Empty queue
    status = worker.get_status()
    assert status.enabled is True
    assert status.queue_depth == 0
    assert status.events_sent_total == 0

    # Add pending events
    _insert_pending_event(store)
    _insert_pending_event(store)

    status = worker.get_status()
    assert status.queue_depth == 2


def test_get_status_after_flush(worker, store):
    """get_status should reflect events_sent_total after a flush."""
    _insert_pending_event(store)

    mock_transport = MagicMock()
    mock_transport.push_events.return_value = 1
    worker.set_transport(mock_transport)

    worker._flush_outbox()

    status = worker.get_status()
    assert status.events_sent_total == 1
    assert status.last_sync is not None
    assert status.last_error is None


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
