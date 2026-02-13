"""Tests for embedding model metadata registry.

Tests cover:
- get_known_dimensions() exact match and partial match
- get_known_dimensions() fallback to DEFAULT_EMBEDDING_DIMENSIONS
- get_known_model_metadata() returns correct dict shape
- get_known_model_metadata() returns None values for unknown models
- KNOWN_EMBEDDING_MODELS data integrity checks
- DEFAULT_PROVIDER_URLS data integrity checks
"""

import pytest

from open_agent_kit.features.codebase_intelligence.embeddings.metadata import (
    DEFAULT_EMBEDDING_DIMENSIONS,
    DEFAULT_PROVIDER_URLS,
    EMBEDDING_MODEL_PATTERNS,
    KNOWN_EMBEDDING_MODELS,
    get_known_dimensions,
    get_known_model_metadata,
)

# =============================================================================
# get_known_dimensions()
# =============================================================================


class TestGetKnownDimensions:
    """Test get_known_dimensions() lookup behaviour."""

    def test_exact_match(self) -> None:
        """Exact model name returns the registered dimensions."""
        assert get_known_dimensions("nomic-embed-text") == 768

    def test_exact_match_openai_model(self) -> None:
        """OpenAI model names are matched exactly."""
        assert get_known_dimensions("text-embedding-3-small") == 1536
        assert get_known_dimensions("text-embedding-3-large") == 3072

    def test_partial_match(self) -> None:
        """Partial model name matches via get_known_model_metadata."""
        # "nomic-embed-text" should match within a longer model string
        result = get_known_dimensions("nomic-embed-text:latest")
        assert result == 768

    def test_unknown_model_returns_default(self) -> None:
        """Completely unknown model falls back to DEFAULT_EMBEDDING_DIMENSIONS."""
        result = get_known_dimensions("totally-unknown-model-xyz")
        assert result == DEFAULT_EMBEDDING_DIMENSIONS

    def test_default_dimensions_value(self) -> None:
        """DEFAULT_EMBEDDING_DIMENSIONS is 768."""
        assert DEFAULT_EMBEDDING_DIMENSIONS == 768

    @pytest.mark.parametrize(
        "model_name,expected_dims",
        [
            ("bge-small", 384),
            ("bge-large", 1024),
            ("bge-m3", 1024),
            ("all-minilm", 384),
            ("mxbai-embed-large", 1024),
            ("text-embedding-ada-002", 1536),
        ],
        ids=[
            "bge-small",
            "bge-large",
            "bge-m3",
            "all-minilm",
            "mxbai-embed-large",
            "ada-002",
        ],
    )
    def test_specific_models(self, model_name: str, expected_dims: int) -> None:
        """Verify specific well-known models return correct dimensions."""
        assert get_known_dimensions(model_name) == expected_dims


# =============================================================================
# get_known_model_metadata()
# =============================================================================


class TestGetKnownModelMetadata:
    """Test get_known_model_metadata() lookup behaviour."""

    def test_known_model_returns_both_fields(self) -> None:
        """Known model returns dimensions and context_window."""
        metadata = get_known_model_metadata("nomic-embed-text")
        assert metadata["dimensions"] == 768
        assert metadata["context_window"] == 8192

    def test_unknown_model_returns_none_values(self) -> None:
        """Unknown model returns dict with None values."""
        metadata = get_known_model_metadata("nonexistent-model-abc")
        assert metadata["dimensions"] is None
        assert metadata["context_window"] is None

    def test_return_shape_always_has_both_keys(self) -> None:
        """Both known and unknown results always have dimensions and context_window keys."""
        for model_name in ["nomic-embed-text", "nonexistent-xyz"]:
            metadata = get_known_model_metadata(model_name)
            assert "dimensions" in metadata
            assert "context_window" in metadata

    def test_case_insensitive_match(self) -> None:
        """Lookup is case-insensitive (model_lower comparison)."""
        # "NOMIC-EMBED-TEXT" lowered is "nomic-embed-text" which is a known name
        metadata = get_known_model_metadata("NOMIC-EMBED-TEXT")
        assert metadata["dimensions"] == 768

    def test_partial_match_with_tag(self) -> None:
        """Model name with tag suffix still matches via partial match."""
        metadata = get_known_model_metadata("bge-m3:latest")
        assert metadata["dimensions"] == 1024
        assert metadata["context_window"] == 8192


# =============================================================================
# KNOWN_EMBEDDING_MODELS data integrity
# =============================================================================


class TestKnownEmbeddingModelsIntegrity:
    """Verify structural integrity of the KNOWN_EMBEDDING_MODELS registry."""

    def test_all_entries_have_positive_dimensions(self) -> None:
        """Every model entry must have dimensions > 0."""
        for model_name, metadata in KNOWN_EMBEDDING_MODELS.items():
            assert "dimensions" in metadata, f"{model_name} missing 'dimensions'"
            assert metadata["dimensions"] > 0, f"{model_name} has non-positive dimensions"

    def test_all_entries_have_positive_context_window(self) -> None:
        """Every model entry must have context_window > 0."""
        for model_name, metadata in KNOWN_EMBEDDING_MODELS.items():
            assert "context_window" in metadata, f"{model_name} missing 'context_window'"
            assert metadata["context_window"] > 0, f"{model_name} has non-positive context_window"

    def test_registry_is_not_empty(self) -> None:
        """The registry should have a meaningful number of entries."""
        assert len(KNOWN_EMBEDDING_MODELS) > 10

    def test_model_names_are_non_empty_strings(self) -> None:
        """All model names must be non-empty strings."""
        for model_name in KNOWN_EMBEDDING_MODELS:
            assert isinstance(model_name, str)
            assert len(model_name) > 0


# =============================================================================
# DEFAULT_PROVIDER_URLS data integrity
# =============================================================================


class TestDefaultProviderUrls:
    """Verify DEFAULT_PROVIDER_URLS has valid entries."""

    def test_all_values_are_non_empty_strings(self) -> None:
        """Every provider URL must be a non-empty string."""
        for provider, url in DEFAULT_PROVIDER_URLS.items():
            assert isinstance(url, str), f"{provider} URL is not a string"
            assert len(url) > 0, f"{provider} URL is empty"

    def test_contains_expected_providers(self) -> None:
        """Registry includes the three core providers."""
        assert "ollama" in DEFAULT_PROVIDER_URLS
        assert "lmstudio" in DEFAULT_PROVIDER_URLS
        assert "openai" in DEFAULT_PROVIDER_URLS

    def test_urls_have_scheme(self) -> None:
        """Every URL should start with http:// or https://."""
        for provider, url in DEFAULT_PROVIDER_URLS.items():
            assert url.startswith("http://") or url.startswith(
                "https://"
            ), f"{provider} URL '{url}' missing scheme"


# =============================================================================
# EMBEDDING_MODEL_PATTERNS data integrity
# =============================================================================


class TestEmbeddingModelPatterns:
    """Verify EMBEDDING_MODEL_PATTERNS has valid entries."""

    def test_patterns_are_non_empty_strings(self) -> None:
        """All patterns must be non-empty strings."""
        for pattern in EMBEDDING_MODEL_PATTERNS:
            assert isinstance(pattern, str)
            assert len(pattern) > 0

    def test_patterns_list_is_not_empty(self) -> None:
        """The patterns list should have entries."""
        assert len(EMBEDDING_MODEL_PATTERNS) > 0
