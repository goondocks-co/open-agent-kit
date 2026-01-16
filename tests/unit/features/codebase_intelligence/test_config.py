"""Tests for configuration management module.

Tests cover:
- EmbeddingConfig validation and initialization
- URL validation for embedding providers
- Model name validation
- CIConfig validation and lifecycle
- Environment variable resolution
- Config file loading and saving
- Error handling for invalid configurations
"""

from pathlib import Path

import pytest

from open_agent_kit.features.codebase_intelligence.config import (
    DEFAULT_EMBEDDING_CONTEXT_TOKENS,
    CIConfig,
    EmbeddingConfig,
    load_ci_config,
    save_ci_config,
)
from open_agent_kit.features.codebase_intelligence.constants import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
    LOG_LEVEL_DEBUG,
    LOG_LEVEL_INFO,
    LOG_LEVEL_WARNING,
)
from open_agent_kit.features.codebase_intelligence.exceptions import (
    ValidationError,
)

# =============================================================================
# EmbeddingConfig Tests
# =============================================================================


class TestEmbeddingConfigInit:
    """Test EmbeddingConfig initialization and validation."""

    def test_init_with_defaults(self, default_embedding_config: EmbeddingConfig):
        """Test default embedding config initialization.

        Verifies that default values are correctly set when no arguments provided.
        """
        assert default_embedding_config.provider == DEFAULT_PROVIDER
        assert default_embedding_config.model == DEFAULT_MODEL
        assert default_embedding_config.base_url == DEFAULT_BASE_URL
        assert default_embedding_config.dimensions is None
        assert default_embedding_config.api_key is None
        assert default_embedding_config.fallback_enabled is False

    def test_init_with_custom_values(self, custom_embedding_config: EmbeddingConfig):
        """Test embedding config with custom values.

        Verifies that custom values are properly stored and validated.
        """
        assert custom_embedding_config.provider == "openai"
        assert custom_embedding_config.model == "text-embedding-3-small"
        assert custom_embedding_config.base_url == "https://api.openai.com/v1"
        assert custom_embedding_config.dimensions == 1536
        assert custom_embedding_config.api_key == "${OPENAI_API_KEY}"

    def test_init_with_all_fields(self):
        """Test embedding config initialization with all fields specified."""
        config = EmbeddingConfig(
            provider="fastembed",
            model="BAAI/bge-large-en-v1.5",
            base_url="http://localhost:8000",
            dimensions=1024,
            api_key="secret-key",
            fallback_enabled=False,
            context_tokens=512,
            max_chunk_chars=1000,
        )
        assert config.provider == "fastembed"
        assert config.model == "BAAI/bge-large-en-v1.5"
        assert config.dimensions == 1024
        assert config.context_tokens == 512
        assert config.max_chunk_chars == 1000
        assert config.fallback_enabled is False


