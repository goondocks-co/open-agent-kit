"""ChromaDB vector store for code and memory storage."""

import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from open_agent_kit.features.codebase_intelligence.constants import (
    DEFAULT_EMBEDDING_BATCH_SIZE,
)
from open_agent_kit.features.codebase_intelligence.embeddings.base import EmbeddingProvider

logger = logging.getLogger(__name__)

# Collection names
CODE_COLLECTION = "oak_code"
MEMORY_COLLECTION = "oak_memory"


@dataclass
class CodeChunk:
    """A chunk of code for indexing."""

    id: str
    content: str
    filepath: str
    language: str
    chunk_type: str
    name: str | None
    start_line: int
    end_line: int
    parent_id: str | None = None
    docstring: str | None = None
    signature: str | None = None

    @property
    def token_estimate(self) -> int:
        """Estimate tokens (~4 chars per token)."""
        return len(self.content) // 4

    def to_metadata(self) -> dict[str, Any]:
        """Convert to ChromaDB metadata format."""
        return {
            "filepath": self.filepath,
            "language": self.language,
            "chunk_type": self.chunk_type,
            "name": self.name or "",
            "start_line": self.start_line,
            "end_line": self.end_line,
            "parent_id": self.parent_id or "",
            "has_docstring": bool(self.docstring),
            "token_estimate": self.token_estimate,
        }

    @staticmethod
    def generate_id(filepath: str, start_line: int, content: str) -> str:
        """Generate stable ID from content."""
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:12]
        return f"{filepath}:{start_line}:{content_hash}"


