"""Tests for session transcript_path storage.

Verifies that the transcript_path column exists in the sessions table
and that the update/read cycle works through the ActivityStore API.
"""

import sqlite3
from datetime import datetime

import pytest

from open_agent_kit.features.codebase_intelligence.activity.store.models import Session
from open_agent_kit.features.codebase_intelligence.activity.store.schema import (
    SCHEMA_VERSION,
)

from .fixtures import (
    SQL_INSERT_SESSION_NO_TRANSCRIPT,
    SQL_INSERT_SESSION_WITH_TRANSCRIPT,
    SQL_SELECT_SESSION_BY_ID,
    SQL_SESSIONS_TABLE_NO_TRANSCRIPT,
    SQL_SESSIONS_TABLE_WITH_TRANSCRIPT,
    SQLITE_MEMORY_URI,
    TEST_AGENT_CLAUDE,
    TEST_CREATED_AT_EPOCH,
    TEST_PROJECT_ROOT,
    TEST_PROJECT_ROOT_SHORT,
    TEST_SCHEMA_VERSION,
    TEST_SESSION_COLUMN_TRANSCRIPT_PATH,
    TEST_SESSION_ID,
    TEST_SESSION_ID_ONE,
    TEST_SESSION_ID_S1,
    TEST_SESSION_ID_THREE,
    TEST_SESSION_ID_TWO,
    TEST_SESSION_STATUS_COMPLETED,
    TEST_STARTED_AT,
    TEST_TRANSCRIPT_PATH,
    TEST_TRANSCRIPT_PATH_GENERIC,
    TEST_TRANSCRIPT_PATH_ONE,
    TEST_TRANSCRIPT_PATH_S1,
)


class TestSchemaVersion:
    """Verify schema version matches constants."""

    def test_schema_version_matches_constant(self):
        assert SCHEMA_VERSION == TEST_SCHEMA_VERSION


class TestSessionModel:
    """Tests for Session model transcript_path field."""

    def test_session_has_transcript_path_field(self):
        """Session dataclass includes transcript_path."""
        session = Session(
            id=TEST_SESSION_ID,
            agent=TEST_AGENT_CLAUDE,
            project_root=TEST_PROJECT_ROOT,
            started_at=datetime.now(),
            transcript_path=TEST_TRANSCRIPT_PATH,
        )
        assert session.transcript_path == TEST_TRANSCRIPT_PATH

    def test_session_transcript_path_defaults_to_none(self):
        """transcript_path defaults to None when not provided."""
        session = Session(
            id=TEST_SESSION_ID,
            agent=TEST_AGENT_CLAUDE,
            project_root=TEST_PROJECT_ROOT,
            started_at=datetime.now(),
        )
        assert session.transcript_path is None

    def test_to_row_includes_transcript_path(self):
        """to_row() serializes transcript_path."""
        session = Session(
            id=TEST_SESSION_ID,
            agent=TEST_AGENT_CLAUDE,
            project_root=TEST_PROJECT_ROOT,
            started_at=datetime.now(),
            transcript_path=TEST_TRANSCRIPT_PATH_GENERIC,
        )
        row = session.to_row()
        assert row[TEST_SESSION_COLUMN_TRANSCRIPT_PATH] == TEST_TRANSCRIPT_PATH_GENERIC

    def test_to_row_includes_none_transcript_path(self):
        """to_row() includes None when transcript_path not set."""
        session = Session(
            id=TEST_SESSION_ID,
            agent=TEST_AGENT_CLAUDE,
            project_root=TEST_PROJECT_ROOT,
            started_at=datetime.now(),
        )
        row = session.to_row()
        assert row[TEST_SESSION_COLUMN_TRANSCRIPT_PATH] is None

    def test_from_row_reads_transcript_path(self):
        """from_row() deserializes transcript_path from database row."""
        # Create an in-memory DB with the session schema including transcript_path
        conn = sqlite3.connect(SQLITE_MEMORY_URI)
        conn.row_factory = sqlite3.Row
        conn.execute(SQL_SESSIONS_TABLE_WITH_TRANSCRIPT)
        conn.execute(
            SQL_INSERT_SESSION_WITH_TRANSCRIPT.format(
                session_id=TEST_SESSION_ID_S1,
                agent=TEST_AGENT_CLAUDE,
                project_root=TEST_PROJECT_ROOT_SHORT,
                started_at=TEST_STARTED_AT,
                created_at_epoch=TEST_CREATED_AT_EPOCH,
                path=TEST_TRANSCRIPT_PATH_S1,
            )
        )
        row = conn.execute(
            SQL_SELECT_SESSION_BY_ID.format(session_id=TEST_SESSION_ID_S1)
        ).fetchone()
        session = Session.from_row(row)
        assert session.transcript_path == TEST_TRANSCRIPT_PATH_S1

    def test_from_row_handles_missing_transcript_path_column(self):
        """from_row() gracefully handles databases without transcript_path column."""
        conn = sqlite3.connect(SQLITE_MEMORY_URI)
        conn.row_factory = sqlite3.Row
        conn.execute(SQL_SESSIONS_TABLE_NO_TRANSCRIPT)
        conn.execute(
            SQL_INSERT_SESSION_NO_TRANSCRIPT.format(
                session_id=TEST_SESSION_ID_S1,
                agent=TEST_AGENT_CLAUDE,
                project_root=TEST_PROJECT_ROOT_SHORT,
                started_at=TEST_STARTED_AT,
                created_at_epoch=TEST_CREATED_AT_EPOCH,
            )
        )
        row = conn.execute(
            SQL_SELECT_SESSION_BY_ID.format(session_id=TEST_SESSION_ID_S1)
        ).fetchone()
        session = Session.from_row(row)
        assert session.transcript_path is None


