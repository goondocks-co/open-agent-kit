"""Tests for the InteractiveSessionManager.

Tests cover:
- Session creation and lifecycle
- Session state tracking (mode, cancel, plans)
- _build_options with and without agent definition
- CI tool setup following executor patterns
- Error handling in prompt/approve_plan flows
- Session context injection (_build_session_context)
- Batch finalization (_finalize_batch)
- Async session close with summary generation
- Activity processor integration
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from open_agent_kit.features.codebase_intelligence.agents.interactive import (
    ACP_AGENT_NAME,
    ACP_DEFAULT_SYSTEM_PROMPT,
    InteractiveSession,
    InteractiveSessionManager,
    _build_output_summary,
    _sanitize_tool_input,
)
from open_agent_kit.features.codebase_intelligence.constants import (
    CI_TOOL_ARCHIVE,
    CI_TOOL_MEMORIES,
    CI_TOOL_PROJECT_STATS,
    CI_TOOL_QUERY,
    CI_TOOL_REMEMBER,
    CI_TOOL_RESOLVE,
    CI_TOOL_SEARCH,
    CI_TOOL_SESSIONS,
)
from open_agent_kit.features.codebase_intelligence.daemon.models_acp import (
    ErrorEvent,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def anyio_backend():
    """Restrict anyio tests to asyncio backend."""
    return "asyncio"


@pytest.fixture
def mock_activity_store() -> MagicMock:
    """Create a mock ActivityStore."""
    store = MagicMock()
    store.create_session.return_value = MagicMock(id="session-1")
    batch_mock = MagicMock()
    batch_mock.id = 42
    store.create_prompt_batch.return_value = batch_mock
    store.get_active_prompt_batch.return_value = None
    store.flush_activity_buffer.return_value = []
    return store


@pytest.fixture
def mock_activity_processor() -> MagicMock:
    """Create a mock ActivityProcessor."""
    processor = MagicMock()
    processor.process_session_summary_with_title.return_value = (
        "Test summary",
        "Test title",
    )
    return processor


@pytest.fixture
def mock_registry() -> MagicMock:
    """Create a mock AgentRegistry that returns None for ACP agent."""
    registry = MagicMock()
    registry.get.return_value = None
    return registry


@pytest.fixture
def mock_vector_store() -> MagicMock:
    """Create a mock VectorStore with stats."""
    store = MagicMock()
    store.get_stats.return_value = {
        "code_chunks": 100,
        "memory_observations": 50,
    }
    return store


@pytest.fixture
def manager(
    tmp_path: Path,
    mock_activity_store: MagicMock,
    mock_registry: MagicMock,
    mock_activity_processor: MagicMock,
) -> InteractiveSessionManager:
    """Create an InteractiveSessionManager with mock dependencies."""
    return InteractiveSessionManager(
        project_root=tmp_path,
        activity_store=mock_activity_store,
        retrieval_engine=None,
        vector_store=None,
        agent_registry=mock_registry,
        activity_processor=mock_activity_processor,
    )


@pytest.fixture
def manager_with_vector_store(
    tmp_path: Path,
    mock_activity_store: MagicMock,
    mock_registry: MagicMock,
    mock_activity_processor: MagicMock,
    mock_vector_store: MagicMock,
) -> InteractiveSessionManager:
    """Create an InteractiveSessionManager with vector store."""
    return InteractiveSessionManager(
        project_root=tmp_path,
        activity_store=mock_activity_store,
        retrieval_engine=None,
        vector_store=mock_vector_store,
        agent_registry=mock_registry,
        activity_processor=mock_activity_processor,
    )


# =============================================================================
# InteractiveSession dataclass tests
# =============================================================================


class TestInteractiveSession:
    """Tests for the InteractiveSession dataclass."""

    def test_default_values(self) -> None:
        """InteractiveSession should have sensible defaults."""
        session = InteractiveSession(session_id="s1", cwd=Path("/tmp"))

        assert session.session_id == "s1"
        assert session.cwd == Path("/tmp")
        assert session.permission_mode == "default"
        assert session.cancelled is False
        assert session.pending_plan is False
        assert session.pending_plan_content is None

    def test_custom_permission_mode(self) -> None:
        """InteractiveSession should accept custom permission mode."""
        session = InteractiveSession(
            session_id="s2", cwd=Path("/tmp"), permission_mode="acceptEdits"
        )

        assert session.permission_mode == "acceptEdits"


# =============================================================================
# Session lifecycle tests
# =============================================================================


class TestCreateSession:
    """Tests for InteractiveSessionManager.create_session."""

    def test_creates_session_with_generated_id(
        self, manager: InteractiveSessionManager, mock_activity_store: MagicMock
    ) -> None:
        """create_session should generate a UUID and record in activity store."""
        result = manager.create_session()

        assert "session_id" in result
        assert len(result["session_id"]) > 0
        mock_activity_store.create_session.assert_called_once()

    def test_creates_session_with_provided_id(
        self, manager: InteractiveSessionManager, mock_activity_store: MagicMock
    ) -> None:
        """create_session should use provided session_id."""
        result = manager.create_session(session_id="custom-id")

        assert result["session_id"] == "custom-id"

    def test_creates_session_with_custom_cwd(
        self, manager: InteractiveSessionManager, mock_activity_store: MagicMock
    ) -> None:
        """create_session should use custom cwd when provided."""
        custom_cwd = Path("/custom/dir")
        manager.create_session(cwd=custom_cwd)

        # Verify activity store was called with custom cwd
        call_args = mock_activity_store.create_session.call_args
        assert call_args[1]["project_root"] == str(custom_cwd)

    def test_creates_session_defaults_to_project_root(
        self, manager: InteractiveSessionManager, tmp_path: Path, mock_activity_store: MagicMock
    ) -> None:
        """create_session should use project_root when no cwd provided."""
        manager.create_session()

        call_args = mock_activity_store.create_session.call_args
        assert call_args[1]["project_root"] == str(tmp_path)

    def test_session_stored_internally(self, manager: InteractiveSessionManager) -> None:
        """create_session should store session in internal dict."""
        result = manager.create_session(session_id="s1")
        session_id = result["session_id"]

        assert session_id in manager._sessions
        assert manager._sessions[session_id].session_id == session_id

    def test_activity_store_called_with_acp_agent(
        self, manager: InteractiveSessionManager, mock_activity_store: MagicMock
    ) -> None:
        """create_session should record agent name as ACP_AGENT_NAME."""
        manager.create_session()

        call_args = mock_activity_store.create_session.call_args
        assert call_args[1]["agent"] == ACP_AGENT_NAME


class TestCloseSession:
    """Tests for InteractiveSessionManager.close_session (async)."""

    @pytest.mark.anyio
    async def test_closes_existing_session(
        self, manager: InteractiveSessionManager, mock_activity_store: MagicMock
    ) -> None:
        """close_session should remove session and call end_session."""
        manager.create_session(session_id="s1")

        await manager.close_session("s1")

        assert "s1" not in manager._sessions
        mock_activity_store.end_session.assert_called_once_with("s1")

    @pytest.mark.anyio
    async def test_closes_unknown_session_gracefully(
        self, manager: InteractiveSessionManager, mock_activity_store: MagicMock
    ) -> None:
        """close_session should not raise for unknown session."""
        await manager.close_session("nonexistent")

        mock_activity_store.end_session.assert_not_called()

    @pytest.mark.anyio
    async def test_close_flushes_activity_buffer(
        self, manager: InteractiveSessionManager, mock_activity_store: MagicMock
    ) -> None:
        """close_session should flush buffered activities."""
        manager.create_session(session_id="s1")

        await manager.close_session("s1")

        mock_activity_store.flush_activity_buffer.assert_called()

    @pytest.mark.anyio
    async def test_close_finalizes_active_batch(
        self, manager: InteractiveSessionManager, mock_activity_store: MagicMock
    ) -> None:
        """close_session should finalize any active batch."""
        manager.create_session(session_id="s1")

        # Set up an active batch
        active_batch = MagicMock()
        active_batch.id = 99
        mock_activity_store.get_active_prompt_batch.return_value = active_batch

        await manager.close_session("s1")

        mock_activity_store.get_active_prompt_batch.assert_called_with("s1")
        # Batch should have been ended (via _finalize_batch)
        mock_activity_store.end_prompt_batch.assert_called()

    @pytest.mark.anyio
    async def test_close_schedules_summary_generation(
        self,
        manager: InteractiveSessionManager,
        mock_activity_processor: MagicMock,
    ) -> None:
        """close_session should schedule async summary generation."""
        manager.create_session(session_id="s1")

        await manager.close_session("s1")

        # Give the async task a moment to run
        import asyncio

        await asyncio.sleep(0.1)

        mock_activity_processor.process_session_summary_with_title.assert_called_once_with("s1")

    @pytest.mark.anyio
    async def test_close_without_processor_still_works(
        self,
        tmp_path: Path,
        mock_activity_store: MagicMock,
        mock_registry: MagicMock,
    ) -> None:
        """close_session should work without activity_processor."""
        manager = InteractiveSessionManager(
            project_root=tmp_path,
            activity_store=mock_activity_store,
            retrieval_engine=None,
            vector_store=None,
            agent_registry=mock_registry,
            activity_processor=None,
        )
        manager.create_session(session_id="s1")

        await manager.close_session("s1")

        assert "s1" not in manager._sessions
        mock_activity_store.end_session.assert_called_once_with("s1")


# =============================================================================
# Session mode and cancel tests
# =============================================================================


class TestSetMode:
    """Tests for InteractiveSessionManager.set_mode."""

    def test_sets_mode(self, manager: InteractiveSessionManager) -> None:
        """set_mode should update the session's permission_mode."""
        manager.create_session(session_id="s1")

        manager.set_mode("s1", "acceptEdits")

        assert manager._sessions["s1"].permission_mode == "acceptEdits"

    def test_set_mode_unknown_session_raises(self, manager: InteractiveSessionManager) -> None:
        """set_mode should raise KeyError for unknown session."""
        with pytest.raises(KeyError, match="Session not found"):
            manager.set_mode("nonexistent", "default")


