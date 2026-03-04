"""Tests for team outbox writer."""

import json
import sqlite3

import pytest

from open_agent_kit.features.team.constants.team import (
    TEAM_EVENT_OBSERVATION_UPSERT,
    TEAM_OUTBOX_STATUS_PENDING,
)
from open_agent_kit.features.team.relay.outbox.schema import (
    TEAM_OUTBOX_DDL,
)
from open_agent_kit.features.team.relay.outbox.writer import (
    enqueue_team_event,
)

TEST_MACHINE_ID = "test-machine-001"
TEST_CONTENT_HASH = "abc123hash"
TEST_SCHEMA_VERSION = 9
TEST_PAYLOAD = {
    "id": "obs-1",
    "observation": "Found a bug in auth module",
    "memory_type": "bug",
}


@pytest.fixture
def outbox_conn():
    """Create an in-memory SQLite connection with the outbox schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(TEAM_OUTBOX_DDL)
    return conn


def test_enqueue_creates_row(outbox_conn):
    """enqueue_team_event should insert a pending row into team_outbox."""
    enqueue_team_event(
        conn=outbox_conn,
        event_type=TEAM_EVENT_OBSERVATION_UPSERT,
        payload=TEST_PAYLOAD,
        source_machine_id=TEST_MACHINE_ID,
        content_hash=TEST_CONTENT_HASH,
        schema_version=TEST_SCHEMA_VERSION,
    )
    outbox_conn.commit()

    cursor = outbox_conn.execute("SELECT * FROM team_outbox")
    rows = cursor.fetchall()
    assert len(rows) == 1

    row = rows[0]
    assert row["event_type"] == TEAM_EVENT_OBSERVATION_UPSERT
    assert row["source_machine_id"] == TEST_MACHINE_ID
    assert row["content_hash"] == TEST_CONTENT_HASH
    assert row["schema_version"] == TEST_SCHEMA_VERSION
    assert row["status"] == TEAM_OUTBOX_STATUS_PENDING
    assert row["retry_count"] == 0
    assert row["error_message"] is None

    # Verify payload is valid JSON matching the input
    parsed = json.loads(row["payload"])
    assert parsed == TEST_PAYLOAD


def test_enqueue_multiple_events(outbox_conn):
    """Multiple enqueue calls should create multiple rows with incrementing IDs."""
    for i in range(3):
        enqueue_team_event(
            conn=outbox_conn,
            event_type=TEAM_EVENT_OBSERVATION_UPSERT,
            payload={"id": f"obs-{i}"},
            source_machine_id=TEST_MACHINE_ID,
            content_hash=f"hash-{i}",
            schema_version=TEST_SCHEMA_VERSION,
        )
    outbox_conn.commit()

    cursor = outbox_conn.execute("SELECT COUNT(*) FROM team_outbox")
    assert cursor.fetchone()[0] == 3


def test_enqueue_uses_pending_status_constant(outbox_conn):
    """Verify the status uses the TEAM_OUTBOX_STATUS_PENDING constant value."""
    enqueue_team_event(
        conn=outbox_conn,
        event_type=TEAM_EVENT_OBSERVATION_UPSERT,
        payload=TEST_PAYLOAD,
        source_machine_id=TEST_MACHINE_ID,
        content_hash=TEST_CONTENT_HASH,
        schema_version=TEST_SCHEMA_VERSION,
    )
    outbox_conn.commit()

    cursor = outbox_conn.execute(
        "SELECT status FROM team_outbox WHERE status = ?",
        (TEAM_OUTBOX_STATUS_PENDING,),
    )
    assert cursor.fetchone() is not None


def test_enqueue_sets_created_at(outbox_conn):
    """Enqueued event should have a non-null created_at timestamp."""
    enqueue_team_event(
        conn=outbox_conn,
        event_type=TEAM_EVENT_OBSERVATION_UPSERT,
        payload=TEST_PAYLOAD,
        source_machine_id=TEST_MACHINE_ID,
        content_hash=TEST_CONTENT_HASH,
        schema_version=TEST_SCHEMA_VERSION,
    )
    outbox_conn.commit()

    cursor = outbox_conn.execute("SELECT created_at FROM team_outbox")
    row = cursor.fetchone()
    assert row["created_at"] is not None
    # Should be ISO 8601 format
    assert "T" in row["created_at"]


def test_enqueue_atomic_with_data_write(outbox_conn):
    """Outbox write should be atomic with the surrounding transaction.

    If the transaction is rolled back, the outbox row should not persist.
    """
    # Create a simple data table to simulate an observation write
    outbox_conn.execute("CREATE TABLE test_data (id TEXT PRIMARY KEY, value TEXT)")

    # Start a transaction, write data + outbox, then rollback
    outbox_conn.execute("INSERT INTO test_data VALUES ('d1', 'hello')")
    enqueue_team_event(
        conn=outbox_conn,
        event_type=TEAM_EVENT_OBSERVATION_UPSERT,
        payload={"id": "d1"},
        source_machine_id=TEST_MACHINE_ID,
        content_hash="rollback-hash",
        schema_version=TEST_SCHEMA_VERSION,
    )
    outbox_conn.rollback()

    # Both the data write and outbox write should be gone
    assert outbox_conn.execute("SELECT COUNT(*) FROM test_data").fetchone()[0] == 0
    assert outbox_conn.execute("SELECT COUNT(*) FROM team_outbox").fetchone()[0] == 0


def test_enqueue_with_agent_created_origin_type(outbox_conn):
    """Agent-created observations should enqueue correctly with origin_type in payload."""
    payload = {
        "id": "obs-agent-1",
        "observation": "Agent-generated insight",
        "memory_type": "insight",
        "origin_type": "agent_created",
    }
    enqueue_team_event(
        conn=outbox_conn,
        event_type=TEAM_EVENT_OBSERVATION_UPSERT,
        payload=payload,
        source_machine_id=TEST_MACHINE_ID,
        content_hash="agent-hash",
        schema_version=TEST_SCHEMA_VERSION,
    )
    outbox_conn.commit()

    cursor = outbox_conn.execute("SELECT payload FROM team_outbox")
    row = cursor.fetchone()
    parsed = json.loads(row["payload"])
    assert parsed["origin_type"] == "agent_created"
