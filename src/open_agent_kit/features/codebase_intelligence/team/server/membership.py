"""Team member tracking service.

Tracks which machines have joined the team, when they were last seen,
and how many events they have contributed.
"""

import logging
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime

from open_agent_kit.features.codebase_intelligence.team.protocol import TeamMemberInfo

logger = logging.getLogger(__name__)

# ---- DDL ----

TEAM_MEMBERS_DDL = """
CREATE TABLE IF NOT EXISTS team_members (
    machine_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    project_id TEXT NOT NULL,
    joined_at TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    event_count INTEGER DEFAULT 0
);
"""


class MembershipService:
    """Manages team member registration and tracking."""

    def __init__(self, conn_factory: Callable[[], sqlite3.Connection]) -> None:
        """Initialize with a connection factory.

        Args:
            conn_factory: Callable that returns a sqlite3.Connection.
        """
        self._conn_factory = conn_factory

    def _conn(self) -> sqlite3.Connection:
        """Get a database connection."""
        return self._conn_factory()

    def register(self, machine_id: str, display_name: str, project_id: str) -> TeamMemberInfo:
        """Register or update a team member.

        If the member already exists, updates display_name, project_id,
        and last_seen.

        Args:
            machine_id: Unique machine identifier.
            display_name: Human-readable name for this machine.
            project_id: Project identity string.

        Returns:
            TeamMemberInfo for the registered member.
        """
        conn = self._conn()
        now = datetime.now(UTC).isoformat()

        # Upsert: insert or update existing
        conn.execute(
            "INSERT INTO team_members (machine_id, display_name, project_id, joined_at, last_seen) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(machine_id) DO UPDATE SET "
            "display_name = excluded.display_name, "
            "project_id = excluded.project_id, "
            "last_seen = excluded.last_seen",
            (machine_id, display_name, project_id, now, now),
        )
        conn.commit()

        return self.get_member(machine_id) or TeamMemberInfo(
            machine_id=machine_id,
            display_name=display_name,
            project_id=project_id,
            last_seen=now,
            event_count=0,
        )

    def update_last_seen(self, machine_id: str) -> None:
        """Update the last_seen timestamp for a member.

        Args:
            machine_id: Unique machine identifier.
        """
        conn = self._conn()
        now = datetime.now(UTC).isoformat()
        conn.execute(
            "UPDATE team_members SET last_seen = ? WHERE machine_id = ?",
            (now, machine_id),
        )
        conn.commit()

    def increment_event_count(self, machine_id: str, count: int) -> None:
        """Increment the event count for a member.

        Args:
            machine_id: Unique machine identifier.
            count: Number of events to add.
        """
        conn = self._conn()
        conn.execute(
            "UPDATE team_members SET event_count = event_count + ? WHERE machine_id = ?",
            (count, machine_id),
        )
        conn.commit()

    def list_members(self) -> list[TeamMemberInfo]:
        """List all registered team members.

        Returns:
            List of TeamMemberInfo for all members.
        """
        conn = self._conn()
        rows = conn.execute(
            "SELECT machine_id, display_name, project_id, last_seen, event_count "
            "FROM team_members ORDER BY last_seen DESC"
        ).fetchall()

        return [
            TeamMemberInfo(
                machine_id=row[0],
                display_name=row[1],
                project_id=row[2],
                last_seen=row[3],
                event_count=row[4],
            )
            for row in rows
        ]

    def get_member(self, machine_id: str) -> TeamMemberInfo | None:
        """Get a single team member by machine_id.

        Args:
            machine_id: Unique machine identifier.

        Returns:
            TeamMemberInfo if found, None otherwise.
        """
        conn = self._conn()
        row = conn.execute(
            "SELECT machine_id, display_name, project_id, last_seen, event_count "
            "FROM team_members WHERE machine_id = ?",
            (machine_id,),
        ).fetchone()

        if row is None:
            return None

        return TeamMemberInfo(
            machine_id=row[0],
            display_name=row[1],
            project_id=row[2],
            last_seen=row[3],
            event_count=row[4],
        )
