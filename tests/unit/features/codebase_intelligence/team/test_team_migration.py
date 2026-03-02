"""Tests for relay-based team sync migration (v8 -> v9).

Tests cover:
- Migration creates team_outbox, team_pull_cursor, team_sync_state,
  team_reconcile_state tables
- Migration creates unique partial index on prompt_batches.content_hash
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
    """Create a SQLite connection with baseline tables for testing v8 -> v9."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)")
    conn.execute("INSERT INTO schema_version (version) VALUES (8)")
    # prompt_batches and activities are needed for the stub cleanup query
    conn.execute("""
        CREATE TABLE IF NOT EXISTS prompt_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            prompt_number INTEGER NOT NULL,
            started_at TEXT NOT NULL,
            created_at_epoch INTEGER NOT NULL,
            content_hash TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            prompt_batch_id INTEGER,
            tool_name TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            timestamp_epoch INTEGER NOT NULL
        )
    """)
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
    """Test v8 -> v9 migration (relay-based team sync tables)."""

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

    def test_creates_team_sync_state_table(self, db_conn):
        """Test that migration creates the team_sync_state table."""
        assert not _table_exists(db_conn, "team_sync_state")

        _migrate_v8_to_v9(db_conn)

        assert _table_exists(db_conn, "team_sync_state")
        columns = _get_column_names(db_conn, "team_sync_state")
        assert columns == {"key", "value", "updated_at"}

    def test_creates_team_reconcile_state_table(self, db_conn):
        """Test that migration creates the team_reconcile_state table."""
        assert not _table_exists(db_conn, "team_reconcile_state")

        _migrate_v8_to_v9(db_conn)

        assert _table_exists(db_conn, "team_reconcile_state")
        columns = _get_column_names(db_conn, "team_reconcile_state")
        assert columns == {
            "machine_id",
            "last_reconcile_at",
            "last_hash_count",
            "last_missing_count",
        }

    def test_creates_indexes(self, db_conn):
        """Test that migration creates the expected indexes."""
        _migrate_v8_to_v9(db_conn)

        assert _index_exists(db_conn, "idx_team_outbox_status")
        assert _index_exists(db_conn, "idx_team_outbox_created")
        assert _index_exists(db_conn, "idx_team_outbox_flush")
        assert _index_exists(db_conn, "idx_prompt_batches_content_hash")

    def test_idempotent(self, db_conn):
        """Test that running migration twice does not error."""
        _migrate_v8_to_v9(db_conn)
        # Running again should not raise
        _migrate_v8_to_v9(db_conn)

        assert _table_exists(db_conn, "team_outbox")
        assert _table_exists(db_conn, "team_pull_cursor")
        assert _table_exists(db_conn, "team_sync_state")
        assert _table_exists(db_conn, "team_reconcile_state")

    def test_cleans_up_stub_prompt_batches(self, db_conn):
        """Test that stub prompt_batches with NULL content_hash are removed."""
        # Insert a stub (NULL content_hash, no linked activities)
        db_conn.execute(
            "INSERT INTO prompt_batches (session_id, prompt_number, started_at, "
            "created_at_epoch, content_hash) VALUES (?, ?, ?, ?, ?)",
            ("sess-1", 1, "2026-01-01T00:00:00Z", 1, None),
        )
        # Insert a real batch (has content_hash)
        db_conn.execute(
            "INSERT INTO prompt_batches (session_id, prompt_number, started_at, "
            "created_at_epoch, content_hash) VALUES (?, ?, ?, ?, ?)",
            ("sess-1", 2, "2026-01-01T00:00:00Z", 1, "hash-real"),
        )
        db_conn.commit()

        _migrate_v8_to_v9(db_conn)

        rows = db_conn.execute("SELECT content_hash FROM prompt_batches").fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "hash-real"

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
