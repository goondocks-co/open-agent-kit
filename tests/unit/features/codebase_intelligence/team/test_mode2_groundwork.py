"""Tests for Mode 2 groundwork: constants, config flags, and processing queue DDL."""

import sqlite3

from open_agent_kit.features.codebase_intelligence.config.team import TeamConfig
from open_agent_kit.features.codebase_intelligence.constants.team import (
    TEAM_EVENT_RAW_SESSION,
)
from open_agent_kit.features.codebase_intelligence.team.server.processing import (
    TEAM_PROCESSING_QUEUE_DDL,
)


class TestMode2Constants:
    """Verify Phase 1 constants exist with expected values."""

    def test_raw_session_event_type_exists(self) -> None:
        assert TEAM_EVENT_RAW_SESSION == "raw_session"

    def test_raw_session_event_type_is_string(self) -> None:
        assert isinstance(TEAM_EVENT_RAW_SESSION, str)


class TestMode2ConfigFlag:
    """Verify server_side_llm config flag defaults."""

    def test_server_side_llm_defaults_false(self) -> None:
        config = TeamConfig()
        assert config.server_side_llm is False

    def test_server_side_llm_can_be_enabled(self) -> None:
        config = TeamConfig(server_side_llm=True)
        assert config.server_side_llm is True

    def test_server_side_llm_from_dict_default(self) -> None:
        config = TeamConfig.from_dict({})
        assert config.server_side_llm is False

    def test_server_side_llm_from_dict_explicit(self) -> None:
        config = TeamConfig.from_dict({"server_side_llm": True})
        assert config.server_side_llm is True


class TestProcessingQueueDDL:
    """Verify processing queue DDL is valid and idempotent."""

    def test_ddl_is_valid_sql(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.executescript(TEAM_PROCESSING_QUEUE_DDL)
        # Verify table was created
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='team_processing_queue'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_ddl_is_idempotent(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.executescript(TEAM_PROCESSING_QUEUE_DDL)
        conn.executescript(TEAM_PROCESSING_QUEUE_DDL)
        # Should still have exactly one table
        cursor = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='team_processing_queue'"
        )
        assert cursor.fetchone()[0] == 1
        conn.close()

    def test_ddl_creates_status_index(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.executescript(TEAM_PROCESSING_QUEUE_DDL)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_team_processing_queue_status'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_ddl_creates_machine_index(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.executescript(TEAM_PROCESSING_QUEUE_DDL)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_team_processing_queue_machine'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_ddl_table_columns(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.executescript(TEAM_PROCESSING_QUEUE_DDL)
        cursor = conn.execute("PRAGMA table_info(team_processing_queue)")
        columns = {row[1] for row in cursor.fetchall()}
        expected = {"id", "machine_id", "session_id", "status", "created_at", "processed_at"}
        assert columns == expected
        conn.close()
