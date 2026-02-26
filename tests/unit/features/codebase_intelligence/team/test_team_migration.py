"""Tests for team sync outbox migration (v8 -> v9).

Tests cover:
- Migration creates team_outbox table
- Migration creates team_pull_cursor table
- Migration is idempotent (run twice, no error)
"""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from open_agent_kit.features.codebase_intelligence.activity.store.migrations import (
    _migrate_v8_to_v9,
)


@pytest.fixture
def db_path():
    """Create a temporary database path."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir) / "test_migration.db"


@pytest.fixture
def db_conn(db_path):
    """Create a SQLite connection with schema_version table for testing."""
    conn = sqlite3.connect(str(db_path))
    # Create minimal schema_version table (required baseline)
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)")
    conn.execute("INSERT INTO schema_version (version) VALUES (8)")
    conn.commit()
    yield conn
    conn.close()


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    """Check if a table exists in the database."""
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def _get_column_names(conn: sqlite3.Connection, table_name: str) -> set[str]:
    """Get column names for a table."""
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}


def _index_exists(conn: sqlite3.Connection, index_name: str) -> bool:
    """Check if an index exists in the database."""
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
        (index_name,),
    )
    return cursor.fetchone() is not None


# =============================================================================
# Migration v8 -> v9 Tests
# =============================================================================


class TestMigrateV8ToV9:
    """Test v8 -> v9 migration (team sync outbox tables)."""

    def test_creates_team_outbox_table(self, db_conn):
        """Test that migration creates the team_outbox table."""
        assert not _table_exists(db_conn, "team_outbox")

        _migrate_v8_to_v9(db_conn)

        assert _table_exists(db_conn, "team_outbox")
        columns = _get_column_names(db_conn, "team_outbox")
        expected_columns = {
            "id",
            "event_type",
            "payload",
            "source_machine_id",
            "content_hash",
            "schema_version",
            "created_at",
            "status",
            "retry_count",
            "error_message",
        }
        assert columns == expected_columns

    def test_creates_team_pull_cursor_table(self, db_conn):
        """Test that migration creates the team_pull_cursor table."""
        assert not _table_exists(db_conn, "team_pull_cursor")

        _migrate_v8_to_v9(db_conn)

        assert _table_exists(db_conn, "team_pull_cursor")
        columns = _get_column_names(db_conn, "team_pull_cursor")
        expected_columns = {
            "server_url",
            "cursor_value",
            "updated_at",
        }
        assert columns == expected_columns

    def test_creates_indexes(self, db_conn):
        """Test that migration creates the expected indexes."""
        _migrate_v8_to_v9(db_conn)

        assert _index_exists(db_conn, "idx_team_outbox_status")
        assert _index_exists(db_conn, "idx_team_outbox_created")

    def test_idempotent(self, db_conn):
        """Test that running migration twice does not error."""
        _migrate_v8_to_v9(db_conn)
        # Running again should not raise
        _migrate_v8_to_v9(db_conn)

        assert _table_exists(db_conn, "team_outbox")
        assert _table_exists(db_conn, "team_pull_cursor")

    def test_outbox_insert_works(self, db_conn):
        """Test that data can be inserted into team_outbox after migration."""
        _migrate_v8_to_v9(db_conn)

        db_conn.execute(
            """
            INSERT INTO team_outbox
                (event_type, payload, source_machine_id, content_hash,
                 schema_version, created_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "observation_upsert",
                '{"id": "obs-1"}',
                "machine-abc",
                "hash123",
                9,
                "2026-02-26T10:00:00Z",
                "pending",
            ),
        )
        db_conn.commit()

        cursor = db_conn.execute("SELECT COUNT(*) FROM team_outbox")
        assert cursor.fetchone()[0] == 1

    def test_pull_cursor_insert_works(self, db_conn):
        """Test that data can be inserted into team_pull_cursor after migration."""
        _migrate_v8_to_v9(db_conn)

        db_conn.execute(
            """
            INSERT INTO team_pull_cursor (server_url, cursor_value, updated_at)
            VALUES (?, ?, ?)
            """,
            ("https://team.example.com", "cursor-abc", "2026-02-26T10:00:00Z"),
        )
        db_conn.commit()

        cursor = db_conn.execute("SELECT COUNT(*) FROM team_pull_cursor")
        assert cursor.fetchone()[0] == 1
