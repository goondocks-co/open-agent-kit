"""Core VectorStore class for memory store.

Contains the main VectorStore class with ChromaDB initialization and delegation
to operation modules.
"""

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from open_agent_kit.features.codebase_intelligence.constants import (
    DEFAULT_EMBEDDING_BATCH_SIZE,
)
from open_agent_kit.features.codebase_intelligence.embeddings.base import EmbeddingProvider
from open_agent_kit.features.codebase_intelligence.memory.store import (
    code_ops,
    management,
    memory_ops,
    search,
    session_ops,
)
from open_agent_kit.features.codebase_intelligence.memory.store.constants import (
    CODE_COLLECTION,
    MEMORY_COLLECTION,
    SESSION_SUMMARIES_COLLECTION,
    default_hnsw_config,
)
from open_agent_kit.features.codebase_intelligence.memory.store.models import (
    CodeChunk,
    MemoryObservation,
    PlanObservation,
)

logger = logging.getLogger(__name__)


class VectorStore:
    """ChromaDB-based vector store for code and memory.

    Manages two collections:
    - oak_code: Indexed code chunks
    - oak_memory: Observations and learnings
    """

    def __init__(
        self,
        persist_directory: Path,
        embedding_provider: EmbeddingProvider,
    ):
        """Initialize vector store.

        Args:
            persist_directory: Directory for ChromaDB persistence.
            embedding_provider: Provider for generating embeddings.
        """
        self.persist_directory = persist_directory
        self.embedding_provider = embedding_provider
        # Lazily initialized - chromadb is an optional dependency
        self._client: Any = None
        self._code_collection: Any = None
        self._memory_collection: Any = None
        self._session_summaries_collection: Any = None

    def _ensure_initialized(self) -> None:
        """Ensure ChromaDB is initialized."""
        if self._client is not None:
            return

        try:
            import chromadb  # type: ignore[import-not-found]
            from chromadb.config import Settings  # type: ignore[import-not-found]

            self.persist_directory.mkdir(parents=True, exist_ok=True)

            self._client = chromadb.PersistentClient(
                path=str(self.persist_directory),
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True,
                ),
            )

            # Get embedding dimensions from provider
            embedding_dims = self.embedding_provider.dimensions

            # Create or get collections with HNSW configuration
            hnsw_config = default_hnsw_config()

            # Check if existing collections have mismatched dimensions
            self._code_collection = self._get_or_recreate_collection(
                CODE_COLLECTION, hnsw_config, embedding_dims
            )
            self._memory_collection = self._get_or_recreate_collection(
                MEMORY_COLLECTION, hnsw_config, embedding_dims
            )
            self._session_summaries_collection = self._get_or_recreate_collection(
                SESSION_SUMMARIES_COLLECTION, hnsw_config, embedding_dims
            )

            logger.info(
                f"ChromaDB initialized at {self.persist_directory} "
                f"(embedding dims: {embedding_dims})"
            )

        except ImportError as e:
            raise RuntimeError(
                "ChromaDB is not installed. Install with: "
                "pip install oak-ci[codebase-intelligence]"
            ) from e

    def _get_or_recreate_collection(self, name: str, hnsw_config: dict, expected_dims: int) -> Any:
        """Get or recreate a collection, handling dimension mismatches.

        If an existing collection has different embedding dimensions than expected,
        it will be deleted and recreated. This handles switching between embedding
        providers (e.g., Ollama 768d vs FastEmbed 384d).

        Args:
            name: Collection name.
            hnsw_config: HNSW configuration for the collection.
            expected_dims: Expected embedding dimensions.

        Returns:
            ChromaDB collection.
        """
        try:
            # Try to get existing collection
            collection = self._client.get_collection(name=name)

            # Check if we can detect dimension mismatch
            # ChromaDB doesn't store dims in metadata, so we try a test query
            # If collection is empty, just use it
            if collection.count() == 0:
                return collection

            # Try to detect dimension mismatch by checking existing embeddings
            # This is a heuristic - if first item has different dims, recreate
            try:
                sample = collection.peek(limit=1)
                # Use explicit len() checks to avoid numpy array truthiness ambiguity
                embeddings = sample.get("embeddings") if sample else None
                if embeddings is not None and len(embeddings) > 0:
                    existing_dims = len(embeddings[0])
                    if existing_dims != expected_dims:
                        logger.warning(
                            f"Collection '{name}' has embeddings with {existing_dims} dims, "
                            f"but current provider uses {expected_dims} dims. Recreating..."
                        )
                        self._client.delete_collection(name)
                        return self._client.create_collection(name=name, metadata=hnsw_config)
            except (AttributeError, KeyError, TypeError, ValueError):
                pass  # Can't check, just use existing

            return collection

        except Exception:  # broad catch intentional: ChromaDB exception types vary by version
            # Collection doesn't exist (NotFoundError) or other ChromaDB error, create it
            return self._client.create_collection(name=name, metadata=hnsw_config)

    def _handle_dimension_mismatch(self, collection_name: str, actual_dims: int) -> None:
        """Check and handle dimension mismatch for a collection.

        If the collection's expected dimensions don't match the actual embedding
        dimensions, recreate the collection. This handles the case where the
        embedding provider falls back to a different provider after collection
        creation.

        Args:
            collection_name: Name of the collection to check.
            actual_dims: Actual dimensions of the embeddings being added.
        """
        if collection_name == CODE_COLLECTION:
            collection = self._code_collection
        elif collection_name == SESSION_SUMMARIES_COLLECTION:
            collection = self._session_summaries_collection
        else:
            collection = self._memory_collection

        # Try to detect current collection dimensions
        try:
            sample = collection.peek(limit=1)
            # Use explicit len() checks to avoid numpy array truthiness ambiguity
            embeddings = sample.get("embeddings") if sample else None
            if embeddings is not None and len(embeddings) > 0:
                existing_dims = len(embeddings[0])
                if existing_dims != actual_dims:
                    logger.warning(
                        f"Dimension mismatch in '{collection_name}': "
                        f"collection has {existing_dims}, got {actual_dims}. Recreating..."
                    )
                    self._recreate_collection(collection_name, actual_dims)
        except (AttributeError, KeyError, TypeError, ValueError):
            # Empty collection or error - check if we need to recreate anyway
            # ChromaDB doesn't store dims in metadata, so we can't check directly
            # Just proceed and let the upsert fail if there's a mismatch
            pass

    def _recreate_collection(self, collection_name: str, dims: int) -> None:
        """Recreate a collection with new dimensions.

        Args:
            collection_name: Name of the collection to recreate.
            dims: Expected embedding dimensions.
        """
        hnsw_config = default_hnsw_config()

        self._client.delete_collection(collection_name)
        new_collection = self._client.create_collection(name=collection_name, metadata=hnsw_config)

        if collection_name == CODE_COLLECTION:
            self._code_collection = new_collection
        elif collection_name == SESSION_SUMMARIES_COLLECTION:
            self._session_summaries_collection = new_collection
        else:
            self._memory_collection = new_collection

        logger.info(f"Recreated collection '{collection_name}' for {dims}-dim embeddings")

    def update_embedding_provider(self, new_provider: EmbeddingProvider) -> None:
        """Update the embedding provider and reinitialize if dimensions changed.

        This should be called when switching embedding models/providers to ensure
        ChromaDB collections are recreated with the correct dimensions.

        Args:
            new_provider: New embedding provider to use.
        """
        old_dims = self.embedding_provider.dimensions if self.embedding_provider else None
        new_dims = new_provider.dimensions

        self.embedding_provider = new_provider

        # If dimensions changed and we're already initialized, reinitialize collections
        if self._client is not None and old_dims != new_dims:
            logger.info(
                f"Embedding dimensions changed ({old_dims} -> {new_dims}), "
                "reinitializing ChromaDB collections..."
            )
            # Force reinitialization by clearing client state
            self._client = None
            self._code_collection = None
            self._memory_collection = None
            self._session_summaries_collection = None
            # Reinitialize with new dimensions
            self._ensure_initialized()
            logger.info(f"ChromaDB reinitialized with {new_dims} dimensions")

    # ==========================================================================
    # Code operations - delegate to code_ops module
    # ==========================================================================

    def add_code_chunks(self, chunks: list[CodeChunk]) -> int:
        """Add code chunks to the index."""
        return code_ops.add_code_chunks(self, chunks)

    def add_code_chunks_batched(
        self,
        chunks: list[CodeChunk],
        batch_size: int = DEFAULT_EMBEDDING_BATCH_SIZE,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> int:
        """Add code chunks to the index in batches."""
        return code_ops.add_code_chunks_batched(self, chunks, batch_size, progress_callback)

    def delete_code_by_filepath(self, filepath: str) -> int:
        """Delete all code chunks for a file."""
        return code_ops.delete_code_by_filepath(self, filepath)

    # ==========================================================================
    # Memory operations - delegate to memory_ops module
    # ==========================================================================

    def add_memory(self, observation: MemoryObservation) -> str:
        """Add a memory observation."""
        return memory_ops.add_memory(self, observation)

    def add_plan(self, plan: PlanObservation) -> str:
        """Add a plan to the memory collection for semantic search."""
        return memory_ops.add_plan(self, plan)

    def delete_memories(self, observation_ids: list[str]) -> int:
        """Delete memories from ChromaDB by their observation IDs."""
        return memory_ops.delete_memories(self, observation_ids)

    # ==========================================================================
    # Search operations - delegate to search module
    # ==========================================================================

    def search_code(self, query: str, limit: int = 20) -> list[dict]:
        """Search code chunks."""
        return search.search_code(self, query, limit)

    def search_memory(
        self,
        query: str,
        limit: int = 10,
        memory_types: list[str] | None = None,
        metadata_filters: dict | None = None,
    ) -> list[dict]:
        """Search memory observations."""
        return search.search_memory(self, query, limit, memory_types, metadata_filters)

    def get_by_ids(self, ids: list[str], collection: str = "code") -> list[dict]:
        """Fetch full content by IDs."""
        return search.get_by_ids(self, ids, collection)

    # ==========================================================================
    # Management operations - delegate to management module
    # ==========================================================================

    def update_memory_status(
        self,
        memory_id: str,
        status: str,
        session_origin_type: str | None = None,
    ) -> bool:
        """Update memory status in ChromaDB metadata."""
        return management.update_memory_status(self, memory_id, status, session_origin_type)

    def archive_memory(self, memory_id: str, archived: bool = True) -> bool:
        """Archive or unarchive a memory."""
        return management.archive_memory(self, memory_id, archived)

    def list_memories(
        self,
        limit: int = 50,
        offset: int = 0,
        memory_types: list[str] | None = None,
        exclude_types: list[str] | None = None,
        tag: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        include_archived: bool = False,
        status: str | None = "active",
        include_resolved: bool = False,
    ) -> tuple[list[dict], int]:
        """List memories with pagination and optional filtering."""
        return management.list_memories(
            self,
            limit,
            offset,
            memory_types,
            exclude_types,
            tag,
            start_date,
            end_date,
            include_archived,
            status,
            include_resolved,
        )

    def bulk_archive_memories(self, memory_ids: list[str], archived: bool = True) -> int:
        """Archive or unarchive multiple memories."""
        return management.bulk_archive_memories(self, memory_ids, archived)

    def add_tag_to_memories(self, memory_ids: list[str], tag: str) -> int:
        """Add a tag to multiple memories."""
        return management.add_tag_to_memories(self, memory_ids, tag)

    def remove_tag_from_memories(self, memory_ids: list[str], tag: str) -> int:
        """Remove a tag from multiple memories."""
        return management.remove_tag_from_memories(self, memory_ids, tag)

    def count_unique_files(self) -> int:
        """Count unique files in the code index."""
        return management.count_unique_files(self)

    def get_all_memory_ids(self) -> list[str]:
        """Get all IDs from the ChromaDB memory collection."""
        return management.get_all_memory_ids(self)

    def get_stats(self) -> dict:
        """Get collection statistics."""
        return management.get_stats(self)

    def count_memories(self) -> int:
        """Count total memory observations in ChromaDB."""
        return management.count_memories(self)

    def count_plans(self) -> int:
        """Count plan entries in ChromaDB memory collection."""
        return management.count_plans(self)

    def clear_code_index(self) -> None:
        """Clear only the code index, preserving memories."""
        management.clear_code_index(self)

    def clear_memory_collection(self) -> int:
        """Clear only memory collection, preserving code index."""
        return management.clear_memory_collection(self)

    def clear_all(self) -> None:
        """Clear all data from both collections."""
        management.clear_all(self)

    def hard_reset(self) -> int:
        """Delete ChromaDB directory to reclaim disk space.

        ChromaDB's delete_collection() does NOT release disk space.
        This deletes the entire directory and reinitializes empty collections.
        Caller must rebuild from SQLite afterward.

        Returns:
            Approximate bytes freed.
        """
        return management.hard_reset(self)

    # ==========================================================================
    # Session summary operations - for similarity-based session linking
    # ==========================================================================

    def add_session_summary(
        self,
        session_id: str,
        title: str,
        summary: str,
        agent: str,
        project_root: str,
        created_at_epoch: int,
    ) -> None:
        """Add a session summary embedding for similarity search."""
        session_ops.add_session_summary(
            self, session_id, title, summary, agent, project_root, created_at_epoch
        )

    def find_similar_sessions(
        self,
        query_text: str,
        project_root: str,
        exclude_session_id: str | None = None,
        limit: int = 5,
        max_age_days: int = 7,
    ) -> list[tuple[str, float]]:
        """Find sessions with similar summaries using vector search."""
        return session_ops.find_similar_sessions(
            self,
            query_text,
            project_root,
            exclude_session_id,
            limit,
            max_age_days,
        )

    def search_session_summaries(self, query: str, limit: int = 10) -> list[dict]:
        """Search session summaries using vector similarity."""
        return session_ops.search_session_summaries(self, query, limit)

    def delete_session_summary(self, session_id: str) -> bool:
        """Delete a session summary from the vector store."""
        return session_ops.delete_session_summary(self, session_id)

    def clear_session_summaries(self) -> int:
        """Clear all session summaries from the vector store."""
        return session_ops.clear_session_summaries(self)

    def count_session_summaries(self) -> int:
        """Count session summaries in the vector store."""
        return session_ops.count_session_summaries(self)