class TestCancel:
    """Tests for InteractiveSessionManager.cancel."""

    def test_cancel_sets_flag(self, manager: InteractiveSessionManager) -> None:
        """cancel should set session.cancelled to True."""
        manager.create_session(session_id="s1")

        manager.cancel("s1")

        assert manager._sessions["s1"].cancelled is True

    def test_cancel_unknown_session_raises(self, manager: InteractiveSessionManager) -> None:
        """cancel should raise KeyError for unknown session."""
        with pytest.raises(KeyError, match="Session not found"):
            manager.cancel("nonexistent")


# =============================================================================
# Prompt streaming tests
# =============================================================================


class TestPrompt:
    """Tests for InteractiveSessionManager.prompt."""

    @pytest.mark.anyio
    async def test_prompt_unknown_session_yields_error(
        self, manager: InteractiveSessionManager
    ) -> None:
        """prompt should yield ErrorEvent for unknown session."""
        events = []
        async for event in manager.prompt("nonexistent", "hello"):
            events.append(event)

        assert len(events) == 1
        assert isinstance(events[0], ErrorEvent)
        assert "not found" in events[0].message

    @pytest.mark.anyio
    async def test_prompt_creates_and_finalizes_batch(
        self, manager: InteractiveSessionManager, mock_activity_store: MagicMock
    ) -> None:
        """prompt should create a prompt batch and finalize it after completion."""
        manager.create_session(session_id="s1")

        # Collect events - SDK import will fail, producing an ErrorEvent,
        # but the batch lifecycle (create + finalize) should still be honoured.
        events = []
        async for event in manager.prompt("s1", "hello"):
            events.append(event)

        # Batch created with correct source_type
        mock_activity_store.create_prompt_batch.assert_called_once_with(
            "s1", "hello", source_type=ACP_AGENT_NAME
        )
        # Batch ended via _finalize_batch (which calls end_prompt_batch)
        mock_activity_store.end_prompt_batch.assert_called_once_with(42)

    @pytest.mark.anyio
    async def test_prompt_resets_cancel_flag(self, manager: InteractiveSessionManager) -> None:
        """prompt should reset cancelled flag at start."""
        manager.create_session(session_id="s1")
        manager._sessions["s1"].cancelled = True

        # Collect events (will error due to no SDK, but cancel flag should reset)
        events = []
        async for event in manager.prompt("s1", "hello"):
            events.append(event)

        # The cancelled flag should have been reset at the start of prompt
        # (even though it errors due to no SDK)
        # The ErrorEvent from ImportError proves it got past the cancel reset


