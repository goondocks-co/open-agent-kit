"""Embedding and summarization provider constants."""

from typing import Final

# =============================================================================
# Embedding Providers
# =============================================================================

PROVIDER_OLLAMA: Final[str] = "ollama"
PROVIDER_OPENAI: Final[str] = "openai"
PROVIDER_LMSTUDIO: Final[str] = "lmstudio"
VALID_PROVIDERS: Final[tuple[str, ...]] = (
    PROVIDER_OLLAMA,
    PROVIDER_OPENAI,
    PROVIDER_LMSTUDIO,
)

# Default embedding configuration
# Model must be selected by user after connecting to provider
DEFAULT_PROVIDER: Final[str] = PROVIDER_OLLAMA
DEFAULT_MODEL: Final[str] = ""  # Empty - user must select from discovered models
DEFAULT_BASE_URL: Final[str] = "http://localhost:11434"
DEFAULT_TEST_EMBEDDING_MODEL: Final[str] = "nomic-embed-text"

# =============================================================================
# Index Status
# =============================================================================

INDEX_STATUS_IDLE: Final[str] = "idle"
INDEX_STATUS_INDEXING: Final[str] = "indexing"
INDEX_STATUS_READY: Final[str] = "ready"
INDEX_STATUS_ERROR: Final[str] = "error"
INDEX_STATUS_UPDATING: Final[str] = "updating"

# =============================================================================
# Summarization Providers
# =============================================================================

SUMMARIZATION_PROVIDER_OLLAMA: Final[str] = "ollama"
SUMMARIZATION_PROVIDER_OPENAI: Final[str] = "openai"
SUMMARIZATION_PROVIDER_LMSTUDIO: Final[str] = "lmstudio"
VALID_SUMMARIZATION_PROVIDERS: Final[tuple[str, ...]] = (
    SUMMARIZATION_PROVIDER_OLLAMA,
    SUMMARIZATION_PROVIDER_OPENAI,
    SUMMARIZATION_PROVIDER_LMSTUDIO,
)

# Default summarization configuration
# Model must be selected by user after connecting to provider
DEFAULT_SUMMARIZATION_PROVIDER: Final[str] = SUMMARIZATION_PROVIDER_OLLAMA
DEFAULT_SUMMARIZATION_MODEL: Final[str] = ""  # Empty - user must select from discovered models
DEFAULT_SUMMARIZATION_BASE_URL: Final[str] = "http://localhost:11434"
DEFAULT_TEST_SUMMARIZATION_MODEL: Final[str] = "qwen2.5:3b"
# Timeout for LLM inference (180s to accommodate local model loading + inference)
# Local Ollama can take 30-60s to load a model on first request, plus inference time
DEFAULT_SUMMARIZATION_TIMEOUT: Final[float] = 180.0
# Extended timeout for first LLM request when model may need loading (warmup)
WARMUP_TIMEOUT_MULTIPLIER: Final[float] = 2.0
