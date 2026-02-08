"""Tests for configuration management module.

Tests cover:
- EmbeddingConfig validation and initialization
- URL validation for embedding providers
- Model name validation
- CIConfig validation and lifecycle
- Environment variable resolution
- Config file loading and saving
- Error handling for invalid configurations
- User config overlay: deep merge, split, load/save, migration, origins
"""

from pathlib import Path

import pytest
import yaml

from open_agent_kit.features.codebase_intelligence.config import (
    DEFAULT_EMBEDDING_CONTEXT_TOKENS,
    CIConfig,
    EmbeddingConfig,
    _deep_merge,
    _split_by_classification,
    _user_config_path,
    _write_yaml_config,
    get_config_origins,
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
            provider="lmstudio",
            model="bge-large-en-v1.5",
            base_url="http://localhost:1234",
            dimensions=1024,
            api_key="secret-key",
            fallback_enabled=False,
            context_tokens=512,
            max_chunk_chars=1000,
        )
        assert config.provider == "lmstudio"
        assert config.model == "bge-large-en-v1.5"
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


# =============================================================================
# Deep Merge Tests
# =============================================================================

MOCK_MACHINE_ID = "test_user_abc123"


class TestDeepMerge:
    """Test _deep_merge helper function."""

    def test_empty_overlay_returns_base(self):
        """Empty overlay should return a copy of base."""
        base = {"a": 1, "b": {"c": 2}}
        result = _deep_merge(base, {})
        assert result == base
        assert result is not base

    def test_empty_base_returns_overlay(self):
        """Empty base should return overlay values."""
        overlay = {"a": 1, "b": 2}
        result = _deep_merge({}, overlay)
        assert result == overlay

    def test_scalar_override(self):
        """Overlay scalars should override base scalars."""
        base = {"a": 1, "b": 2}
        overlay = {"b": 99}
        result = _deep_merge(base, overlay)
        assert result == {"a": 1, "b": 99}

    def test_list_replace(self):
        """Overlay lists should replace base lists (not merge)."""
        base = {"patterns": ["a", "b"]}
        overlay = {"patterns": ["x"]}
        result = _deep_merge(base, overlay)
        assert result == {"patterns": ["x"]}

    def test_nested_recurse(self):
        """Nested dicts should be recursively merged."""
        base = {"embedding": {"provider": "ollama", "model": "bge-m3"}}
        overlay = {"embedding": {"model": "nomic-embed-text"}}
        result = _deep_merge(base, overlay)
        assert result == {"embedding": {"provider": "ollama", "model": "nomic-embed-text"}}

    def test_no_base_mutation(self):
        """Base dict should not be mutated."""
        base = {"a": {"b": 1}}
        overlay = {"a": {"b": 2}}
        _deep_merge(base, overlay)
        assert base == {"a": {"b": 1}}

    def test_new_keys_added(self):
        """New keys in overlay should be added to result."""
        base = {"a": 1}
        overlay = {"b": 2}
        result = _deep_merge(base, overlay)
        assert result == {"a": 1, "b": 2}


# =============================================================================
# Split By Classification Tests
# =============================================================================


