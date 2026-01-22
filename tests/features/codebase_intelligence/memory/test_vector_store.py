"""Comprehensive tests for VectorStore operations.

This module tests critical VectorStore functionality:
- Dimension mismatch detection and recovery
- Batch embedding with progress tracking
- Search relevance filtering
- Collection separation (code vs memory)
- Error handling and edge cases

These tests ensure the vector store can handle various failure scenarios
and maintain data integrity during provider switches and updates.
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from open_agent_kit.features.codebase_intelligence.embeddings.base import (
    EmbeddingProvider,
    EmbeddingResult,
)
from open_agent_kit.features.codebase_intelligence.memory.store import (
    CODE_COLLECTION,
    MEMORY_COLLECTION,
    CodeChunk,
    MemoryObservation,
    VectorStore,
)


@pytest.fixture
def mock_embedding_provider() -> MagicMock:
    """Provide a mock embedding provider.

    Returns:
        MagicMock configured for EmbeddingProvider.
    """
    mock = MagicMock(spec=EmbeddingProvider)
    mock.dimensions = 384

    # Default embed behavior
    def embed_side_effect(texts):
        if isinstance(texts, str):
            texts = [texts]
        return EmbeddingResult(
            embeddings=[[0.1, 0.2, 0.3] * 128 for _ in texts],  # 384 dims
            model="mock-model",
            provider="mock",
            dimensions=384,
        )

    mock.embed.side_effect = embed_side_effect
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
    return tmp_path / "chroma_store"


@pytest.fixture
def vector_store(temp_vector_store_dir: Path, mock_embedding_provider: MagicMock) -> VectorStore:
    """Provide a VectorStore instance.

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


class TestVectorStoreDimensionMismatch:
    """Test dimension mismatch detection and recovery."""

    def test_dimension_mismatch_detection_logic(
        self,
        temp_vector_store_dir: Path,
        mock_embedding_provider: MagicMock,
    ):
        """Test the dimension mismatch detection logic.

        This test verifies the _handle_dimension_mismatch method logic
        without requiring full ChromaDB setup.

        Args:
            temp_vector_store_dir: Temporary directory for store.
            mock_embedding_provider: Mock embedding provider.
        """
        # Create store
        store = VectorStore(
            persist_directory=temp_vector_store_dir,
            embedding_provider=mock_embedding_provider,
        )

        # Mock the collections
        mock_code_collection = MagicMock()
        mock_memory_collection = MagicMock()

        # Simulate existing collection with different dimensions
        mock_code_collection.count.return_value = 10
        mock_code_collection.peek.return_value = {
            "embeddings": [[0.1] * 768]  # 768 dims (mismatch with 384)
        }

        store._code_collection = mock_code_collection
        store._memory_collection = mock_memory_collection
        store._client = MagicMock()

        # Call dimension mismatch handler with mismatched dimensions
        store._handle_dimension_mismatch("oak_code", 384)

        # Should have called recreate logic internally
        # The method should detect the mismatch and attempt to recreate
        # Verify peek was called to check dimensions
        mock_code_collection.peek.assert_called_once()

    def test_recreate_collection_creates_new_collection(
        self,
        temp_vector_store_dir: Path,
        mock_embedding_provider: MagicMock,
    ):
        """Test that _recreate_collection creates a new collection.

        Args:
            temp_vector_store_dir: Temporary directory for store.
            mock_embedding_provider: Mock embedding provider.
        """
        # Create store
        store = VectorStore(
            persist_directory=temp_vector_store_dir,
            embedding_provider=mock_embedding_provider,
        )

        # Mock client and collections
        store._client = MagicMock()
        store._code_collection = MagicMock()

        # Call recreate
        store._recreate_collection("oak_code", 384)

        # Verify delete was called
        store._client.delete_collection.assert_called_once_with("oak_code")

        # Verify create was called
        store._client.create_collection.assert_called_once()

    def test_dimension_mismatch_empty_collection_handling(
        self,
        temp_vector_store_dir: Path,
        mock_embedding_provider: MagicMock,
    ):
        """Test that empty collections don't trigger dimension mismatch.

        Args:
            temp_vector_store_dir: Temporary directory for store.
            mock_embedding_provider: Mock embedding provider.
        """
        # Create store
        store = VectorStore(
            persist_directory=temp_vector_store_dir,
            embedding_provider=mock_embedding_provider,
        )

        # Mock empty collection
        mock_collection = MagicMock()
        mock_collection.count.return_value = 0
        mock_collection.peek.return_value = None

        store._code_collection = mock_collection
        store._client = MagicMock()

        # Handle dimension check on empty collection
        store._handle_dimension_mismatch("oak_code", 384)

        # Should not recreate collection for empty
        store._client.delete_collection.assert_not_called()


