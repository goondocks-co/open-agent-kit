"""Tests for the vector store module (memory and code indexing).

Tests cover:
- VectorStore initialization (lazy init, ChromaDB setup)
- Code chunk indexing (add_code_chunks, add_code_chunks_batched)
- Code search functionality
- Memory observation storage
- Memory search and listing
- Collection management (clear, delete)
- Edge cases and error handling
- Dimension mismatch handling
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from open_agent_kit.features.codebase_intelligence.embeddings.base import (
    EmbeddingProvider,
    EmbeddingResult,
)
from open_agent_kit.features.codebase_intelligence.memory.store import (
    CODE_COLLECTION,
    CodeChunk,
    MemoryObservation,
    VectorStore,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_embedding_provider() -> MagicMock:
    """Provide a mock embedding provider.

    Returns:
        MagicMock configured for EmbeddingProvider.
    """
    mock = MagicMock(spec=EmbeddingProvider)
    mock.dimensions = 384
    mock.embed.return_value = EmbeddingResult(
        embeddings=[[0.1, 0.2, 0.3] * 128],  # 384 dims
        model="mock-model",
        provider="mock",
        dimensions=384,
    )
    mock.embed_query.return_value = [0.1, 0.2, 0.3] * 128  # 384 dims
    return mock


@pytest.fixture
def temp_vector_store_dir(tmp_path: Path) -> Path:
    """Provide a temporary directory for vector store.

    Args:
        tmp_path: pytest temporary directory.

    Returns:
        Path to temporary vector store directory.
    """
    store_dir = tmp_path / "chroma_store"
    return store_dir


@pytest.fixture
def vector_store(temp_vector_store_dir: Path, mock_embedding_provider: MagicMock) -> VectorStore:
    """Provide an uninitialized VectorStore instance.

    Args:
        temp_vector_store_dir: Temporary directory for store.
        mock_embedding_provider: Mock embedding provider.

    Returns:
        VectorStore instance.
    """
    return VectorStore(
        persist_directory=temp_vector_store_dir,
        embedding_provider=mock_embedding_provider,
    )


@pytest.fixture
def mock_chromadb_client() -> MagicMock:
    """Provide a mock ChromaDB client.

    Returns:
        MagicMock configured for ChromaDB PersistentClient.
    """
    mock_client = MagicMock()

    # Mock collections
    mock_code_collection = MagicMock()
    mock_code_collection.count.return_value = 0
    mock_code_collection.peek.return_value = None
    mock_code_collection.upsert.return_value = None
    mock_code_collection.query.return_value = {
        "ids": [["id1", "id2"]],
        "documents": [["content1", "content2"]],
        "distances": [[0.1, 0.2]],
        "metadatas": [[{"filepath": "file1.py"}, {"filepath": "file2.py"}]],
    }
    mock_code_collection.get.return_value = {
        "ids": ["id1"],
        "documents": ["content1"],
        "metadatas": [{"filepath": "file1.py"}],
    }
    mock_code_collection.delete.return_value = None

    mock_memory_collection = MagicMock()
    mock_memory_collection.count.return_value = 0
    mock_memory_collection.peek.return_value = None
    mock_memory_collection.upsert.return_value = None
    mock_memory_collection.query.return_value = {
        "ids": [["mem1"]],
        "documents": [["observation1"]],
        "distances": [[0.1]],
        "metadatas": [[{"memory_type": "insight", "tags": "tag1,tag2"}]],
    }
    mock_memory_collection.get.return_value = {
        "ids": ["mem1"],
        "documents": ["observation1"],
        "metadatas": [{"memory_type": "insight", "tags": "tag1"}],
    }

    mock_client.get_collection.side_effect = lambda name: (
        mock_code_collection if name == CODE_COLLECTION else mock_memory_collection
    )
    mock_client.create_collection.side_effect = lambda name, metadata: (
        mock_code_collection if name == CODE_COLLECTION else mock_memory_collection
    )
    mock_client.delete_collection.return_value = None

    return mock_client


# =============================================================================
# VectorStore Initialization Tests
# =============================================================================


class TestVectorStoreInitialization:
    """Test VectorStore initialization and lazy loading."""

    def test_lazy_initialization(
        self,
        vector_store: VectorStore,
        temp_vector_store_dir: Path,
    ):
        """Test that VectorStore is lazily initialized.

        The collections should be None until _ensure_initialized is called.
        """
        assert vector_store._client is None
        assert vector_store._code_collection is None
        assert vector_store._memory_collection is None

    def test_init_creates_persist_directory(
        self,
        vector_store: VectorStore,
        temp_vector_store_dir: Path,
        mock_chromadb_client: MagicMock,
    ):
        """Test that initialization creates the persist directory."""
        with patch("chromadb.PersistentClient", return_value=mock_chromadb_client):
            with patch("chromadb.config.Settings"):
                vector_store._ensure_initialized()

        assert temp_vector_store_dir.exists()

    def test_ensure_initialized_creates_collections(
        self,
        vector_store: VectorStore,
        mock_chromadb_client: MagicMock,
    ):
        """Test that _ensure_initialized creates ChromaDB collections."""
        with patch("chromadb.PersistentClient", return_value=mock_chromadb_client):
            with patch("chromadb.config.Settings"):
                vector_store._ensure_initialized()

        assert vector_store._client is not None
        assert vector_store._code_collection is not None
        assert vector_store._memory_collection is not None

    def test_chromadb_not_installed_raises_error(
        self,
        vector_store: VectorStore,
    ):
        """Test that ImportError is raised when ChromaDB is not available."""
        with patch("chromadb.PersistentClient", side_effect=ImportError("No module")):
            with pytest.raises(RuntimeError, match="ChromaDB is not installed"):
                vector_store._ensure_initialized()

    def test_idempotent_initialization(
        self,
        vector_store: VectorStore,
        mock_chromadb_client: MagicMock,
    ):
        """Test that calling _ensure_initialized multiple times is safe."""
        with patch("chromadb.PersistentClient", return_value=mock_chromadb_client):
            with patch("chromadb.config.Settings"):
                vector_store._ensure_initialized()
                first_client = vector_store._client

                vector_store._ensure_initialized()
                second_client = vector_store._client

                assert first_client is second_client


# =============================================================================
# CodeChunk Tests
# =============================================================================


class TestCodeChunk:
    """Test CodeChunk dataclass and methods."""

    def test_create_code_chunk(self):
        """Test creating a CodeChunk."""
        chunk = CodeChunk(
            id="test:1:hash",
            content="def foo(): pass",
            filepath="test.py",
            language="python",
            chunk_type="function",
            name="foo",
            start_line=1,
            end_line=2,
        )

        assert chunk.id == "test:1:hash"
        assert chunk.content == "def foo(): pass"
        assert chunk.filepath == "test.py"
        assert chunk.language == "python"
        assert chunk.chunk_type == "function"

    def test_chunk_token_estimate(self):
        """Test token estimation for chunks."""
        chunk = CodeChunk(
            id="test:1:hash",
            content="x" * 400,  # 400 chars = ~100 tokens
            filepath="test.py",
            language="python",
            chunk_type="function",
            name="foo",
            start_line=1,
            end_line=2,
        )

        assert chunk.token_estimate == 100

    def test_chunk_to_metadata(self):
        """Test converting chunk to metadata format."""
        chunk = CodeChunk(
            id="test:1:hash",
            content="def foo(): pass",
            filepath="test.py",
            language="python",
            chunk_type="function",
            name="foo",
            start_line=1,
            end_line=2,
            docstring="Test docstring",
            parent_id="parent:1",
        )

        metadata = chunk.to_metadata()

        assert metadata["filepath"] == "test.py"
        assert metadata["language"] == "python"
        assert metadata["chunk_type"] == "function"
        assert metadata["name"] == "foo"
        assert metadata["start_line"] == 1
        assert metadata["end_line"] == 2
        assert metadata["has_docstring"] is True
        assert metadata["parent_id"] == "parent:1"

    def test_chunk_to_metadata_with_empty_fields(self):
        """Test metadata conversion with None/empty fields."""
        chunk = CodeChunk(
            id="test:1:hash",
            content="code",
            filepath="test.py",
            language="python",
            chunk_type="module",
            name=None,
            start_line=1,
            end_line=2,
        )

        metadata = chunk.to_metadata()

        assert metadata["name"] == ""
        assert metadata["parent_id"] == ""
        assert metadata["has_docstring"] is False

    def test_generate_chunk_id(self):
        """Test stable ID generation from content."""
        filepath = "test.py"
        start_line = 10
        content = "def my_function(): pass"

        id1 = CodeChunk.generate_id(filepath, start_line, content)
        id2 = CodeChunk.generate_id(filepath, start_line, content)

        assert id1 == id2
        assert filepath in id1
        assert str(start_line) in id1

    def test_generate_chunk_id_different_content(self):
        """Test that different content produces different IDs."""
        filepath = "test.py"
        start_line = 10

        id1 = CodeChunk.generate_id(filepath, start_line, "content1")
        id2 = CodeChunk.generate_id(filepath, start_line, "content2")

        assert id1 != id2


# =============================================================================
# MemoryObservation Tests
# =============================================================================


class TestMemoryObservation:
    """Test MemoryObservation dataclass and methods."""

    def test_create_memory_observation(self):
        """Test creating a MemoryObservation."""
        now = datetime.now()
        obs = MemoryObservation(
            id="mem:1",
            observation="Discovered pattern X",
            memory_type="insight",
            context="During session Y",
            tags=["pattern", "important"],
            created_at=now,
        )

        assert obs.id == "mem:1"
        assert obs.observation == "Discovered pattern X"
        assert obs.memory_type == "insight"
        assert obs.tags == ["pattern", "important"]
        assert obs.created_at == now

    def test_observation_token_estimate(self):
        """Test token estimation for observations."""
        obs = MemoryObservation(
            id="mem:1",
            observation="x" * 400,  # 400 chars = ~100 tokens
            memory_type="insight",
        )

        assert obs.token_estimate == 100

    def test_observation_to_metadata(self):
        """Test converting observation to metadata format."""
        now = datetime.now()
        obs = MemoryObservation(
            id="mem:1",
            observation="Test observation",
            memory_type="insight",
            context="Test context",
            tags=["tag1", "tag2"],
            created_at=now,
        )

        metadata = obs.to_metadata()

        assert metadata["memory_type"] == "insight"
        assert metadata["context"] == "Test context"
        assert metadata["tags"] == "tag1,tag2"
        assert metadata["created_at"] == now.isoformat()

    def test_observation_to_metadata_with_no_tags(self):
        """Test metadata conversion without tags."""
        obs = MemoryObservation(
            id="mem:1",
            observation="Test",
            memory_type="insight",
        )

        metadata = obs.to_metadata()

        assert metadata["tags"] == ""


# =============================================================================
# Code Indexing Tests
# =============================================================================


class TestAddCodeChunks:
    """Test adding code chunks to the index."""

    def test_add_single_chunk(
        self,
        vector_store: VectorStore,
        mock_chromadb_client: MagicMock,
        mock_embedding_provider: MagicMock,
    ):
        """Test adding a single code chunk."""
        chunk = CodeChunk(
            id="test:1:hash",
            content="def foo(): pass",
            filepath="test.py",
            language="python",
            chunk_type="function",
            name="foo",
            start_line=1,
            end_line=2,
        )

        with patch("chromadb.PersistentClient", return_value=mock_chromadb_client):
            with patch("chromadb.config.Settings"):
                added = vector_store.add_code_chunks([chunk])

        assert added == 1
        mock_chromadb_client.get_collection.assert_called()

    def test_add_multiple_chunks(
        self,
        vector_store: VectorStore,
        mock_chromadb_client: MagicMock,
        mock_embedding_provider: MagicMock,
    ):
        """Test adding multiple code chunks."""
        chunks = [
            CodeChunk(
                id=f"test:{i}:hash",
                content=f"def func{i}(): pass",
                filepath="test.py",
                language="python",
                chunk_type="function",
                name=f"func{i}",
                start_line=i,
                end_line=i + 1,
            )
            for i in range(3)
        ]

        with patch("chromadb.PersistentClient", return_value=mock_chromadb_client):
            with patch("chromadb.config.Settings"):
                added = vector_store.add_code_chunks(chunks)

        assert added == 3

    def test_add_empty_chunk_list(
        self,
        vector_store: VectorStore,
        mock_embedding_provider: MagicMock,
    ):
        """Test adding an empty list of chunks."""
        added = vector_store.add_code_chunks([])

        assert added == 0

    def test_add_duplicate_chunks(
        self,
        vector_store: VectorStore,
        mock_chromadb_client: MagicMock,
        mock_embedding_provider: MagicMock,
    ):
        """Test that duplicate chunks are deduplicated."""
        chunk = CodeChunk(
            id="test:1:hash",
            content="def foo(): pass",
            filepath="test.py",
            language="python",
            chunk_type="function",
            name="foo",
            start_line=1,
            end_line=2,
        )

        with patch("chromadb.PersistentClient", return_value=mock_chromadb_client):
            with patch("chromadb.config.Settings"):
                added = vector_store.add_code_chunks([chunk, chunk, chunk])

        # Should only add unique chunk once
        assert added == 1


class TestAddCodeChunksBatched:
    """Test batched code chunk addition."""

    def test_batch_size_division(
        self,
        vector_store: VectorStore,
        mock_chromadb_client: MagicMock,
        mock_embedding_provider: MagicMock,
    ):
        """Test that chunks are processed in batches."""
        chunks = [
            CodeChunk(
                id=f"test:{i}:hash",
                content=f"def func{i}(): pass",
                filepath="test.py",
                language="python",
                chunk_type="function",
                name=f"func{i}",
                start_line=i,
                end_line=i + 1,
            )
            for i in range(10)
        ]

        with patch("chromadb.PersistentClient", return_value=mock_chromadb_client):
            with patch("chromadb.config.Settings"):
                added = vector_store.add_code_chunks_batched(chunks, batch_size=3)

        assert added == 10

    def test_batch_with_progress_callback(
        self,
        vector_store: VectorStore,
        mock_chromadb_client: MagicMock,
        mock_embedding_provider: MagicMock,
    ):
        """Test that progress callback is invoked."""
        chunks = [
            CodeChunk(
                id=f"test:{i}:hash",
                content=f"def func{i}(): pass",
                filepath="test.py",
                language="python",
                chunk_type="function",
                name=f"func{i}",
                start_line=i,
                end_line=i + 1,
            )
            for i in range(5)
        ]

        progress_calls = []

        def progress_callback(processed: int, total: int):
            progress_calls.append((processed, total))

        with patch("chromadb.PersistentClient", return_value=mock_chromadb_client):
            with patch("chromadb.config.Settings"):
                vector_store.add_code_chunks_batched(
                    chunks, batch_size=2, progress_callback=progress_callback
                )

        # Should have called progress callback for each batch
        assert len(progress_calls) > 0

    def test_empty_batch_list(
        self,
        vector_store: VectorStore,
        mock_embedding_provider: MagicMock,
    ):
        """Test batched add with empty list."""
        added = vector_store.add_code_chunks_batched([])

        assert added == 0


# =============================================================================
# Code Search Tests
# =============================================================================


class TestSearchCode:
    """Test code search functionality."""

    def test_search_code_basic(
        self,
        vector_store: VectorStore,
        mock_chromadb_client: MagicMock,
    ):
        """Test basic code search."""
        with patch("chromadb.PersistentClient", return_value=mock_chromadb_client):
            with patch("chromadb.config.Settings"):
                results = vector_store.search_code("find function definition")

        assert isinstance(results, list)
        assert len(results) > 0
        assert "id" in results[0]
        assert "content" in results[0]
        assert "relevance" in results[0]

    def test_search_code_with_limit(
        self,
        vector_store: VectorStore,
        mock_chromadb_client: MagicMock,
    ):
        """Test code search with custom limit."""
        with patch("chromadb.PersistentClient", return_value=mock_chromadb_client):
            with patch("chromadb.config.Settings"):
                results = vector_store.search_code("test query", limit=5)

        assert len(results) <= 5

    def test_search_empty_query(
        self,
        vector_store: VectorStore,
        mock_chromadb_client: MagicMock,
    ):
        """Test searching with empty query string."""
        with patch("chromadb.PersistentClient", return_value=mock_chromadb_client):
            with patch("chromadb.config.Settings"):
                # Should still try to embed empty query
                results = vector_store.search_code("")

        assert isinstance(results, list)


# =============================================================================
# Memory Operations Tests
# =============================================================================


class TestAddMemory:
    """Test adding memory observations."""

    def test_add_single_memory(
        self,
        vector_store: VectorStore,
        mock_chromadb_client: MagicMock,
    ):
        """Test adding a single memory observation."""
        obs = MemoryObservation(
            id="mem:1",
            observation="Discovered important pattern",
            memory_type="insight",
            tags=["pattern", "optimization"],
        )

        with patch("chromadb.PersistentClient", return_value=mock_chromadb_client):
            with patch("chromadb.config.Settings"):
                mem_id = vector_store.add_memory(obs)

        assert mem_id == obs.id

    def test_add_memory_with_context(
        self,
        vector_store: VectorStore,
        mock_chromadb_client: MagicMock,
    ):
        """Test adding memory with full context."""
        now = datetime.now()
        obs = MemoryObservation(
            id="mem:2",
            observation="User preference discovered",
            memory_type="user_preference",
            context="During debugging session",
            tags=["user", "preference"],
            created_at=now,
        )

        with patch("chromadb.PersistentClient", return_value=mock_chromadb_client):
            with patch("chromadb.config.Settings"):
                mem_id = vector_store.add_memory(obs)

        assert mem_id == "mem:2"

    def test_add_memory_without_optional_fields(
        self,
        vector_store: VectorStore,
        mock_chromadb_client: MagicMock,
    ):
        """Test adding memory without optional fields."""
        obs = MemoryObservation(
            id="mem:3",
            observation="Simple observation",
            memory_type="note",
        )

        with patch("chromadb.PersistentClient", return_value=mock_chromadb_client):
            with patch("chromadb.config.Settings"):
                mem_id = vector_store.add_memory(obs)

        assert mem_id == "mem:3"


class TestSearchMemory:
    """Test memory search functionality."""

    def test_search_memory_basic(
        self,
        vector_store: VectorStore,
        mock_chromadb_client: MagicMock,
    ):
        """Test basic memory search."""
        with patch("chromadb.PersistentClient", return_value=mock_chromadb_client):
            with patch("chromadb.config.Settings"):
                results = vector_store.search_memory("find insights")

        assert isinstance(results, list)
        assert len(results) > 0
        assert "id" in results[0]
        assert "observation" in results[0]
        assert "relevance" in results[0]

    def test_search_memory_by_type(
        self,
        vector_store: VectorStore,
        mock_chromadb_client: MagicMock,
    ):
        """Test memory search filtered by type."""
        with patch("chromadb.PersistentClient", return_value=mock_chromadb_client):
            with patch("chromadb.config.Settings"):
                results = vector_store.search_memory(
                    "test", memory_types=["insight", "user_preference"]
                )

        assert isinstance(results, list)

    def test_search_memory_parses_tags(
        self,
        vector_store: VectorStore,
        mock_chromadb_client: MagicMock,
    ):
        """Test that tags are parsed from metadata."""
        with patch("chromadb.PersistentClient", return_value=mock_chromadb_client):
            with patch("chromadb.config.Settings"):
                results = vector_store.search_memory("test")

        if results:
            assert "tags" in results[0]
            assert isinstance(results[0]["tags"], list)


class TestListMemories:
    """Test memory listing with pagination."""

    def test_list_all_memories(
        self,
        vector_store: VectorStore,
        mock_chromadb_client: MagicMock,
    ):
        """Test listing all memories."""
        with patch("chromadb.PersistentClient", return_value=mock_chromadb_client):
            with patch("chromadb.config.Settings"):
                memories, total = vector_store.list_memories()

        assert isinstance(memories, list)
        assert isinstance(total, int)

    def test_list_memories_with_pagination(
        self,
        vector_store: VectorStore,
        mock_chromadb_client: MagicMock,
    ):
        """Test memory listing with limit and offset."""
        with patch("chromadb.PersistentClient", return_value=mock_chromadb_client):
            with patch("chromadb.config.Settings"):
                memories, total = vector_store.list_memories(limit=10, offset=5)

        assert isinstance(memories, list)
        assert isinstance(total, int)

    def test_list_memories_filter_by_type(
        self,
        vector_store: VectorStore,
        mock_chromadb_client: MagicMock,
    ):
        """Test filtering memories by type."""
        with patch("chromadb.PersistentClient", return_value=mock_chromadb_client):
            with patch("chromadb.config.Settings"):
                memories, total = vector_store.list_memories(memory_types=["insight", "pattern"])

        assert isinstance(memories, list)

    def test_list_memories_exclude_types(
        self,
        vector_store: VectorStore,
        mock_chromadb_client: MagicMock,
    ):
        """Test excluding memory types."""
        with patch("chromadb.PersistentClient", return_value=mock_chromadb_client):
            with patch("chromadb.config.Settings"):
                memories, total = vector_store.list_memories(exclude_types=["system"])

        assert isinstance(memories, list)


# =============================================================================
# Retrieval Tests
# =============================================================================


class TestGetByIds:
    """Test retrieving full documents by ID."""

    def test_get_code_by_ids(
        self,
        vector_store: VectorStore,
        mock_chromadb_client: MagicMock,
    ):
        """Test retrieving code chunks by ID."""
        with patch("chromadb.PersistentClient", return_value=mock_chromadb_client):
            with patch("chromadb.config.Settings"):
                results = vector_store.get_by_ids(["id1", "id2"], collection="code")

        assert isinstance(results, list)
        assert len(results) > 0
        assert "id" in results[0]
        assert "content" in results[0]

    def test_get_memory_by_ids(
        self,
        vector_store: VectorStore,
        mock_chromadb_client: MagicMock,
    ):
        """Test retrieving memory observations by ID."""
        with patch("chromadb.PersistentClient", return_value=mock_chromadb_client):
            with patch("chromadb.config.Settings"):
                results = vector_store.get_by_ids(["mem1"], collection="memory")

        assert isinstance(results, list)

    def test_get_nonexistent_ids(
        self,
        vector_store: VectorStore,
        mock_chromadb_client: MagicMock,
    ):
        """Test retrieving non-existent IDs."""
        # Create a fresh mock for this specific test
        mock_code_coll = MagicMock()
        mock_code_coll.get.return_value = {
            "ids": [],
            "documents": [],
            "metadatas": [],
        }
        mock_chromadb_client.get_collection.side_effect = lambda name: (
            mock_code_coll if name == CODE_COLLECTION else MagicMock()
        )

        with patch("chromadb.PersistentClient", return_value=mock_chromadb_client):
            with patch("chromadb.config.Settings"):
                results = vector_store.get_by_ids(["nonexistent"], collection="code")

        assert results == []


# =============================================================================
# Deletion Tests
# =============================================================================


class TestDeleteCodeByFilepath:
    """Test deleting code chunks by filepath."""

    def test_delete_existing_file(
        self,
        vector_store: VectorStore,
        mock_chromadb_client: MagicMock,
    ):
        """Test deleting chunks for an existing file."""
        mock_code_coll = MagicMock()
        mock_code_coll.get.return_value = {
            "ids": ["id1", "id2", "id3"],
        }
        mock_chromadb_client.get_collection.side_effect = lambda name: (
            mock_code_coll if name == CODE_COLLECTION else MagicMock()
        )

        with patch("chromadb.PersistentClient", return_value=mock_chromadb_client):
            with patch("chromadb.config.Settings"):
                deleted = vector_store.delete_code_by_filepath("test.py")

        assert deleted == 3

    def test_delete_nonexistent_file(
        self,
        vector_store: VectorStore,
        mock_chromadb_client: MagicMock,
    ):
        """Test deleting chunks for non-existent file."""
        mock_code_coll = MagicMock()
        mock_code_coll.get.return_value = {
            "ids": [],
        }
        mock_chromadb_client.get_collection.side_effect = lambda name: (
            mock_code_coll if name == CODE_COLLECTION else MagicMock()
        )

        with patch("chromadb.PersistentClient", return_value=mock_chromadb_client):
            with patch("chromadb.config.Settings"):
                deleted = vector_store.delete_code_by_filepath("nonexistent.py")

        assert deleted == 0


# =============================================================================
# Statistics and Clearing Tests
# =============================================================================


class TestCountUniqueFiles:
    """Test counting unique files in the index."""

    def test_count_unique_files(
        self,
        vector_store: VectorStore,
        mock_chromadb_client: MagicMock,
    ):
        """Test counting unique files."""
        mock_code_coll = MagicMock()
        mock_code_coll.get.return_value = {
            "metadatas": [
                {"filepath": "file1.py"},
                {"filepath": "file1.py"},
                {"filepath": "file2.py"},
                {"filepath": "file3.py"},
            ],
        }
        mock_chromadb_client.get_collection.side_effect = lambda name: (
            mock_code_coll if name == CODE_COLLECTION else MagicMock()
        )

        with patch("chromadb.PersistentClient", return_value=mock_chromadb_client):
            with patch("chromadb.config.Settings"):
                count = vector_store.count_unique_files()

        assert count == 3

    def test_count_empty_index(
        self,
        vector_store: VectorStore,
        mock_chromadb_client: MagicMock,
    ):
        """Test counting files in empty index."""
        mock_code_coll = MagicMock()
        mock_code_coll.get.return_value = {
            "metadatas": [],
        }
        mock_chromadb_client.get_collection.side_effect = lambda name: (
            mock_code_coll if name == CODE_COLLECTION else MagicMock()
        )

        with patch("chromadb.PersistentClient", return_value=mock_chromadb_client):
            with patch("chromadb.config.Settings"):
                count = vector_store.count_unique_files()

        assert count == 0

    def test_count_handles_missing_filepath(
        self,
        vector_store: VectorStore,
        mock_chromadb_client: MagicMock,
    ):
        """Test that missing filepath metadata is handled."""
        mock_code_coll = MagicMock()
        mock_code_coll.get.return_value = {
            "metadatas": [
                {"filepath": "file1.py"},
                {},  # Missing filepath
                {"filepath": "file2.py"},
            ],
        }
        mock_chromadb_client.get_collection.side_effect = lambda name: (
            mock_code_coll if name == CODE_COLLECTION else MagicMock()
        )

        with patch("chromadb.PersistentClient", return_value=mock_chromadb_client):
            with patch("chromadb.config.Settings"):
                count = vector_store.count_unique_files()

        assert count == 2


class TestGetStats:
    """Test getting collection statistics."""

    def test_get_stats(
        self,
        vector_store: VectorStore,
        mock_chromadb_client: MagicMock,
    ):
        """Test retrieving statistics."""
        mock_chromadb_client.get_collection.return_value.count.return_value = 42

        with patch("chromadb.PersistentClient", return_value=mock_chromadb_client):
            with patch("chromadb.config.Settings"):
                stats = vector_store.get_stats()

        assert "code_chunks" in stats
        assert "unique_files" in stats
        assert "memory_count" in stats
        assert "memory_observations" in stats
        assert "persist_directory" in stats


class TestClearOperations:
    """Test clearing collections."""

    def test_clear_code_index_only(
        self,
        vector_store: VectorStore,
        mock_chromadb_client: MagicMock,
    ):
        """Test clearing only the code index."""
        with patch("chromadb.PersistentClient", return_value=mock_chromadb_client):
            with patch("chromadb.config.Settings"):
                vector_store._ensure_initialized()
                vector_store.clear_code_index()

        # Should have deleted and recreated code collection only
        mock_chromadb_client.delete_collection.assert_called_with(CODE_COLLECTION)

    def test_clear_all(
        self,
        vector_store: VectorStore,
        mock_chromadb_client: MagicMock,
    ):
        """Test clearing all collections."""
        with patch("chromadb.PersistentClient", return_value=mock_chromadb_client):
            with patch("chromadb.config.Settings"):
                vector_store._ensure_initialized()
                vector_store.clear_all()

        # Should have deleted both collections
        assert mock_chromadb_client.delete_collection.call_count >= 2


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestEdgeCasesAndErrors:
    """Test edge cases and error conditions."""

    def test_add_chunks_with_dimension_mismatch(
        self,
        vector_store: VectorStore,
        mock_chromadb_client: MagicMock,
        mock_embedding_provider: MagicMock,
    ):
        """Test handling dimension mismatch during chunk insertion."""
        # Mock dimension mismatch error
        mock_chromadb_client.get_collection.return_value.upsert.side_effect = [
            RuntimeError("dimension mismatch"),
            None,  # Success on retry
        ]

        chunk = CodeChunk(
            id="test:1:hash",
            content="code",
            filepath="test.py",
            language="python",
            chunk_type="function",
            name="foo",
            start_line=1,
            end_line=2,
        )

        with patch("chromadb.PersistentClient", return_value=mock_chromadb_client):
            with patch("chromadb.config.Settings"):
                # Should handle the error and retry
                added = vector_store.add_code_chunks([chunk])

        assert added == 1

    def test_add_memory_with_unicode_content(
        self,
        vector_store: VectorStore,
        mock_chromadb_client: MagicMock,
    ):
        """Test adding memory with unicode characters."""
        obs = MemoryObservation(
            id="mem:unicode",
            observation="Found pattern with émojis 🎉 and spëcial chars",
            memory_type="insight",
        )

        with patch("chromadb.PersistentClient", return_value=mock_chromadb_client):
            with patch("chromadb.config.Settings"):
                mem_id = vector_store.add_memory(obs)

        assert mem_id == "mem:unicode"

    def test_search_with_special_characters(
        self,
        vector_store: VectorStore,
        mock_chromadb_client: MagicMock,
    ):
        """Test searching with special characters in query."""
        with patch("chromadb.PersistentClient", return_value=mock_chromadb_client):
            with patch("chromadb.config.Settings"):
                results = vector_store.search_code("async/await patterns @decorator")

        assert isinstance(results, list)

    def test_large_batch_processing(
        self,
        vector_store: VectorStore,
        mock_chromadb_client: MagicMock,
        mock_embedding_provider: MagicMock,
    ):
        """Test batched processing with large number of chunks."""
        chunks = [
            CodeChunk(
                id=f"test:{i}:hash",
                content=f"def func{i}(): pass",
                filepath="test.py",
                language="python",
                chunk_type="function",
                name=f"func{i}",
                start_line=i,
                end_line=i + 1,
            )
            for i in range(250)  # More than batch size
        ]

        with patch("chromadb.PersistentClient", return_value=mock_chromadb_client):
            with patch("chromadb.config.Settings"):
                added = vector_store.add_code_chunks_batched(chunks, batch_size=50)

        assert added == 250

    def test_concurrent_access_safety(
        self,
        vector_store: VectorStore,
        mock_chromadb_client: MagicMock,
    ):
        """Test that operations handle ChromaDB client properly."""
        with patch("chromadb.PersistentClient", return_value=mock_chromadb_client):
            with patch("chromadb.config.Settings"):
                # Multiple operations should use same client
                vector_store._ensure_initialized()
                client1 = vector_store._client

                vector_store.count_unique_files()
                client2 = vector_store._client

                assert client1 is client2