class TestSplitByClassification:
    """Test _split_by_classification helper function."""

    def test_full_split(self):
        """Full config should split correctly into user and project parts."""
        ci_dict = CIConfig().to_dict()
        user, project = _split_by_classification(ci_dict)

        # Entire user-classified sections
        assert "embedding" in user
        assert "summarization" in user
        assert "tunnel" in user
        assert "log_level" in user
        assert "log_rotation" in user

        # Project-classified sections
        assert "session_quality" in project
        assert "exclude_patterns" in project
        assert "index_on_startup" in project
        assert "watch_files" in project

    def test_embedding_is_all_user(self):
        """Embedding section should be entirely user-classified."""
        ci_dict = {"embedding": {"provider": "ollama", "model": "bge-m3"}}
        user, project = _split_by_classification(ci_dict)
        assert "embedding" in user
        assert "embedding" not in project

    def test_summarization_is_all_user(self):
        """Summarization section should be entirely user-classified."""
        ci_dict = {"summarization": {"provider": "ollama", "model": "qwen2.5:3b"}}
        user, project = _split_by_classification(ci_dict)
        assert "summarization" in user
        assert "summarization" not in project

    def test_agents_mixed_section(self):
        """Agents section should split into user and project parts."""
        ci_dict = {
            "agents": {
                "enabled": True,
                "max_turns": 10,
                "provider_type": "ollama",
                "provider_base_url": "http://localhost:11434",
                "provider_model": "llama3",
            }
        }
        user, project = _split_by_classification(ci_dict)

        # User-classified agent keys
        assert "agents" in user
        assert "provider_type" in user["agents"]
        assert "provider_base_url" in user["agents"]
        assert "provider_model" in user["agents"]

        # Project-classified agent keys
        assert "agents" in project
        assert "enabled" in project["agents"]
        assert "max_turns" in project["agents"]

    def test_session_quality_is_project(self):
        """Session quality section should be entirely project-classified."""
        ci_dict = {"session_quality": {"min_activities": 3}}
        user, project = _split_by_classification(ci_dict)
        assert "session_quality" not in user
        assert "session_quality" in project

    def test_exclude_patterns_is_project(self):
        """Exclude patterns should be project-classified."""
        ci_dict = {"exclude_patterns": ["*.pyc"]}
        user, project = _split_by_classification(ci_dict)
        assert "exclude_patterns" not in user
        assert "exclude_patterns" in project

    def test_roundtrip_split_merge(self):
        """Splitting then merging should reproduce the original config."""
        original = CIConfig().to_dict()
        user, project = _split_by_classification(original)
        reconstructed = _deep_merge(project, user)
        assert reconstructed == original


# =============================================================================
# User Config Overlay Tests
# =============================================================================


@pytest.fixture
def mock_machine_id(monkeypatch):
    """Monkeypatch get_machine_identifier to return a stable test value."""
    monkeypatch.setattr(
        "open_agent_kit.features.codebase_intelligence.activity.store.backup.get_machine_identifier",
        lambda *_args, **_kwargs: MOCK_MACHINE_ID,
    )


