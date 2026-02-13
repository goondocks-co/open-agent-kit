"""Embedding provider chain for embedding operations."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from open_agent_kit.features.codebase_intelligence.constants import DEFAULT_BASE_URL
from open_agent_kit.features.codebase_intelligence.embeddings.base import (
    EmbeddingError,
    EmbeddingProvider,
    EmbeddingResult,
)
from open_agent_kit.features.codebase_intelligence.embeddings.ollama import (
    OllamaProvider,
)

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.config import EmbeddingConfig

logger = logging.getLogger(__name__)


def create_provider_from_config(config: EmbeddingConfig) -> EmbeddingProvider:
    """Create an embedding provider from configuration.

    Args:
        config: Embedding configuration.

    Returns:
        Configured embedding provider.

    Raises:
        ValueError: If provider type is not supported.
    """
    provider_type = config.provider.lower()

    if provider_type == "ollama":
        return OllamaProvider(
            model=config.model,
            base_url=config.base_url,
            max_chars=config.get_max_chunk_chars(),
            dimensions=config.dimensions,
        )
    elif provider_type == "openai":
        from open_agent_kit.features.codebase_intelligence.embeddings.openai_compat import (
            OpenAICompatProvider,
        )

        return OpenAICompatProvider(
            model=config.model,
            base_url=config.base_url,
            api_key=config.api_key,
            dimensions=config.dimensions,
        )
    elif provider_type == "lmstudio":
        from open_agent_kit.features.codebase_intelligence.embeddings.lmstudio import (
            LMStudioProvider,
        )

        return LMStudioProvider(
            model=config.model,
            base_url=config.base_url,
            dimensions=config.dimensions,
        )
    else:
        raise ValueError(f"Unknown embedding provider type: {provider_type}")


class EmbeddingProviderChain(EmbeddingProvider):
    """Chain of embedding providers.

    Manages a list of providers and uses the first available one.
    By default, uses Ollama for local inference with GPU acceleration.

    The chain tries each provider in order for each request, ensuring
    we use the best available provider for each embedding request.
    """

    def __init__(
        self,
        providers: list[EmbeddingProvider] | None = None,
        ollama_model: str = "nomic-embed-text",
        ollama_url: str = DEFAULT_BASE_URL,
    ):
        """Initialize provider chain.

        Args:
            providers: Custom list of providers. If None, creates default with Ollama.
            ollama_model: Ollama model to use if using default chain.
            ollama_url: Ollama base URL if using default chain.
        """
        if providers is not None:
            self._providers = providers
        else:
            self._providers = [
                OllamaProvider(model=ollama_model, base_url=ollama_url),
            ]

        self._active_provider: EmbeddingProvider | None = None
        self._tried_providers: set[str] = set()
        # Track usage statistics per provider
        self._usage_stats: dict[str, dict[str, int]] = {}

    @property
    def name(self) -> str:
        """Name of the currently active provider."""
        if self._active_provider:
            return self._active_provider.name
        return "chain:none"

    @property
    def dimensions(self) -> int:
        """Dimensions of the primary (configured) provider.

        Returns the dimensions from the configured provider, regardless of
        whether it's currently available. This ensures consistent dimensions
        across daemon restarts, avoiding race conditions where a slow-starting
        provider (like Ollama) could cause dimension mismatches.

        Configuration is the source of truth, not runtime availability.
        """
        if self._active_provider:
            return self._active_provider.dimensions
        # Return primary provider's dimensions (first in chain)
        # This is the configured provider - use its dimensions regardless of availability
        if self._providers:
            return self._providers[0].dimensions
        # Fallback only if no providers configured at all
        return 768

    @property
    def is_available(self) -> bool:
        """Check if any provider is available."""
        return any(p.is_available for p in self._providers)

    @property
    def active_provider(self) -> EmbeddingProvider | None:
        """Get the currently active provider."""
        return self._active_provider

    def _select_provider(self) -> EmbeddingProvider:
        """Select the first available provider.

        Returns:
            An available embedding provider.

        Raises:
            EmbeddingError: If no providers are available.
        """
        for provider in self._providers:
            if provider.name in self._tried_providers:
                continue

            if provider.is_available:
                logger.info(f"Selected embedding provider: {provider.name}")
                return provider
            else:
                logger.debug(f"Provider {provider.name} is not available")
                self._tried_providers.add(provider.name)

        raise EmbeddingError(
            "No embedding providers available. Please ensure Ollama is installed "
            "and running, or configure an alternative provider (LM Studio, OpenAI).",
            provider="chain",
        )

    def _track_usage(self, provider_name: str, success: bool) -> None:
        """Track usage statistics for a provider."""
        if provider_name not in self._usage_stats:
            self._usage_stats[provider_name] = {"success": 0, "failure": 0}
        if success:
            self._usage_stats[provider_name]["success"] += 1
        else:
            self._usage_stats[provider_name]["failure"] += 1

    def embed(self, texts: list[str]) -> EmbeddingResult:
        """Generate embeddings using providers in order.

        Tries each provider in order for each request, tracking success/failure
        statistics. Only falls back to providers with matching dimensions to
        prevent dimension mismatch errors in the vector store.

        Args:
            texts: List of texts to embed.

        Returns:
            EmbeddingResult from the successful provider.

        Raises:
            EmbeddingError: If all providers fail.
        """
        last_error: EmbeddingError | None = None
        primary_dimensions: int | None = None

        # Try each provider in order
        for i, provider in enumerate(self._providers):
            if not provider.is_available:
                continue

            # Track primary provider's dimensions
            if primary_dimensions is None:
                primary_dimensions = provider.dimensions

            # Skip fallback providers with different dimensions to prevent mismatch
            if i > 0 and provider.dimensions != primary_dimensions:
                logger.warning(
                    f"Skipping fallback {provider.name} - dimension mismatch "
                    f"({provider.dimensions} vs {primary_dimensions})"
                )
                continue

            try:
                result = provider.embed(texts)
                # Success - track and update active provider
                self._track_usage(provider.name, success=True)
                self._active_provider = provider
                return result
            except EmbeddingError as e:
                self._track_usage(provider.name, success=False)
                logger.warning(f"Provider {provider.name} failed: {e}. Trying next provider...")
                last_error = e

        # All providers failed
        raise EmbeddingError(
            "All embedding providers failed. Check that your configured provider "
            "(Ollama, LM Studio, or OpenAI) is running and accessible.",
            provider="chain",
            cause=last_error,
        )

    def reset(self) -> None:
        """Reset the provider chain to try all providers again."""
        self._active_provider = None
        self._tried_providers.clear()

    def get_status(self) -> dict:
        """Get status of all providers in the chain.

        Returns:
            Dictionary with provider status information including usage stats.
        """
        # Determine primary provider based on usage stats
        primary_provider = None
        max_success = 0
        for name, stats in self._usage_stats.items():
            if stats["success"] > max_success:
                max_success = stats["success"]
                primary_provider = name

        return {
            "active_provider": self._active_provider.name if self._active_provider else None,
            "primary_provider": primary_provider
            or (self._providers[0].name if self._providers else None),
            "providers": [
                {
                    "name": p.name,
                    "available": p.is_available,
                    "dimensions": p.dimensions,
                    "usage": self._usage_stats.get(p.name, {"success": 0, "failure": 0}),
                }
                for p in self._providers
            ],
            "total_embeds": sum(s["success"] + s["failure"] for s in self._usage_stats.values()),
        }
