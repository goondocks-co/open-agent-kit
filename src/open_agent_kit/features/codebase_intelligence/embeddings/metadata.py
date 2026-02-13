"""Shared embedding model metadata.

Centralized registry of known embedding models, their dimensions,
context windows, and name patterns. Used by provider implementations
and daemon config routes to provide consistent model information.
"""

from open_agent_kit.features.codebase_intelligence.constants import DEFAULT_BASE_URL

# Default provider URLs
DEFAULT_PROVIDER_URLS: dict[str, str] = {
    "ollama": DEFAULT_BASE_URL,
    "lmstudio": "http://localhost:1234",
    "openai": "https://api.openai.com",
}

# Known embedding model metadata: dimensions and context window (tokens)
# Used by model discovery, test endpoints, and provider implementations
# to provide accurate metadata without probing the model.
KNOWN_EMBEDDING_MODELS: dict[str, dict[str, int]] = {
    # Nomic models
    "nomic-embed-text": {"dimensions": 768, "context_window": 8192},
    "nomic-embed-code": {"dimensions": 768, "context_window": 8192},
    # BGE family (BAAI General Embedding)
    "bge-small": {"dimensions": 384, "context_window": 512},
    "bge-base": {"dimensions": 768, "context_window": 512},
    "bge-large": {"dimensions": 1024, "context_window": 512},
    "bge-m3": {"dimensions": 1024, "context_window": 8192},
    # Full BAAI model names (used by OpenAI-compatible APIs)
    "BAAI/bge-small-en-v1.5": {"dimensions": 384, "context_window": 512},
    "BAAI/bge-base-en-v1.5": {"dimensions": 768, "context_window": 512},
    "BAAI/bge-large-en-v1.5": {"dimensions": 1024, "context_window": 512},
    # GTE family (General Text Embedding)
    "gte-small": {"dimensions": 384, "context_window": 512},
    "gte-base": {"dimensions": 768, "context_window": 512},
    "gte-large": {"dimensions": 1024, "context_window": 512},
    "gte-qwen": {"dimensions": 1536, "context_window": 8192},
    # E5 family (Microsoft)
    "e5-small": {"dimensions": 384, "context_window": 512},
    "e5-base": {"dimensions": 768, "context_window": 512},
    "e5-large": {"dimensions": 1024, "context_window": 512},
    # Other common models
    "mxbai-embed-large": {"dimensions": 1024, "context_window": 512},
    "all-minilm": {"dimensions": 384, "context_window": 256},
    "snowflake-arctic-embed": {"dimensions": 1024, "context_window": 512},
    # OpenAI models
    "text-embedding-3-small": {"dimensions": 1536, "context_window": 8191},
    "text-embedding-3-large": {"dimensions": 3072, "context_window": 8191},
    "text-embedding-ada-002": {"dimensions": 1536, "context_window": 8191},
    # LM Studio prefixed variants (maps to same underlying models)
    "text-embedding-nomic-embed-text-v1.5": {"dimensions": 768, "context_window": 8192},
    "text-embedding-nomic-embed-code": {"dimensions": 768, "context_window": 8192},
    "text-embedding-bge-m3": {"dimensions": 1024, "context_window": 8192},
    "text-embedding-gte-qwen2": {"dimensions": 1536, "context_window": 8192},
}

# Patterns that indicate a model is an embedding model (case-insensitive)
# Used to filter embedding models from general model lists
EMBEDDING_MODEL_PATTERNS: list[str] = [
    "embed",  # nomic-embed-text, mxbai-embed-large, etc.
    "embedding",  # text-embedding-3-small, etc.
    "bge-",  # bge-m3, bge-small, bge-large (BAAI General Embedding)
    "bge:",  # bge:latest
    "gte-",  # gte-qwen (General Text Embedding)
    "e5-",  # e5-large, e5-small (Microsoft)
    "snowflake-arctic-embed",  # Snowflake embedding
    "paraphrase",  # paraphrase-multilingual
    "nomic-embed",  # Explicit nomic embedding
    "arctic-embed",  # Arctic embedding
    "mxbai-embed",  # mxbai embedding
]

# Default dimension when model is unknown
DEFAULT_EMBEDDING_DIMENSIONS = 768


def get_known_model_metadata(model_name: str) -> dict[str, int | None]:
    """Look up known model metadata by name (case-insensitive partial match).

    Args:
        model_name: Model name to look up.

    Returns:
        Dict with 'dimensions' and 'context_window' keys
        (values may be None if model is unknown).
    """
    model_lower = model_name.lower()
    for known_name, metadata in KNOWN_EMBEDDING_MODELS.items():
        if known_name in model_lower or model_lower in known_name:
            return {
                "dimensions": metadata.get("dimensions"),
                "context_window": metadata.get("context_window"),
            }
    return {"dimensions": None, "context_window": None}


def get_known_dimensions(model_name: str) -> int:
    """Look up known dimensions for a model, falling back to default.

    Checks exact match first, then partial match via get_known_model_metadata.

    Args:
        model_name: Model name to look up.

    Returns:
        Embedding dimensions (int).
    """
    # Exact match
    if model_name in KNOWN_EMBEDDING_MODELS:
        return KNOWN_EMBEDDING_MODELS[model_name]["dimensions"]

    # Partial match
    metadata = get_known_model_metadata(model_name)
    if metadata["dimensions"] is not None:
        return metadata["dimensions"]

    return DEFAULT_EMBEDDING_DIMENSIONS