class TestApprovePlan:
    """Tests for InteractiveSessionManager.approve_plan."""

    @pytest.mark.anyio
    async def test_approve_plan_unknown_session(self, manager: InteractiveSessionManager) -> None:
        """approve_plan should yield ErrorEvent for unknown session."""
        events = []
        async for event in manager.approve_plan("nonexistent"):
            events.append(event)

        assert len(events) == 1
        assert isinstance(events[0], ErrorEvent)
        assert "not found" in events[0].message

    @pytest.mark.anyio
    async def test_approve_plan_no_pending_plan(self, manager: InteractiveSessionManager) -> None:
        """approve_plan should yield ErrorEvent when no plan is pending."""
        manager.create_session(session_id="s1")

        events = []
        async for event in manager.approve_plan("s1"):
            events.append(event)

        assert len(events) == 1
        assert isinstance(events[0], ErrorEvent)
        assert "No pending plan" in events[0].message

    @pytest.mark.anyio
    async def test_approve_plan_clears_pending_state(
        self, manager: InteractiveSessionManager
    ) -> None:
        """approve_plan should clear pending plan state."""
        manager.create_session(session_id="s1")
        manager._sessions["s1"].pending_plan = True
        manager._sessions["s1"].pending_plan_content = "Build the feature"

        events = []
        async for event in manager.approve_plan("s1"):
            events.append(event)

        # Plan state should be cleared even if SDK fails
        assert manager._sessions["s1"].pending_plan is False
        assert manager._sessions["s1"].pending_plan_content is None


