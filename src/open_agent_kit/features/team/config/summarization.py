"""Summarization configuration for Team."""

import logging
import os
import re
from dataclasses import dataclass
from typing import Any

from open_agent_kit.features.team.constants import (
    DEFAULT_SUMMARIZATION_BASE_URL,
    DEFAULT_SUMMARIZATION_MODEL,
    DEFAULT_SUMMARIZATION_PROVIDER,
    DEFAULT_SUMMARIZATION_TIMEOUT,
    VALID_SUMMARIZATION_PROVIDERS,
)
from open_agent_kit.features.team.exceptions import (
    ValidationError,
)

logger = logging.getLogger(__name__)

# Default context tokens for summarization models when not explicitly configured
# Conservative default that works safely with most local models
DEFAULT_CONTEXT_TOKENS = 4096


@dataclass
class SummarizationConfig:
    """Configuration for LLM-based session summarization.

    Attributes:
        enabled: Whether to enable LLM summarization of sessions.
        provider: LLM provider (ollama, openai).
        model: Model name/identifier.
        base_url: Base URL for the LLM API.
        api_key: API key (supports ${ENV_VAR} syntax).
        timeout: Request timeout in seconds.
        context_tokens: Max context tokens (auto-detect from known models).
    """

    enabled: bool = True
    provider: str = DEFAULT_SUMMARIZATION_PROVIDER
    model: str = DEFAULT_SUMMARIZATION_MODEL
    base_url: str = DEFAULT_SUMMARIZATION_BASE_URL
    api_key: str | None = None
    timeout: float = DEFAULT_SUMMARIZATION_TIMEOUT
    context_tokens: int | None = None  # Auto-detect if None

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        self._validate()

    def _validate(self) -> None:
        """Validate configuration values.

        Raises:
            ValidationError: If any configuration value is invalid.
        """
        # Validate provider
        if self.provider not in VALID_SUMMARIZATION_PROVIDERS:
            raise ValidationError(
                f"Invalid summarization provider: {self.provider}",
                field="provider",
                value=self.provider,
                expected=f"one of {VALID_SUMMARIZATION_PROVIDERS}",
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

        # Validate timeout
        if self.timeout <= 0:
            raise ValidationError(
                "Timeout must be positive",
                field="timeout",
                value=self.timeout,
                expected="positive number",
            )

        # Warn about hardcoded API keys
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
        url_pattern = re.compile(
            r"^https?://" r"[a-zA-Z0-9.-]+" r"(:\d+)?" r"(/.*)?$",
            re.IGNORECASE,
        )
        return bool(url_pattern.match(url))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SummarizationConfig":
        """Create config from dictionary.

        Args:
            data: Configuration dictionary.

        Returns:
            SummarizationConfig instance.
        """
        # Resolve environment variables in api_key
        api_key = data.get("api_key")
        if api_key and api_key.startswith("${") and api_key.endswith("}"):
            env_var = api_key[2:-1]
            api_key = os.environ.get(env_var)

        return cls(
            enabled=data.get("enabled", True),
            provider=data.get("provider", DEFAULT_SUMMARIZATION_PROVIDER),
            model=data.get("model", DEFAULT_SUMMARIZATION_MODEL),
            base_url=data.get("base_url", DEFAULT_SUMMARIZATION_BASE_URL),
            api_key=api_key,
            timeout=data.get("timeout", DEFAULT_SUMMARIZATION_TIMEOUT),
            context_tokens=data.get("context_tokens"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "enabled": self.enabled,
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "api_key": self.api_key,
            "timeout": self.timeout,
            "context_tokens": self.context_tokens,
        }

    def get_context_tokens(self) -> int:
        """Get context tokens from config.

        The config file is the single source of truth. Set context_tokens
        in your .oak/config.yaml to optimize for your model's capabilities.

        Returns:
            Context token limit (from config, or conservative default).
        """
        return self.context_tokens or DEFAULT_CONTEXT_TOKENS
