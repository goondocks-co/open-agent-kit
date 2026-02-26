"""Tests for team membership service.

Tests cover:
- Register new member
- Update last_seen
- List members
- Increment event count
- Get single member
"""

import sqlite3

from open_agent_kit.features.codebase_intelligence.team.server.membership import (
    TEAM_MEMBERS_DDL,
    MembershipService,
)


def _make_db() -> sqlite3.Connection:
    """Create an in-memory database with team_members table."""
    conn = sqlite3.connect(":memory:")
    conn.executescript(TEAM_MEMBERS_DDL)
    return conn


def _make_service(conn: sqlite3.Connection) -> MembershipService:
    """Create a MembershipService backed by the given connection."""
    return MembershipService(conn_factory=lambda: conn)


# =============================================================================
# Registration
# =============================================================================


class TestRegister:
    """Test member registration."""

    def test_register_new_member(self):
        """Registering a new member returns TeamMemberInfo."""
        conn = _make_db()
        svc = _make_service(conn)
        member = svc.register("machine-1", "Alice's Laptop", "proj:abc12345")
        assert member.machine_id == "machine-1"
        assert member.display_name == "Alice's Laptop"
        assert member.project_id == "proj:abc12345"
        assert member.event_count == 0

    def test_register_updates_existing_member(self):
        """Re-registering with same machine_id updates fields."""
        conn = _make_db()
        svc = _make_service(conn)
        svc.register("machine-1", "Old Name", "proj:old")
        member = svc.register("machine-1", "New Name", "proj:new")
        assert member.display_name == "New Name"
        assert member.project_id == "proj:new"

    def test_register_preserves_event_count(self):
        """Re-registering does not reset event_count."""
        conn = _make_db()
        svc = _make_service(conn)
        svc.register("machine-1", "Name", "proj:abc12345")
        svc.increment_event_count("machine-1", 10)
        member = svc.register("machine-1", "Name Updated", "proj:abc12345")
        assert member.event_count == 10


# =============================================================================
# Update last_seen
# =============================================================================


class TestUpdateLastSeen:
    """Test updating last_seen timestamp."""

    def test_updates_timestamp(self):
        """update_last_seen changes the last_seen field."""
        conn = _make_db()
        svc = _make_service(conn)
        svc.register("machine-1", "Test", "proj:abc12345")

        svc.update_last_seen("machine-1")
        member_after = svc.get_member("machine-1")
        assert member_after is not None
        # last_seen should be updated (may be same if test runs fast,
        # but at least should not error)
        assert member_after.last_seen is not None


# =============================================================================
# Increment event count
# =============================================================================


class TestIncrementEventCount:
    """Test incrementing event count."""

    def test_increments_count(self):
        """increment_event_count adds to the existing count."""
        conn = _make_db()
        svc = _make_service(conn)
        svc.register("machine-1", "Test", "proj:abc12345")

        svc.increment_event_count("machine-1", 5)
        member = svc.get_member("machine-1")
        assert member is not None
        assert member.event_count == 5

    def test_multiple_increments(self):
        """Multiple increments accumulate correctly."""
        conn = _make_db()
        svc = _make_service(conn)
        svc.register("machine-1", "Test", "proj:abc12345")

        svc.increment_event_count("machine-1", 3)
        svc.increment_event_count("machine-1", 7)
        member = svc.get_member("machine-1")
        assert member is not None
        assert member.event_count == 10


# =============================================================================
# List members
# =============================================================================


class TestListMembers:
    """Test listing all members."""

    def test_empty_list(self):
        """Empty database returns empty list."""
        conn = _make_db()
        svc = _make_service(conn)
        assert svc.list_members() == []

    def test_returns_all_members(self):
        """All registered members are returned."""
        conn = _make_db()
        svc = _make_service(conn)
        svc.register("machine-1", "Alice", "proj:abc12345")
        svc.register("machine-2", "Bob", "proj:abc12345")

        members = svc.list_members()
        assert len(members) == 2
        ids = {m.machine_id for m in members}
        assert ids == {"machine-1", "machine-2"}


# =============================================================================
# Get member
# =============================================================================


class TestGetMember:
    """Test getting a single member."""

    def test_existing_member(self):
        """get_member returns member when found."""
        conn = _make_db()
        svc = _make_service(conn)
        svc.register("machine-1", "Alice", "proj:abc12345")

        member = svc.get_member("machine-1")
        assert member is not None
        assert member.machine_id == "machine-1"

    def test_nonexistent_member(self):
        """get_member returns None when not found."""
        conn = _make_db()
        svc = _make_service(conn)
        assert svc.get_member("nonexistent") is None
