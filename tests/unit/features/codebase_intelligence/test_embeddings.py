"""Tests for embedding provider modules.

Tests cover:
- EmbeddingResult dataclass
- EmbeddingError exception
- EmbeddingProvider base class
- EmbeddingProviderChain functionality
- create_provider_from_config factory function
"""

from unittest.mock import MagicMock, patch

import pytest

from open_agent_kit.features.codebase_intelligence.embeddings.base import (
    EmbeddingError,
    EmbeddingProvider,
    EmbeddingResult,
)
from open_agent_kit.features.codebase_intelligence.embeddings.provider_chain import (
    EmbeddingProviderChain,
    create_provider_from_config,
)

# =============================================================================
# EmbeddingResult Tests
# =============================================================================


class TestEmbeddingResult:
    """Test EmbeddingResult dataclass."""

    def test_create_result(self):
        """Test creating an embedding result."""
        result = EmbeddingResult(
            embeddings=[[0.1, 0.2, 0.3]],
            model="test-model",
            provider="test-provider",
            dimensions=3,
        )

        assert result.embeddings == [[0.1, 0.2, 0.3]]
        assert result.model == "test-model"
        assert result.provider == "test-provider"
        assert result.dimensions == 3

    def test_multiple_embeddings(self):
        """Test result with multiple embeddings."""
        result = EmbeddingResult(
            embeddings=[[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]],
            model="multi-model",
            provider="multi-provider",
            dimensions=2,
        )

        assert len(result.embeddings) == 3


# =============================================================================
# EmbeddingError Tests
# =============================================================================


class TestEmbeddingError:
    """Test EmbeddingError exception."""

    def test_basic_error(self):
        """Test creating basic embedding error."""
        error = EmbeddingError("Test error", provider="test-provider")

        assert str(error) == "Test error"
        assert error.provider == "test-provider"
        assert error.cause is None

    def test_error_with_cause(self):
        """Test error with underlying cause."""
        cause = ValueError("Underlying error")
        error = EmbeddingError("Wrapper error", provider="test-provider", cause=cause)

        assert error.cause is cause

    def test_error_is_exception(self):
        """Test that EmbeddingError is an Exception subclass."""
        error = EmbeddingError("Test", provider="test")

        assert isinstance(error, Exception)


# =============================================================================
# Mock Provider for Testing
# =============================================================================


class MockProvider(EmbeddingProvider):
    """Mock embedding provider for testing."""

    def __init__(
        self,
        name: str = "mock",
        dimensions: int = 768,
        is_available: bool = True,
        should_fail: bool = False,
    ):
        self._name = name
        self._dimensions = dimensions
        self._is_available = is_available
        self._should_fail = should_fail

    @property
    def name(self) -> str:
        return self._name

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @property
    def is_available(self) -> bool:
        return self._is_available

    def embed(self, texts: list[str]) -> EmbeddingResult:
        if self._should_fail:
            raise EmbeddingError("Mock provider failed", provider=self._name)
        return EmbeddingResult(
            embeddings=[[0.1] * self._dimensions for _ in texts],
            model="mock-model",
            provider=self._name,
            dimensions=self._dimensions,
        )


# =============================================================================
# EmbeddingProviderChain Tests
# =============================================================================


class TestEmbeddingProviderChainInit:
    """Test EmbeddingProviderChain initialization."""

    def test_init_with_custom_providers(self):
        """Test initialization with custom provider list."""
        providers = [MockProvider("provider1"), MockProvider("provider2")]
        chain = EmbeddingProviderChain(providers=providers)

        assert len(chain._providers) == 2

    @patch("open_agent_kit.features.codebase_intelligence.embeddings.provider_chain.OllamaProvider")
    def test_init_default_creates_ollama(self, mock_ollama):
        """Test that default init creates Ollama provider."""
        mock_ollama.return_value = MockProvider("ollama")

        EmbeddingProviderChain()

        mock_ollama.assert_called_once()