class TestUserConfigOverlay:
    """Test user config overlay load/save behavior."""

    def test_load_without_overlay_is_identical(self, project_with_oak_config, mock_machine_id):
        """Loading without a user overlay should be identical to current behavior."""
        config = load_ci_config(project_with_oak_config)
        assert config.embedding.provider == "ollama"
        assert config.embedding.model == "bge-m3"

    def test_load_with_overlay_merges(self, project_with_oak_config, mock_machine_id):
        """User overlay should merge on top of project config."""
        # Create user overlay that overrides embedding model
        user_file = project_with_oak_config / ".oak" / f"config.{MOCK_MACHINE_ID}.yaml"
        user_file.write_text(
            yaml.dump(
                {
                    "codebase_intelligence": {
                        "embedding": {
                            "model": "nomic-embed-text",
                        }
                    }
                }
            )
        )

        config = load_ci_config(project_with_oak_config)
        # User overlay wins for model
        assert config.embedding.model == "nomic-embed-text"
        # Project config still provides provider
        assert config.embedding.provider == "ollama"

    def test_corrupted_overlay_falls_back(self, project_with_oak_config, mock_machine_id):
        """Corrupted user overlay should be ignored with a warning."""
        user_file = project_with_oak_config / ".oak" / f"config.{MOCK_MACHINE_ID}.yaml"
        user_file.write_text("{{invalid yaml: [")

        # Should still load successfully from project config only
        config = load_ci_config(project_with_oak_config)
        assert config.embedding.provider == "ollama"
        assert config.embedding.model == "bge-m3"

    def test_save_splits_to_two_files(self, tmp_path, mock_machine_id):
        """Default save should write user keys to overlay, project keys to config."""
        oak_dir = tmp_path / ".oak"
        oak_dir.mkdir()

        config = CIConfig()
        save_ci_config(tmp_path, config)

        project_file = oak_dir / "config.yaml"
        user_file = oak_dir / f"config.{MOCK_MACHINE_ID}.yaml"

        assert project_file.exists()
        assert user_file.exists()

        # Project file has project-classified keys
        with open(project_file) as f:
            project_data = yaml.safe_load(f)
        project_ci = project_data.get("codebase_intelligence", {})
        assert "session_quality" in project_ci

        # User file has user-classified keys
        with open(user_file) as f:
            user_data = yaml.safe_load(f)
        user_ci = user_data.get("codebase_intelligence", {})
        assert "embedding" in user_ci

    def test_save_preserves_existing_user_defaults(self, tmp_path, mock_machine_id):
        """Save should preserve user-classified defaults already in project config."""
        oak_dir = tmp_path / ".oak"
        oak_dir.mkdir()

        # Simulate project config from oak init (has all keys including user-classified)
        config_file = oak_dir / "config.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "codebase_intelligence": {
                        "embedding": {"provider": "ollama", "model": "team-default"},
                        "session_quality": {"min_activities": 3},
                    }
                }
            )
        )

        # User changes embedding model via dashboard
        config = load_ci_config(tmp_path)
        config.embedding.model = "bge-m3"
        save_ci_config(tmp_path, config)

        # Project config should STILL have embedding defaults
        with open(config_file) as f:
            project_data = yaml.safe_load(f)
        project_ci = project_data["codebase_intelligence"]
        assert "embedding" in project_ci
        assert project_ci["embedding"]["provider"] == "ollama"
        # Original default model preserved (not overwritten by user change)
        assert project_ci["embedding"]["model"] == "team-default"

        # User overlay has the user's change
        user_file = oak_dir / f"config.{MOCK_MACHINE_ID}.yaml"
        with open(user_file) as f:
            user_data = yaml.safe_load(f)
        user_ci = user_data["codebase_intelligence"]
        assert user_ci["embedding"]["model"] == "bge-m3"

    def test_force_project_writes_all(self, tmp_path, mock_machine_id):
        """force_project=True should write all keys to project config."""
        oak_dir = tmp_path / ".oak"
        oak_dir.mkdir()

        config = CIConfig()
        save_ci_config(tmp_path, config, force_project=True)

        project_file = oak_dir / "config.yaml"
        user_file = oak_dir / f"config.{MOCK_MACHINE_ID}.yaml"

        assert project_file.exists()
        # User file should NOT be created
        assert not user_file.exists()

        # Project file should have everything
        with open(project_file) as f:
            project_data = yaml.safe_load(f)
        project_ci = project_data.get("codebase_intelligence", {})
        assert "embedding" in project_ci
        assert "session_quality" in project_ci

    def test_force_project_does_not_touch_overlay(self, tmp_path, mock_machine_id):
        """force_project should leave existing overlay untouched."""
        oak_dir = tmp_path / ".oak"
        oak_dir.mkdir()

        # Create pre-existing user overlay
        user_file = oak_dir / f"config.{MOCK_MACHINE_ID}.yaml"
        original_content = "codebase_intelligence:\n  embedding:\n    model: custom-model\n"
        user_file.write_text(original_content)

        config = CIConfig()
        save_ci_config(tmp_path, config, force_project=True)

        # User file should be unchanged
        assert user_file.read_text() == original_content

    def test_save_preserves_non_ci_keys(self, tmp_path, mock_machine_id):
        """Save should preserve non-CI keys in both project and user files."""
        oak_dir = tmp_path / ".oak"
        oak_dir.mkdir()
        config_file = oak_dir / "config.yaml"
        config_file.write_text("other_feature:\n  key: value\n")

        config = CIConfig()
        save_ci_config(tmp_path, config)

        with open(config_file) as f:
            data = yaml.safe_load(f)
        assert "other_feature" in data
        assert "codebase_intelligence" in data


# =============================================================================
# Migration Tests
# =============================================================================


