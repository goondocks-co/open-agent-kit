"""Code indexing operations for vector store.

Functions for adding and removing code chunks from ChromaDB.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from open_agent_kit.features.codebase_intelligence.constants import (
    DEFAULT_EMBEDDING_BATCH_SIZE,
)
from open_agent_kit.features.codebase_intelligence.memory.store.constants import CODE_COLLECTION
from open_agent_kit.features.codebase_intelligence.memory.store.models import CodeChunk

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.memory.store.core import VectorStore

logger = logging.getLogger(__name__)


def add_code_chunks(store: VectorStore, chunks: list[CodeChunk]) -> int:
    """Add code chunks to the index.

    Args:
        store: The VectorStore instance.
        chunks: List of code chunks to add.

    Returns:
        Number of chunks added.
    """
    store._ensure_initialized()

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

    # Generate embeddings using document envelope (includes metadata for better search)
    # But store original content for display/retrieval
    embedding_texts = [chunk.get_embedding_text() for chunk in chunks]
    original_contents = [chunk.content for chunk in chunks]
    result = store.embedding_provider.embed(embedding_texts)

    # Get actual dimensions from embeddings
    actual_dims = result.dimensions
    if result.embeddings is not None and len(result.embeddings) > 0:
        actual_dims = len(result.embeddings[0])

    # Check for dimension mismatch (for non-empty collections)
    store._handle_dimension_mismatch(CODE_COLLECTION, actual_dims)

    # Prepare data for ChromaDB
    # Store original content as documents (for display), embeddings from enriched text
    ids = [chunk.id for chunk in chunks]
    documents = original_contents
    embeddings = result.embeddings
    metadatas = [chunk.to_metadata() for chunk in chunks]

    # Upsert to handle updates, with dimension mismatch recovery
    try:
        store._code_collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )
    except (RuntimeError, ValueError, TypeError) as e:
        # Handle dimension mismatch for empty collections
        if "dimension" in str(e).lower():
            logger.warning(f"Dimension mismatch on insert, recreating collection: {e}")
            store._recreate_collection(CODE_COLLECTION, actual_dims)
            store._code_collection.upsert(
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
    store: VectorStore,
    chunks: list[CodeChunk],
    batch_size: int = DEFAULT_EMBEDDING_BATCH_SIZE,
    progress_callback: Callable[[int, int], None] | None = None,
) -> int:
    """Add code chunks to the index in batches.

    This method processes chunks in smaller batches to prevent memory
    issues when indexing large codebases with thousands of files.

    Args:
        store: The VectorStore instance.
        chunks: List of code chunks to add.
        batch_size: Number of chunks to process per batch.
        progress_callback: Optional callback(processed, total) for progress.

    Returns:
        Number of chunks added.
    """
    store._ensure_initialized()

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

        # Generate embeddings using document envelope (includes metadata for better search)
        # But store original content for display/retrieval
        embedding_texts = [chunk.get_embedding_text() for chunk in batch]
        original_contents = [chunk.content for chunk in batch]
        result = store.embedding_provider.embed(embedding_texts)

        # Get actual dimensions
        actual_dims = result.dimensions
        if result.embeddings is not None and len(result.embeddings) > 0:
            actual_dims = len(result.embeddings[0])

        # Handle dimension mismatch (only check on first batch)
        if batch_start == 0:
            store._handle_dimension_mismatch(CODE_COLLECTION, actual_dims)

        # Prepare data for ChromaDB
        # Store original content as documents (for display), embeddings from enriched text
        ids = [chunk.id for chunk in batch]
        documents = original_contents
        embeddings = result.embeddings
        metadatas = [chunk.to_metadata() for chunk in batch]

        # Upsert batch with dimension mismatch recovery
        try:
            store._code_collection.upsert(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
            )
            total_added += len(batch)
        except (RuntimeError, ValueError, TypeError) as e:
            if "dimension" in str(e).lower():
                logger.warning(f"Dimension mismatch on batch insert, recreating collection: {e}")
                store._recreate_collection(CODE_COLLECTION, actual_dims)
                store._code_collection.upsert(
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


def delete_code_by_filepath(store: VectorStore, filepath: str) -> int:
    """Delete all code chunks for a file.

    Args:
        store: The VectorStore instance.
        filepath: File path to delete chunks for.

    Returns:
        Number of chunks deleted.
    """
    store._ensure_initialized()

    # Get IDs for this filepath
    results = store._code_collection.get(
        where={"filepath": filepath},
        include=[],
    )

    if not results["ids"]:
        return 0

    store._code_collection.delete(ids=results["ids"])
    return len(results["ids"])
