"""Tests for get_events_for_machine() in team server cursors.

Tests cover:
- Empty machine returns empty list
- Returns only events for requested machine_id
- Returns events ordered by id ASC
- Pagination via offset/limit
- Returns expected fields in each dict
"""

import sqlite3

from open_agent_kit.features.codebase_intelligence.constants.team import (
    TEAM_EVENT_OBSERVATION_UPSERT,
)
from open_agent_kit.features.codebase_intelligence.team.protocol import TeamEvent
from open_agent_kit.features.codebase_intelligence.team.server.cursors import (
    TEAM_EVENTS_DDL,
    get_events_for_machine,
    store_events,
)

# Test constants
_TEST_PROJECT_ID = "test-project:abcd1234"
_MACHINE_A = "machine-A"
_MACHINE_B = "machine-B"


def _make_db() -> sqlite3.Connection:
    """Create an in-memory database with team_events table."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(TEAM_EVENTS_DDL)
    return conn


def _make_event(
    content_hash: str,
    source_machine_id: str = _MACHINE_A,
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


def _seed_events(conn: sqlite3.Connection, machine_id: str, hashes: list[str]) -> None:
    """Insert events for a given machine."""
    events = [_make_event(h, source_machine_id=machine_id) for h in hashes]
    store_events(conn, events, _TEST_PROJECT_ID)


# =============================================================================
# get_events_for_machine
# =============================================================================


class TestGetEventsForMachineEmpty:
    """Test empty/no-match scenarios."""

    def test_empty_database(self):
        """Empty database returns empty list."""
        conn = _make_db()
        result = get_events_for_machine(conn, _MACHINE_A)
        assert result == []

    def test_no_events_for_requested_machine(self):
        """Returns empty list when no events match the machine_id."""
        conn = _make_db()
        _seed_events(conn, _MACHINE_B, ["h1", "h2"])
        result = get_events_for_machine(conn, _MACHINE_A)
        assert result == []


class TestGetEventsForMachineFiltering:
    """Test machine_id filtering."""

    def test_returns_only_requested_machine(self):
        """Returns only events for the requested machine_id."""
        conn = _make_db()
        _seed_events(conn, _MACHINE_A, ["a1", "a2"])
        _seed_events(conn, _MACHINE_B, ["b1", "b2", "b3"])

        result = get_events_for_machine(conn, _MACHINE_A)
        assert len(result) == 2
        for event in result:
            assert event["source_machine_id"] == _MACHINE_A

    def test_ignores_other_machines(self):
        """Events from other machines are not included."""
        conn = _make_db()
        _seed_events(conn, _MACHINE_A, ["a1"])
        _seed_events(conn, _MACHINE_B, ["b1"])

        result_a = get_events_for_machine(conn, _MACHINE_A)
        result_b = get_events_for_machine(conn, _MACHINE_B)

        assert len(result_a) == 1
        assert result_a[0]["content_hash"] == "a1"
        assert len(result_b) == 1
        assert result_b[0]["content_hash"] == "b1"


class TestGetEventsForMachineOrdering:
    """Test ordering by id ASC."""

    def test_ordered_by_id_asc(self):
        """Events are returned in insertion order (id ASC)."""
        conn = _make_db()
        hashes = ["first", "second", "third"]
        _seed_events(conn, _MACHINE_A, hashes)

        result = get_events_for_machine(conn, _MACHINE_A)
        assert len(result) == 3
        result_hashes = [e["content_hash"] for e in result]
        assert result_hashes == hashes


class TestGetEventsForMachinePagination:
    """Test offset/limit pagination."""

    def test_limit_constrains_results(self):
        """Limit parameter constrains result count."""
        conn = _make_db()
        _seed_events(conn, _MACHINE_A, [f"h{i}" for i in range(10)])

        result = get_events_for_machine(conn, _MACHINE_A, limit=3)
        assert len(result) == 3

    def test_offset_skips_rows(self):
        """Offset parameter skips the first N results."""
        conn = _make_db()
        _seed_events(conn, _MACHINE_A, [f"h{i}" for i in range(5)])

        result = get_events_for_machine(conn, _MACHINE_A, limit=100, offset=3)
        assert len(result) == 2

    def test_offset_and_limit_together(self):
        """Offset and limit work together for pagination."""
        conn = _make_db()
        hashes = [f"h{i}" for i in range(10)]
        _seed_events(conn, _MACHINE_A, hashes)

        page1 = get_events_for_machine(conn, _MACHINE_A, limit=3, offset=0)
        page2 = get_events_for_machine(conn, _MACHINE_A, limit=3, offset=3)
        page3 = get_events_for_machine(conn, _MACHINE_A, limit=3, offset=6)
        page4 = get_events_for_machine(conn, _MACHINE_A, limit=3, offset=9)

        assert len(page1) == 3
        assert len(page2) == 3
        assert len(page3) == 3
        assert len(page4) == 1

        # No overlaps
        all_hashes = [e["content_hash"] for e in page1 + page2 + page3 + page4]
        assert len(set(all_hashes)) == 10

    def test_offset_beyond_data(self):
        """Offset past all data returns empty list."""
        conn = _make_db()
        _seed_events(conn, _MACHINE_A, ["h1"])

        result = get_events_for_machine(conn, _MACHINE_A, limit=100, offset=100)
        assert result == []

    def test_default_limit_is_500(self):
        """Default limit is 500 (function signature default)."""
        conn = _make_db()
        # Insert fewer than default limit to verify all are returned
        _seed_events(conn, _MACHINE_A, [f"h{i}" for i in range(20)])

        result = get_events_for_machine(conn, _MACHINE_A)
        assert len(result) == 20


class TestGetEventsForMachineFields:
    """Test that returned dicts have all expected fields."""

    def test_returns_expected_fields(self):
        """Each returned dict contains all expected fields."""
        conn = _make_db()
        _seed_events(conn, _MACHINE_A, ["h1"])

        result = get_events_for_machine(conn, _MACHINE_A)
        assert len(result) == 1

        event = result[0]
        expected_fields = {
            "event_type",
            "payload",
            "source_machine_id",
            "content_hash",
            "schema_version",
        }
        assert expected_fields.issubset(set(event.keys()))

    def test_field_values_match_stored(self):
        """Field values match what was stored."""
        conn = _make_db()
        _seed_events(conn, _MACHINE_A, ["test-hash"])

        result = get_events_for_machine(conn, _MACHINE_A)
        event = result[0]

        assert event["event_type"] == TEAM_EVENT_OBSERVATION_UPSERT
        assert event["source_machine_id"] == _MACHINE_A
        assert event["content_hash"] == "test-hash"
        assert event["schema_version"] == 9
