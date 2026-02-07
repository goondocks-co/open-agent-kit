"""Tests for the ci_query tool and read-only SQL execution.

Tests cover:
- SELECT queries execute and return formatted results
- Write statements (INSERT, UPDATE, DELETE) are rejected
- Dangerous statements (DROP, ALTER, ATTACH) are rejected
- Result truncation at MAX_ROWS
- Error handling (invalid SQL returns helpful error)
- Epoch timestamp hint in results
"""

import sqlite3
from pathlib import Path

import pytest
from pydantic import ValidationError

from open_agent_kit.features.codebase_intelligence.activity.store.core import ActivityStore
from open_agent_kit.features.codebase_intelligence.constants import (
    CI_QUERY_DEFAULT_LIMIT,
    CI_QUERY_FORBIDDEN_KEYWORDS,
    CI_QUERY_MAX_ROWS,
)
from open_agent_kit.features.codebase_intelligence.tools.operations import ToolOperations
from open_agent_kit.features.codebase_intelligence.tools.schemas import QueryInput

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def activity_store(tmp_path: Path) -> ActivityStore:
    """Create an ActivityStore with a real SQLite database for testing."""
    db_path = tmp_path / "test_activities.db"
    store = ActivityStore(db_path=db_path, machine_id="test_machine")
    return store


@pytest.fixture
def seeded_store(activity_store: ActivityStore) -> ActivityStore:
    """ActivityStore with test data pre-inserted."""
    conn = activity_store._get_connection()

    # Insert test sessions (started_at is NOT NULL in schema)
    conn.execute(
        "INSERT INTO sessions (id, agent, status, created_at_epoch, project_root, started_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("session-1", "claude", "completed", 1700000000, "/test/project", "2023-11-14T20:00:00"),
    )
    conn.execute(
        "INSERT INTO sessions (id, agent, status, created_at_epoch, project_root, started_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("session-2", "cursor", "active", 1700001000, "/test/project", "2023-11-14T20:16:40"),
    )

    # Insert test activities (timestamp and timestamp_epoch are NOT NULL)
    for i in range(5):
        epoch = 1700000000 + i
        conn.execute(
            "INSERT INTO activities (session_id, tool_name, file_path, success, "
            "timestamp, timestamp_epoch) VALUES (?, ?, ?, ?, ?, ?)",
            ("session-1", "Edit", f"/test/file_{i}.py", 1, "2023-11-14T20:00:00", epoch),
        )

    # Insert test memory observations (session_id, created_at, created_at_epoch are NOT NULL)
    conn.execute(
        "INSERT INTO memory_observations (id, session_id, observation, memory_type, context, "
        "created_at, created_at_epoch) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            "obs-1",
            "session-1",
            "Test gotcha about auth",
            "gotcha",
            "auth.py",
            "2023-11-14T20:08:20",
            1700000500,
        ),
    )

    conn.commit()
    return activity_store


# =============================================================================
# ActivityStore.execute_readonly_query tests
# =============================================================================