@dataclass
class MemoryObservation:
    """A memory observation."""

    id: str
    observation: str
    memory_type: str
    context: str | None = None
    tags: list[str] | None = None
    created_at: datetime | None = None

    @property
    def token_estimate(self) -> int:
        """Estimate tokens."""
        return len(self.observation) // 4

    def to_metadata(self) -> dict[str, Any]:
        """Convert to ChromaDB metadata format."""
        return {
            "memory_type": self.memory_type,
            "context": self.context or "",
            "tags": ",".join(self.tags) if self.tags else "",
            "created_at": self.created_at.isoformat() if self.created_at else "",
            "token_estimate": self.token_estimate,
        }


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
            hnsw_config = {
                "hnsw:space": "cosine",
                "hnsw:construction_ef": 200,
                "hnsw:M": 16,
            }

            # Check if existing collections have mismatched dimensions
            self._code_collection = self._get_or_recreate_collection(
                CODE_COLLECTION, hnsw_config, embedding_dims
            )
            self._memory_collection = self._get_or_recreate_collection(
                MEMORY_COLLECTION, hnsw_config, embedding_dims
            )

            logger.info(
                f"ChromaDB initialized at {self.persist_directory} "
                f"(embedding dims: {embedding_dims})"
            )

        except ImportError as e:
            raise RuntimeError(
                "ChromaDB is not installed. Install with: "
                "pip install open-agent-kit[codebase-intelligence]"
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

        except Exception:
            # Collection doesn't exist (NotFoundError) or other ChromaDB error, create it
            # Using broad Exception since ChromaDB exception types vary by version
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
        collection = (
            self._code_collection if collection_name == CODE_COLLECTION else self._memory_collection
        )

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
        hnsw_config = {
            "hnsw:space": "cosine",
            "hnsw:construction_ef": 200,
            "hnsw:M": 16,
        }

        self._client.delete_collection(collection_name)
        new_collection = self._client.create_collection(name=collection_name, metadata=hnsw_config)

        if collection_name == CODE_COLLECTION:
            self._code_collection = new_collection
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
            # Reinitialize with new dimensions
            self._ensure_initialized()
            logger.info(f"ChromaDB reinitialized with {new_dims} dimensions")

    def add_code_chunks(self, chunks: list[CodeChunk]) -> int:
        """Add code chunks to the index.

        Args:
            chunks: List of code chunks to add.

        Returns:
            Number of chunks added.
        """
        self._ensure_initialized()

        if not chunks:
            return 0

        # Deduplicate chunks by ID (can happen with overlap in split chunks)
        seen_ids: set[str] = set()
        unique_chunks: list[CodeChunk] = []
        for chunk in chunks:
            if chunk.id not in seen_ids:
                seen_ids.add(chunk.id)
                unique_chunks.append(chunk)
            else:
                logger.debug(f"Skipping duplicate chunk ID: {chunk.id}")

        if len(unique_chunks) < len(chunks):
            logger.info(f"Deduplicated {len(chunks)} chunks to {len(unique_chunks)} unique")

        chunks = unique_chunks

        # Generate embeddings for all chunks
        contents = [chunk.content for chunk in chunks]
        result = self.embedding_provider.embed(contents)

        # Get actual dimensions from embeddings
        actual_dims = result.dimensions
        if result.embeddings is not None and len(result.embeddings) > 0:
            actual_dims = len(result.embeddings[0])

        # Check for dimension mismatch (for non-empty collections)
        self._handle_dimension_mismatch(CODE_COLLECTION, actual_dims)

        # Prepare data for ChromaDB
        ids = [chunk.id for chunk in chunks]
        documents = contents
        embeddings = result.embeddings
        metadatas = [chunk.to_metadata() for chunk in chunks]

        # Upsert to handle updates, with dimension mismatch recovery
        try:
            self._code_collection.upsert(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
            )
        except (RuntimeError, ValueError, TypeError) as e:
            # Handle dimension mismatch for empty collections
            if "dimension" in str(e).lower():
                logger.warning(f"Dimension mismatch on insert, recreating collection: {e}")
                self._recreate_collection(CODE_COLLECTION, actual_dims)
                self._code_collection.upsert(
                    ids=ids,
                    documents=documents,
                    embeddings=embeddings,
                    metadatas=metadatas,
                )
            else:
                raise

        logger.info(f"Added {len(chunks)} code chunks to index")
        return len(chunks)

    def add_code_chunks_batched(
        self,
        chunks: list[CodeChunk],
        batch_size: int = DEFAULT_EMBEDDING_BATCH_SIZE,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> int:
        """Add code chunks to the index in batches.

        This method processes chunks in smaller batches to prevent memory
        issues when indexing large codebases with thousands of files.

        Args:
            chunks: List of code chunks to add.
            batch_size: Number of chunks to process per batch.
            progress_callback: Optional callback(processed, total) for progress.

        Returns:
            Number of chunks added.
        """
        self._ensure_initialized()

        if not chunks:
            return 0

        # Deduplicate chunks by ID
        seen_ids: set[str] = set()
        unique_chunks: list[CodeChunk] = []
        for chunk in chunks:
            if chunk.id not in seen_ids:
                seen_ids.add(chunk.id)
                unique_chunks.append(chunk)

        if len(unique_chunks) < len(chunks):
            logger.info(f"Deduplicated {len(chunks)} chunks to {len(unique_chunks)} unique")

        total_chunks = len(unique_chunks)
        total_added = 0

        # Process in batches
        for batch_start in range(0, total_chunks, batch_size):
            batch_end = min(batch_start + batch_size, total_chunks)
            batch = unique_chunks[batch_start:batch_end]

            # Generate embeddings for this batch
            contents = [chunk.content for chunk in batch]
            result = self.embedding_provider.embed(contents)

            # Get actual dimensions
            actual_dims = result.dimensions
            if result.embeddings is not None and len(result.embeddings) > 0:
                actual_dims = len(result.embeddings[0])

            # Handle dimension mismatch (only check on first batch)
            if batch_start == 0:
                self._handle_dimension_mismatch(CODE_COLLECTION, actual_dims)

            # Prepare data for ChromaDB
            ids = [chunk.id for chunk in batch]
            documents = contents
            embeddings = result.embeddings
            metadatas = [chunk.to_metadata() for chunk in batch]

            # Upsert batch with dimension mismatch recovery
            try:
                self._code_collection.upsert(
                    ids=ids,
                    documents=documents,
                    embeddings=embeddings,
                    metadatas=metadatas,
                )
                total_added += len(batch)
            except (RuntimeError, ValueError, TypeError) as e:
                if "dimension" in str(e).lower():
                    logger.warning(
                        f"Dimension mismatch on batch insert, recreating collection: {e}"
                    )
                    self._recreate_collection(CODE_COLLECTION, actual_dims)
                    self._code_collection.upsert(
                        ids=ids,
                        documents=documents,
                        embeddings=embeddings,
                        metadatas=metadatas,
                    )
                    total_added += len(batch)
                else:
                    raise

            # Report progress
            if progress_callback:
                progress_callback(batch_end, total_chunks)

            logger.debug(f"Processed batch {batch_start // batch_size + 1}: {len(batch)} chunks")

        logger.info(f"Added {total_added} code chunks to index in batches of {batch_size}")
        return total_added

    def add_memory(self, observation: MemoryObservation) -> str:
        """Add a memory observation.

        Args:
            observation: The observation to store.

        Returns:
            The observation ID.
        """
        self._ensure_initialized()

        # Generate embedding
        result = self.embedding_provider.embed([observation.observation])

        # Get actual dimensions
        actual_dims = result.dimensions
        if result.embeddings is not None and len(result.embeddings) > 0:
            actual_dims = len(result.embeddings[0])

        # Check for dimension mismatch
        self._handle_dimension_mismatch(MEMORY_COLLECTION, actual_dims)

        # Upsert with dimension mismatch recovery
        try:
            self._memory_collection.upsert(
                ids=[observation.id],
                documents=[observation.observation],
                embeddings=result.embeddings,
                metadatas=[observation.to_metadata()],
            )
        except (RuntimeError, ValueError, TypeError) as e:
            if "dimension" in str(e).lower():
                logger.warning(f"Dimension mismatch on memory insert, recreating: {e}")
                self._recreate_collection(MEMORY_COLLECTION, actual_dims)
                self._memory_collection.upsert(
                    ids=[observation.id],
                    documents=[observation.observation],
                    embeddings=result.embeddings,
                    metadatas=[observation.to_metadata()],
                )
            else:
                raise

        logger.info(f"Added memory observation: {observation.id}")
        return observation.id

    def search_code(
        self,
        query: str,
        limit: int = 20,
        relevance_threshold: float = 0.3,
    ) -> list[dict]:
        """Search code chunks.

        Args:
            query: Search query.
            limit: Maximum results to return.
            relevance_threshold: Minimum relevance score.

        Returns:
            List of search results with metadata.
        """
        self._ensure_initialized()

        query_embedding = self.embedding_provider.embed_query(query)

        results = self._code_collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
            include=["documents", "metadatas", "distances"],
        )

        # Convert to response format
        search_results = []
        for i, doc_id in enumerate(results["ids"][0]):
            # ChromaDB returns distances, convert to similarity
            distance = results["distances"][0][i] if results["distances"] else 0
            relevance = 1 - distance  # Cosine distance to similarity

            if relevance < relevance_threshold:
                continue

            metadata = results["metadatas"][0][i] if results["metadatas"] else {}
            search_results.append(
                {
                    "id": doc_id,
                    "content": results["documents"][0][i] if results["documents"] else "",
                    "relevance": relevance,
                    **metadata,
                }
            )

        return search_results

    def search_memory(
        self,
        query: str,
        limit: int = 10,
        relevance_threshold: float = 0.3,
        memory_types: list[str] | None = None,
    ) -> list[dict]:
        """Search memory observations.

        Args:
            query: Search query.
            limit: Maximum results to return.
            relevance_threshold: Minimum relevance score.
            memory_types: Filter by memory types.

        Returns:
            List of search results.
        """
        self._ensure_initialized()

        query_embedding = self.embedding_provider.embed_query(query)

        # Build where filter if memory_types specified
        where = None
        if memory_types:
            where = {"memory_type": {"$in": memory_types}}

        results = self._memory_collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        # Convert to response format
        search_results = []
        for i, doc_id in enumerate(results["ids"][0]):
            distance = results["distances"][0][i] if results["distances"] else 0
            relevance = 1 - distance

            if relevance < relevance_threshold:
                continue

            metadata = results["metadatas"][0][i] if results["metadatas"] else {}
            # Parse tags from comma-separated string back to list
            tags_str = metadata.pop("tags", "")
            tags_list = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []
            search_results.append(
                {
                    "id": doc_id,
                    "observation": results["documents"][0][i] if results["documents"] else "",
                    "relevance": relevance,
                    "tags": tags_list,
                    **metadata,
                }
            )

        return search_results

    def list_memories(
        self,
        limit: int = 50,
        offset: int = 0,
        memory_types: list[str] | None = None,
        exclude_types: list[str] | None = None,
    ) -> tuple[list[dict], int]:
        """List memories with pagination and optional filtering.

        Args:
            limit: Maximum number of memories to return.
            offset: Number of memories to skip.
            memory_types: Only include these memory types.
            exclude_types: Exclude these memory types.

        Returns:
            Tuple of (memories list, total count).
        """
        self._ensure_initialized()

        # Build where filter
        where = None
        if memory_types:
            where = {"memory_type": {"$in": memory_types}}
        elif exclude_types:
            where = {"memory_type": {"$nin": exclude_types}}

        # Get total count for pagination
        if where:
            count_results = self._memory_collection.get(
                where=where,
                include=[],
            )
            total_count = len(count_results["ids"]) if count_results["ids"] else 0
        else:
            total_count = self._memory_collection.count()

        # Fetch paginated results
        # ChromaDB get() doesn't support offset/limit with where, so we fetch all matching
        # and slice. For large collections, this could be optimized with a different approach.
        results = self._memory_collection.get(
            where=where,
            include=["documents", "metadatas"],
        )

        memories = []
        ids_list = results["ids"] if results["ids"] else []

        # Sort by created_at descending (most recent first)
        # Create tuples of (index, created_at) for sorting
        sorted_indices = list(range(len(ids_list)))
        if results["metadatas"]:
            sorted_indices.sort(
                key=lambda i: results["metadatas"][i].get("created_at", ""),
                reverse=True,
            )

        # Apply pagination
        paginated_indices = sorted_indices[offset : offset + limit]

        for i in paginated_indices:
            doc_id = ids_list[i]
            metadata = results["metadatas"][i] if results["metadatas"] else {}
            # Parse tags from comma-separated string back to list
            tags_str = metadata.pop("tags", "")
            tags_list = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []
            memories.append(
                {
                    "id": doc_id,
                    "observation": results["documents"][i] if results["documents"] else "",
                    "tags": tags_list,
                    **metadata,
                }
            )

        return memories, total_count

    def get_by_ids(self, ids: list[str], collection: str = "code") -> list[dict]:
        """Fetch full content by IDs.

        Args:
            ids: List of IDs to fetch.
            collection: Which collection ('code' or 'memory').

        Returns:
            List of full documents.
        """
        self._ensure_initialized()

        coll = self._code_collection if collection == "code" else self._memory_collection

        results = coll.get(
            ids=ids,
            include=["documents", "metadatas"],
        )

        fetched = []
        for i, doc_id in enumerate(results["ids"]):
            fetched.append(
                {
                    "id": doc_id,
                    "content": results["documents"][i] if results["documents"] else "",
                    **(results["metadatas"][i] if results["metadatas"] else {}),
                }
            )

        return fetched

    def delete_code_by_filepath(self, filepath: str) -> int:
        """Delete all code chunks for a file.

        Args:
            filepath: File path to delete chunks for.

        Returns:
            Number of chunks deleted.
        """
        self._ensure_initialized()

        # Get IDs for this filepath
        results = self._code_collection.get(
            where={"filepath": filepath},
            include=[],
        )

        if not results["ids"]:
            return 0

        self._code_collection.delete(ids=results["ids"])
        return len(results["ids"])

    def count_unique_files(self) -> int:
        """Count unique files in the code index.

        Returns:
            Number of unique files indexed.
        """
        self._ensure_initialized()

        try:
            # ChromaDB doesn't have a distinct count query, so we fetch metadata
            # For large datasets, this might be slow, but it's accurate
            results = self._code_collection.get(include=["metadatas"])
            if not results or not results["metadatas"]:
                return 0

            unique_files = {m.get("filepath") for m in results["metadatas"] if m.get("filepath")}
            return len(unique_files)
        except (OSError, RuntimeError, AttributeError) as e:
            logger.exception(f"Failed to count unique files: {e}")
            return 0

    def get_stats(self) -> dict:
        """Get collection statistics.

        Returns:
            Dictionary with statistics.
        """
        self._ensure_initialized()

        # Handle race condition where collection may be deleted during reindex
        try:
            code_count = self._code_collection.count() if self._code_collection else 0
        except Exception:
            code_count = 0

        try:
            memory_count = self._memory_collection.count() if self._memory_collection else 0
        except Exception:
            memory_count = 0

        return {
            "code_chunks": code_count,
            "memory_observations": memory_count,
            "persist_directory": str(self.persist_directory),
        }

    def count_memories(self) -> int:
        """Count total memory observations in ChromaDB.

        Returns:
            Number of memory observations.
        """
        self._ensure_initialized()
        return self._memory_collection.count() if self._memory_collection else 0

    def clear_code_index(self) -> None:
        """Clear only the code index, preserving memories.

        Use this for rebuilds/reindexing - memories should persist across
        code index rebuilds since they represent user-captured observations.
        """
        self._ensure_initialized()

        # Delete and recreate only the code collection
        self._client.delete_collection(CODE_COLLECTION)

        hnsw_config = {
            "hnsw:space": "cosine",
            "hnsw:construction_ef": 200,
            "hnsw:M": 16,
        }

        self._code_collection = self._client.create_collection(
            name=CODE_COLLECTION,
            metadata=hnsw_config,
        )

        logger.info("Cleared code index (memories preserved)")

    def clear_all(self) -> None:
        """Clear all data from both collections.

        WARNING: This also clears memories! Use clear_code_index() for rebuilds.
        """
        self._ensure_initialized()

        # Delete and recreate collections
        self._client.delete_collection(CODE_COLLECTION)
        self._client.delete_collection(MEMORY_COLLECTION)

        # Recreate
        hnsw_config = {
            "hnsw:space": "cosine",
            "hnsw:construction_ef": 200,
            "hnsw:M": 16,
        }

        self._code_collection = self._client.create_collection(
            name=CODE_COLLECTION,
            metadata=hnsw_config,
        )

        self._memory_collection = self._client.create_collection(
            name=MEMORY_COLLECTION,
            metadata=hnsw_config,
        )

        logger.info("Cleared all vector store data (including memories)")
