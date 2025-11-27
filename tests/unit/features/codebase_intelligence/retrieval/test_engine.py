"""Tests for the RetrievalEngine module.

Tests the central retrieval abstraction that handles all search operations
for the Codebase Intelligence feature.
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from open_agent_kit.features.codebase_intelligence.constants import (
    SEARCH_TYPE_ALL,
    SEARCH_TYPE_CODE,
    SEARCH_TYPE_MEMORY,
)
from open_agent_kit.features.codebase_intelligence.retrieval.engine import (
    Confidence,
    ContextResult,
    FetchResult,
    RetrievalConfig,
    RetrievalEngine,
    SearchResult,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_vector_store() -> MagicMock:
    """Provide a mock vector store with pre-configured responses.

    Returns:
        MagicMock configured for VectorStore interface.
    """
    mock = MagicMock()

    # Default search_code response
    mock.search_code.return_value = [
        {
            "id": "code-1",
            "chunk_type": "function",
            "name": "process_data",
            "filepath": "src/utils.py",
            "start_line": 10,
            "end_line": 25,
            "content": "def process_data(input):\n    return input.strip()",
            "relevance": 0.85,
            "token_estimate": 50,
        },
        {
            "id": "code-2",
            "chunk_type": "class",
            "name": "DataProcessor",
            "filepath": "src/processor.py",
            "start_line": 1,
            "end_line": 50,
            "content": "class DataProcessor:\n    pass",
            "relevance": 0.75,
            "token_estimate": 100,
        },
    ]

    # Default search_memory response
    mock.search_memory.return_value = [
        {
            "id": "mem-1",
            "memory_type": "gotcha",
            "observation": "Always validate input before processing",
            "relevance": 0.90,
            "token_estimate": 20,
            "context": "src/utils.py",
        },
        {
            "id": "mem-2",
            "memory_type": "decision",
            "observation": "Chose async pattern for I/O operations",
            "relevance": 0.70,
            "token_estimate": 30,
            "context": None,
        },
    ]

    # Default get_by_ids response
    mock.get_by_ids.return_value = []

    # Default list_memories response
    mock.list_memories.return_value = ([], 0)

    # Default add_memory response
    mock.add_memory.return_value = "new-mem-id"

    return mock


@pytest.fixture
def default_config() -> RetrievalConfig:
    """Provide default retrieval configuration.

    Returns:
        RetrievalConfig with default values.
    """
    return RetrievalConfig()


@pytest.fixture
def custom_config() -> RetrievalConfig:
    """Provide custom retrieval configuration.

    Returns:
        RetrievalConfig with custom values.
    """
    return RetrievalConfig(
        default_limit=10,
        max_context_tokens=1000,
        preview_length=100,
    )


@pytest.fixture
def engine(mock_vector_store: MagicMock) -> RetrievalEngine:
    """Provide a RetrievalEngine with mock vector store.

    Args:
        mock_vector_store: Mock vector store fixture.

    Returns:
        RetrievalEngine instance for testing.
    """
    return RetrievalEngine(vector_store=mock_vector_store)


@pytest.fixture
def engine_with_custom_config(
    mock_vector_store: MagicMock, custom_config: RetrievalConfig
) -> RetrievalEngine:
    """Provide a RetrievalEngine with custom configuration.

    Args:
        mock_vector_store: Mock vector store fixture.
        custom_config: Custom configuration fixture.

    Returns:
        RetrievalEngine instance with custom config.
    """
    return RetrievalEngine(vector_store=mock_vector_store, config=custom_config)


# =============================================================================
# RetrievalConfig Tests
# =============================================================================


class TestRetrievalConfig:
    """Tests for RetrievalConfig dataclass."""

    def test_default_values(self) -> None:
        """Test that default values are set correctly."""
        config = RetrievalConfig()

        assert config.default_limit == 20
        assert config.max_context_tokens == 2000
        assert config.preview_length == 200

    def test_custom_values(self) -> None:
        """Test that custom values are applied correctly."""
        config = RetrievalConfig(
            default_limit=10,
            max_context_tokens=5000,
            preview_length=500,
        )

        assert config.default_limit == 10
        assert config.max_context_tokens == 5000
        assert config.preview_length == 500


# =============================================================================
# Result Dataclass Tests
# =============================================================================


class TestSearchResult:
    """Tests for SearchResult dataclass."""

    def test_default_values(self) -> None:
        """Test that default values are set correctly."""
        result = SearchResult(query="test query")

        assert result.query == "test query"
        assert result.code == []
        assert result.memory == []
        assert result.total_tokens_available == 0

    def test_with_results(self) -> None:
        """Test that results can be set."""
        result = SearchResult(
            query="test",
            code=[{"id": "1"}],
            memory=[{"id": "2"}],
            total_tokens_available=100,
        )

        assert len(result.code) == 1
        assert len(result.memory) == 1
        assert result.total_tokens_available == 100


class TestFetchResult:
    """Tests for FetchResult dataclass."""

    def test_default_values(self) -> None:
        """Test that default values are set correctly."""
        result = FetchResult()

        assert result.results == []
        assert result.total_tokens == 0

    def test_with_results(self) -> None:
        """Test that results can be set."""
        result = FetchResult(
            results=[{"id": "1", "content": "test"}],
            total_tokens=50,
        )

        assert len(result.results) == 1
        assert result.total_tokens == 50


class TestContextResult:
    """Tests for ContextResult dataclass."""

    def test_default_values(self) -> None:
        """Test that default values are set correctly."""
        result = ContextResult(task="implement feature")

        assert result.task == "implement feature"
        assert result.code == []
        assert result.memories == []
        assert result.guidelines == []
        assert result.total_tokens == 0

    def test_with_all_fields(self) -> None:
        """Test that all fields can be set."""
        result = ContextResult(
            task="fix bug",
            code=[{"file_path": "src/main.py"}],
            memories=[{"observation": "test"}],
            guidelines=["follow conventions"],
            total_tokens=200,
        )

        assert result.task == "fix bug"
        assert len(result.code) == 1
        assert len(result.memories) == 1
        assert len(result.guidelines) == 1
        assert result.total_tokens == 200


# =============================================================================
# RetrievalEngine Initialization Tests
# =============================================================================


class TestRetrievalEngineInit:
    """Tests for RetrievalEngine initialization."""

    def test_init_with_store_only(self, mock_vector_store: MagicMock) -> None:
        """Test initialization with only vector store."""
        engine = RetrievalEngine(vector_store=mock_vector_store)

        assert engine.store == mock_vector_store
        assert engine.config is not None
        assert engine.config.default_limit == 20  # Default value

    def test_init_with_custom_config(
        self, mock_vector_store: MagicMock, custom_config: RetrievalConfig
    ) -> None:
        """Test initialization with custom configuration."""
        engine = RetrievalEngine(vector_store=mock_vector_store, config=custom_config)

        assert engine.store == mock_vector_store
        assert engine.config == custom_config
        assert engine.config.default_limit == 10  # Custom value


# =============================================================================
# Search Method Tests
# =============================================================================


class TestSearch:
    """Tests for the search method."""

    def test_search_all_returns_code_and_memory(
        self, engine: RetrievalEngine, mock_vector_store: MagicMock
    ) -> None:
        """Test that search with 'all' type returns both code and memory."""
        # Configure mock to return empty for plans search (second call)
        mock_vector_store.search_memory.side_effect = [
            # First call: regular memory search
            [
                {
                    "id": "mem-1",
                    "memory_type": "gotcha",
                    "observation": "Always validate input before processing",
                    "relevance": 0.90,
                    "token_estimate": 20,
                    "context": "src/utils.py",
                },
                {
                    "id": "mem-2",
                    "memory_type": "decision",
                    "observation": "Chose async pattern for I/O operations",
                    "relevance": 0.70,
                    "token_estimate": 30,
                    "context": None,
                },
            ],
            # Second call: plans search (empty)
            [],
        ]

        result = engine.search(query="test query", search_type=SEARCH_TYPE_ALL)

        assert result.query == "test query"
        assert len(result.code) == 2
        assert len(result.memory) == 2
        assert len(result.plans) == 0
        mock_vector_store.search_code.assert_called_once()
        # search_memory is called twice: once for memories, once for plans
        assert mock_vector_store.search_memory.call_count == 2

    def test_search_code_only(self, engine: RetrievalEngine, mock_vector_store: MagicMock) -> None:
        """Test that search with 'code' type only returns code results."""
        result = engine.search(query="test query", search_type=SEARCH_TYPE_CODE)

        assert len(result.code) == 2
        assert len(result.memory) == 0
        mock_vector_store.search_code.assert_called_once()
        mock_vector_store.search_memory.assert_not_called()

    def test_search_memory_only(
        self, engine: RetrievalEngine, mock_vector_store: MagicMock
    ) -> None:
        """Test that search with 'memory' type only returns memory results."""
        result = engine.search(query="test query", search_type=SEARCH_TYPE_MEMORY)

        assert len(result.code) == 0
        assert len(result.memory) == 2
        mock_vector_store.search_code.assert_not_called()
        mock_vector_store.search_memory.assert_called_once()

    def test_search_uses_default_limit(
        self, engine: RetrievalEngine, mock_vector_store: MagicMock
    ) -> None:
        """Test that default limit is used when not specified."""
        engine.search(query="test")

        mock_vector_store.search_code.assert_called_once()
        call_kwargs = mock_vector_store.search_code.call_args.kwargs
        assert call_kwargs["limit"] == 20  # Default limit

    def test_search_uses_custom_limit(
        self, engine: RetrievalEngine, mock_vector_store: MagicMock
    ) -> None:
        """Test that custom limit is passed to store."""
        engine.search(query="test", limit=5)

        call_kwargs = mock_vector_store.search_code.call_args.kwargs
        assert call_kwargs["limit"] == 5

    def test_search_calculates_total_tokens(
        self, engine: RetrievalEngine, mock_vector_store: MagicMock
    ) -> None:
        """Test that total_tokens_available is calculated correctly."""
        # Configure mock to return empty for plans search (second call)
        mock_vector_store.search_memory.side_effect = [
            # First call: regular memory search
            [
                {
                    "id": "mem-1",
                    "memory_type": "gotcha",
                    "observation": "Always validate input before processing",
                    "relevance": 0.90,
                    "token_estimate": 20,
                    "context": "src/utils.py",
                },
                {
                    "id": "mem-2",
                    "memory_type": "decision",
                    "observation": "Chose async pattern for I/O operations",
                    "relevance": 0.70,
                    "token_estimate": 30,
                    "context": None,
                },
            ],
            # Second call: plans search (empty)
            [],
        ]

        result = engine.search(query="test", search_type=SEARCH_TYPE_ALL)

        # code: 50 + 100 = 150, memory: 20 + 30 = 50, plans: 0, total = 200
        assert result.total_tokens_available == 200

    def test_search_maps_code_fields_correctly(self, engine: RetrievalEngine) -> None:
        """Test that code result fields are mapped correctly."""
        result = engine.search(query="test", search_type=SEARCH_TYPE_CODE)

        code_result = result.code[0]
        assert code_result["id"] == "code-1"
        assert code_result["chunk_type"] == "function"
        assert code_result["name"] == "process_data"
        assert code_result["filepath"] == "src/utils.py"
        assert code_result["start_line"] == 10
        assert code_result["end_line"] == 25
        assert code_result["tokens"] == 50
        assert code_result["relevance"] == 0.85
        assert "def process_data" in code_result["content"]

    def test_search_maps_memory_fields_correctly(self, engine: RetrievalEngine) -> None:
        """Test that memory result fields are mapped correctly."""
        result = engine.search(query="test", search_type=SEARCH_TYPE_MEMORY)

        mem_result = result.memory[0]
        assert mem_result["id"] == "mem-1"
        assert mem_result["memory_type"] == "gotcha"
        assert mem_result["observation"] == "Always validate input before processing"
        assert mem_result["tokens"] == 20
        assert mem_result["relevance"] == 0.90

    def test_search_handles_empty_results(
        self, engine: RetrievalEngine, mock_vector_store: MagicMock
    ) -> None:
        """Test that empty results are handled correctly."""
        mock_vector_store.search_code.return_value = []
        mock_vector_store.search_memory.return_value = []

        result = engine.search(query="nonexistent")

        assert result.code == []
        assert result.memory == []
        assert result.total_tokens_available == 0


# =============================================================================
# Fetch Method Tests
# =============================================================================


class TestFetch:
    """Tests for the fetch method."""

    def test_fetch_returns_code_items(
        self, engine: RetrievalEngine, mock_vector_store: MagicMock
    ) -> None:
        """Test that fetch retrieves code items correctly."""
        mock_vector_store.get_by_ids.side_effect = [
            [{"id": "code-1", "content": "def test(): pass"}],  # code collection
            [],  # memory collection
        ]

        result = engine.fetch(ids=["code-1"])

        assert len(result.results) == 1
        assert result.results[0]["id"] == "code-1"
        assert result.results[0]["content"] == "def test(): pass"

    def test_fetch_returns_memory_items(
        self, engine: RetrievalEngine, mock_vector_store: MagicMock
    ) -> None:
        """Test that fetch retrieves memory items correctly."""
        mock_vector_store.get_by_ids.side_effect = [
            [],  # code collection
            [{"id": "mem-1", "content": "Important observation"}],  # memory collection
        ]

        result = engine.fetch(ids=["mem-1"])

        assert len(result.results) == 1
        assert result.results[0]["id"] == "mem-1"

    def test_fetch_calculates_tokens(
        self, engine: RetrievalEngine, mock_vector_store: MagicMock
    ) -> None:
        """Test that tokens are calculated correctly (len/4)."""
        content = "a" * 100  # 100 chars = 25 tokens
        mock_vector_store.get_by_ids.side_effect = [
            [{"id": "code-1", "content": content}],
            [],
        ]

        result = engine.fetch(ids=["code-1"])

        assert result.results[0]["tokens"] == 25
        assert result.total_tokens == 25

    def test_fetch_multiple_ids(
        self, engine: RetrievalEngine, mock_vector_store: MagicMock
    ) -> None:
        """Test fetching multiple IDs from both collections."""
        mock_vector_store.get_by_ids.side_effect = [
            [{"id": "code-1", "content": "code content"}],
            [{"id": "mem-1", "content": "memory content"}],
        ]

        result = engine.fetch(ids=["code-1", "mem-1"])

        assert len(result.results) == 2
        assert result.total_tokens > 0

    def test_fetch_empty_ids(self, engine: RetrievalEngine, mock_vector_store: MagicMock) -> None:
        """Test fetching with empty ID list."""
        mock_vector_store.get_by_ids.return_value = []

        result = engine.fetch(ids=[])

        assert result.results == []
        assert result.total_tokens == 0


# =============================================================================
# Get Task Context Tests
# =============================================================================


class TestGetTaskContext:
    """Tests for the get_task_context method."""

    def test_returns_context_result(self, engine: RetrievalEngine) -> None:
        """Test that method returns ContextResult."""
        result = engine.get_task_context(task="implement feature")

        assert isinstance(result, ContextResult)
        assert result.task == "implement feature"

    def test_includes_code_results(self, engine: RetrievalEngine) -> None:
        """Test that code results are included."""
        result = engine.get_task_context(task="test task")

        assert len(result.code) > 0
        assert result.code[0]["file_path"] == "src/utils.py"

    def test_includes_memory_results(self, engine: RetrievalEngine) -> None:
        """Test that memory results are included."""
        result = engine.get_task_context(task="test task")

        assert len(result.memories) > 0
        assert result.memories[0]["memory_type"] == "gotcha"

    def test_respects_max_tokens(
        self, engine: RetrievalEngine, mock_vector_store: MagicMock
    ) -> None:
        """Test that max_tokens limit is respected."""
        # Configure large token results
        mock_vector_store.search_code.return_value = [
            {
                "id": f"code-{i}",
                "chunk_type": "function",
                "name": f"func_{i}",
                "filepath": "src/main.py",
                "start_line": 1,
                "end_line": 10,
                "content": "x" * 1000,  # Large content
                "relevance": 0.9,
                "token_estimate": 500,  # 500 tokens each
            }
            for i in range(10)
        ]

        result = engine.get_task_context(task="test", max_tokens=1000)

        # Should only include items up to max_tokens
        total_tokens = sum(500 for _ in result.code)
        assert total_tokens <= 1000

    def test_builds_query_with_current_files(
        self, engine: RetrievalEngine, mock_vector_store: MagicMock
    ) -> None:
        """Test that current_files are included in search query."""
        engine.get_task_context(
            task="fix bug",
            current_files=["src/main.py", "src/utils.py"],
        )

        call_kwargs = mock_vector_store.search_code.call_args.kwargs
        query = call_kwargs["query"]
        assert "fix bug" in query
        assert "main.py" in query
        assert "utils.py" in query

    def test_adds_guidelines_when_constitution_exists(
        self, engine: RetrievalEngine, tmp_path: Path
    ) -> None:
        """Test that guidelines are added when .constitution.md exists."""
        constitution = tmp_path / ".constitution.md"
        constitution.write_text("# Project Constitution")

        result = engine.get_task_context(
            task="test task",
            project_root=tmp_path,
        )

        assert len(result.guidelines) > 0
        assert ".constitution.md" in result.guidelines[0]

    def test_no_guidelines_without_constitution(
        self, engine: RetrievalEngine, tmp_path: Path
    ) -> None:
        """Test that no guidelines are added when .constitution.md doesn't exist."""
        result = engine.get_task_context(
            task="test task",
            project_root=tmp_path,
        )

        assert len(result.guidelines) == 0

    def test_uses_config_max_tokens_when_not_specified(
        self, engine_with_custom_config: RetrievalEngine
    ) -> None:
        """Test that config max_context_tokens is used as default."""
        result = engine_with_custom_config.get_task_context(task="test")

        # Custom config has max_context_tokens=1000
        # Total tokens should be limited by this
        assert result.total_tokens <= 1000