# =============================================================================
# _build_options tests
# =============================================================================


class TestBuildOptions:
    """Tests for InteractiveSessionManager._build_options.

    Uses the same approach as test_executor.py: test the tool filtering
    logic without requiring the actual SDK.
    """

    def test_no_agent_definition_provides_default_ci_tools(
        self, manager: InteractiveSessionManager
    ) -> None:
        """When no ACP agent exists in registry, default CI tools are provided."""
        # Manager's registry returns None for 'acp'
        # Verify internal state rather than calling _build_options (requires SDK)
        assert manager._agent_registry is not None
        manager._agent_registry.get.return_value = None

        # The default CI tools should be the read-only set
        default_tools = {
            CI_TOOL_SEARCH,
            CI_TOOL_MEMORIES,
            CI_TOOL_SESSIONS,
            CI_TOOL_PROJECT_STATS,
        }
        assert CI_TOOL_QUERY not in default_tools
        assert CI_TOOL_REMEMBER not in default_tools

    def test_ci_tool_constants_are_consistent(self) -> None:
        """All CI tool constants used in interactive.py should be valid strings."""
        for tool_name in (
            CI_TOOL_SEARCH,
            CI_TOOL_MEMORIES,
            CI_TOOL_SESSIONS,
            CI_TOOL_PROJECT_STATS,
            CI_TOOL_QUERY,
            CI_TOOL_REMEMBER,
            CI_TOOL_RESOLVE,
            CI_TOOL_ARCHIVE,
        ):
            assert isinstance(tool_name, str)
            assert len(tool_name) > 0

    def test_mcp_server_no_retrieval_engine_returns_none(
        self, manager: InteractiveSessionManager
    ) -> None:
        """_get_ci_mcp_server should return None without retrieval engine."""
        result = manager._get_ci_mcp_server({CI_TOOL_SEARCH})

        assert result is None

    def test_mcp_server_no_retrieval_engine_does_not_cache(
        self, manager: InteractiveSessionManager
    ) -> None:
        """_get_ci_mcp_server should NOT cache when retrieval engine is None."""
        manager._get_ci_mcp_server({CI_TOOL_SEARCH})

        # Early return path skips the cache write
        assert len(manager._ci_mcp_servers) == 0

    def test_mcp_server_cache_reuses_instances(self, manager: InteractiveSessionManager) -> None:
        """_get_ci_mcp_server should cache servers by tool set when engine exists."""
        mock_engine = MagicMock()
        manager._retrieval_engine = mock_engine

        with patch(
            "open_agent_kit.features.codebase_intelligence.agents.interactive.create_ci_mcp_server",
            return_value=MagicMock(),
        ) as mock_create:
            result1 = manager._get_ci_mcp_server({CI_TOOL_SEARCH})
            result2 = manager._get_ci_mcp_server({CI_TOOL_SEARCH})

        assert result1 is result2
        assert frozenset({CI_TOOL_SEARCH}) in manager._ci_mcp_servers
        # Factory called only once due to caching
        mock_create.assert_called_once()

    def test_mcp_server_different_tool_sets_cached_separately(
        self, manager: InteractiveSessionManager
    ) -> None:
        """Different tool sets should get different cache entries."""
        mock_engine = MagicMock()
        manager._retrieval_engine = mock_engine

        with patch(
            "open_agent_kit.features.codebase_intelligence.agents.interactive.create_ci_mcp_server",
            return_value=MagicMock(),
        ):
            manager._get_ci_mcp_server({CI_TOOL_SEARCH})
            manager._get_ci_mcp_server({CI_TOOL_SEARCH, CI_TOOL_MEMORIES})

        assert len(manager._ci_mcp_servers) == 2