class TestEmbeddingConfigValidation:
    """Test EmbeddingConfig validation."""

    def test_invalid_provider_raises_error(self, invalid_provider_config: dict):
        """Test that invalid provider raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            EmbeddingConfig.from_dict(invalid_provider_config)
        assert "Invalid embedding provider" in str(exc_info.value)
        assert exc_info.value.field == "provider"

    def test_empty_model_is_valid(self, empty_model_config: dict):
        """Test that empty model name is valid (not configured yet)."""
        # Empty model is valid - user will select from discovered models
        config = EmbeddingConfig.from_dict(empty_model_config)
        assert config.model == ""

    def test_whitespace_only_model_raises_error(self):
        """Test that whitespace-only model name raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            EmbeddingConfig(model="   ")
        assert "Model name cannot be only whitespace" in str(exc_info.value)
        assert exc_info.value.field == "model"

    def test_invalid_url_raises_error(self, invalid_url_config: dict):
        """Test that invalid URL raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            EmbeddingConfig.from_dict(invalid_url_config)
        assert "Invalid base URL" in str(exc_info.value)
        assert exc_info.value.field == "base_url"

    def test_negative_dimensions_raises_error(self):
        """Test that negative dimensions raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            EmbeddingConfig(
                provider="ollama",
                model="bge-m3",
                dimensions=-1,
            )
        assert "Dimensions must be positive" in str(exc_info.value)

    def test_zero_dimensions_raises_error(self):
        """Test that zero dimensions raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            EmbeddingConfig(
                provider="ollama",
                model="bge-m3",
                dimensions=0,
            )
        assert "Dimensions must be positive" in str(exc_info.value)

    @pytest.mark.parametrize(
        "invalid_url",
        [
            "",
            "ftp://invalid.com",
            "localhost:11434",
            "not a url",
            "   ",
        ],
    )
    def test_invalid_urls(self, invalid_url: str):
        """Test various invalid URL formats.

        Args:
            invalid_url: Invalid URL string to test.
        """
        with pytest.raises(ValidationError) as exc_info:
            EmbeddingConfig(
                provider="ollama",
                model="bge-m3",
                base_url=invalid_url,
            )
        assert "Invalid base URL" in str(exc_info.value)

    @pytest.mark.parametrize(
        "valid_url",
        [
            "http://localhost:11434",
            "https://api.openai.com/v1",
            "http://192.168.1.1:8000",
            "https://example.com",
            "http://localhost:11434/v1",
        ],
    )
    def test_valid_urls(self, valid_url: str):
        """Test various valid URL formats.

        Args:
            valid_url: Valid URL string to test.
        """
        config = EmbeddingConfig(
            provider="ollama",
            model="bge-m3",
            base_url=valid_url,
        )
        assert config.base_url == valid_url


class TestEmbeddingConfigFromDict:
    """Test EmbeddingConfig.from_dict factory method."""

    def test_from_dict_with_defaults(self):
        """Test from_dict with empty dictionary uses defaults."""
        config = EmbeddingConfig.from_dict({})
        assert config.provider == DEFAULT_PROVIDER
        assert config.model == DEFAULT_MODEL
        assert config.base_url == DEFAULT_BASE_URL

    def test_from_dict_with_custom_values(self):
        """Test from_dict with custom values."""
        data = {
            "provider": "openai",
            "model": "text-embedding-3-small",
            "base_url": "https://api.openai.com/v1",
            "dimensions": 1536,
        }
        config = EmbeddingConfig.from_dict(data)
        assert config.provider == "openai"
        assert config.model == "text-embedding-3-small"
        assert config.dimensions == 1536

    def test_from_dict_resolves_env_var_in_api_key(self, mock_env_vars):
        """Test that from_dict resolves environment variables in api_key.

        Args:
            mock_env_vars: Environment variable helper fixture.
        """
        mock_env_vars.set("TEST_API_KEY", "secret-value-123")
        data = {
            "provider": "openai",
            "model": "bge-m3",
            "base_url": "http://localhost:11434",
            "api_key": "${TEST_API_KEY}",
        }
        config = EmbeddingConfig.from_dict(data)
        assert config.api_key == "secret-value-123"

    def test_from_dict_missing_env_var_results_in_none(self, mock_env_vars):
        """Test that missing environment variable results in None api_key.

        Args:
            mock_env_vars: Environment variable helper fixture.
        """
        mock_env_vars.unset("NONEXISTENT_VAR")
        data = {
            "provider": "ollama",
            "model": "bge-m3",
            "base_url": "http://localhost:11434",
            "api_key": "${NONEXISTENT_VAR}",
        }
        config = EmbeddingConfig.from_dict(data)
        assert config.api_key is None

    def test_from_dict_preserves_hardcoded_api_key(self):
        """Test that hardcoded API keys (without ${}) are preserved as-is."""
        data = {
            "provider": "openai",
            "model": "bge-m3",
            "base_url": "http://localhost:11434",
            "api_key": "hardcoded-key-value",
        }
        config = EmbeddingConfig.from_dict(data)
        assert config.api_key == "hardcoded-key-value"


class TestEmbeddingConfigToDict:
    """Test EmbeddingConfig.to_dict serialization."""

    def test_to_dict_round_trip(self, custom_embedding_config: EmbeddingConfig):
        """Test that to_dict output can be used to recreate config.

        Args:
            custom_embedding_config: Custom embedding config fixture.
        """
        dict_repr = custom_embedding_config.to_dict()
        recreated = EmbeddingConfig.from_dict(dict_repr)
        assert recreated.provider == custom_embedding_config.provider
        assert recreated.model == custom_embedding_config.model
        assert recreated.base_url == custom_embedding_config.base_url
        assert recreated.dimensions == custom_embedding_config.dimensions


class TestEmbeddingConfigContextTokens:
    """Test context token retrieval and defaults."""

    def test_get_context_tokens_from_explicit_value(self):
        """Test getting explicitly set context tokens."""
        config = EmbeddingConfig(
            provider="ollama",
            model="bge-m3",
            context_tokens=1024,
        )
        assert config.get_context_tokens() == 1024

    def test_get_context_tokens_default_fallback(self):
        """Test default fallback when context_tokens not set."""
        config = EmbeddingConfig(
            provider="ollama",
            model="bge-m3",
        )
        # Should return default of 8192
        assert config.get_context_tokens() == DEFAULT_EMBEDDING_CONTEXT_TOKENS

    def test_explicit_context_tokens_override_default(self):
        """Test that explicit context_tokens override default."""
        config = EmbeddingConfig(
            provider="ollama",
            model="bge-m3",
            context_tokens=2048,
        )
        assert config.get_context_tokens() == 2048


class TestEmbeddingConfigMaxChunkChars:
    """Test max chunk chars calculation."""

    def test_get_max_chunk_chars_explicit_value(self):
        """Test getting explicitly set max_chunk_chars."""
        config = EmbeddingConfig(
            provider="ollama",
            model="bge-m3",
            max_chunk_chars=5000,
        )
        assert config.get_max_chunk_chars() == 5000

    def test_get_max_chunk_chars_auto_scaled_from_context(self):
        """Test auto-scaling max_chunk_chars from context tokens."""
        config = EmbeddingConfig(
            provider="ollama",
            model="unknown-model",
            context_tokens=2000,
        )
        # Should auto-scale: 2000 * 0.75 = 1500 (conservative for code)
        assert config.get_max_chunk_chars() == 1500

    def test_get_max_chunk_chars_default_fallback(self):
        """Test fallback when no model info available.

        For unknown models, max_chunk_chars is auto-calculated from
        get_context_tokens() × 0.75. Default context_tokens is 8192,
        so: 8192 × 0.75 = 6144.
        """
        config = EmbeddingConfig(
            provider="ollama",
            model="unknown-model",
        )
        # Auto-scaled from default context_tokens (8192 * 0.75 = 6144)
        assert config.get_max_chunk_chars() == 6144

    def test_explicit_overrides_all(self):
        """Test that explicit max_chunk_chars overrides everything."""
        config = EmbeddingConfig(
            provider="ollama",
            model="bge-m3",
            max_chunk_chars=999,
        )
        assert config.get_max_chunk_chars() == 999


class TestEmbeddingConfigDimensions:
    """Test embedding dimensions retrieval."""

    def test_get_dimensions_explicit_value(self):
        """Test getting explicitly set dimensions."""
        config = EmbeddingConfig(
            provider="ollama",
            model="bge-m3",
            dimensions=768,
        )
        assert config.get_dimensions() == 768

    def test_get_dimensions_returns_none_when_not_set(self):
        """Test that dimensions returns None when not explicitly set."""
        config = EmbeddingConfig(
            provider="ollama",
            model="bge-m3",
        )
        # Dimensions must be explicitly set or discovered
        assert config.get_dimensions() is None


# =============================================================================
# CIConfig Tests
# =============================================================================


class TestCIConfigInit:
    """Test CIConfig initialization."""

    def test_init_with_defaults(self, default_ci_config: CIConfig):
        """Test default CI config initialization."""
        assert isinstance(default_ci_config.embedding, EmbeddingConfig)
        assert default_ci_config.index_on_startup is True
        assert default_ci_config.watch_files is True
        assert default_ci_config.log_level == LOG_LEVEL_INFO

    def test_init_with_custom_values(self, custom_ci_config: CIConfig):
        """Test CI config with custom values."""
        assert custom_ci_config.embedding.provider == "openai"
        assert custom_ci_config.index_on_startup is False
        assert custom_ci_config.watch_files is False
        assert custom_ci_config.log_level == LOG_LEVEL_DEBUG

    def test_init_with_exclude_patterns(self):
        """Test CI config with custom exclude patterns."""
        config = CIConfig(
            exclude_patterns=["**/*.pyc", "**/__pycache__/**", "**/node_modules/**"],
        )
        assert len(config.exclude_patterns) == 3
        assert "**/*.pyc" in config.exclude_patterns

    def test_default_exclude_patterns_are_copied(self):
        """Test that default exclude patterns are copied, not referenced.

        This prevents accidental modification of the default patterns list.
        """
        config1 = CIConfig()
        config2 = CIConfig()
        config1.exclude_patterns.append("**/*.custom")
        # config2 should not be affected
        assert "**/*.custom" not in config2.exclude_patterns


class TestCIConfigValidation:
    """Test CIConfig validation."""

    def test_invalid_log_level_raises_error(self):
        """Test that invalid log level raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            CIConfig(log_level="INVALID_LEVEL")
        assert "Invalid log level" in str(exc_info.value)

    @pytest.mark.parametrize(
        "valid_level",
        [LOG_LEVEL_DEBUG, "debug", "INFO", "warning", "ERROR"],
    )
    def test_valid_log_levels(self, valid_level: str):
        """Test that valid log levels are accepted.

        Args:
            valid_level: Valid log level string.
        """
        config = CIConfig(log_level=valid_level)
        assert config.log_level == valid_level