# =============================================================================
# Remember Method Tests
# =============================================================================


class TestRemember:
    """Tests for the remember method."""

    def test_stores_observation(
        self, engine: RetrievalEngine, mock_vector_store: MagicMock
    ) -> None:
        """Test that observation is stored in vector store."""
        result_id = engine.remember(
            observation="Important discovery",
            memory_type="discovery",
        )

        assert result_id == "new-mem-id"
        mock_vector_store.add_memory.assert_called_once()

    def test_creates_memory_observation(
        self, engine: RetrievalEngine, mock_vector_store: MagicMock
    ) -> None:
        """Test that MemoryObservation is created correctly."""
        engine.remember(
            observation="Test observation",
            memory_type="gotcha",
            context="src/main.py",
            tags=["important", "bug"],
        )

        call_args = mock_vector_store.add_memory.call_args[0][0]
        assert call_args.observation == "Test observation"
        assert call_args.memory_type == "gotcha"
        assert call_args.context == "src/main.py"
        assert call_args.tags == ["important", "bug"]

    def test_generates_unique_id(
        self, engine: RetrievalEngine, mock_vector_store: MagicMock
    ) -> None:
        """Test that unique ID is generated for observation."""
        engine.remember(observation="Test")

        call_args = mock_vector_store.add_memory.call_args[0][0]
        assert call_args.id is not None
        assert len(call_args.id) > 0

    def test_sets_created_at_timestamp(
        self, engine: RetrievalEngine, mock_vector_store: MagicMock
    ) -> None:
        """Test that created_at timestamp is set."""
        before = datetime.now()
        engine.remember(observation="Test")
        after = datetime.now()

        call_args = mock_vector_store.add_memory.call_args[0][0]
        assert before <= call_args.created_at <= after

    def test_default_memory_type(
        self, engine: RetrievalEngine, mock_vector_store: MagicMock
    ) -> None:
        """Test that default memory type is 'discovery'."""
        engine.remember(observation="Test")

        call_args = mock_vector_store.add_memory.call_args[0][0]
        assert call_args.memory_type == "discovery"