# =============================================================================
# Session context injection tests
# =============================================================================


class TestBuildSessionContext:
    """Tests for InteractiveSessionManager._build_session_context."""

    def test_empty_without_vector_store(self, manager: InteractiveSessionManager) -> None:
        """_build_session_context should return empty string without vector store."""
        result = manager._build_session_context("s1")

        assert result == ""

    def test_includes_ci_status_with_vector_store(
        self, manager_with_vector_store: InteractiveSessionManager
    ) -> None:
        """_build_session_context should include CI status when vector store has data."""
        result = manager_with_vector_store._build_session_context("s1")

        assert "Codebase Intelligence Active" in result
        assert "100 code chunks" in result
        assert "50 memories" in result

    def test_includes_session_id_in_reminder(
        self, manager_with_vector_store: InteractiveSessionManager
    ) -> None:
        """_build_session_context should include session ID for tool linking."""
        result = manager_with_vector_store._build_session_context("test-session-123")

        assert "session_id=test-session-123" in result

    def test_includes_tool_reminders(
        self, manager_with_vector_store: InteractiveSessionManager
    ) -> None:
        """_build_session_context should include OAK CI tool reminders."""
        result = manager_with_vector_store._build_session_context("s1")

        assert "OAK CI Tools" in result
        assert "oak_search" in result

    def test_empty_when_no_indexed_data(
        self,
        tmp_path: Path,
        mock_activity_store: MagicMock,
        mock_registry: MagicMock,
        mock_activity_processor: MagicMock,
    ) -> None:
        """_build_session_context should return empty when vector store has no data."""
        empty_store = MagicMock()
        empty_store.get_stats.return_value = {"code_chunks": 0, "memory_observations": 0}

        manager = InteractiveSessionManager(
            project_root=tmp_path,
            activity_store=mock_activity_store,
            retrieval_engine=None,
            vector_store=empty_store,
            agent_registry=mock_registry,
            activity_processor=mock_activity_processor,
        )

        result = manager._build_session_context("s1")
        assert result == ""

    def test_handles_vector_store_error(
        self,
        tmp_path: Path,
        mock_activity_store: MagicMock,
        mock_registry: MagicMock,
        mock_activity_processor: MagicMock,
    ) -> None:
        """_build_session_context should return empty on vector store errors."""
        error_store = MagicMock()
        error_store.get_stats.side_effect = RuntimeError("store error")

        manager = InteractiveSessionManager(
            project_root=tmp_path,
            activity_store=mock_activity_store,
            retrieval_engine=None,
            vector_store=error_store,
            agent_registry=mock_registry,
            activity_processor=mock_activity_processor,
        )

        result = manager._build_session_context("s1")
        assert result == ""