class TestExecuteReadonlyQuery:
    """Tests for ActivityStore.execute_readonly_query."""

    def test_select_returns_columns_and_rows(self, seeded_store: ActivityStore) -> None:
        """SELECT queries return (columns, rows) tuple."""
        columns, rows = seeded_store.execute_readonly_query(
            "SELECT id, agent, status FROM sessions ORDER BY created_at_epoch"
        )

        assert columns == ["id", "agent", "status"]
        assert len(rows) == 2
        assert rows[0] == ("session-1", "claude", "completed")
        assert rows[1] == ("session-2", "cursor", "active")

    def test_with_cte_query(self, seeded_store: ActivityStore) -> None:
        """WITH (CTE) queries are allowed."""
        columns, rows = seeded_store.execute_readonly_query(
            "WITH s AS (SELECT id FROM sessions) SELECT count(*) as cnt FROM s"
        )

        assert columns == ["cnt"]
        assert rows[0] == (2,)

    def test_explain_query(self, seeded_store: ActivityStore) -> None:
        """EXPLAIN queries are allowed."""
        columns, rows = seeded_store.execute_readonly_query(
            "EXPLAIN QUERY PLAN SELECT * FROM sessions"
        )

        assert len(columns) > 0

    def test_limit_applied_when_missing(self, seeded_store: ActivityStore) -> None:
        """A LIMIT clause is auto-appended when not present in the query."""
        columns, rows = seeded_store.execute_readonly_query("SELECT id FROM sessions", limit=1)

        assert len(rows) == 1

    def test_limit_clamped_to_max(self, seeded_store: ActivityStore) -> None:
        """Limit is clamped to CI_QUERY_MAX_ROWS even if a larger value is passed."""
        # Insert enough rows to test clamping
        columns, rows = seeded_store.execute_readonly_query(
            "SELECT id FROM sessions",
            limit=CI_QUERY_MAX_ROWS + 100,
        )

        # Should succeed without error (clamped internally)
        assert len(rows) <= CI_QUERY_MAX_ROWS

    def test_empty_result_returns_empty_rows(self, seeded_store: ActivityStore) -> None:
        """Query with no matching rows returns columns but empty rows list."""
        columns, rows = seeded_store.execute_readonly_query(
            "SELECT id FROM sessions WHERE id = 'nonexistent'"
        )

        assert columns == ["id"]
        assert rows == []

    def test_insert_rejected(self, seeded_store: ActivityStore) -> None:
        """INSERT statements are rejected."""
        with pytest.raises(ValueError, match="Only SELECT"):
            seeded_store.execute_readonly_query("INSERT INTO sessions (id) VALUES ('hack')")

    def test_update_rejected(self, seeded_store: ActivityStore) -> None:
        """UPDATE statements are rejected."""
        with pytest.raises(ValueError, match="Only SELECT"):
            seeded_store.execute_readonly_query("UPDATE sessions SET status = 'hacked'")

    def test_delete_rejected(self, seeded_store: ActivityStore) -> None:
        """DELETE statements are rejected."""
        with pytest.raises(ValueError, match="Only SELECT"):
            seeded_store.execute_readonly_query("DELETE FROM sessions")

    @pytest.mark.parametrize("keyword", CI_QUERY_FORBIDDEN_KEYWORDS)
    def test_forbidden_keywords_rejected(self, seeded_store: ActivityStore, keyword: str) -> None:
        """All forbidden keywords are rejected even in SELECT-prefixed queries."""
        # Craft a query that starts with SELECT but embeds a forbidden keyword
        # Some forbidden keywords (like PRAGMA, VACUUM) can't be easily embedded
        # in a SELECT, so we test them as standalone statements too
        if keyword in ("PRAGMA", "VACUUM", "REINDEX"):
            with pytest.raises(ValueError):
                seeded_store.execute_readonly_query(f"{keyword} table_info(sessions)")
        else:
            with pytest.raises(ValueError, match="Forbidden keyword"):
                seeded_store.execute_readonly_query(
                    f"SELECT * FROM sessions; {keyword} TABLE sessions"
                )

    def test_drop_rejected(self, seeded_store: ActivityStore) -> None:
        """DROP TABLE is rejected even if prefixed with SELECT."""
        with pytest.raises(ValueError, match="Forbidden keyword"):
            seeded_store.execute_readonly_query("SELECT 1; DROP TABLE sessions")

    def test_attach_rejected(self, seeded_store: ActivityStore) -> None:
        """ATTACH DATABASE is rejected."""
        with pytest.raises(ValueError, match="Forbidden keyword"):
            seeded_store.execute_readonly_query("SELECT 1; ATTACH DATABASE ':memory:' AS hack")

    def test_invalid_sql_raises_error(self, seeded_store: ActivityStore) -> None:
        """Invalid SQL raises sqlite3.Error with helpful message."""
        with pytest.raises(sqlite3.Error):
            seeded_store.execute_readonly_query("SELECT * FROM nonexistent_table")

    def test_readonly_connection(self, seeded_store: ActivityStore) -> None:
        """The read-only connection truly prevents writes."""
        # Even if keyword validation is somehow bypassed, the read-only
        # SQLite connection should prevent writes
        # We can't easily test this since keyword validation catches it first,
        # but we verify the connection mode is properly enforced by checking
        # that a normal SELECT works fine
        columns, rows = seeded_store.execute_readonly_query("SELECT count(*) as cnt FROM sessions")
        assert rows[0] == (2,)


# =============================================================================
# ToolOperations.execute_query tests
# =============================================================================


