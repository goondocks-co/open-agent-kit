"""Search operations for vector store.

Functions for semantic search of code and memories.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.memory.store.core import VectorStore


def search_code(
    store: VectorStore,
    query: str,
    limit: int = 20,
) -> list[dict]:
    """Search code chunks.

    Args:
        store: The VectorStore instance.
        query: Search query.
        limit: Maximum results to return.

    Returns:
        List of search results with metadata.
    """
    store._ensure_initialized()

    query_embedding = store.embedding_provider.embed_query(query)

    results = store._code_collection.query(
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
    store: VectorStore,
    query: str,
    limit: int = 10,
    memory_types: list[str] | None = None,
    metadata_filters: dict | None = None,
) -> list[dict]:
    """Search memory observations.

    Args:
        store: The VectorStore instance.
        query: Search query.
        limit: Maximum results to return.
        memory_types: Filter by memory types.
        metadata_filters: Additional ChromaDB where-clause filters.

    Returns:
        List of search results.
    """
    store._ensure_initialized()

    query_embedding = store.embedding_provider.embed_query(query)

    # Build where filter
    where_clauses: list[dict] = []
    if memory_types:
        where_clauses.append({"memory_type": {"$in": memory_types}})
    if metadata_filters:
        where_clauses.append(metadata_filters)

    where: dict | None = None
    if len(where_clauses) == 1:
        where = where_clauses[0]
    elif len(where_clauses) > 1:
        where = {"$and": where_clauses}

    results = store._memory_collection.query(
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


def get_by_ids(store: VectorStore, ids: list[str], collection: str = "code") -> list[dict]:
    """Fetch full content by IDs.

    Args:
        store: The VectorStore instance.
        ids: List of IDs to fetch.
        collection: Which collection ('code' or 'memory').

    Returns:
        List of full documents.
    """
    store._ensure_initialized()

    coll = store._code_collection if collection == "code" else store._memory_collection

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