class TestActivityStoreTranscriptPath:
    """Integration tests for transcript_path through the ActivityStore."""

    @pytest.fixture
    def store(self, tmp_path):
        """Create a fresh ActivityStore with the latest schema."""
        from open_agent_kit.features.codebase_intelligence.activity.store import (
            ActivityStore,
        )

        db_path = tmp_path / "test.db"
        return ActivityStore(db_path, machine_id="test_machine_abc123")

    def test_update_and_read_transcript_path(self, store):
        """Can store and retrieve transcript_path through the store API."""
        # Create a session first
        session, created = store.get_or_create_session(
            TEST_SESSION_ID_ONE, TEST_AGENT_CLAUDE, TEST_PROJECT_ROOT
        )
        assert created

        # Update transcript path
        store.update_session_transcript_path(TEST_SESSION_ID_ONE, TEST_TRANSCRIPT_PATH_ONE)

        # Read it back
        updated = store.get_session(TEST_SESSION_ID_ONE)
        assert updated is not None
        assert updated.transcript_path == TEST_TRANSCRIPT_PATH_ONE

    def test_transcript_path_none_by_default(self, store):
        """New sessions have transcript_path=None."""
        session, created = store.get_or_create_session(
            TEST_SESSION_ID_TWO, TEST_AGENT_CLAUDE, TEST_PROJECT_ROOT
        )
        assert created
        assert session.transcript_path is None

    def test_transcript_path_survives_session_end(self, store):
        """transcript_path persists after session is ended."""
        store.get_or_create_session(TEST_SESSION_ID_THREE, TEST_AGENT_CLAUDE, TEST_PROJECT_ROOT)
        store.update_session_transcript_path(TEST_SESSION_ID_THREE, TEST_TRANSCRIPT_PATH_GENERIC)
        store.end_session(TEST_SESSION_ID_THREE)

        session = store.get_session(TEST_SESSION_ID_THREE)
        assert session is not None
        assert session.status == TEST_SESSION_STATUS_COMPLETED
        assert session.transcript_path == TEST_TRANSCRIPT_PATH_GENERIC