class TestSplitUserConfig:
    """Test the user config split logic (formerly tested via migration)."""

    @staticmethod
    def _split_user_config(project_root: Path) -> None:
        """Replicate the split_user_config logic using config utilities."""
        from open_agent_kit.utils import read_yaml

        config_path = project_root / ".oak" / "config.yaml"
        if not config_path.exists():
            return
        user_file = _user_config_path(project_root)
        if user_file.exists():
            return
        data = read_yaml(config_path)
        if not data:
            return
        ci_data = data.get("codebase_intelligence")
        if not ci_data or not isinstance(ci_data, dict):
            return
        user_keys, _project_keys = _split_by_classification(ci_data)
        if not user_keys:
            return
        _write_yaml_config(user_file, {"codebase_intelligence": user_keys})

    def test_copies_user_keys_to_overlay(self, tmp_path, mock_machine_id):
        """Split should copy user keys to overlay without stripping project config."""
        oak_dir = tmp_path / ".oak"
        oak_dir.mkdir()
        config_file = oak_dir / "config.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "codebase_intelligence": {
                        "embedding": {"provider": "ollama", "model": "bge-m3"},
                        "session_quality": {"min_activities": 3},
                        "log_level": "DEBUG",
                    }
                }
            )
        )

        self._split_user_config(tmp_path)

        user_file = oak_dir / f"config.{MOCK_MACHINE_ID}.yaml"
        assert user_file.exists()

        with open(user_file) as f:
            user_data = yaml.safe_load(f)
        user_ci = user_data["codebase_intelligence"]
        assert "embedding" in user_ci
        assert "log_level" in user_ci

        # Project config should STILL have all keys (defaults preserved)
        with open(config_file) as f:
            project_data = yaml.safe_load(f)
        project_ci = project_data["codebase_intelligence"]
        assert "session_quality" in project_ci
        assert "embedding" in project_ci
        assert "log_level" in project_ci

    def test_idempotent_skips_existing_overlay(self, tmp_path, mock_machine_id):
        """Split should skip if user overlay already exists."""
        oak_dir = tmp_path / ".oak"
        oak_dir.mkdir()
        config_file = oak_dir / "config.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "codebase_intelligence": {
                        "embedding": {"provider": "ollama"},
                    }
                }
            )
        )

        # Pre-create user overlay
        user_file = oak_dir / f"config.{MOCK_MACHINE_ID}.yaml"
        original_content = "existing: true\n"
        user_file.write_text(original_content)

        self._split_user_config(tmp_path)

        # User file should be untouched
        assert user_file.read_text() == original_content

    def test_no_ci_section_is_noop(self, tmp_path, mock_machine_id):
        """Split should be a no-op if no CI section exists."""
        oak_dir = tmp_path / ".oak"
        oak_dir.mkdir()
        config_file = oak_dir / "config.yaml"
        config_file.write_text("other_feature:\n  key: value\n")

        self._split_user_config(tmp_path)

        user_file = oak_dir / f"config.{MOCK_MACHINE_ID}.yaml"
        assert not user_file.exists()

    def test_no_config_file_is_noop(self, tmp_path, mock_machine_id):
        """Split should be a no-op if config file doesn't exist."""
        self._split_user_config(tmp_path)
        # Should not raise


class TestRestoreUserConfigDefaults:
    """Test the user config restore logic (formerly tested via migration)."""

    @staticmethod
    def _restore_user_config_defaults(project_root: Path) -> None:
        """Replicate the restore_user_config_defaults logic using config utilities."""
        from open_agent_kit.utils import read_yaml

        config_path = project_root / ".oak" / "config.yaml"
        if not config_path.exists():
            return
        user_file = _user_config_path(project_root)
        if not user_file.exists():
            return
        user_data = read_yaml(user_file)
        if not user_data:
            return
        user_ci = user_data.get("codebase_intelligence", {})
        if not user_ci or not isinstance(user_ci, dict):
            return
        data = read_yaml(config_path)
        if not data:
            return
        project_ci = data.get("codebase_intelligence", {})
        if not isinstance(project_ci, dict):
            project_ci = {}
        restored = _deep_merge(user_ci, project_ci)
        data["codebase_intelligence"] = restored
        _write_yaml_config(config_path, data)

    def test_restores_missing_keys_from_overlay(self, tmp_path, mock_machine_id):
        """Should restore user-classified keys from overlay."""
        oak_dir = tmp_path / ".oak"
        oak_dir.mkdir()

        # Simulate state after destructive split: project config missing user keys
        config_file = oak_dir / "config.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "codebase_intelligence": {
                        "session_quality": {"min_activities": 3},
                    }
                }
            )
        )

        # User overlay has the values that were stripped
        user_file = oak_dir / f"config.{MOCK_MACHINE_ID}.yaml"
        user_file.write_text(
            yaml.dump(
                {
                    "codebase_intelligence": {
                        "embedding": {"provider": "ollama", "model": "bge-m3"},
                        "log_level": "DEBUG",
                    }
                }
            )
        )

        self._restore_user_config_defaults(tmp_path)

        with open(config_file) as f:
            project_data = yaml.safe_load(f)
        project_ci = project_data["codebase_intelligence"]
        # Restored from overlay
        assert project_ci["embedding"]["provider"] == "ollama"
        assert project_ci["log_level"] == "DEBUG"
        # Existing project keys preserved
        assert project_ci["session_quality"]["min_activities"] == 3

    def test_does_not_overwrite_existing_project_values(self, tmp_path, mock_machine_id):
        """Project config values should win over overlay values."""
        oak_dir = tmp_path / ".oak"
        oak_dir.mkdir()

        # Project config has its own embedding default
        config_file = oak_dir / "config.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "codebase_intelligence": {
                        "embedding": {"provider": "lm-studio", "model": "team-model"},
                    }
                }
            )
        )

        # User overlay has different values
        user_file = oak_dir / f"config.{MOCK_MACHINE_ID}.yaml"
        user_file.write_text(
            yaml.dump(
                {
                    "codebase_intelligence": {
                        "embedding": {"provider": "ollama", "model": "bge-m3"},
                    }
                }
            )
        )

        self._restore_user_config_defaults(tmp_path)

        with open(config_file) as f:
            project_data = yaml.safe_load(f)
        project_ci = project_data["codebase_intelligence"]
        # Project values should win (not overwritten by overlay)
        assert project_ci["embedding"]["provider"] == "lm-studio"
        assert project_ci["embedding"]["model"] == "team-model"

    def test_noop_without_overlay(self, tmp_path, mock_machine_id):
        """Should be a no-op if no user overlay exists."""
        oak_dir = tmp_path / ".oak"
        oak_dir.mkdir()
        config_file = oak_dir / "config.yaml"
        original = "codebase_intelligence:\n  session_quality:\n    min_activities: 3\n"
        config_file.write_text(original)

        self._restore_user_config_defaults(tmp_path)

        assert config_file.read_text() == original