class TestVectorStoreBatchEmbedding:
    """Test batch embedding with progress tracking."""

    def test_batch_embedding_reports_progress(
        self,
        temp_vector_store_dir: Path,
        mock_embedding_provider: MagicMock,
    ):
        """Test that batch embedding calls progress callback correctly.

        Args:
            temp_vector_store_dir: Temporary directory for store.
            mock_embedding_provider: Mock embedding provider.
        """
        # Create store and inject mocks
        store = VectorStore(
            persist_directory=temp_vector_store_dir,
            embedding_provider=mock_embedding_provider,
        )

        # Setup mock client and collection
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 0

        store._client = mock_client
        store._code_collection = mock_collection
        store._memory_collection = MagicMock()

        # Create many chunks to trigger batching
        chunks = [
            CodeChunk(
                id=f"test:{i}:abc{i}",
                content=f"def test{i}():\n    pass",
                filepath="test.py",
                language="python",
                chunk_type="function",
                name=f"test{i}",
                start_line=i * 2,
                end_line=i * 2 + 1,
            )
            for i in range(100)
        ]

        # Track progress calls
        progress_calls = []

        def progress_callback(current: int, total: int):
            progress_calls.append((current, total))

        # Add chunks in batches
        store.add_code_chunks_batched(chunks, batch_size=20, progress_callback=progress_callback)

        # Verify progress was reported
        assert len(progress_calls) > 0

        # Verify progress goes from 0 to total
        assert progress_calls[-1][0] == 100  # Final call shows all processed

    def test_batch_embedding_handles_empty_chunks(
        self,
        temp_vector_store_dir: Path,
        mock_embedding_provider: MagicMock,
    ):
        """Test that batch embedding handles empty chunk list gracefully.

        Args:
            temp_vector_store_dir: Temporary directory for store.
            mock_embedding_provider: Mock embedding provider.
        """
        # Create store and inject mocks
        store = VectorStore(
            persist_directory=temp_vector_store_dir,
            embedding_provider=mock_embedding_provider,
        )

        mock_collection = MagicMock()
        store._client = MagicMock()
        store._code_collection = mock_collection
        store._memory_collection = MagicMock()

        # Add empty list
        result = store.add_code_chunks_batched([])

        # Should return 0 without errors
        assert result == 0

    def test_batch_embedding_deduplicates_chunks(
        self,
        temp_vector_store_dir: Path,
        mock_embedding_provider: MagicMock,
    ):
        """Test that batch embedding deduplicates chunks by ID.

        Args:
            temp_vector_store_dir: Temporary directory for store.
            mock_embedding_provider: Mock embedding provider.
        """
        # Create store and inject mocks
        store = VectorStore(
            persist_directory=temp_vector_store_dir,
            embedding_provider=mock_embedding_provider,
        )

        mock_collection = MagicMock()
        mock_collection.count.return_value = 0

        store._client = MagicMock()
        store._code_collection = mock_collection
        store._memory_collection = MagicMock()

        # Create chunks with duplicate IDs
        chunks = [
            CodeChunk(
                id="test:1:abc123",
                content="def test():\n    pass",
                filepath="test.py",
                language="python",
                chunk_type="function",
                name="test",
                start_line=1,
                end_line=2,
            ),
            CodeChunk(
                id="test:1:abc123",  # Duplicate ID
                content="def test():\n    pass",
                filepath="test.py",
                language="python",
                chunk_type="function",
                name="test",
                start_line=1,
                end_line=2,
            ),
            CodeChunk(
                id="test:2:def456",
                content="def test2():\n    pass",
                filepath="test.py",
                language="python",
                chunk_type="function",
                name="test2",
                start_line=3,
                end_line=4,
            ),
        ]

        result = store.add_code_chunks_batched(chunks, batch_size=10)

        # Should deduplicate to 2 unique chunks
        assert result == 2


