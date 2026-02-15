"""Memory and plan operations for vector store.

Functions for adding and removing memories and plans from ChromaDB.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from open_agent_kit.features.codebase_intelligence.memory.store.constants import MEMORY_COLLECTION
from open_agent_kit.features.codebase_intelligence.memory.store.models import (
    MemoryObservation,
    PlanObservation,
)

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.memory.store.core import VectorStore

logger = logging.getLogger(__name__)


def add_memory(store: VectorStore, observation: MemoryObservation) -> str:
    """Add a memory observation.

    Args:
        store: The VectorStore instance.
        observation: The observation to store.

    Returns:
        The observation ID.
    """
    store._ensure_initialized()

    # Generate embedding
    embedding_text = observation.get_embedding_text()
    result = store.embedding_provider.embed([embedding_text])

    # Get actual dimensions
    actual_dims = result.dimensions
    if result.embeddings is not None and len(result.embeddings) > 0:
        actual_dims = len(result.embeddings[0])

    # Check for dimension mismatch
    store._handle_dimension_mismatch(MEMORY_COLLECTION, actual_dims)

    # Upsert with dimension mismatch recovery
    try:
        store._memory_collection.upsert(
            ids=[observation.id],
            documents=[observation.observation],
            embeddings=result.embeddings,
            metadatas=[observation.to_metadata()],
        )
    except (RuntimeError, ValueError, TypeError) as e:
        if "dimension" in str(e).lower():
            logger.warning(f"Dimension mismatch on memory insert, recreating: {e}")
            store._recreate_collection(MEMORY_COLLECTION, actual_dims)
            store._memory_collection.upsert(
                ids=[observation.id],
                documents=[observation.observation],
                embeddings=result.embeddings,
                metadatas=[observation.to_metadata()],
            )
        else:
            raise

    logger.info(f"Added memory observation: {observation.id}")
    return observation.id


def add_plan(store: VectorStore, plan: PlanObservation) -> str:
    """Add a plan to the memory collection for semantic search.

    Plans are embedded as full text (already LLM-generated) and stored
    with memory_type='plan' to distinguish from other memories.
    This enables semantic search of plans alongside code and memories.

    Args:
        store: The VectorStore instance.
        plan: The plan observation to store.

    Returns:
        The plan ID.
    """
    store._ensure_initialized()

    # Generate embedding from enriched text
    embedding_text = plan.get_embedding_text()
    result = store.embedding_provider.embed([embedding_text])

    # Get actual dimensions
    actual_dims = result.dimensions
    if result.embeddings is not None and len(result.embeddings) > 0:
        actual_dims = len(result.embeddings[0])

    # Check for dimension mismatch
    store._handle_dimension_mismatch(MEMORY_COLLECTION, actual_dims)

    # Upsert with dimension mismatch recovery
    try:
        store._memory_collection.upsert(
            ids=[plan.id],
            documents=[plan.content],
            embeddings=result.embeddings,
            metadatas=[plan.to_metadata()],
        )
    except (RuntimeError, ValueError, TypeError) as e:
        if "dimension" in str(e).lower():
            logger.warning(f"Dimension mismatch on plan insert, recreating: {e}")
            store._recreate_collection(MEMORY_COLLECTION, actual_dims)
            store._memory_collection.upsert(
                ids=[plan.id],
                documents=[plan.content],
                embeddings=result.embeddings,
                metadatas=[plan.to_metadata()],
            )
        else:
            raise

    logger.info(f"Added plan to memory index: {plan.id} ({plan.title})")
    return plan.id


"""Maximum retry attempts for ChromaDB delete operations."""
CHROMADB_DELETE_MAX_RETRIES = 3

"""Backoff delay in seconds between ChromaDB delete retries."""
CHROMADB_DELETE_RETRY_DELAY = 0.5


def delete_memories(store: VectorStore, observation_ids: list[str]) -> int:
    """Delete memories from ChromaDB by their observation IDs.

    Retries on transient errors to prevent orphaned entries when SQLite
    deletes succeed but ChromaDB deletes fail.

    Args:
        store: The VectorStore instance.
        observation_ids: List of observation IDs to delete.

    Returns:
        Number of memories deleted.
    """
    if not observation_ids:
        return 0

    store._ensure_initialized()

    # Filter to only IDs that exist in the collection
    existing = store._memory_collection.get(
        ids=observation_ids,
        include=[],
    )

    existing_ids = existing["ids"] if existing["ids"] else []
    if not existing_ids:
        return 0

    last_error: Exception | None = None
    for attempt in range(CHROMADB_DELETE_MAX_RETRIES):
        try:
            store._memory_collection.delete(ids=existing_ids)
            logger.info(f"Deleted {len(existing_ids)} memories from ChromaDB")
            return len(existing_ids)
        except (RuntimeError, OSError) as e:
            last_error = e
            if attempt < CHROMADB_DELETE_MAX_RETRIES - 1:
                logger.warning(
                    f"ChromaDB delete attempt {attempt + 1} failed, "
                    f"retrying in {CHROMADB_DELETE_RETRY_DELAY}s: {e}"
                )
                time.sleep(CHROMADB_DELETE_RETRY_DELAY)

    logger.error(
        f"ChromaDB delete failed after {CHROMADB_DELETE_MAX_RETRIES} attempts "
        f"({len(existing_ids)} orphaned entries may remain): {last_error}"
    )
    raise last_error  # type: ignore[misc]
