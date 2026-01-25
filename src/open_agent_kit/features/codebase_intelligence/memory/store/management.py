"""Management operations for vector store.

Functions for stats, listing, archiving, and cleanup.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from open_agent_kit.features.codebase_intelligence.memory.store.constants import (
    CODE_COLLECTION,
    MEMORY_COLLECTION,
)

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.memory.store.core import VectorStore

logger = logging.getLogger(__name__)


def archive_memory(store: VectorStore, memory_id: str, archived: bool = True) -> bool:
    """Archive or unarchive a memory.

    Args:
        store: The VectorStore instance.
        memory_id: ID of the memory to archive/unarchive.
        archived: True to archive, False to unarchive.

    Returns:
        True if the memory was found and updated.
    """
    store._ensure_initialized()

    try:
        # Get current metadata
        result = store._memory_collection.get(ids=[memory_id], include=["metadatas"])
        if not result["ids"]:
            return False

        # Update metadata with archived flag
        metadata = result["metadatas"][0] if result["metadatas"] else {}
        metadata["archived"] = archived

        store._memory_collection.update(ids=[memory_id], metadatas=[metadata])
        return True
    except Exception as e:
        logger.error(f"Failed to archive memory {memory_id}: {e}")
        return False


def list_memories(
    store: VectorStore,
    limit: int = 50,
    offset: int = 0,
    memory_types: list[str] | None = None,
    exclude_types: list[str] | None = None,
    tag: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    include_archived: bool = False,
) -> tuple[list[dict], int]:
    """List memories with pagination and optional filtering.

    Args:
        store: The VectorStore instance.
        limit: Maximum number of memories to return.
        offset: Number of memories to skip.
        memory_types: Only include these memory types.
        exclude_types: Exclude these memory types.
        tag: Filter to memories containing this tag.
        start_date: Filter to memories created on or after this date (ISO format).
        end_date: Filter to memories created on or before this date (ISO format).
        include_archived: If True, include archived memories. Default False.

    Returns:
        Tuple of (memories list, total count).
    """
    store._ensure_initialized()

    # Build where filter
    where = None
    if memory_types:
        where = {"memory_type": {"$in": memory_types}}
    elif exclude_types:
        where = {"memory_type": {"$nin": exclude_types}}

    # Get total count for pagination
    if where:
        count_results = store._memory_collection.get(
            where=where,
            include=[],
        )
        total_count = len(count_results["ids"]) if count_results["ids"] else 0
    else:
        total_count = store._memory_collection.count()

    # Fetch paginated results
    # ChromaDB get() doesn't support offset/limit with where, so we fetch all matching
    # and slice. For large collections, this could be optimized with a different approach.
    results = store._memory_collection.get(
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

    # Apply tag filter if specified (post-filter since tags are comma-separated)
    if tag:
        filtered_indices = []
        for i in sorted_indices:
            tags_str = results["metadatas"][i].get("tags", "") if results["metadatas"] else ""
            tags_list = [t.strip() for t in tags_str.split(",") if t.strip()]
            if tag in tags_list:
                filtered_indices.append(i)
        sorted_indices = filtered_indices
        total_count = len(sorted_indices)

    # Apply date range filter if specified (ISO string comparison works for dates)
    if start_date or end_date:
        filtered_indices = []
        for i in sorted_indices:
            created_at = (
                results["metadatas"][i].get("created_at", "") if results["metadatas"] else ""
            )
            if start_date and created_at < start_date:
                continue
            if end_date and created_at > end_date + "T23:59:59":  # Include full end date
                continue
            filtered_indices.append(i)
        sorted_indices = filtered_indices
        total_count = len(sorted_indices)

    # Filter out archived memories unless explicitly requested
    if not include_archived:
        filtered_indices = []
        for i in sorted_indices:
            archived = (
                results["metadatas"][i].get("archived", False) if results["metadatas"] else False
            )
            if not archived:
                filtered_indices.append(i)
        sorted_indices = filtered_indices
        total_count = len(sorted_indices)

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


def bulk_archive_memories(store: VectorStore, memory_ids: list[str], archived: bool = True) -> int:
    """Archive or unarchive multiple memories.

    Args:
        store: The VectorStore instance.
        memory_ids: List of memory IDs to archive/unarchive.
        archived: True to archive, False to unarchive.

    Returns:
        Number of memories updated.
    """
    store._ensure_initialized()
    count = 0

    for memory_id in memory_ids:
        if archive_memory(store, memory_id, archived):
            count += 1

    return count


def add_tag_to_memories(store: VectorStore, memory_ids: list[str], tag: str) -> int:
    """Add a tag to multiple memories.

    Args:
        store: The VectorStore instance.
        memory_ids: List of memory IDs to update.
        tag: Tag to add.

    Returns:
        Number of memories updated.
    """
    store._ensure_initialized()
    count = 0

    try:
        for memory_id in memory_ids:
            result = store._memory_collection.get(ids=[memory_id], include=["metadatas"])
            if not result["ids"]:
                continue

            metadata = result["metadatas"][0] if result["metadatas"] else {}
            tags_str = metadata.get("tags", "")
            tags_list = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []

            if tag not in tags_list:
                tags_list.append(tag)
                metadata["tags"] = ",".join(tags_list)
                store._memory_collection.update(ids=[memory_id], metadatas=[metadata])
                count += 1
    except Exception as e:
        logger.error(f"Failed to add tag to memories: {e}")

    return count


def remove_tag_from_memories(store: VectorStore, memory_ids: list[str], tag: str) -> int:
    """Remove a tag from multiple memories.

    Args:
        store: The VectorStore instance.
        memory_ids: List of memory IDs to update.
        tag: Tag to remove.

    Returns:
        Number of memories updated.
    """
    store._ensure_initialized()
    count = 0

    try:
        for memory_id in memory_ids:
            result = store._memory_collection.get(ids=[memory_id], include=["metadatas"])
            if not result["ids"]:
                continue

            metadata = result["metadatas"][0] if result["metadatas"] else {}
            tags_str = metadata.get("tags", "")
            tags_list = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []

            if tag in tags_list:
                tags_list.remove(tag)
                metadata["tags"] = ",".join(tags_list)
                store._memory_collection.update(ids=[memory_id], metadatas=[metadata])
                count += 1
    except Exception as e:
        logger.error(f"Failed to remove tag from memories: {e}")

    return count


def count_unique_files(store: VectorStore) -> int:
    """Count unique files in the code index.

    Args:
        store: The VectorStore instance.

    Returns:
        Number of unique files indexed.
    """
    store._ensure_initialized()

    try:
        # ChromaDB doesn't have a distinct count query, so we fetch metadata
        # For large datasets, this might be slow, but it's accurate
        results = store._code_collection.get(include=["metadatas"])
        if not results or not results["metadatas"]:
            return 0

        unique_files = {m.get("filepath") for m in results["metadatas"] if m.get("filepath")}
        return len(unique_files)
    except (OSError, RuntimeError, AttributeError) as e:
        logger.exception(f"Failed to count unique files: {e}")
        return 0


def get_stats(store: VectorStore) -> dict:
    """Get collection statistics.

    Args:
        store: The VectorStore instance.

    Returns:
        Dictionary with statistics.
    """
    store._ensure_initialized()

    # Handle race condition where collection may be deleted during reindex
    try:
        code_count = store._code_collection.count() if store._code_collection else 0
    except Exception:
        code_count = 0

    try:
        memory_count = store._memory_collection.count() if store._memory_collection else 0
    except Exception:
        memory_count = 0

    return {
        "code_chunks": code_count,
        "memory_observations": memory_count,
        "persist_directory": str(store.persist_directory),
    }


def count_memories(store: VectorStore) -> int:
    """Count total memory observations in ChromaDB.

    Args:
        store: The VectorStore instance.

    Returns:
        Number of memory observations.
    """
    store._ensure_initialized()
    return store._memory_collection.count() if store._memory_collection else 0


def clear_code_index(store: VectorStore) -> None:
    """Clear only the code index, preserving memories.

    Use this for rebuilds/reindexing - memories should persist across
    code index rebuilds since they represent user-captured observations.

    Args:
        store: The VectorStore instance.
    """
    store._ensure_initialized()

    # Delete and recreate only the code collection
    store._client.delete_collection(CODE_COLLECTION)

    hnsw_config = {
        "hnsw:space": "cosine",
        "hnsw:construction_ef": 200,
        "hnsw:M": 16,
    }

    store._code_collection = store._client.create_collection(
        name=CODE_COLLECTION,
        metadata=hnsw_config,
    )

    logger.info("Cleared code index (memories preserved)")


def clear_all(store: VectorStore) -> None:
    """Clear all data from both collections.

    WARNING: This also clears memories! Use clear_code_index() for rebuilds.

    Args:
        store: The VectorStore instance.
    """
    store._ensure_initialized()

    # Delete and recreate collections
    store._client.delete_collection(CODE_COLLECTION)
    store._client.delete_collection(MEMORY_COLLECTION)

    # Recreate
    hnsw_config = {
        "hnsw:space": "cosine",
        "hnsw:construction_ef": 200,
        "hnsw:M": 16,
    }

    store._code_collection = store._client.create_collection(
        name=CODE_COLLECTION,
        metadata=hnsw_config,
    )

    store._memory_collection = store._client.create_collection(
        name=MEMORY_COLLECTION,
        metadata=hnsw_config,
    )

    logger.info("Cleared all vector store data (including memories)")