# =============================================================================
# List Memories Tests
# =============================================================================


class TestListMemories:
    """Tests for the list_memories method."""

    def test_returns_memories_and_total(
        self, engine: RetrievalEngine, mock_vector_store: MagicMock
    ) -> None:
        """Test that method returns tuple of memories and total count."""
        mock_vector_store.list_memories.return_value = (
            [{"id": "mem-1", "observation": "test"}],
            10,
        )

        memories, total = engine.list_memories()

        assert len(memories) == 1
        assert total == 10

    def test_passes_limit_and_offset(
        self, engine: RetrievalEngine, mock_vector_store: MagicMock
    ) -> None:
        """Test that limit and offset are passed to store."""
        engine.list_memories(limit=25, offset=50)

        mock_vector_store.list_memories.assert_called_once_with(
            limit=25,
            offset=50,
            memory_types=None,
            exclude_types=None,
            tag=None,
            start_date=None,
            end_date=None,
            include_archived=False,
        )

    def test_passes_memory_types_filter(
        self, engine: RetrievalEngine, mock_vector_store: MagicMock
    ) -> None:
        """Test that memory_types filter is passed to store."""
        engine.list_memories(memory_types=["gotcha", "bug_fix"])

        call_kwargs = mock_vector_store.list_memories.call_args.kwargs
        assert call_kwargs["memory_types"] == ["gotcha", "bug_fix"]

    def test_passes_exclude_types_filter(
        self, engine: RetrievalEngine, mock_vector_store: MagicMock
    ) -> None:
        """Test that exclude_types filter is passed to store."""
        engine.list_memories(exclude_types=["session_summary"])

        call_kwargs = mock_vector_store.list_memories.call_args.kwargs
        assert call_kwargs["exclude_types"] == ["session_summary"]

    def test_default_pagination_values(
        self, engine: RetrievalEngine, mock_vector_store: MagicMock
    ) -> None:
        """Test default pagination values."""
        engine.list_memories()

        mock_vector_store.list_memories.assert_called_once_with(
            limit=50,
            offset=0,
            memory_types=None,
            exclude_types=None,
            tag=None,
            start_date=None,
            end_date=None,
            include_archived=False,
        )


