"""Tests for team server event storage and cursor management.

Tests cover:
- store_events with dedup by content_hash
- get_events_since with cursor pagination
- get_events_since excluding a machine_id
- get_latest_cursor
"""

import sqlite3

from open_agent_kit.features.codebase_intelligence.constants.team import (
    TEAM_EVENT_OBSERVATION_UPSERT,
)
from open_agent_kit.features.codebase_intelligence.team.protocol import TeamEvent
from open_agent_kit.features.codebase_intelligence.team.server.cursors import (
    TEAM_EVENTS_DDL,
    get_events_since,
    get_latest_cursor,
    store_events,
)

# Test project ID constant
_TEST_PROJECT_ID = "test-project:abcd1234"


def _make_db() -> sqlite3.Connection:
    """Create an in-memory database with team_events table."""
    conn = sqlite3.connect(":memory:")
    conn.executescript(TEAM_EVENTS_DDL)
    return conn


def _make_event(
    content_hash: str,
    source_machine_id: str = "machine-1",
    event_type: str = TEAM_EVENT_OBSERVATION_UPSERT,
) -> TeamEvent:
    """Create a test TeamEvent."""
    return TeamEvent(
        event_type=event_type,
        payload={"test": True},
        source_machine_id=source_machine_id,
        content_hash=content_hash,
        schema_version=9,
        timestamp="2026-02-26T10:00:00Z",
        project_id=_TEST_PROJECT_ID,
    )


# =============================================================================
# store_events
# =============================================================================


class TestStoreEvents:
    """Test storing events with deduplication."""

    def test_store_new_events(self):
        """New events are accepted and stored."""
        conn = _make_db()
        events = [_make_event("hash-1"), _make_event("hash-2")]
        accepted = store_events(conn, events, _TEST_PROJECT_ID)
        assert accepted == 2

    def test_dedup_by_content_hash(self):
        """Duplicate content_hash events are rejected."""
        conn = _make_db()
        events = [_make_event("hash-1"), _make_event("hash-1")]
        accepted = store_events(conn, events, _TEST_PROJECT_ID)
        assert accepted == 1

    def test_dedup_across_batches(self):
        """Events with same hash across different batches are deduplicated."""
        conn = _make_db()
        store_events(conn, [_make_event("hash-1")], _TEST_PROJECT_ID)
        accepted = store_events(conn, [_make_event("hash-1")], _TEST_PROJECT_ID)
        assert accepted == 0

    def test_empty_list(self):
        """Empty event list returns 0."""
        conn = _make_db()
        assert store_events(conn, [], _TEST_PROJECT_ID) == 0

    def test_mixed_new_and_duplicate(self):
        """Mix of new and duplicate events."""
        conn = _make_db()
        store_events(conn, [_make_event("hash-1")], _TEST_PROJECT_ID)
        events = [_make_event("hash-1"), _make_event("hash-2"), _make_event("hash-3")]
        accepted = store_events(conn, events, _TEST_PROJECT_ID)
        assert accepted == 2


# =============================================================================
# get_events_since
# =============================================================================


class TestGetEventsSince:
    """Test cursor-based event retrieval."""

    def test_get_all_events(self):
        """cursor=None returns all events."""
        conn = _make_db()
        store_events(
            conn,
            [_make_event("h1"), _make_event("h2"), _make_event("h3")],
            _TEST_PROJECT_ID,
        )
        events, cursor = get_events_since(conn, cursor=None, limit=100)
        assert len(events) == 3
        assert cursor is not None

    def test_cursor_pagination(self):
        """Events after cursor are returned."""
        conn = _make_db()
        store_events(conn, [_make_event("h1"), _make_event("h2")], _TEST_PROJECT_ID)

        # Get first event
        events_1, cursor_1 = get_events_since(conn, cursor=None, limit=1)
        assert len(events_1) == 1
        assert cursor_1 is not None

        # Get next event using cursor
        events_2, cursor_2 = get_events_since(conn, cursor=cursor_1, limit=1)
        assert len(events_2) == 1
        assert events_2[0].content_hash == "h2"

    def test_cursor_no_more_events(self):
        """Returns empty when cursor is past all events."""
        conn = _make_db()
        store_events(conn, [_make_event("h1")], _TEST_PROJECT_ID)
        _, cursor = get_events_since(conn, cursor=None, limit=100)
        events, new_cursor = get_events_since(conn, cursor=cursor, limit=100)
        assert len(events) == 0
        # Cursor should remain the same (no new events)
        assert new_cursor == cursor

    def test_exclude_machine_id(self):
        """Events from excluded machine are filtered out."""
        conn = _make_db()
        store_events(
            conn,
            [
                _make_event("h1", source_machine_id="machine-A"),
                _make_event("h2", source_machine_id="machine-B"),
                _make_event("h3", source_machine_id="machine-A"),
            ],
            _TEST_PROJECT_ID,
        )
        events, _ = get_events_since(conn, cursor=None, limit=100, exclude_machine="machine-A")
        assert len(events) == 1
        assert events[0].source_machine_id == "machine-B"

    def test_empty_database(self):
        """Empty database returns empty list and None cursor stays None."""
        conn = _make_db()
        events, cursor = get_events_since(conn, cursor=None, limit=100)
        assert events == []
        assert cursor is None

    def test_limit_respected(self):
        """Limit parameter constrains result count."""
        conn = _make_db()
        store_events(
            conn,
            [_make_event(f"h{i}") for i in range(10)],
            _TEST_PROJECT_ID,
        )
        events, _ = get_events_since(conn, cursor=None, limit=3)
        assert len(events) == 3


# =============================================================================
# get_latest_cursor
# =============================================================================


class TestGetLatestCursor:
    """Test latest cursor retrieval."""

    def test_empty_database(self):
        """Empty database returns None."""
        conn = _make_db()
        assert get_latest_cursor(conn) is None

    def test_returns_highest_id(self):
        """Returns cursor for the most recent event."""
        conn = _make_db()
        store_events(
            conn,
            [_make_event("h1"), _make_event("h2")],
            _TEST_PROJECT_ID,
        )
        cursor = get_latest_cursor(conn)
        assert cursor is not None
        assert int(cursor) == 2