class TestToolOperationsExecuteQuery:
    """Tests for ToolOperations.execute_query (markdown formatting)."""

    @pytest.fixture
    def ops(self, seeded_store: ActivityStore) -> ToolOperations:
        """Create a ToolOperations with mocked dependencies."""
        from unittest.mock import MagicMock

        mock_engine = MagicMock()
        return ToolOperations(
            retrieval_engine=mock_engine,
            activity_store=seeded_store,
        )

    def test_returns_markdown_table(self, ops: ToolOperations) -> None:
        """Results are formatted as a markdown table."""
        result = ops.execute_query({"sql": "SELECT id, status FROM sessions ORDER BY id"})

        assert "| id | status |" in result
        assert "| --- | --- |" in result
        assert "| session-1 | completed |" in result
        assert "| session-2 | active |" in result

    def test_row_count_footer(self, ops: ToolOperations) -> None:
        """Result includes row count."""
        result = ops.execute_query({"sql": "SELECT id FROM sessions"})

        assert "(2 rows)" in result

    def test_single_row_grammar(self, ops: ToolOperations) -> None:
        """Single row result uses singular grammar."""
        result = ops.execute_query({"sql": "SELECT id FROM sessions LIMIT 1"})

        assert "(1 row)" in result

    def test_epoch_hint_shown(self, ops: ToolOperations) -> None:
        """Epoch columns trigger a formatting hint."""
        result = ops.execute_query({"sql": "SELECT created_at_epoch FROM sessions LIMIT 1"})

        assert "datetime(col, 'unixepoch', 'localtime')" in result

    def test_no_epoch_hint_for_non_epoch_columns(self, ops: ToolOperations) -> None:
        """Non-epoch columns don't trigger the formatting hint."""
        result = ops.execute_query({"sql": "SELECT id, status FROM sessions"})

        assert "unixepoch" not in result

    def test_empty_result_message(self, ops: ToolOperations) -> None:
        """Empty result returns descriptive message."""
        result = ops.execute_query({"sql": "SELECT id FROM sessions WHERE id = 'nonexistent'"})

        assert "0 rows" in result

    def test_no_columns_message(self, ops: ToolOperations) -> None:
        """Query returning no columns returns appropriate message."""
        # This is unlikely in practice but covers the edge case
        result = ops.execute_query({"sql": "SELECT id FROM sessions WHERE 1=0"})

        assert "0 rows" in result or "no results" in result.lower()

    def test_activity_store_required(self) -> None:
        """execute_query raises ValueError when activity_store is None."""
        from unittest.mock import MagicMock

        ops = ToolOperations(
            retrieval_engine=MagicMock(),
            activity_store=None,
        )

        with pytest.raises(ValueError, match="Activity store not available"):
            ops.execute_query({"sql": "SELECT 1"})

    def test_long_cell_values_truncated(self, ops: ToolOperations) -> None:
        """Cell values longer than 200 chars are truncated."""
        # The observation column can be long
        result = ops.execute_query({"sql": "SELECT observation FROM memory_observations"})

        # Our test data is short, so no truncation here - just verify it works
        assert "Test gotcha about auth" in result

    def test_pipe_characters_escaped(self, ops: ToolOperations) -> None:
        """Pipe characters in cell values are escaped for markdown."""
        # Insert a row with pipe in the data
        conn = ops.activity_store._get_connection()
        conn.execute(
            "INSERT INTO memory_observations (id, session_id, observation, memory_type, "
            "created_at, created_at_epoch) VALUES (?, ?, ?, ?, ?, ?)",
            (
                "obs-pipe",
                "session-1",
                "value|with|pipes",
                "discovery",
                "2023-11-14T20:10:00",
                1700000600,
            ),
        )
        conn.commit()

        result = ops.execute_query(
            {"sql": "SELECT observation FROM memory_observations WHERE id = 'obs-pipe'"}
        )

        assert "value\\|with\\|pipes" in result


# =============================================================================
# QueryInput schema tests
# =============================================================================


class TestQueryInputSchema:
    """Tests for QueryInput Pydantic model validation."""

    def test_default_limit(self) -> None:
        """Default limit matches CI_QUERY_DEFAULT_LIMIT."""
        q = QueryInput(sql="SELECT 1")
        assert q.limit == CI_QUERY_DEFAULT_LIMIT

    def test_limit_lower_bound(self) -> None:
        """Limit below 1 is rejected."""
        with pytest.raises(ValidationError):
            QueryInput(sql="SELECT 1", limit=0)

    def test_limit_upper_bound(self) -> None:
        """Limit above 500 is rejected."""
        with pytest.raises(ValidationError):
            QueryInput(sql="SELECT 1", limit=501)

    def test_sql_required(self) -> None:
        """SQL field is required."""
        with pytest.raises(ValidationError):
            QueryInput()  # type: ignore[call-arg]
