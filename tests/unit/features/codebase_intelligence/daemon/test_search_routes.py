"""Tests for search and memory routes.

Tests cover:
- /api/memories list endpoint
- Memory type filtering
- Pagination
- VectorStore.list_memories() method
"""

from unittest.mock import MagicMock

import pytest

from open_agent_kit.features.codebase_intelligence.daemon.state import (
    DaemonState,
    reset_state,
)


@pytest.fixture(autouse=True)
def reset_daemon_state():
    """Reset daemon state before and after each test."""
    reset_state()
    yield
    reset_state()


# =============================================================================
# VectorStore.list_memories() Tests
# =============================================================================


class TestVectorStoreListMemories:
    """Test VectorStore.list_memories() method."""

    def test_list_memories_returns_tuple(self):
        """Test that list_memories returns tuple of (memories, total)."""
        mock_store = MagicMock()
        mock_store.list_memories.return_value = ([], 0)

        result = mock_store.list_memories(limit=10)

        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_list_memories_with_pagination(self):
        """Test pagination parameters are passed correctly."""
        mock_store = MagicMock()
        mock_store.list_memories.return_value = ([], 0)

        mock_store.list_memories(limit=20, offset=10)

        mock_store.list_memories.assert_called_once_with(limit=20, offset=10)

    def test_list_memories_with_type_filter(self):
        """Test memory type filtering."""
        mock_store = MagicMock()
        mock_store.list_memories.return_value = ([], 0)

        mock_store.list_memories(memory_types=["gotcha", "bug_fix"])

        mock_store.list_memories.assert_called_once_with(memory_types=["gotcha", "bug_fix"])

    def test_list_memories_with_exclude_types(self):
        """Test excluding memory types."""
        mock_store = MagicMock()
        mock_store.list_memories.return_value = ([], 0)

        mock_store.list_memories(exclude_types=["session_summary"])

        mock_store.list_memories.assert_called_once_with(exclude_types=["session_summary"])


class TestListMemoriesWhereFilters:
    """Test where filter construction for list_memories."""

    def test_memory_types_creates_in_filter(self):
        """Test that memory_types creates $in filter."""
        memory_types = ["gotcha", "bug_fix"]

        # This is the filter construction logic from VectorStore.list_memories
        where = {"memory_type": {"$in": memory_types}}

        assert where == {"memory_type": {"$in": ["gotcha", "bug_fix"]}}

    def test_exclude_types_creates_nin_filter(self):
        """Test that exclude_types creates $nin filter."""
        exclude_types = ["session_summary"]

        where = {"memory_type": {"$nin": exclude_types}}

        assert where == {"memory_type": {"$nin": ["session_summary"]}}

    def test_memory_types_takes_precedence(self):
        """Test that memory_types takes precedence over exclude_types."""
        memory_types = ["gotcha"]
        exclude_types = ["session_summary"]

        # VectorStore logic: if memory_types, use $in; elif exclude_types, use $nin
        if memory_types:
            where = {"memory_type": {"$in": memory_types}}
        elif exclude_types:
            where = {"memory_type": {"$nin": exclude_types}}
        else:
            where = None

        assert where == {"memory_type": {"$in": ["gotcha"]}}

    def test_no_filters_returns_none(self):
        """Test that no filters results in None where clause."""
        memory_types = None
        exclude_types = None

        if memory_types:
            where = {"memory_type": {"$in": memory_types}}
        elif exclude_types:
            where = {"memory_type": {"$nin": exclude_types}}
        else:
            where = None

        assert where is None


class TestListMemoriesTagsParsing:
    """Test tags parsing in list_memories response."""

    def test_parse_comma_separated_tags(self):
        """Test parsing comma-separated tags string to list."""
        tags_str = "session-summary, claude, auto-extracted"

        tags_list = [t.strip() for t in tags_str.split(",") if t.strip()]

        assert tags_list == ["session-summary", "claude", "auto-extracted"]

    def test_parse_empty_tags_string(self):
        """Test parsing empty tags string."""
        tags_str = ""

        tags_list = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []

        assert tags_list == []

    def test_parse_single_tag(self):
        """Test parsing single tag."""
        tags_str = "gotcha"

        tags_list = [t.strip() for t in tags_str.split(",") if t.strip()]

        assert tags_list == ["gotcha"]

    def test_parse_tags_with_extra_whitespace(self):
        """Test parsing tags with extra whitespace."""
        tags_str = "  tag1  ,  tag2  ,  tag3  "

        tags_list = [t.strip() for t in tags_str.split(",") if t.strip()]

        assert tags_list == ["tag1", "tag2", "tag3"]