class TestCIConfigEffectiveLogLevel:
    """Test effective log level with environment variable overrides."""

    def test_debug_env_var_overrides_config(self, mock_env_vars):
        """Test that OAK_CI_DEBUG=1 overrides config log level.

        Args:
            mock_env_vars: Environment variable helper fixture.
        """
        mock_env_vars.set("OAK_CI_DEBUG", "1")
        config = CIConfig(log_level=LOG_LEVEL_INFO)
        assert config.get_effective_log_level() == LOG_LEVEL_DEBUG

    def test_debug_true_string_overrides_config(self, mock_env_vars):
        """Test that OAK_CI_DEBUG=true also overrides config.

        Args:
            mock_env_vars: Environment variable helper fixture.
        """
        mock_env_vars.set("OAK_CI_DEBUG", "true")
        config = CIConfig(log_level=LOG_LEVEL_INFO)
        assert config.get_effective_log_level() == LOG_LEVEL_DEBUG

    def test_log_level_env_var_overrides_config(self, mock_env_vars):
        """Test that OAK_CI_LOG_LEVEL env var overrides config.

        Args:
            mock_env_vars: Environment variable helper fixture.
        """
        mock_env_vars.set("OAK_CI_LOG_LEVEL", "WARNING")
        config = CIConfig(log_level=LOG_LEVEL_INFO)
        assert config.get_effective_log_level() == LOG_LEVEL_WARNING

    def test_config_log_level_used_without_overrides(self, mock_env_vars):
        """Test that config log_level is used when no overrides present.

        Args:
            mock_env_vars: Environment variable helper fixture.
        """
        mock_env_vars.unset("OAK_CI_DEBUG")
        mock_env_vars.unset("OAK_CI_LOG_LEVEL")
        config = CIConfig(log_level=LOG_LEVEL_DEBUG)
        assert config.get_effective_log_level() == LOG_LEVEL_DEBUG

    def test_debug_overrides_log_level_env_var(self, mock_env_vars):
        """Test that OAK_CI_DEBUG has higher priority than OAK_CI_LOG_LEVEL.

        Args:
            mock_env_vars: Environment variable helper fixture.
        """
        mock_env_vars.set("OAK_CI_DEBUG", "1")
        mock_env_vars.set("OAK_CI_LOG_LEVEL", "INFO")
        config = CIConfig(log_level=LOG_LEVEL_WARNING)
        # Debug should win
        assert config.get_effective_log_level() == LOG_LEVEL_DEBUG