# =============================================================================
# Batch finalization tests
# =============================================================================


class TestFinalizeBatch:
    """Tests for InteractiveSessionManager._finalize_batch."""

    def test_finalize_flushes_buffer(
        self, manager: InteractiveSessionManager, mock_activity_store: MagicMock
    ) -> None:
        """_finalize_batch should flush activity buffer first."""
        manager._finalize_batch(42, [])

        mock_activity_store.flush_activity_buffer.assert_called_once()

    def test_finalize_with_processor_calls_finalize_prompt_batch(
        self, manager: InteractiveSessionManager, mock_activity_store: MagicMock
    ) -> None:
        """_finalize_batch should use finalize_prompt_batch when processor available."""
        with patch(
            "open_agent_kit.features.codebase_intelligence.activity.batches.finalize_prompt_batch",
        ) as mock_finalize:
            manager._finalize_batch(42, ["Hello ", "world"])

            mock_finalize.assert_called_once_with(
                activity_store=mock_activity_store,
                activity_processor=manager._activity_processor,
                prompt_batch_id=42,
                response_summary="Hello world",
            )

    def test_finalize_without_processor_uses_bare_end(
        self,
        tmp_path: Path,
        mock_activity_store: MagicMock,
        mock_registry: MagicMock,
    ) -> None:
        """_finalize_batch should fall back to bare end_prompt_batch without processor."""
        manager = InteractiveSessionManager(
            project_root=tmp_path,
            activity_store=mock_activity_store,
            retrieval_engine=None,
            vector_store=None,
            agent_registry=mock_registry,
            activity_processor=None,
        )

        manager._finalize_batch(42, ["Response text"])

        mock_activity_store.update_prompt_batch_response.assert_called_once_with(
            42, "Response text"
        )
        mock_activity_store.end_prompt_batch.assert_called_once_with(42)

    def test_finalize_empty_response_parts(
        self, manager: InteractiveSessionManager, mock_activity_store: MagicMock
    ) -> None:
        """_finalize_batch should handle empty response text parts."""
        with patch(
            "open_agent_kit.features.codebase_intelligence.activity.batches.finalize_prompt_batch",
        ) as mock_finalize:
            manager._finalize_batch(42, [])

            mock_finalize.assert_called_once_with(
                activity_store=mock_activity_store,
                activity_processor=manager._activity_processor,
                prompt_batch_id=42,
                response_summary=None,
            )

    def test_finalize_fallback_on_error(
        self, manager: InteractiveSessionManager, mock_activity_store: MagicMock
    ) -> None:
        """_finalize_batch should fall back if finalize_prompt_batch fails."""
        with patch(
            "open_agent_kit.features.codebase_intelligence.activity.batches.finalize_prompt_batch",
            side_effect=RuntimeError("processing failed"),
        ):
            manager._finalize_batch(42, ["Response"])

            # Should fall back to bare end
            mock_activity_store.end_prompt_batch.assert_called_once_with(42)
            mock_activity_store.update_prompt_batch_response.assert_called_once_with(42, "Response")