class TestEmbeddingProviderChainProperties:
    """Test EmbeddingProviderChain properties."""

    def test_name_returns_chain_none_without_active(self):
        """Test name property when no active provider."""
        chain = EmbeddingProviderChain(providers=[MockProvider()])

        assert chain.name == "chain:none"

    def test_name_returns_active_provider_name(self):
        """Test name property returns active provider name after embed."""
        provider = MockProvider(name="test-provider")
        chain = EmbeddingProviderChain(providers=[provider])

        chain.embed(["test"])

        assert chain.name == "test-provider"

    def test_dimensions_from_active_provider(self):
        """Test dimensions returns active provider dimensions."""
        provider = MockProvider(dimensions=1024)
        chain = EmbeddingProviderChain(providers=[provider])

        chain.embed(["test"])

        assert chain.dimensions == 1024

    def test_dimensions_from_primary_provider_regardless_of_availability(self):
        """Test dimensions returns primary (first) provider dimensions regardless of availability.

        Configuration is the source of truth, not runtime availability. This prevents
        race conditions where a slow-starting provider (like Ollama) could cause
        spurious dimension mismatches.
        """
        provider1 = MockProvider(dimensions=512, is_available=False)
        provider2 = MockProvider(dimensions=768, is_available=True)
        chain = EmbeddingProviderChain(providers=[provider1, provider2])

        # Should return primary (first) provider's dimensions, not first available
        assert chain.dimensions == 512

    def test_dimensions_default_fallback(self):
        """Test dimensions returns 768 when no providers available."""
        provider = MockProvider(is_available=False)
        chain = EmbeddingProviderChain(providers=[provider])

        assert chain.dimensions == 768

    def test_is_available_true_when_provider_available(self):
        """Test is_available returns True when any provider is available."""
        provider1 = MockProvider(is_available=False)
        provider2 = MockProvider(is_available=True)
        chain = EmbeddingProviderChain(providers=[provider1, provider2])

        assert chain.is_available is True

    def test_is_available_false_when_no_providers_available(self):
        """Test is_available returns False when no providers available."""
        provider = MockProvider(is_available=False)
        chain = EmbeddingProviderChain(providers=[provider])

        assert chain.is_available is False

    def test_active_provider_is_none_initially(self):
        """Test active_provider is None before any embed calls."""
        chain = EmbeddingProviderChain(providers=[MockProvider()])

        assert chain.active_provider is None


class TestEmbeddingProviderChainEmbed:
    """Test EmbeddingProviderChain embed method."""

    def test_embed_uses_first_available_provider(self):
        """Test that embed uses first available provider."""
        provider1 = MockProvider(name="first", is_available=True)
        provider2 = MockProvider(name="second", is_available=True)
        chain = EmbeddingProviderChain(providers=[provider1, provider2])

        result = chain.embed(["test"])

        assert result.provider == "first"

    def test_embed_falls_back_on_failure(self):
        """Test that embed falls back when first provider fails."""
        provider1 = MockProvider(name="failing", should_fail=True)
        provider2 = MockProvider(name="working")
        chain = EmbeddingProviderChain(providers=[provider1, provider2])

        result = chain.embed(["test"])

        assert result.provider == "working"

    def test_embed_skips_unavailable_providers(self):
        """Test that embed skips unavailable providers."""
        provider1 = MockProvider(name="unavailable", is_available=False)
        provider2 = MockProvider(name="available", is_available=True)
        chain = EmbeddingProviderChain(providers=[provider1, provider2])

        result = chain.embed(["test"])

        assert result.provider == "available"

    def test_embed_raises_when_all_fail(self):
        """Test that embed raises EmbeddingError when all providers fail."""
        provider = MockProvider(should_fail=True)
        chain = EmbeddingProviderChain(providers=[provider])

        with pytest.raises(EmbeddingError, match="All embedding providers failed"):
            chain.embed(["test"])

    def test_embed_skips_fallback_with_dimension_mismatch(self):
        """Test that embed skips fallback providers with different dimensions."""
        provider1 = MockProvider(name="primary", dimensions=768, should_fail=True)
        provider2 = MockProvider(name="fallback", dimensions=1024)
        chain = EmbeddingProviderChain(providers=[provider1, provider2])

        with pytest.raises(EmbeddingError):
            chain.embed(["test"])

    def test_embed_updates_active_provider(self):
        """Test that successful embed updates active_provider."""
        provider = MockProvider(name="test-provider")
        chain = EmbeddingProviderChain(providers=[provider])

        chain.embed(["test"])

        assert chain.active_provider == provider

    def test_embed_tracks_usage_stats(self):
        """Test that embed tracks usage statistics."""
        provider = MockProvider(name="tracked-provider")
        chain = EmbeddingProviderChain(providers=[provider])

        chain.embed(["test1"])
        chain.embed(["test2"])

        assert chain._usage_stats["tracked-provider"]["success"] == 2


class TestEmbeddingProviderChainReset:
    """Test EmbeddingProviderChain reset method."""

    def test_reset_clears_active_provider(self):
        """Test that reset clears active provider."""
        provider = MockProvider()
        chain = EmbeddingProviderChain(providers=[provider])
        chain.embed(["test"])

        chain.reset()

        assert chain._active_provider is None

    def test_reset_clears_tried_providers(self):
        """Test that reset clears tried providers set."""
        provider = MockProvider()
        chain = EmbeddingProviderChain(providers=[provider])
        chain._tried_providers.add("test")

        chain.reset()

        assert len(chain._tried_providers) == 0