class TestCIConfigFromDict:
    """Test CIConfig.from_dict factory method."""

    def test_from_dict_with_empty_dict(self):
        """Test from_dict with empty dictionary uses defaults."""
        config = CIConfig.from_dict({})
        assert config.index_on_startup is True
        assert config.watch_files is True
        assert config.log_level == LOG_LEVEL_INFO

    def test_from_dict_with_custom_values(self):
        """Test from_dict with custom values."""
        data = {
            "index_on_startup": False,
            "watch_files": False,
            "exclude_patterns": ["**/*.pyc"],
            "log_level": LOG_LEVEL_DEBUG,
        }
        config = CIConfig.from_dict(data)
        assert config.index_on_startup is False
        assert config.watch_files is False
        assert config.log_level == LOG_LEVEL_DEBUG

    def test_from_dict_with_embedding_config(self):
        """Test from_dict with embedding configuration."""
        data = {
            "embedding": {
                "provider": "openai",
                "model": "text-embedding-3-small",
                "base_url": "https://api.openai.com/v1",
            },
            "log_level": LOG_LEVEL_INFO,
        }
        config = CIConfig.from_dict(data)
        assert config.embedding.provider == "openai"
        assert config.embedding.model == "text-embedding-3-small"


class TestCIConfigToDict:
    """Test CIConfig.to_dict serialization."""

    def test_to_dict_round_trip(self, custom_ci_config: CIConfig):
        """Test that to_dict output can recreate config."""
        dict_repr = custom_ci_config.to_dict()
        recreated = CIConfig.from_dict(dict_repr)
        assert recreated.index_on_startup == custom_ci_config.index_on_startup
        assert recreated.watch_files == custom_ci_config.watch_files
        assert recreated.log_level == custom_ci_config.log_level