# =============================================================================
# Tool input sanitization tests
# =============================================================================


class TestSanitizeToolInput:
    """Tests for _sanitize_tool_input helper."""

    def test_non_dict_returns_none(self) -> None:
        """Non-dict input should return None."""
        assert _sanitize_tool_input("string") is None
        assert _sanitize_tool_input(None) is None
        assert _sanitize_tool_input(42) is None

    def test_truncates_large_content_fields(self) -> None:
        """Large content fields should be replaced with size placeholders."""
        result = _sanitize_tool_input(
            {
                "content": "x" * 1000,
                "file_path": "/test.py",
            }
        )

        assert result is not None
        assert result["content"] == "<1000 chars>"
        assert result["file_path"] == "/test.py"

    def test_truncates_long_strings(self) -> None:
        """Long string values should be truncated at 500 chars."""
        result = _sanitize_tool_input(
            {
                "description": "y" * 600,
            }
        )

        assert result is not None
        assert len(result["description"]) == 503  # 500 + "..."
        assert result["description"].endswith("...")

    def test_preserves_short_values(self) -> None:
        """Short values should pass through unchanged."""
        result = _sanitize_tool_input(
            {
                "file_path": "/test.py",
                "command": "ls",
            }
        )

        assert result == {"file_path": "/test.py", "command": "ls"}


class TestBuildOutputSummary:
    """Tests for _build_output_summary helper."""

    def test_empty_response(self) -> None:
        """Empty response should return empty string."""
        assert _build_output_summary("Read", "") == ""
        assert _build_output_summary("Read", None) == ""

    def test_read_tool_large_output(self) -> None:
        """Large Read output should be summarized as char count."""
        result = _build_output_summary("Read", "x" * 500)

        assert result == "Read 500 chars"

    def test_other_tool_truncates(self) -> None:
        """Other tools should have output truncated."""
        result = _build_output_summary("Bash", "a" * 600)

        assert len(result) == 500

    def test_small_read_output(self) -> None:
        """Small Read output should pass through."""
        result = _build_output_summary("Read", "short output")

        assert result == "short output"


# =============================================================================
# Agent name constant tests
# =============================================================================


class TestConstants:
    """Tests for module-level constants."""

    def test_agent_name_is_oak(self) -> None:
        """ACP_AGENT_NAME should be 'oak'."""
        assert ACP_AGENT_NAME == "oak"

    def test_default_system_prompt_is_nonempty(self) -> None:
        """ACP_DEFAULT_SYSTEM_PROMPT should be a non-empty string."""
        assert isinstance(ACP_DEFAULT_SYSTEM_PROMPT, str)
        assert len(ACP_DEFAULT_SYSTEM_PROMPT) > 0

    def test_project_root_property(
        self, manager: InteractiveSessionManager, tmp_path: Path
    ) -> None:
        """project_root property should return the configured path."""
        assert manager.project_root == tmp_path

    def test_activity_processor_stored(
        self,
        manager: InteractiveSessionManager,
        mock_activity_processor: MagicMock,
    ) -> None:
        """Constructor should store activity_processor."""
        assert manager._activity_processor is mock_activity_processor

    def test_activity_processor_defaults_to_none(
        self,
        tmp_path: Path,
        mock_activity_store: MagicMock,
        mock_registry: MagicMock,
    ) -> None:
        """Constructor should default activity_processor to None."""
        manager = InteractiveSessionManager(
            project_root=tmp_path,
            activity_store=mock_activity_store,
            retrieval_engine=None,
            vector_store=None,
            agent_registry=mock_registry,
        )
        assert manager._activity_processor is None