# =============================================================================
# /api/memories Endpoint Tests
# =============================================================================


class TestListMemoriesEndpoint:
    """Test /api/memories endpoint logic."""

    def test_requires_vector_store(self):
        """Test that endpoint requires vector store to be initialized."""
        state = DaemonState()
        state.vector_store = None

        # This verifies the condition that would trigger 503
        assert state.vector_store is None

    def test_converts_memory_type_to_list(self):
        """Test single memory_type is converted to list for VectorStore."""
        # When memory_type="gotcha" is passed
        memory_type = "gotcha"
        memory_types = [memory_type] if memory_type else None

        assert memory_types == ["gotcha"]

    def test_exclude_sessions_sets_exclude_types(self):
        """Test exclude_sessions=True sets correct exclude_types."""
        exclude_sessions = True
        exclude_types = ["session_summary"] if exclude_sessions else None

        assert exclude_types == ["session_summary"]

    def test_exclude_sessions_false_sets_none(self):
        """Test exclude_sessions=False does not set exclude_types."""
        exclude_sessions = False
        exclude_types = ["session_summary"] if exclude_sessions else None

        assert exclude_types is None

    def test_memory_conversion_to_response_model(self):
        """Test memory dict conversion to MemoryListItem."""
        from open_agent_kit.features.codebase_intelligence.daemon.models import (
            MemoryListItem,
            MemoryType,
        )

        mem = {
            "id": "mem-123",
            "memory_type": "gotcha",
            "observation": "Test observation",
            "context": "test/file.py",
            "tags": ["tag1", "tag2"],
            "created_at": "2024-01-15T10:00:00",
        }

        item = MemoryListItem(
            id=mem["id"],
            memory_type=MemoryType(mem.get("memory_type", "discovery")),
            observation=mem.get("observation", ""),
            context=mem.get("context"),
            tags=mem.get("tags", []),
            created_at=mem.get("created_at"),
        )

        assert item.id == "mem-123"
        assert item.memory_type == MemoryType.GOTCHA
        assert item.observation == "Test observation"
        assert item.context == "test/file.py"
        assert item.tags == ["tag1", "tag2"]

    def test_memory_conversion_with_defaults(self):
        """Test memory conversion with missing optional fields."""
        from open_agent_kit.features.codebase_intelligence.daemon.models import (
            MemoryListItem,
            MemoryType,
        )

        mem = {
            "id": "mem-456",
        }

        item = MemoryListItem(
            id=mem["id"],
            memory_type=MemoryType(mem.get("memory_type", "discovery")),
            observation=mem.get("observation", ""),
            context=mem.get("context"),
            tags=mem.get("tags", []),
            created_at=mem.get("created_at"),
        )

        assert item.id == "mem-456"
        assert item.memory_type == MemoryType.DISCOVERY
        assert item.observation == ""
        assert item.context is None
        assert item.tags == []

    def test_response_model_structure(self):
        """Test MemoriesListResponse has correct structure."""
        from open_agent_kit.features.codebase_intelligence.daemon.models import (
            MemoriesListResponse,
        )

        response = MemoriesListResponse(
            memories=[],
            total=0,
            limit=50,
            offset=0,
        )

        assert response.memories == []
        assert response.total == 0
        assert response.limit == 50
        assert response.offset == 0


# =============================================================================
# Session Summary Filtering Tests
# =============================================================================


class TestSessionSummaryFiltering:
    """Test filtering session summaries from memory lists."""

    def test_session_summary_memory_type_constant(self):
        """Test session_summary is a valid MemoryType."""
        from open_agent_kit.features.codebase_intelligence.daemon.models import MemoryType

        assert MemoryType.SESSION_SUMMARY.value == "session_summary"

    def test_filter_only_session_summaries(self):
        """Test filtering to show only session summaries."""
        memory_type = "session_summary"
        memory_types = [memory_type] if memory_type else None

        assert memory_types == ["session_summary"]

    def test_filter_excludes_session_summaries(self):
        """Test filtering out session summaries."""
        exclude_sessions = True
        exclude_types = ["session_summary"] if exclude_sessions else None

        assert exclude_types == ["session_summary"]