class TestVectorStoreSearchRelevance:
    """Test search relevance scoring."""

    def test_search_returns_all_results_with_relevance_scores(
        self,
        temp_vector_store_dir: Path,
        mock_embedding_provider: MagicMock,
    ):
        """Test that search returns all results with relevance scores.

        Args:
            temp_vector_store_dir: Temporary directory for store.
            mock_embedding_provider: Mock embedding provider.
        """
        # Create store and inject mocks
        store = VectorStore(
            persist_directory=temp_vector_store_dir,
            embedding_provider=mock_embedding_provider,
        )

        mock_collection = MagicMock()
        mock_collection.count.return_value = 3
        mock_collection.query.return_value = {
            "ids": [["id1", "id2", "id3"]],
            "documents": [["doc1", "doc2", "doc3"]],
            "distances": [[0.1, 0.5, 0.8]],  # Relevances: 0.9, 0.5, 0.2
            "metadatas": [[{}, {}, {}]],
        }

        store._client = MagicMock()
        store._code_collection = mock_collection
        store._memory_collection = MagicMock()

        # Search returns all results with relevance scores
        results = store.search_code(query="test", limit=10)

        # All results should be returned with relevance scores
        assert len(results) == 3
        assert results[0]["relevance"] == 0.9
        assert results[1]["relevance"] == 0.5
        assert results[2]["relevance"] == pytest.approx(0.2, rel=0.01)


class TestVectorStoreCollectionSeparation:
    """Test that code and memory collections are kept separate."""

    def test_clear_code_preserves_memories(
        self,
        temp_vector_store_dir: Path,
        mock_embedding_provider: MagicMock,
    ):
        """Test that clearing code doesn't affect memories.

        Args:
            temp_vector_store_dir: Temporary directory for store.
            mock_embedding_provider: Mock embedding provider.
        """
        # Create store and inject mocks
        store = VectorStore(
            persist_directory=temp_vector_store_dir,
            embedding_provider=mock_embedding_provider,
        )

        mock_client = MagicMock()
        mock_code_collection = MagicMock()
        mock_memory_collection = MagicMock()

        mock_code_collection.count.return_value = 0
        mock_memory_collection.count.return_value = 0

        store._client = mock_client
        store._code_collection = mock_code_collection
        store._memory_collection = mock_memory_collection

        # Clear code index
        store.clear_code_index()

        # Verify only code collection was deleted
        mock_client.delete_collection.assert_called_once_with(CODE_COLLECTION)

        # Memory collection should not be deleted
        assert all(
            call_args[0][0] != MEMORY_COLLECTION
            for call_args in mock_client.delete_collection.call_args_list
        )

    def test_add_memory_uses_memory_collection(
        self,
        temp_vector_store_dir: Path,
        mock_embedding_provider: MagicMock,
    ):
        """Test that memories are added to memory collection, not code.

        Args:
            temp_vector_store_dir: Temporary directory for store.
            mock_embedding_provider: Mock embedding provider.
        """
        # Create store and inject mocks
        store = VectorStore(
            persist_directory=temp_vector_store_dir,
            embedding_provider=mock_embedding_provider,
        )

        mock_code_collection = MagicMock()
        mock_memory_collection = MagicMock()

        mock_code_collection.count.return_value = 0
        mock_memory_collection.count.return_value = 0

        store._client = MagicMock()
        store._code_collection = mock_code_collection
        store._memory_collection = mock_memory_collection

        # Add memory observation
        memory = MemoryObservation(
            id="mem1",
            observation="User prefers TypeScript",
            memory_type="preference",
            created_at=datetime.now(),
        )

        store.add_memory(memory)

        # Verify memory collection was used, not code
        mock_memory_collection.upsert.assert_called_once()
        mock_code_collection.upsert.assert_not_called()

    def test_search_code_only_queries_code_collection(
        self,
        temp_vector_store_dir: Path,
        mock_embedding_provider: MagicMock,
    ):
        """Test that code search only queries code collection.

        Args:
            temp_vector_store_dir: Temporary directory for store.
            mock_embedding_provider: Mock embedding provider.
        """
        # Create store and inject mocks
        store = VectorStore(
            persist_directory=temp_vector_store_dir,
            embedding_provider=mock_embedding_provider,
        )

        mock_code_collection = MagicMock()
        mock_memory_collection = MagicMock()

        mock_code_collection.count.return_value = 0
        mock_memory_collection.count.return_value = 0

        # Mock query results
        mock_code_collection.query.return_value = {
            "ids": [["id1"]],
            "documents": [["def test(): pass"]],
            "distances": [[0.1]],
            "metadatas": [[{"filepath": "test.py"}]],
        }

        store._client = MagicMock()
        store._code_collection = mock_code_collection
        store._memory_collection = mock_memory_collection

        # Search code
        _results = store.search_code(query="test function", limit=10)

        # Verify code collection was queried
        mock_code_collection.query.assert_called_once()

        # Verify memory collection was NOT queried
        mock_memory_collection.query.assert_not_called()