# =============================================================================
# Config Loading Tests
# =============================================================================


class TestLoadCIConfig:
    """Test load_ci_config function."""

    def test_load_config_from_file(self, project_with_oak_config: Path):
        """Test loading config from .oak/config.yaml.

        Args:
            project_with_oak_config: Project with valid config file.
        """
        config = load_ci_config(project_with_oak_config)
        assert config.embedding.provider == "ollama"
        assert config.embedding.model == "bge-m3"
        assert config.index_on_startup is True

    def test_load_custom_config(self, project_with_custom_config: Path):
        """Test loading custom config values.

        Args:
            project_with_custom_config: Project with custom config.
        """
        config = load_ci_config(project_with_custom_config)
        assert config.embedding.provider == "openai"
        assert config.embedding.model == "text-embedding-3-small"
        assert config.index_on_startup is False
        assert config.log_level == LOG_LEVEL_DEBUG

    def test_load_config_returns_defaults_if_file_missing(self, project_without_config: Path):
        """Test that defaults are returned if config file missing.

        Args:
            project_without_config: Project without config file.
        """
        config = load_ci_config(project_without_config)
        assert config.embedding.provider == DEFAULT_PROVIDER
        assert config.embedding.model == DEFAULT_MODEL
        assert config.index_on_startup is True

    def test_load_config_returns_defaults_on_invalid_yaml(self, project_with_malformed_yaml: Path):
        """Test that defaults returned on malformed YAML.

        Args:
            project_with_malformed_yaml: Project with malformed YAML.
        """
        config = load_ci_config(project_with_malformed_yaml)
        # Should return defaults without raising
        assert config.embedding.provider == DEFAULT_PROVIDER

    def test_load_config_returns_defaults_on_validation_error(
        self, project_with_invalid_config: Path
    ):
        """Test that defaults returned on validation error.

        Args:
            project_with_invalid_config: Project with invalid config.
        """
        config = load_ci_config(project_with_invalid_config)
        # Should return defaults without raising
        assert config.embedding.provider == DEFAULT_PROVIDER

    def test_load_config_handles_permission_error(self, tmp_path: Path):
        """Test that permission errors are handled gracefully.

        Args:
            tmp_path: Temporary directory fixture.
        """
        oak_dir = tmp_path / ".oak"
        oak_dir.mkdir()
        config_file = oak_dir / "config.yaml"
        config_file.write_text("codebase_intelligence: {}")

        # Make file unreadable
        config_file.chmod(0o000)

        try:
            config = load_ci_config(tmp_path)
            # Should return defaults without raising
            assert config.embedding.provider == DEFAULT_PROVIDER
        finally:
            # Restore permissions for cleanup
            config_file.chmod(0o644)


class TestSaveCIConfig:
    """Test save_ci_config function."""

    def test_save_config_creates_file(self, tmp_path: Path, default_ci_config: CIConfig):
        """Test that save_ci_config creates config file.

        Args:
            tmp_path: Temporary directory fixture.
            default_ci_config: Default CI config fixture.
        """
        save_ci_config(tmp_path, default_ci_config)

        config_file = tmp_path / ".oak" / "config.yaml"
        assert config_file.exists()

    def test_save_config_roundtrip(self, tmp_path: Path, custom_ci_config: CIConfig):
        """Test that config can be saved and loaded back.

        Args:
            tmp_path: Temporary directory fixture.
            custom_ci_config: Custom CI config fixture.
        """
        save_ci_config(tmp_path, custom_ci_config)

        loaded_config = load_ci_config(tmp_path)
        assert loaded_config.embedding.provider == custom_ci_config.embedding.provider
        assert loaded_config.log_level == custom_ci_config.log_level

    def test_save_config_preserves_other_keys(self, tmp_path: Path):
        """Test that save_ci_config preserves other config keys.

        Args:
            tmp_path: Temporary directory fixture.
        """
        # Create initial config with other keys
        oak_dir = tmp_path / ".oak"
        oak_dir.mkdir()
        config_file = oak_dir / "config.yaml"
        config_file.write_text("other_feature:\n  key: value\n")

        # Save CI config
        ci_config = CIConfig()
        save_ci_config(tmp_path, ci_config)

        # Load and verify both keys exist
        content = config_file.read_text()
        assert "other_feature:" in content
        assert "codebase_intelligence:" in content