# =============================================================================
# Confidence Calculation Tests
# =============================================================================


class TestConfidenceEnum:
    """Tests for the Confidence enum."""

    def test_confidence_values(self) -> None:
        """Test that confidence enum has expected values."""
        assert Confidence.HIGH.value == "high"
        assert Confidence.MEDIUM.value == "medium"
        assert Confidence.LOW.value == "low"


class TestCalculateConfidence:
    """Tests for the calculate_confidence static method."""

    def test_single_result_is_high(self) -> None:
        """Test that a single result gets HIGH confidence."""
        confidence = RetrievalEngine.calculate_confidence([0.85], 0)
        assert confidence == Confidence.HIGH

    def test_empty_scores_returns_medium(self) -> None:
        """Test that empty scores list returns MEDIUM."""
        confidence = RetrievalEngine.calculate_confidence([], 0)
        assert confidence == Confidence.MEDIUM

    def test_out_of_bounds_index_returns_medium(self) -> None:
        """Test that out of bounds index returns MEDIUM."""
        confidence = RetrievalEngine.calculate_confidence([0.9, 0.8], 5)
        assert confidence == Confidence.MEDIUM

    def test_top_result_with_clear_gap_is_high(self) -> None:
        """Test that top result with clear gap gets HIGH confidence."""
        # First result clearly better than second
        scores = [0.95, 0.70, 0.65, 0.60]
        confidence = RetrievalEngine.calculate_confidence(scores, 0)
        assert confidence == Confidence.HIGH

    def test_top_result_in_tight_cluster(self) -> None:
        """Test confidence for top result in tight cluster."""
        # All scores very close - still HIGH for first result
        scores = [0.091, 0.090, 0.089, 0.088]
        confidence = RetrievalEngine.calculate_confidence(scores, 0)
        assert confidence == Confidence.HIGH

    def test_middle_result_in_top_range_is_medium(self) -> None:
        """Test that middle result in top 60% gets MEDIUM."""
        scores = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5]
        # Index 2 (0.8) is at normalized position 0.6 (top 60%)
        confidence = RetrievalEngine.calculate_confidence(scores, 2)
        assert confidence == Confidence.MEDIUM

    def test_bottom_result_is_low(self) -> None:
        """Test that result in bottom 40% gets LOW."""
        scores = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3]
        # Last result should be LOW
        confidence = RetrievalEngine.calculate_confidence(scores, 7)
        assert confidence == Confidence.LOW

    def test_all_same_score_fallback(self) -> None:
        """Test fallback behavior when all scores are the same."""
        scores = [0.5, 0.5, 0.5, 0.5, 0.5]
        # First result should be HIGH
        assert RetrievalEngine.calculate_confidence(scores, 0) == Confidence.HIGH
        # Early results should be MEDIUM
        assert RetrievalEngine.calculate_confidence(scores, 1) == Confidence.MEDIUM
        # Later results should be LOW
        assert RetrievalEngine.calculate_confidence(scores, 4) == Confidence.LOW

    def test_two_results_with_gap(self) -> None:
        """Test two results where first has clear advantage."""
        scores = [0.9, 0.5]
        confidence_0 = RetrievalEngine.calculate_confidence(scores, 0)
        confidence_1 = RetrievalEngine.calculate_confidence(scores, 1)
        assert confidence_0 == Confidence.HIGH
        assert confidence_1 == Confidence.LOW

    def test_realistic_nomic_scores(self) -> None:
        """Test with realistic nomic-embed-text scores (~0.09 range)."""
        # Simulating actual nomic-embed-text results
        scores = [0.0916, 0.0900, 0.0872, 0.0870]

        # First result should be HIGH (top of range)
        assert RetrievalEngine.calculate_confidence(scores, 0) == Confidence.HIGH
        # Second might be HIGH or MEDIUM depending on gap
        conf_1 = RetrievalEngine.calculate_confidence(scores, 1)
        assert conf_1 in (Confidence.HIGH, Confidence.MEDIUM)
        # Last results should be LOW (bottom of range)
        assert RetrievalEngine.calculate_confidence(scores, 3) == Confidence.LOW