class TestVectorStoreEdgeCases:
    """Test edge cases and error handling."""

    def test_add_chunks_with_none_values(
        self,
        temp_vector_store_dir: Path,
        mock_embedding_provider: MagicMock,
    ):
        """Test that chunks with None optional fields are handled correctly.

        Args:
            temp_vector_store_dir: Temporary directory for store.
            mock_embedding_provider: Mock embedding provider.
        """
        # Create store and inject mocks
        store = VectorStore(
            persist_directory=temp_vector_store_dir,
            embedding_provider=mock_embedding_provider,
        )

        mock_collection = MagicMock()
        mock_collection.count.return_value = 0

        store._client = MagicMock()
        store._code_collection = mock_collection
        store._memory_collection = MagicMock()

        # Create chunk with None optional fields
        chunk = CodeChunk(
            id="test:1:abc123",
            content="def test():\n    pass",
            filepath="test.py",
            language="python",
            chunk_type="function",
            name=None,  # None name
            start_line=1,
            end_line=2,
            parent_id=None,  # None parent
            docstring=None,  # None docstring
            signature=None,  # None signature
        )

        # Should not raise error
        result = store.add_code_chunks([chunk])
        assert result == 1

    def test_get_stats_handles_collection_errors(
        self,
        temp_vector_store_dir: Path,
        mock_embedding_provider: MagicMock,
    ):
        """Test that get_stats handles errors gracefully.

        Args:
            temp_vector_store_dir: Temporary directory for store.
            mock_embedding_provider: Mock embedding provider.
        """
        # Create store and inject mocks
        store = VectorStore(
            persist_directory=temp_vector_store_dir,
            embedding_provider=mock_embedding_provider,
        )

        mock_code_collection = MagicMock()
        mock_memory_collection = MagicMock()

        # Make count() raise error
        mock_code_collection.count.side_effect = RuntimeError("Collection deleted")
        mock_memory_collection.count.return_value = 5

        store._client = MagicMock()
        store._code_collection = mock_code_collection
        store._memory_collection = mock_memory_collection

        # Should not raise error, should return 0 for failed collection
        stats = store.get_stats()

        assert stats["code_chunks"] == 0  # Error handled
        assert stats["memory_observations"] == 5  # Success

    def test_count_unique_files_with_empty_collection(
        self,
        temp_vector_store_dir: Path,
        mock_embedding_provider: MagicMock,
    ):
        """Test counting unique files in empty collection.

        Args:
            temp_vector_store_dir: Temporary directory for store.
            mock_embedding_provider: Mock embedding provider.
        """
        # Create store and inject mocks
        store = VectorStore(
            persist_directory=temp_vector_store_dir,
            embedding_provider=mock_embedding_provider,
        )

        mock_collection = MagicMock()
        mock_collection.count.return_value = 0
        mock_collection.get.return_value = {"metadatas": []}

        store._client = MagicMock()
        store._code_collection = mock_collection
        store._memory_collection = MagicMock()

        # Should return 0 without errors
        count = store.count_unique_files()
        assert count == 0