# =============================================================================
# Config Origins Tests
# =============================================================================


class TestGetConfigOrigins:
    """Test get_config_origins function."""

    def test_all_defaults_when_no_config(self, tmp_path, mock_machine_id):
        """All sections should be 'default' when no config files exist."""
        origins = get_config_origins(tmp_path)
        for section in origins:
            assert origins[section] == "default"

    def test_project_origin_for_project_keys(self, tmp_path, mock_machine_id):
        """Project-classified keys should show 'project' origin."""
        oak_dir = tmp_path / ".oak"
        oak_dir.mkdir()
        config_file = oak_dir / "config.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "codebase_intelligence": {
                        "session_quality": {"min_activities": 5},
                        "exclude_patterns": ["*.pyc"],
                    }
                }
            )
        )

        origins = get_config_origins(tmp_path)
        assert origins["session_quality"] == "project"
        assert origins["exclude_patterns"] == "project"

    def test_user_origin_for_overlay_keys(self, tmp_path, mock_machine_id):
        """User-classified keys in overlay should show 'user' origin."""
        oak_dir = tmp_path / ".oak"
        oak_dir.mkdir()
        (oak_dir / "config.yaml").write_text(yaml.dump({"codebase_intelligence": {}}))

        user_file = oak_dir / f"config.{MOCK_MACHINE_ID}.yaml"
        user_file.write_text(
            yaml.dump(
                {
                    "codebase_intelligence": {
                        "embedding": {"provider": "ollama"},
                        "log_level": "DEBUG",
                    }
                }
            )
        )

        origins = get_config_origins(tmp_path)
        assert origins["embedding"] == "user"
        assert origins["log_level"] == "user"

    def test_mixed_section_agents_user_override(self, tmp_path, mock_machine_id):
        """Mixed agents section should show 'user' when overlay has sub-keys."""
        oak_dir = tmp_path / ".oak"
        oak_dir.mkdir()
        (oak_dir / "config.yaml").write_text(
            yaml.dump(
                {
                    "codebase_intelligence": {
                        "agents": {"enabled": True, "max_turns": 10},
                    }
                }
            )
        )

        user_file = oak_dir / f"config.{MOCK_MACHINE_ID}.yaml"
        user_file.write_text(
            yaml.dump(
                {
                    "codebase_intelligence": {
                        "agents": {"provider_type": "ollama"},
                    }
                }
            )
        )

        origins = get_config_origins(tmp_path)
        assert origins["agents"] == "user"