class TestCalculateConfidenceBatch:
    """Tests for the calculate_confidence_batch static method."""

    def test_returns_list_of_confidences(self) -> None:
        """Test that batch method returns list of confidences."""
        scores = [0.9, 0.7, 0.5, 0.3]
        confidences = RetrievalEngine.calculate_confidence_batch(scores)

        assert len(confidences) == 4
        assert all(isinstance(c, Confidence) for c in confidences)

    def test_empty_scores(self) -> None:
        """Test batch with empty scores."""
        confidences = RetrievalEngine.calculate_confidence_batch([])
        assert confidences == []

    def test_batch_matches_individual(self) -> None:
        """Test that batch results match individual calculations."""
        scores = [0.95, 0.80, 0.65, 0.50, 0.35]
        batch_results = RetrievalEngine.calculate_confidence_batch(scores)

        for i, batch_conf in enumerate(batch_results):
            individual_conf = RetrievalEngine.calculate_confidence(scores, i)
            assert batch_conf == individual_conf


class TestFilterByConfidence:
    """Tests for the filter_by_confidence static method."""

    def test_filter_high_only(self) -> None:
        """Test filtering for high confidence only."""
        results = [
            {"id": "1", "confidence": "high"},
            {"id": "2", "confidence": "medium"},
            {"id": "3", "confidence": "low"},
            {"id": "4", "confidence": "high"},
        ]

        filtered = RetrievalEngine.filter_by_confidence(results, min_confidence="high")

        assert len(filtered) == 2
        assert all(r["confidence"] == "high" for r in filtered)

    def test_filter_logs_dropped_count(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that filtering logs the number of dropped results."""
        import logging

        results = [
            {"id": "1", "confidence": "high"},
            {"id": "2", "confidence": "medium"},
            {"id": "3", "confidence": "low"},
            {"id": "4", "confidence": "low"},
        ]

        with caplog.at_level(logging.DEBUG):
            filtered = RetrievalEngine.filter_by_confidence(results, min_confidence="high")

        # Should have dropped 3 results (2 low + 1 medium)
        assert len(filtered) == 1
        assert any("[FILTER]" in record.message for record in caplog.records)
        assert any("Dropped 3/4" in record.message for record in caplog.records)

    def test_filter_no_log_when_nothing_dropped(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that no log is emitted when nothing is dropped."""
        import logging

        results = [
            {"id": "1", "confidence": "high"},
            {"id": "2", "confidence": "high"},
        ]

        with caplog.at_level(logging.DEBUG):
            filtered = RetrievalEngine.filter_by_confidence(results, min_confidence="high")

        assert len(filtered) == 2
        # No [FILTER] log should be emitted
        assert not any("[FILTER]" in record.message for record in caplog.records)

    def test_filter_medium_includes_high(self) -> None:
        """Test filtering for medium includes high and medium."""
        results = [
            {"id": "1", "confidence": "high"},
            {"id": "2", "confidence": "medium"},
            {"id": "3", "confidence": "low"},
        ]

        filtered = RetrievalEngine.filter_by_confidence(results, min_confidence="medium")

        assert len(filtered) == 2
        assert {"1", "2"} == {r["id"] for r in filtered}

    def test_filter_low_returns_all(self) -> None:
        """Test filtering for low returns all results."""
        results = [
            {"id": "1", "confidence": "high"},
            {"id": "2", "confidence": "medium"},
            {"id": "3", "confidence": "low"},
        ]

        filtered = RetrievalEngine.filter_by_confidence(results, min_confidence="low")

        assert len(filtered) == 3

    def test_filter_all_returns_all(self) -> None:
        """Test filtering for 'all' returns all results."""
        results = [
            {"id": "1", "confidence": "high"},
            {"id": "2", "confidence": "low"},
        ]

        filtered = RetrievalEngine.filter_by_confidence(results, min_confidence="all")

        assert len(filtered) == 2

    def test_filter_empty_list(self) -> None:
        """Test filtering empty list."""
        filtered = RetrievalEngine.filter_by_confidence([], min_confidence="high")

        assert filtered == []

    def test_missing_confidence_treated_as_low(self) -> None:
        """Test that results without confidence field are treated as low."""
        results = [
            {"id": "1", "confidence": "high"},
            {"id": "2"},  # No confidence field
        ]

        filtered = RetrievalEngine.filter_by_confidence(results, min_confidence="high")

        assert len(filtered) == 1
        assert filtered[0]["id"] == "1"


class TestSearchWithConfidence:
    """Tests for search method confidence integration."""

    def test_search_results_include_confidence(
        self, engine: RetrievalEngine, mock_vector_store: MagicMock
    ) -> None:
        """Test that search results include confidence field."""
        result = engine.search(query="test", search_type="all")

        # Check code results have confidence
        for code_result in result.code:
            assert "confidence" in code_result
            assert code_result["confidence"] in ("high", "medium", "low")

        # Check memory results have confidence
        for mem_result in result.memory:
            assert "confidence" in mem_result
            assert mem_result["confidence"] in ("high", "medium", "low")

    def test_search_confidence_reflects_scores(
        self, engine: RetrievalEngine, mock_vector_store: MagicMock
    ) -> None:
        """Test that confidence reflects relative score positions."""
        # Configure mock with spread scores
        mock_vector_store.search_code.return_value = [
            {"id": "1", "relevance": 0.95, "token_estimate": 10, "chunk_type": "function"},
            {"id": "2", "relevance": 0.50, "token_estimate": 10, "chunk_type": "function"},
            {"id": "3", "relevance": 0.20, "token_estimate": 10, "chunk_type": "function"},
        ]
        mock_vector_store.search_memory.return_value = []

        result = engine.search(query="test", search_type="code")

        # First result should be high confidence
        assert result.code[0]["confidence"] == "high"
        # Last result should be low confidence
        assert result.code[2]["confidence"] == "low"


# =============================================================================
# Combined Score Tests (Confidence + Importance)
# =============================================================================


class TestCalculateCombinedScore:
    """Tests for the calculate_combined_score static method."""

    def test_high_confidence_high_importance(self) -> None:
        """Test combined score for high confidence and high importance."""
        score = RetrievalEngine.calculate_combined_score("high", 10)
        # (0.7 * 1.0) + (0.3 * 1.0) = 1.0
        assert score == 1.0

    def test_high_confidence_low_importance(self) -> None:
        """Test combined score for high confidence and low importance."""
        score = RetrievalEngine.calculate_combined_score("high", 1)
        # (0.7 * 1.0) + (0.3 * 0.1) = 0.73
        assert abs(score - 0.73) < 0.01

    def test_low_confidence_high_importance(self) -> None:
        """Test combined score for low confidence and high importance."""
        score = RetrievalEngine.calculate_combined_score("low", 10)
        # (0.7 * 0.3) + (0.3 * 1.0) = 0.51
        assert abs(score - 0.51) < 0.01

    def test_medium_confidence_medium_importance(self) -> None:
        """Test combined score for medium confidence and medium importance."""
        score = RetrievalEngine.calculate_combined_score("medium", 5)
        # (0.7 * 0.6) + (0.3 * 0.5) = 0.57
        assert abs(score - 0.57) < 0.01

    def test_unknown_confidence_defaults_to_medium(self) -> None:
        """Test that unknown confidence defaults to medium score."""
        score = RetrievalEngine.calculate_combined_score("unknown", 5)
        expected = RetrievalEngine.calculate_combined_score("medium", 5)
        assert score == expected

    def test_importance_clamped_to_valid_range(self) -> None:
        """Test that importance is clamped to 1-10 range."""
        # Test below minimum (should use 1)
        score_below = RetrievalEngine.calculate_combined_score("high", 0)
        score_at_min = RetrievalEngine.calculate_combined_score("high", 1)
        assert score_below == score_at_min

        # Test above maximum (should use 10)
        score_above = RetrievalEngine.calculate_combined_score("high", 15)
        score_at_max = RetrievalEngine.calculate_combined_score("high", 10)
        assert score_above == score_at_max


class TestGetImportanceLevel:
    """Tests for the get_importance_level static method."""

    def test_high_importance(self) -> None:
        """Test that importance >= 7 returns 'high'."""
        assert RetrievalEngine.get_importance_level(7) == "high"
        assert RetrievalEngine.get_importance_level(8) == "high"
        assert RetrievalEngine.get_importance_level(10) == "high"

    def test_medium_importance(self) -> None:
        """Test that importance >= 4 and < 7 returns 'medium'."""
        assert RetrievalEngine.get_importance_level(4) == "medium"
        assert RetrievalEngine.get_importance_level(5) == "medium"
        assert RetrievalEngine.get_importance_level(6) == "medium"

    def test_low_importance(self) -> None:
        """Test that importance < 4 returns 'low'."""
        assert RetrievalEngine.get_importance_level(1) == "low"
        assert RetrievalEngine.get_importance_level(2) == "low"
        assert RetrievalEngine.get_importance_level(3) == "low"


class TestFilterByCombinedScore:
    """Tests for the filter_by_combined_score static method."""

    def test_filter_high_combined_score(self) -> None:
        """Test filtering for high combined score."""
        results = [
            {"id": "1", "confidence": "high", "importance": 8},  # Combined: ~0.94
            {"id": "2", "confidence": "high", "importance": 2},  # Combined: ~0.76
            {"id": "3", "confidence": "low", "importance": 9},  # Combined: ~0.48
            {"id": "4", "confidence": "medium", "importance": 5},  # Combined: ~0.57
        ]

        filtered = RetrievalEngine.filter_by_combined_score(results, min_combined="high")

        # Threshold is 0.7, so results 1 and 2 should pass
        assert len(filtered) == 2
        assert {"1", "2"} == {r["id"] for r in filtered}

    def test_filter_medium_combined_score(self) -> None:
        """Test filtering for medium combined score."""
        results = [
            {"id": "1", "confidence": "high", "importance": 8},  # Combined: ~0.94
            {"id": "2", "confidence": "medium", "importance": 5},  # Combined: ~0.57
            {"id": "3", "confidence": "low", "importance": 3},  # Combined: ~0.30
        ]

        filtered = RetrievalEngine.filter_by_combined_score(results, min_combined="medium")

        # Threshold is 0.5, so results 1 and 2 should pass
        assert len(filtered) == 2
        assert {"1", "2"} == {r["id"] for r in filtered}

    def test_filter_low_returns_all(self) -> None:
        """Test that 'low' threshold returns all results."""
        results = [
            {"id": "1", "confidence": "high", "importance": 8},
            {"id": "2", "confidence": "low", "importance": 1},
        ]

        filtered = RetrievalEngine.filter_by_combined_score(results, min_combined="low")

        assert len(filtered) == 2

    def test_filter_all_returns_all(self) -> None:
        """Test that 'all' threshold returns all results."""
        results = [
            {"id": "1", "confidence": "high", "importance": 8},
            {"id": "2", "confidence": "low", "importance": 1},
        ]

        filtered = RetrievalEngine.filter_by_combined_score(results, min_combined="all")

        assert len(filtered) == 2

    def test_adds_combined_score_to_results(self) -> None:
        """Test that combined_score is added to kept results when filtering."""
        results = [
            {"id": "1", "confidence": "high", "importance": 8},  # Passes high threshold
        ]

        # Use a threshold that actually filters (not 'low' or 'all' which return early)
        filtered = RetrievalEngine.filter_by_combined_score(results, min_combined="high")

        assert "combined_score" in filtered[0]
        assert isinstance(filtered[0]["combined_score"], float)

    def test_handles_missing_importance(self) -> None:
        """Test that missing importance defaults to 5."""
        results = [
            {"id": "1", "confidence": "high"},  # No importance, defaults to 5
        ]

        filtered = RetrievalEngine.filter_by_combined_score(results, min_combined="high")

        # high confidence (1.0) + default importance (5 -> 0.5)
        # (0.7 * 1.0) + (0.3 * 0.5) = 0.85 -> passes high threshold (0.7)
        assert len(filtered) == 1

    def test_handles_string_importance(self) -> None:
        """Test that string importance values are converted."""
        results = [
            {"id": "1", "confidence": "medium", "importance": "high"},  # Should map to 8
            {"id": "2", "confidence": "medium", "importance": "low"},  # Should map to 3
        ]

        filtered = RetrievalEngine.filter_by_combined_score(results, min_combined="medium")

        # Result 1: (0.7 * 0.6) + (0.3 * 0.8) = 0.66 -> passes medium (0.5)
        # Result 2: (0.7 * 0.6) + (0.3 * 0.3) = 0.51 -> passes medium (0.5)
        assert len(filtered) == 2

    def test_filter_logs_dropped_count(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that filtering logs the number of dropped results."""
        import logging

        results = [
            {"id": "1", "confidence": "high", "importance": 8},  # Passes
            {"id": "2", "confidence": "low", "importance": 2},  # Fails
            {"id": "3", "confidence": "low", "importance": 1},  # Fails
        ]

        with caplog.at_level(logging.DEBUG):
            filtered = RetrievalEngine.filter_by_combined_score(results, min_combined="high")

        assert len(filtered) == 1
        assert any("[FILTER:combined]" in record.message for record in caplog.records)
        assert any("Dropped 2/3" in record.message for record in caplog.records)

    def test_no_log_when_nothing_dropped(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that no log is emitted when nothing is dropped."""
        import logging

        results = [
            {"id": "1", "confidence": "high", "importance": 8},
        ]

        with caplog.at_level(logging.DEBUG):
            filtered = RetrievalEngine.filter_by_combined_score(results, min_combined="low")

        assert len(filtered) == 1
        assert not any("[FILTER:combined]" in record.message for record in caplog.records)

    def test_empty_list(self) -> None:
        """Test filtering empty list."""
        filtered = RetrievalEngine.filter_by_combined_score([], min_combined="high")
        assert filtered == []
