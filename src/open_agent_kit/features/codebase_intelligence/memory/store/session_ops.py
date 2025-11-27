"""Session summary operations for vector store.

Functions for embedding and searching session summaries in ChromaDB.
Part of the user-driven session linking system.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from open_agent_kit.features.codebase_intelligence.memory.store.constants import (
    SESSION_SUMMARIES_COLLECTION,
)

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.memory.store.core import VectorStore

logger = logging.getLogger(__name__)


def add_session_summary(
    store: VectorStore,
    session_id: str,
    title: str,
    summary: str,
    agent: str,
    project_root: str,
    created_at_epoch: int,
) -> None:
    """Embed session summary to ChromaDB for similarity search.

    Called after generating a session summary to enable vector-based
    similarity search for parent session suggestions.

    Args:
        store: The VectorStore instance.
        session_id: Unique session identifier.
        title: Session title (can be empty string).
        summary: Session summary text.
        agent: Agent name (claude, cursor, etc.).
        project_root: Project root directory.
        created_at_epoch: Creation timestamp as Unix epoch.
    """
    store._ensure_initialized()

    # Create embedding text with semantic prefix (like Plans use "Plan:")
    # This helps the embedding model understand document type for better matching
    if title:
        embed_text = f"Session: {title}\n\n{summary}"
    else:
        embed_text = f"Session Summary:\n\n{summary}"

    if not embed_text or not embed_text.strip():
        logger.debug(f"Skipping session summary embedding for {session_id}: empty text")
        return

    # Generate embedding
    try:
        result = store.embedding_provider.embed([embed_text])
        if not result.embeddings or len(result.embeddings) == 0:
            logger.warning(f"No embedding generated for session {session_id}")
            return
        embedding = result.embeddings[0]
    except (OSError, ValueError, RuntimeError) as e:
        logger.error(f"Failed to embed session summary for {session_id}: {e}")
        return

    # Check for dimension mismatch
    store._handle_dimension_mismatch(SESSION_SUMMARIES_COLLECTION, len(embedding))

    # Upsert to collection (allows re-embedding on session update)
    store._session_summaries_collection.upsert(
        ids=[session_id],
        embeddings=[embedding],
        metadatas=[
            {
                "session_id": session_id,
                "agent": agent,
                "project_root": project_root,
                "created_at_epoch": created_at_epoch,
                "title": title[:200] if title else "",
            }
        ],
        documents=[embed_text[:2000]],  # Truncate for storage
    )
    logger.debug(f"Embedded session summary for {session_id}")


def find_similar_sessions(
    store: VectorStore,
    query_text: str,
    project_root: str,
    exclude_session_id: str | None = None,
    limit: int = 5,
    max_age_days: int = 7,
) -> list[tuple[str, float]]:
    """Find sessions with similar summaries using vector search.

    Args:
        store: The VectorStore instance.
        query_text: Text to search for (typically session summary/title).
        project_root: Filter to same project.
        exclude_session_id: Session to exclude from results.
        limit: Maximum number of results.
        max_age_days: Only include sessions created within this many days.

    Returns:
        List of (session_id, similarity_score) tuples, highest similarity first.
    """
    store._ensure_initialized()

    if not query_text or not query_text.strip():
        return []

    # Generate query embedding
    try:
        result = store.embedding_provider.embed([query_text])
        if not result.embeddings or len(result.embeddings) == 0:
            return []
        query_embedding = result.embeddings[0]
    except (OSError, ValueError, RuntimeError) as e:
        logger.error(f"Failed to embed query for similar sessions: {e}")
        return []

    # Build filter for project_root and age
    min_created_epoch = int(time.time()) - (max_age_days * 24 * 3600)
    where_filter: dict = {
        "$and": [
            {"project_root": {"$eq": project_root}},
            {"created_at_epoch": {"$gte": min_created_epoch}},
        ]
    }

    # Query the collection
    # Request more than limit to allow for filtering out excluded session
    fetch_limit = limit + 1 if exclude_session_id else limit

    try:
        results = store._session_summaries_collection.query(
            query_embeddings=[query_embedding],
            n_results=fetch_limit,
            where=where_filter,
            include=["metadatas", "distances"],
        )
    except (OSError, ValueError, RuntimeError, TypeError) as e:
        logger.error(f"Failed to query similar sessions: {e}")
        return []

    if not results or not results.get("ids") or len(results["ids"]) == 0:
        return []

    # Convert distances to similarities and filter
    similar_sessions: list[tuple[str, float]] = []
    ids = results["ids"][0]
    distances = results["distances"][0] if results.get("distances") else []

    for i, session_id in enumerate(ids):
        # Skip excluded session
        if exclude_session_id and session_id == exclude_session_id:
            continue

        # Convert distance to similarity (ChromaDB uses cosine distance)
        # distance = 1 - similarity for cosine, so similarity = 1 - distance
        distance = distances[i] if i < len(distances) else 1.0
        similarity = max(0.0, 1.0 - distance)

        similar_sessions.append((session_id, similarity))

        if len(similar_sessions) >= limit:
            break

    return similar_sessions


def search_session_summaries(
    store: VectorStore,
    query: str,
    limit: int = 10,
) -> list[dict]:
    """Search session summaries using vector similarity.

    Args:
        store: The VectorStore instance.
        query: Search query text.
        limit: Maximum number of results.

    Returns:
        List of matching session summaries with metadata and relevance scores.
    """
    store._ensure_initialized()

    if not query or not query.strip():
        return []

    # Generate query embedding
    try:
        result = store.embedding_provider.embed([query])
        if not result.embeddings or len(result.embeddings) == 0:
            return []
        query_embedding = result.embeddings[0]
    except (OSError, ValueError, RuntimeError) as e:
        logger.error(f"Failed to embed query for session search: {e}")
        return []

    # Query the collection
    try:
        results = store._session_summaries_collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
            include=["metadatas", "distances", "documents"],
        )
    except (OSError, ValueError, RuntimeError, TypeError) as e:
        logger.error(f"Failed to query session summaries: {e}")
        return []

    if not results or not results.get("ids") or len(results["ids"]) == 0:
        return []

    # Convert to result format
    search_results: list[dict] = []
    ids = results["ids"][0]
    distances = results["distances"][0] if results.get("distances") else []
    metadatas = results["metadatas"][0] if results.get("metadatas") else []
    documents = results["documents"][0] if results.get("documents") else []

    for i, session_id in enumerate(ids):
        # Convert distance to similarity (ChromaDB uses cosine distance)
        distance = distances[i] if i < len(distances) else 1.0
        similarity = max(0.0, 1.0 - distance)

        metadata = metadatas[i] if i < len(metadatas) else {}
        document = documents[i] if i < len(documents) else ""

        search_results.append(
            {
                "id": session_id,
                "relevance": similarity,
                "title": metadata.get("title", ""),
                "agent": metadata.get("agent", ""),
                "project_root": metadata.get("project_root", ""),
                "created_at_epoch": metadata.get("created_at_epoch", 0),
                "document": document,  # The embedded text (title + summary)
            }
        )

    return search_results


def delete_session_summary(store: VectorStore, session_id: str) -> bool:
    """Delete a session summary from the vector store.

    Args:
        store: The VectorStore instance.
        session_id: Session to delete.

    Returns:
        True if deleted, False if not found.
    """
    store._ensure_initialized()

    try:
        store._session_summaries_collection.delete(ids=[session_id])
        return True
    except (OSError, ValueError, RuntimeError) as e:
        logger.warning(f"Failed to delete session summary {session_id}: {e}")
        return False


def clear_session_summaries(store: VectorStore) -> int:
    """Clear all session summaries from the vector store.

    Args:
        store: The VectorStore instance.

    Returns:
        Number of summaries deleted.
    """
    store._ensure_initialized()

    try:
        count: int = store._session_summaries_collection.count()
        if count > 0:
            # Get all IDs and delete
            all_data = store._session_summaries_collection.get()
            if all_data and all_data.get("ids"):
                store._session_summaries_collection.delete(ids=all_data["ids"])
        logger.info(f"Cleared {count} session summaries from ChromaDB")
        return count
    except (OSError, ValueError, RuntimeError) as e:
        logger.error(f"Failed to clear session summaries: {e}")
        return 0


def count_session_summaries(store: VectorStore) -> int:
    """Count session summaries in the vector store.

    Args:
        store: The VectorStore instance.

    Returns:
        Number of session summaries.
    """
    store._ensure_initialized()
    try:
        count: int = store._session_summaries_collection.count()
        return count
    except (OSError, ValueError, RuntimeError):
        return 0