class TestEmbeddingProviderChainStatus:
    """Test EmbeddingProviderChain get_status method."""

    def test_get_status_returns_dict(self):
        """Test that get_status returns a dictionary."""
        chain = EmbeddingProviderChain(providers=[MockProvider()])

        status = chain.get_status()

        assert isinstance(status, dict)

    def test_get_status_includes_active_provider(self):
        """Test that status includes active_provider."""
        provider = MockProvider(name="active-test")
        chain = EmbeddingProviderChain(providers=[provider])
        chain.embed(["test"])

        status = chain.get_status()

        assert status["active_provider"] == "active-test"

    def test_get_status_includes_provider_list(self):
        """Test that status includes provider list."""
        providers = [MockProvider(name="p1"), MockProvider(name="p2")]
        chain = EmbeddingProviderChain(providers=providers)

        status = chain.get_status()

        assert len(status["providers"]) == 2
        assert status["providers"][0]["name"] == "p1"

    def test_get_status_includes_usage_stats(self):
        """Test that status includes usage statistics."""
        provider = MockProvider(name="usage-test")
        chain = EmbeddingProviderChain(providers=[provider])
        chain.embed(["test"])

        status = chain.get_status()

        assert status["providers"][0]["usage"]["success"] == 1

    def test_get_status_includes_total_embeds(self):
        """Test that status includes total embed count."""
        provider = MockProvider()
        chain = EmbeddingProviderChain(providers=[provider])
        chain.embed(["test1"])
        chain.embed(["test2"])

        status = chain.get_status()

        assert status["total_embeds"] == 2


# =============================================================================
# create_provider_from_config Tests
# =============================================================================


class TestCreateProviderFromConfig:
    """Test create_provider_from_config factory function."""

    def test_creates_ollama_provider(self):
        """Test creating Ollama provider from config."""
        config = MagicMock()
        config.provider = "ollama"
        config.model = "test-model"
        config.base_url = "http://localhost:11434"
        config.get_max_chunk_chars.return_value = 8000
        config.dimensions = 768

        with patch(
            "open_agent_kit.features.codebase_intelligence.embeddings.provider_chain.OllamaProvider"
        ) as mock_ollama:
            create_provider_from_config(config)

            mock_ollama.assert_called_once_with(
                model="test-model",
                base_url="http://localhost:11434",
                max_chars=8000,
                dimensions=768,
            )

    def test_creates_openai_provider(self):
        """Test creating OpenAI provider from config."""
        config = MagicMock()
        config.provider = "openai"
        config.model = "text-embedding-ada-002"
        config.base_url = "https://api.openai.com/v1"
        config.api_key = "test-key"
        config.dimensions = 1536

        # Import the module to patch the local import
        with patch(
            "open_agent_kit.features.codebase_intelligence.embeddings.openai_compat.OpenAICompatProvider"
        ) as mock_openai:
            mock_instance = MagicMock()
            mock_openai.return_value = mock_instance

            result = create_provider_from_config(config)

            mock_openai.assert_called_once_with(
                model="text-embedding-ada-002",
                base_url="https://api.openai.com/v1",
                api_key="test-key",
                dimensions=1536,
            )
            assert result == mock_instance

    def test_raises_for_unknown_provider(self):
        """Test that unknown provider raises ValueError."""
        config = MagicMock()
        config.provider = "unknown_provider"

        with pytest.raises(ValueError, match="Unknown embedding provider type"):
            create_provider_from_config(config)

    def test_provider_name_is_case_insensitive(self):
        """Test that provider name matching is case insensitive."""
        config = MagicMock()
        config.provider = "OLLAMA"
        config.model = "test"
        config.base_url = "http://localhost:11434"
        config.get_max_chunk_chars.return_value = 8000
        config.dimensions = 768

        with patch(
            "open_agent_kit.features.codebase_intelligence.embeddings.provider_chain.OllamaProvider"
        ):
            # Should not raise
            create_provider_from_config(config)


# =============================================================================
# EmbeddingProvider Base Class Tests
# =============================================================================


class TestEmbeddingProviderBase:
    """Test EmbeddingProvider base class methods."""

    def test_embed_query_calls_embed(self):
        """Test that embed_query calls embed with single text."""
        provider = MockProvider(dimensions=3)

        result = provider.embed_query("test query")

        assert len(result) == 3
        assert isinstance(result, list)
