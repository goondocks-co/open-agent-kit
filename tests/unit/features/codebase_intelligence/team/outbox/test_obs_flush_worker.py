"""Unit tests for ObsFlushWorker."""

import asyncio
import json
import threading
from unittest.mock import AsyncMock, MagicMock

import pytest

from open_agent_kit.features.codebase_intelligence.activity.store.core import ActivityStore
from open_agent_kit.features.codebase_intelligence.constants.team import (
    TEAM_EVENT_OBSERVATION_UPSERT,
    TEAM_OUTBOX_STATUS_PENDING,
)
from open_agent_kit.features.codebase_intelligence.team.outbox.worker import (
    ObsFlushWorker,
)

TEST_MACHINE_ID = "test-machine-flush"
TEST_PROJECT_ID = "test-project-flush"


@pytest.fixture
def store(tmp_path):
    """Create a real ActivityStore for testing."""
    db_path = tmp_path / ".oak" / "ci" / "activities.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return ActivityStore(db_path, machine_id=TEST_MACHINE_ID)


@pytest.fixture
def team_config():
    """Create a minimal TeamConfig mock."""
    from open_agent_kit.features.codebase_intelligence.config.team import TeamConfig

    return TeamConfig(sync_interval_seconds=3)


@pytest.fixture
def worker(store, team_config):
    """Create an ObsFlushWorker for testing."""
    return ObsFlushWorker(store=store, config=team_config, project_id=TEST_PROJECT_ID)


@pytest.fixture
def event_loop_thread():
    """Run an event loop in a background thread (mirrors production daemon pattern).

    The ObsFlushWorker uses asyncio.run_coroutine_threadsafe to schedule
    async relay calls from its daemon thread, so tests must provide a
    running loop on a separate thread.
    """
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    yield loop
    loop.call_soon_threadsafe(loop.stop)
    thread.join(timeout=5)
    loop.close()


def _insert_outbox_row(store, event_type=TEAM_EVENT_OBSERVATION_UPSERT, payload=None):
    """Insert a pending outbox row directly into the database."""
    if payload is None:
        payload = {"id": "obs-1", "observation": "Test obs", "memory_type": "pattern"}

    conn = store._get_connection()
    conn.execute(
        """
        INSERT INTO team_outbox
        (event_type, payload, source_machine_id, content_hash, schema_version, status, retry_count, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """,
        (
            event_type,
            json.dumps(payload),
            TEST_MACHINE_ID,
            "hash-" + payload.get("id", "unknown"),
            9,
            TEAM_OUTBOX_STATUS_PENDING,
            0,
        ),
    )
    conn.commit()


def test_flush_calls_push_observations(worker, store, event_loop_thread):
    """ObsFlushWorker.flush() should call relay_client.push_observations() with obs dicts."""
    relay_client = MagicMock()
    relay_client.push_observations = AsyncMock()

    # Wire up relay client and event loop (mirrors startup.py wiring)
    worker._relay_client = relay_client
    worker._event_loop = event_loop_thread

    _insert_outbox_row(store)

    flushed = worker.flush()

    assert flushed == 1
    relay_client.push_observations.assert_called_once()

    # Verify the observation payload structure
    call_args = relay_client.push_observations.call_args[0][0]
    assert len(call_args) == 1
    assert call_args[0]["event_type"] == TEAM_EVENT_OBSERVATION_UPSERT
    assert call_args[0]["source_machine_id"] == TEST_MACHINE_ID
    assert call_args[0]["project_id"] == TEST_PROJECT_ID

    obs_payload = call_args[0]["payload"]
    assert obs_payload["id"] == "obs-1"


def test_flush_skips_when_no_relay_client(worker, store):
    """ObsFlushWorker.flush() should return 0 when relay_client is None."""
    _insert_outbox_row(store)

    flushed = worker.flush()
    assert flushed == 0
