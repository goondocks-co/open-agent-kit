"""Embedding configuration for Codebase Intelligence."""

import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Literal

from open_agent_kit.features.codebase_intelligence.constants import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
    VALID_PROVIDERS,
)
from open_agent_kit.features.codebase_intelligence.exceptions import (
    ValidationError,
)

logger = logging.getLogger(__name__)

# Type alias for valid providers
ProviderType = Literal["ollama", "openai", "lmstudio"]

# Default embedding configuration
# Model must be selected by user from discovered models
DEFAULT_EMBEDDING_CONFIG = {
    "provider": DEFAULT_PROVIDER,
    "model": DEFAULT_MODEL,  # Empty - user must select
    "base_url": DEFAULT_BASE_URL,
    "dimensions": None,  # Auto-detect
    "api_key": None,
}

# =============================================================================
# Default fallback values for embedding configuration
# These are used when discovery fails and no explicit config is set
# =============================================================================
DEFAULT_EMBEDDING_CONTEXT_TOKENS = 8192  # Conservative default for most models


@dataclass
class EmbeddingConfig:
    """Configuration for embedding provider.

    Attributes:
        provider: Embedding provider (ollama, openai, fastembed).
        model: Model name/identifier.
        base_url: Base URL for the embedding API.
        dimensions: Embedding dimensions (auto-detected if None).
        api_key: API key (supports ${ENV_VAR} syntax).
        fallback_enabled: Reserved for future use (currently ignored).
        context_tokens: Max input tokens (auto-detect from known models).
        max_chunk_chars: Max chars per chunk (auto-detect from model).
    """

    provider: str = DEFAULT_PROVIDER
    model: str = DEFAULT_MODEL
    base_url: str = DEFAULT_BASE_URL
    dimensions: int | None = None
    api_key: str | None = None
    fallback_enabled: bool = False
    context_tokens: int | None = None
    max_chunk_chars: int | None = None

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        self._validate()

    def _validate(self) -> None:
        """Validate configuration values.

        Raises:
            ValidationError: If any configuration value is invalid.
        """
        # Validate provider
        if self.provider not in VALID_PROVIDERS:
            raise ValidationError(
                f"Invalid embedding provider: {self.provider}",
                field="provider",
                value=self.provider,
                expected=f"one of {VALID_PROVIDERS}",
            )

        # Model can be empty (not configured) but if provided must be non-whitespace
        if self.model and not self.model.strip():
            raise ValidationError(
                "Model name cannot be only whitespace",
                field="model",
                value=self.model,
                expected="non-empty string or empty",
            )

        # Validate base_url
        if not self._is_valid_url(self.base_url):
            raise ValidationError(
                f"Invalid base URL: {self.base_url}",
                field="base_url",
                value=self.base_url,
                expected="valid HTTP(S) URL",
            )

        # Validate dimensions if provided
        if self.dimensions is not None and self.dimensions <= 0:
            raise ValidationError(
                "Dimensions must be positive",
                field="dimensions",
                value=self.dimensions,
                expected="positive integer",
            )

        # Warn about hardcoded API keys (but don't fail)
        if self.api_key and not self.api_key.startswith("${"):
            logger.warning(
                "API key appears to be hardcoded in config. "
                "For security, use ${ENV_VAR_NAME} syntax instead."
            )

    @staticmethod
    def _is_valid_url(url: str) -> bool:
        """Check if URL is valid HTTP(S) URL."""
        if not url:
            return False
        # Simple URL validation
        url_pattern = re.compile(
            r"^https?://"  # http:// or https://
            r"[a-zA-Z0-9.-]+"  # domain
            r"(:\d+)?"  # optional port
            r"(/.*)?$",  # optional path
            re.IGNORECASE,
        )
        return bool(url_pattern.match(url))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EmbeddingConfig":
        """Create config from dictionary.

        Args:
            data: Configuration dictionary.

        Returns:
            EmbeddingConfig instance.

        Raises:
            ValidationError: If configuration values are invalid.
        """
        # Resolve environment variables in api_key
        api_key = data.get("api_key")
        if api_key and api_key.startswith("${") and api_key.endswith("}"):
            env_var = api_key[2:-1]
            api_key = os.environ.get(env_var)

        return cls(
            provider=data.get("provider", DEFAULT_PROVIDER),
            model=data.get("model", DEFAULT_MODEL),
            base_url=data.get("base_url", DEFAULT_BASE_URL),
            dimensions=data.get("dimensions"),
            api_key=api_key,
            fallback_enabled=data.get("fallback_enabled", False),
            context_tokens=data.get("context_tokens"),
            max_chunk_chars=data.get("max_chunk_chars"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "dimensions": self.dimensions,
            "api_key": self.api_key,
            "fallback_enabled": self.fallback_enabled,
            "context_tokens": self.context_tokens,
            "max_chunk_chars": self.max_chunk_chars,
        }

    def get_context_tokens(self) -> int:
        """Get context tokens from config or use default.

        Use the Discover button in the UI or CLI to populate this from the API.
        """
        return self.context_tokens or DEFAULT_EMBEDDING_CONTEXT_TOKENS

    def get_max_chunk_chars(self) -> int:
        """Get max chunk chars, auto-scaling with context tokens if not explicitly set.

        Priority:
        1. Explicitly set max_chunk_chars
        2. Auto-calculated from context_tokens (0.75 chars per token)
        3. Default fallback
        """
        if self.max_chunk_chars:
            return self.max_chunk_chars

        # Auto-scale based on context tokens
        # Use 0.75 chars per token - conservative for code which tokenizes aggressively
        # (BERT tokenizers often produce 1 token per 1-2 chars for code)
        context = self.get_context_tokens()
        return int(context * 0.75)

    def get_dimensions(self) -> int | None:
        """Get dimensions from config.

        Dimensions are auto-detected on first embedding test if not set.
        """
        return self.dimensions
