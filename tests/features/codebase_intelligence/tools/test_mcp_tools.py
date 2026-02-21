"""Tests for expanded MCP tools.

Tests cover:
- MCPToolHandler store injection from retrieval engine
- MCP tool definitions schema correctness
- Handler dispatch routing for all 8 tools
- oak_sessions listing through ToolOperations
- oak_memories listing through ToolOperations
- oak_stats through ToolOperations
- oak_activity (list_activities) through ToolOperations
- ActivityInput Pydantic validation
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from open_agent_kit.features.codebase_intelligence.activity.store.core import ActivityStore
from open_agent_kit.features.codebase_intelligence.daemon.mcp_tools import (
    MCP_TOOLS,
    MCPToolHandler,
)
from open_agent_kit.features.codebase_intelligence.tools.operations import ToolOperations
from open_agent_kit.features.codebase_intelligence.tools.schemas import ActivityInput

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def activity_store(tmp_path: Path) -> ActivityStore:
    """Create an ActivityStore with a real SQLite database."""
    db_path = tmp_path / "test_activities.db"
    return ActivityStore(db_path=db_path, machine_id="test_machine")


@pytest.fixture
def seeded_store(activity_store: ActivityStore) -> ActivityStore:
    """ActivityStore with test data pre-inserted."""
    conn = activity_store._get_connection()
    # Insert 2 sessions
    conn.execute(
        "INSERT INTO sessions (id, agent, status, created_at_epoch, project_root, started_at, summary, title) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "session-1",
            "claude",
            "completed",
            1700000000,
            "/test/project",
            "2023-11-14T20:00:00",
            "Worked on authentication",
            "Auth feature",
        ),
    )
    conn.execute(
        "INSERT INTO sessions (id, agent, status, created_at_epoch, project_root, started_at, summary, title) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "session-2",
            "cursor",
            "active",
            1700001000,
            "/test/project",
            "2023-11-14T20:16:40",
            "Debugging tests",
            "Test fixes",
        ),
    )
    # Insert 5 activities: 3 success + 2 failures
    for i in range(3):
        epoch = 1700000000 + i
        conn.execute(
            "INSERT INTO activities (session_id, tool_name, file_path, success, "
            "tool_output_summary, timestamp, timestamp_epoch) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "session-1",
                "Edit",
                f"/test/file_{i}.py",
                1,
                f"Edited file {i}",
                "2023-11-14T20:00:00",
                epoch,
            ),
        )
    for i in range(2):
        epoch = 1700000003 + i
        conn.execute(
            "INSERT INTO activities (session_id, tool_name, file_path, success, "
            "error_message, timestamp, timestamp_epoch) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "session-1",
                "Bash",
                f"/test/script_{i}.sh",
                0,
                f"Command failed with exit code {i + 1}",
                "2023-11-14T20:00:00",
                epoch,
            ),
        )
    # Insert 2 observations
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
    conn.execute(
        "INSERT INTO memory_observations (id, session_id, observation, memory_type, context, "
        "created_at, created_at_epoch) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            "obs-2",
            "session-1",
            "Database connection pattern",
            "discovery",
            "db.py",
            "2023-11-14T20:10:00",
            1700000600,
        ),
    )
    conn.commit()
    return activity_store


@pytest.fixture
def mock_engine() -> MagicMock:
    """Create a mock RetrievalEngine."""
    engine = MagicMock()
    engine.activity_store = None
    engine.store = None
    # Mock methods that ToolOperations might call
    engine.search.return_value = MagicMock(code=[], memory=[], plans=[], sessions=[])
    engine.remember.return_value = "test-obs-id"
    engine.get_task_context.return_value = MagicMock(code=[], memories=[])
    engine.list_memories.return_value = ([], 0)
    engine.resolve_memory.return_value = True
    return engine


@pytest.fixture
def mock_vector_store() -> MagicMock:
    """Create a mock VectorStore."""
    vs = MagicMock()
    vs.get_stats.return_value = {
        "code_chunks": 100,
        "unique_files": 20,
        "memory_count": 50,
    }
    return vs


@pytest.fixture
def ops(
    mock_engine: MagicMock,
    seeded_store: ActivityStore,
    mock_vector_store: MagicMock,
) -> ToolOperations:
    """Create ToolOperations with seeded store."""
    return ToolOperations(
        retrieval_engine=mock_engine,
        activity_store=seeded_store,
        vector_store=mock_vector_store,
    )


@pytest.fixture
def handler(
    mock_engine: MagicMock,
    seeded_store: ActivityStore,
    mock_vector_store: MagicMock,
) -> MCPToolHandler:
    """Create MCPToolHandler with engine that has stores set."""
    mock_engine.activity_store = seeded_store
    mock_engine.store = mock_vector_store
    return MCPToolHandler(mock_engine)


# =============================================================================
# MCPToolHandler init tests
# =============================================================================


class TestMCPToolHandlerInit:
    """Verifies store injection from RetrievalEngine into ToolOperations."""

    def test_extracts_stores_from_engine(self, handler: MCPToolHandler) -> None:
        """Handler extracts activity_store and vector_store from engine attributes."""
        assert handler.ops.activity_store is not None
        assert handler.ops.vector_store is not None

    def test_handles_engine_without_stores(self) -> None:
        """Handler gracefully handles engine without activity_store/store attrs."""
        engine = MagicMock(spec=[])  # Empty spec: no attributes
        h = MCPToolHandler(engine)
        assert h.ops.activity_store is None
        assert h.ops.vector_store is None


# =============================================================================
# MCPToolHandler dispatch tests
# =============================================================================


class TestMCPToolHandlerDispatch:
    """Verifies handler routing for all tools."""

    EXPECTED_TOOLS = [
        "oak_search",
        "oak_remember",
        "oak_context",
        "oak_resolve_memory",
        "oak_sessions",
        "oak_memories",
        "oak_stats",
        "oak_activity",
    ]

    def test_all_tools_registered(self, handler: MCPToolHandler) -> None:
        """All 8 tool names route without 'Unknown tool' error."""
        for tool_name in self.EXPECTED_TOOLS:
            # Provide minimal valid args for each tool
            args = self._minimal_args(tool_name)
            result = handler.handle_tool_call(tool_name, args)
            # Should not return "Unknown tool" error
            if result.get("isError"):
                assert (
                    "Unknown tool" not in result["content"][0]["text"]
                ), f"Tool {tool_name} not registered in handler"

    def test_unknown_tool_returns_error(self, handler: MCPToolHandler) -> None:
        """Unknown tool name returns isError response."""
        result = handler.handle_tool_call("fake_tool", {})
        assert result["isError"] is True
        assert "Unknown tool" in result["content"][0]["text"]

    def test_tool_error_returns_error_response(self, handler: MCPToolHandler) -> None:
        """When an ops method raises ValueError, response has isError: True."""
        # Force list_sessions to raise by setting activity_store to None
        handler.ops.activity_store = None
        result = handler.handle_tool_call("oak_sessions", {})
        assert result["isError"] is True
        assert "Tool error" in result["content"][0]["text"]

    def test_successful_call_returns_content(self, handler: MCPToolHandler) -> None:
        """Successful tool call returns content key (no isError)."""
        result = handler.handle_tool_call("oak_stats", {})
        assert "content" in result
        assert "isError" not in result

    @staticmethod
    def _minimal_args(tool_name: str) -> dict:
        """Return minimal valid arguments for each tool."""
        minimal = {
            "oak_search": {"query": "test"},
            "oak_remember": {"observation": "test observation"},
            "oak_context": {"task": "test task"},
            "oak_resolve_memory": {"id": "test-id"},
            "oak_sessions": {},
            "oak_memories": {},
            "oak_stats": {},
            "oak_activity": {"session_id": "session-1"},
        }
        return minimal.get(tool_name, {})


# =============================================================================
# MCP tool definitions tests
# =============================================================================


class TestMCPToolDefinitions:
    """Validates MCP_TOOLS schema definitions."""

    def test_tool_count(self) -> None:
        """There are exactly 9 tools defined."""
        assert len(MCP_TOOLS) == 9

    def test_all_tools_have_required_fields(self) -> None:
        """Each tool definition has name, description, and inputSchema."""
        for tool in MCP_TOOLS:
            assert "name" in tool, f"Tool missing 'name': {tool}"
            assert "description" in tool, f"Tool {tool.get('name')} missing 'description'"
            assert "inputSchema" in tool, f"Tool {tool.get('name')} missing 'inputSchema'"

    def test_oak_search_includes_sessions_type(self) -> None:
        """oak_search search_type enum includes 'sessions'."""
        search_tool = next(t for t in MCP_TOOLS if t["name"] == "oak_search")
        search_type_enum = search_tool["inputSchema"]["properties"]["search_type"]["enum"]
        assert "sessions" in search_type_enum

    def test_oak_search_includes_include_resolved(self) -> None:
        """oak_search has include_resolved in properties."""
        search_tool = next(t for t in MCP_TOOLS if t["name"] == "oak_search")
        assert "include_resolved" in search_tool["inputSchema"]["properties"]

    def test_oak_activity_requires_session_id(self) -> None:
        """oak_activity has session_id in required list."""
        activity_tool = next(t for t in MCP_TOOLS if t["name"] == "oak_activity")
        assert "session_id" in activity_tool["inputSchema"]["required"]

    def test_tool_names_match_handler_keys(self) -> None:
        """MCP_TOOLS names match the handler dispatch dictionary keys."""
        engine = MagicMock()
        engine.activity_store = None
        engine.store = None
        h = MCPToolHandler(engine)

        tool_def_names = {t["name"] for t in MCP_TOOLS}

        # Call each tool name and check none return "Unknown tool"
        for name in tool_def_names:
            result = h.handle_tool_call(
                name, {"query": "x", "observation": "x", "task": "x", "id": "x", "session_id": "x"}
            )
            if result.get("isError"):
                assert (
                    "Unknown tool" not in result["content"][0]["text"]
                ), f"Tool definition '{name}' has no handler"


# =============================================================================
# oak_sessions tests (ToolOperations.list_sessions)
# =============================================================================


class TestListSessions:
    """Verifies oak_sessions through ToolOperations."""

    def test_returns_formatted_sessions(self, ops: ToolOperations) -> None:
        """list_sessions with seeded store returns both sessions."""
        result = ops.list_sessions({})
        assert "Auth feature" in result
        assert "Test fixes" in result
        assert "session-1" in result
        assert "session-2" in result

    def test_respects_limit(self, ops: ToolOperations) -> None:
        """list_sessions with limit=1 returns only 1 session."""
        result = ops.list_sessions({"limit": 1})
        # Should have exactly 1 session (shown in footer)
        assert "(Showing 1 sessions)" in result

    def test_empty_sessions(self, activity_store: ActivityStore) -> None:
        """Fresh activity store with no data returns 'No sessions found.'"""
        engine = MagicMock()
        empty_ops = ToolOperations(
            retrieval_engine=engine,
            activity_store=activity_store,
        )
        result = empty_ops.list_sessions({})
        assert result == "No sessions found."

    def test_requires_activity_store(self, mock_engine: MagicMock) -> None:
        """ToolOperations with activity_store=None raises ValueError."""
        ops_no_store = ToolOperations(
            retrieval_engine=mock_engine,
            activity_store=None,
        )
        with pytest.raises(ValueError, match="Session history not available"):
            ops_no_store.list_sessions({})


# =============================================================================
# oak_memories tests (ToolOperations.list_memories)
# =============================================================================


class TestListMemories:
    """Verifies oak_memories through ToolOperations."""

    def test_returns_formatted_memories(self, ops: ToolOperations) -> None:
        """list_memories returns formatted output when engine has memories."""
        ops.engine.list_memories.return_value = (
            [
                {"observation": "Auth gotcha", "memory_type": "gotcha", "context": "auth.py"},
                {"observation": "DB pattern", "memory_type": "discovery", "context": "db.py"},
            ],
            2,
        )
        result = ops.list_memories({})
        assert "Auth gotcha" in result
        assert "DB pattern" in result
        assert "Showing 2 of 2 total memories" in result

    def test_filters_by_type(self, ops: ToolOperations) -> None:
        """memory_type arg is forwarded to engine.list_memories."""
        ops.engine.list_memories.return_value = ([], 0)
        ops.list_memories({"memory_type": "gotcha"})
        _, kwargs = ops.engine.list_memories.call_args
        assert kwargs["memory_types"] == ["gotcha"]

    def test_empty_memories(self, ops: ToolOperations) -> None:
        """Engine returning empty list produces 'No memories found.'"""
        ops.engine.list_memories.return_value = ([], 0)
        result = ops.list_memories({})
        assert result == "No memories found."


# =============================================================================
# oak_stats tests (ToolOperations.get_stats)
# =============================================================================


class TestGetStats:
    """Verifies oak_stats through ToolOperations."""

    def test_returns_formatted_stats(self, ops: ToolOperations) -> None:
        """Both stores contribute to stats output."""
        result = ops.get_stats({})
        assert "Code Index" in result
        assert "Indexed chunks: 100" in result
        assert "Unique files: 20" in result
        assert "Activity History" in result

    def test_handles_missing_vector_store(
        self,
        mock_engine: MagicMock,
        seeded_store: ActivityStore,
    ) -> None:
        """Stats works without vector store (shows zero code stats)."""
        ops_no_vs = ToolOperations(
            retrieval_engine=mock_engine,
            activity_store=seeded_store,
            vector_store=None,
        )
        result = ops_no_vs.get_stats({})
        assert "Code Index" in result
        assert "Indexed chunks: 0" in result

    def test_handles_missing_activity_store(
        self,
        mock_engine: MagicMock,
        mock_vector_store: MagicMock,
    ) -> None:
        """Stats works without activity store (no activity history section)."""
        ops_no_as = ToolOperations(
            retrieval_engine=mock_engine,
            activity_store=None,
            vector_store=mock_vector_store,
        )
        result = ops_no_as.get_stats({})
        assert "Code Index" in result
        # No observations means no Activity History section
        assert "Activity History" not in result


# =============================================================================
# oak_activity tests (ToolOperations.list_activities)
# =============================================================================


class TestListActivities:
    """Verifies oak_activity through ToolOperations."""

    def test_returns_formatted_activities(self, ops: ToolOperations) -> None:
        """Seeded store returns activities for session-1."""
        result = ops.list_activities({"session_id": "session-1"})
        assert "Found 5 activities" in result
        assert "Edit" in result
        assert "Bash" in result

    def test_filters_by_tool_name(self, ops: ToolOperations) -> None:
        """tool_name='Edit' only returns Edit activities."""
        result = ops.list_activities({"session_id": "session-1", "tool_name": "Edit"})
        assert "Found 3 activities" in result
        assert "Edit" in result
        # Bash activities should not appear
        assert "Bash" not in result

    def test_tool_name_filter_is_case_insensitive(self, ops: ToolOperations) -> None:
        """tool_name='edit' (lowercase) matches 'Edit' activities."""
        result = ops.list_activities({"session_id": "session-1", "tool_name": "edit"})
        assert "Found 3 activities" in result
        assert "Edit" in result

    def test_respects_limit(self, ops: ToolOperations) -> None:
        """limit=2 returns exactly 2 activities."""
        result = ops.list_activities({"session_id": "session-1", "limit": 2})
        assert "Found 2 activities" in result

    def test_empty_activities(self, ops: ToolOperations) -> None:
        """Nonexistent session returns 'No activities found.'"""
        result = ops.list_activities({"session_id": "nonexistent-session"})
        assert result == "No activities found."

    def test_requires_activity_store(self, mock_engine: MagicMock) -> None:
        """ToolOperations with activity_store=None raises ValueError."""
        ops_no_store = ToolOperations(
            retrieval_engine=mock_engine,
            activity_store=None,
        )
        with pytest.raises(ValueError, match="Activity history not available"):
            ops_no_store.list_activities({"session_id": "session-1"})

    def test_shows_error_for_failed_activities(self, ops: ToolOperations) -> None:
        """Failed activities show error message in output."""
        result = ops.list_activities({"session_id": "session-1", "tool_name": "Bash"})
        assert "Command failed with exit code 1" in result
        assert "Command failed with exit code 2" in result
        assert "[x]" in result


# =============================================================================
# ActivityInput schema tests
# =============================================================================


class TestActivityInputSchema:
    """Pydantic validation for ActivityInput."""

    def test_session_id_required(self) -> None:
        """ValidationError when session_id is missing."""
        with pytest.raises(ValidationError):
            ActivityInput()  # type: ignore[call-arg]

    def test_default_limit(self) -> None:
        """Default limit is 50."""
        ai = ActivityInput(session_id="s-1")
        assert ai.limit == 50

    def test_limit_rejects_zero(self) -> None:
        """Limit of 0 is rejected."""
        with pytest.raises(ValidationError):
            ActivityInput(session_id="s-1", limit=0)

    def test_limit_rejects_over_max(self) -> None:
        """Limit of 201 is rejected."""
        with pytest.raises(ValidationError):
            ActivityInput(session_id="s-1", limit=201)

    def test_optional_tool_name(self) -> None:
        """tool_name defaults to None."""
        ai = ActivityInput(session_id="s-1")
        assert ai.tool_name is None
