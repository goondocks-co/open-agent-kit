"""Constants for vector store.

Collection names and other shared constants.
"""

from typing import Final

# Collection names
CODE_COLLECTION = "oak_code"
MEMORY_COLLECTION = "oak_memory"
SESSION_SUMMARIES_COLLECTION = "oak_session_summaries"

# HNSW index configuration for ChromaDB collections
HNSW_SPACE: Final[str] = "cosine"
HNSW_CONSTRUCTION_EF: Final[int] = 200
HNSW_M: Final[int] = 16


def default_hnsw_config() -> dict[str, str | int]:
    """Return the standard HNSW metadata config for ChromaDB collections."""
    return {
        "hnsw:space": HNSW_SPACE,
        "hnsw:construction_ef": HNSW_CONSTRUCTION_EF,
        "hnsw:M": HNSW_M,
    }
