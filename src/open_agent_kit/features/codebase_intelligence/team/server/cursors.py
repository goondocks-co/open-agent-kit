"""Server-side event storage and cursor management.

Events pushed by team members are stored in the ``team_events`` table.
Pull requests use cursor-based pagination (cursor = event ID).
Deduplication is by ``content_hash``.
"""

import json
import logging
import sqlite3
from datetime import UTC, datetime

from open_agent_kit.features.codebase_intelligence.team.protocol import TeamEvent

logger = logging.getLogger(__name__)

# ---- DDL ----

TEAM_EVENTS_DDL = """
CREATE TABLE IF NOT EXISTS team_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    payload TEXT NOT NULL,
    source_machine_id TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    project_id TEXT NOT NULL,
    received_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_team_events_hash ON team_events(content_hash);
CREATE INDEX IF NOT EXISTS idx_team_events_received ON team_events(received_at);
CREATE INDEX IF NOT EXISTS idx_team_events_source ON team_events(source_machine_id);
CREATE INDEX IF NOT EXISTS idx_team_events_source_hash
    ON team_events(source_machine_id, content_hash);
"""


def get_latest_cursor(conn: sqlite3.Connection) -> str | None:
    """Get the latest event cursor (highest event ID).

    Args:
        conn: SQLite connection with team_events table.

    Returns:
        String cursor (event ID) or None if no events exist.
    """
    row = conn.execute("SELECT MAX(id) FROM team_events").fetchone()
    if row is None or row[0] is None:
        return None
    return str(row[0])


def store_events(conn: sqlite3.Connection, events: list[TeamEvent], project_id: str) -> int:
    """Store events, deduplicating by content_hash.

    Args:
        conn: SQLite connection with team_events table.
        events: List of TeamEvent to store.
        project_id: Project identity for these events.

    Returns:
        Number of events actually accepted (not duplicates).
    """
    if not events:
        return 0

    now = datetime.now(UTC).isoformat()
    accepted = 0

    for event in events:
        # Check for existing content_hash
        existing = conn.execute(
            "SELECT 1 FROM team_events WHERE content_hash = ?",
            (event.content_hash,),
        ).fetchone()

        if existing is not None:
            continue

        payload_json = (
            json.dumps(event.payload) if isinstance(event.payload, dict) else event.payload
        )

        conn.execute(
            "INSERT INTO team_events "
            "(event_type, payload, source_machine_id, content_hash, schema_version, project_id, received_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                event.event_type,
                payload_json,
                event.source_machine_id,
                event.content_hash,
                event.schema_version,
                project_id,
                now,
            ),
        )
        accepted += 1

    conn.commit()
    return accepted


def get_events_since(
    conn: sqlite3.Connection,
    cursor: str | None,
    limit: int,
    exclude_machine: str | None = None,
) -> tuple[list[TeamEvent], str | None]:
    """Get events since a cursor, optionally excluding a source machine.

    Args:
        conn: SQLite connection with team_events table.
        cursor: Event ID to start after (None = from beginning).
        limit: Maximum number of events to return.
        exclude_machine: Machine ID whose events to exclude (typically
            the requester's own machine).

    Returns:
        Tuple of (events, new_cursor). new_cursor is None if no events found.
    """
    params: list = []
    conditions: list[str] = []

    if cursor is not None:
        conditions.append("id > ?")
        params.append(int(cursor))

    if exclude_machine is not None:
        conditions.append("source_machine_id != ?")
        params.append(exclude_machine)

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    query = f"SELECT id, event_type, payload, source_machine_id, content_hash, schema_version, project_id, received_at FROM team_events {where_clause} ORDER BY id ASC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()

    if not rows:
        return [], cursor

    events: list[TeamEvent] = []
    new_cursor: str | None = None

    for row in rows:
        (
            event_id,
            event_type,
            payload_str,
            source_machine_id,
            content_hash,
            schema_version,
            project_id,
            received_at,
        ) = row

        # Parse payload JSON
        try:
            payload = json.loads(payload_str) if isinstance(payload_str, str) else payload_str
        except (json.JSONDecodeError, TypeError):
            payload = {}

        events.append(
            TeamEvent(
                event_type=event_type,
                payload=payload,
                source_machine_id=source_machine_id,
                content_hash=content_hash,
                schema_version=schema_version,
                timestamp=received_at,
                project_id=project_id,
            )
        )
        new_cursor = str(event_id)

    return events, new_cursor
