"""Configuration management for Codebase Intelligence.

This module provides configuration classes with validation for the CI feature.
Configuration follows a priority hierarchy:
1. Environment variables (OAK_CI_*)
2. Project config (.oak/config.yaml)
3. Feature manifest defaults
4. Hardcoded defaults in this module
"""

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

from open_agent_kit.config.paths import OAK_DIR
from open_agent_kit.features.codebase_intelligence.constants import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
    DEFAULT_SUMMARIZATION_BASE_URL,
    DEFAULT_SUMMARIZATION_MODEL,
    DEFAULT_SUMMARIZATION_PROVIDER,
    DEFAULT_SUMMARIZATION_TIMEOUT,
    LOG_LEVEL_DEBUG,
    LOG_LEVEL_INFO,
    VALID_LOG_LEVELS,
    VALID_PROVIDERS,
    VALID_SUMMARIZATION_PROVIDERS,
)
from open_agent_kit.features.codebase_intelligence.exceptions import (
    ValidationError,
)
from open_agent_kit.models.agent_manifest import AgentManifest

logger = logging.getLogger(__name__)

# Package agents directory (where agent manifests are stored)
# Path: features/codebase_intelligence/config.py -> codebase_intelligence/ -> features/ -> open_agent_kit/
_PACKAGE_ROOT = Path(__file__).parent.parent.parent
_AGENTS_DIR = _PACKAGE_ROOT / "agents"

# Type alias for valid providers
ProviderType = Literal["ollama", "openai", "fastembed"]

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


def _get_oak_managed_paths() -> list[str]:
    """Get paths managed by OAK from all agent manifests.

    Reads all agent manifests and collects OAK-managed paths (commands, skills,
    settings files) that should be excluded from code indexing.

    Returns:
        List of relative paths that OAK manages across all supported agents.
    """
    paths: set[str] = set()

    try:
        if not _AGENTS_DIR.exists():
            logger.debug(f"Agents directory not found: {_AGENTS_DIR}")
            return []

        for agent_dir in _AGENTS_DIR.iterdir():
            if not agent_dir.is_dir():
                continue

            manifest_path = agent_dir / "manifest.yaml"
            if not manifest_path.exists():
                continue

            try:
                manifest = AgentManifest.load(manifest_path)
                agent_paths = manifest.get_oak_managed_paths()
                paths.update(agent_paths)
                logger.debug(f"Agent {manifest.name} managed paths: {agent_paths}")
            except Exception as e:
                logger.warning(f"Failed to load manifest for {agent_dir.name}: {e}")

    except Exception as e:
        logger.warning(f"Error scanning agent manifests: {e}")

    return sorted(paths)


# OAK-managed paths derived from agent manifests
# These are directories/files that OAK installs (commands, skills, settings)
# User-generated files like AGENT.md and constitution are NOT excluded
_OAK_MANAGED_PATHS = _get_oak_managed_paths()


# Default patterns to exclude from indexing
DEFAULT_EXCLUDE_PATTERNS = [
    # Version control and tools
    ".git",
    ".git/**",
    ".oak",
    ".oak/**",
    # OAK-managed agent directories (derived from agent manifests)
    # Includes: commands, skills, settings files for all supported agents
    *_OAK_MANAGED_PATHS,
    # CI-managed hook configurations (installed by oak ci enable)
    # These contain generated hook scripts, not user code
    ".claude/settings.json",
    ".cursor/hooks.json",
    ".cursor/hooks",
    ".cursor/hooks/**",
    # Dependencies (match at any level for nested node_modules)
    "node_modules",
    "node_modules/**",
    "**/node_modules",
    "**/node_modules/**",
    # Python caches
    "__pycache__",
    "__pycache__/**",
    ".mypy_cache",
    ".mypy_cache/**",
    ".pytest_cache",
    ".pytest_cache/**",
    ".ruff_cache",
    ".ruff_cache/**",
    "htmlcov",
    "htmlcov/**",
    # Virtual environments
    ".venv",
    ".venv/**",
    "venv",
    "venv/**",
    # Environment and sensitive files (quiet exclusion)
    ".env",
    ".env.*",
    "*.env",
    "*.pem",
    "*.key",
    "*.crt",
    "*.p12",
    "*.pfx",
    "*.jks",
    "*.keystore",
    # Build artifacts
    "*.pyc",
    "*.pyo",
    "*.min.js",
    "*.min.css",
    "*.map",
    "*.lock",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "dist/**",
    "build/**",
    ".next/**",
    "coverage/**",
    "*.egg-info/**",
    # Localization/translation files (cause search pollution with repeated content)
    "translations/**",
    "locales/**",
    "locale/**",
    "i18n/**",
    "l10n/**",
    "*.po",
    "*.pot",
    "*.mo",
]


@dataclass
class CIConfig:
    """Codebase Intelligence configuration.

    Attributes:
        embedding: Embedding provider configuration.
        summarization: LLM summarization configuration.
        index_on_startup: Whether to build index when daemon starts.
        watch_files: Whether to watch files for changes.
        exclude_patterns: Glob patterns to exclude from indexing.
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR).
    """

    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    summarization: SummarizationConfig = field(default_factory=SummarizationConfig)
    index_on_startup: bool = True
    watch_files: bool = True
    exclude_patterns: list[str] = field(default_factory=lambda: DEFAULT_EXCLUDE_PATTERNS.copy())
    log_level: str = LOG_LEVEL_INFO

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        self._validate()

    def _validate(self) -> None:
        """Validate configuration values.

        Raises:
            ValidationError: If any configuration value is invalid.
        """
        # Validate log level
        if self.log_level.upper() not in VALID_LOG_LEVELS:
            raise ValidationError(
                f"Invalid log level: {self.log_level}",
                field="log_level",
                value=self.log_level,
                expected=f"one of {VALID_LOG_LEVELS}",
            )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CIConfig":
        """Create config from dictionary.

        Args:
            data: Configuration dictionary.

        Returns:
            CIConfig instance.

        Raises:
            ValidationError: If configuration values are invalid.
        """
        embedding_data = data.get("embedding", {})
        summarization_data = data.get("summarization", {})
        return cls(
            embedding=EmbeddingConfig.from_dict(embedding_data),
            summarization=SummarizationConfig.from_dict(summarization_data),
            index_on_startup=data.get("index_on_startup", True),
            watch_files=data.get("watch_files", True),
            exclude_patterns=data.get("exclude_patterns", DEFAULT_EXCLUDE_PATTERNS.copy()),
            log_level=data.get("log_level", LOG_LEVEL_INFO),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "embedding": self.embedding.to_dict(),
            "summarization": self.summarization.to_dict(),
            "index_on_startup": self.index_on_startup,
            "watch_files": self.watch_files,
            "exclude_patterns": self.exclude_patterns,
            "log_level": self.log_level,
        }

    def get_combined_exclude_patterns(self) -> list[str]:
        """Get combined exclusion patterns (user patterns merged with defaults).

        Returns:
            List of all exclusion patterns with defaults first, then user additions.
            Duplicates are removed.
        """
        combined = list(DEFAULT_EXCLUDE_PATTERNS)
        for pattern in self.exclude_patterns:
            if pattern not in combined:
                combined.append(pattern)
        return combined

    def get_user_exclude_patterns(self) -> list[str]:
        """Get only user-added exclusion patterns (not in defaults).

        Returns:
            List of patterns that were added by the user.
        """
        return [p for p in self.exclude_patterns if p not in DEFAULT_EXCLUDE_PATTERNS]

    def get_effective_log_level(self) -> str:
        """Get effective log level, considering environment variable overrides.

        Priority (highest to lowest):
        1. OAK_CI_DEBUG=1 → DEBUG
        2. OAK_CI_LOG_LEVEL environment variable
        3. Config file log_level setting
        4. Default: INFO
        """
        # Debug mode override
        if os.environ.get("OAK_CI_DEBUG", "").lower() in ("1", "true", "yes"):
            return LOG_LEVEL_DEBUG

        # Environment variable override
        env_level = os.environ.get("OAK_CI_LOG_LEVEL", "").upper()
        if env_level in VALID_LOG_LEVELS:
            return env_level

        # Config file setting
        if self.log_level.upper() in VALID_LOG_LEVELS:
            return self.log_level.upper()

        return LOG_LEVEL_INFO


def load_ci_config(project_root: Path) -> CIConfig:
    """Load Codebase Intelligence configuration from project.

    Reads from .oak/config.yaml under the 'codebase_intelligence' key.

    Args:
        project_root: Project root directory.

    Returns:
        CIConfig with settings (defaults if not configured).

    Note:
        Returns defaults on error rather than raising, to allow daemon
        to start even with invalid config.
    """
    config_file = project_root / OAK_DIR / "config.yaml"

    if not config_file.exists():
        logger.debug(f"No config file at {config_file}, using defaults")
        return CIConfig()

    try:
        with open(config_file, encoding="utf-8") as f:
            config_data = yaml.safe_load(f) or {}

        ci_data = config_data.get("codebase_intelligence", {})
        config = CIConfig.from_dict(ci_data)
        logger.info(
            f"Loaded CI config: provider={config.embedding.provider}, "
            f"model={config.embedding.model}"
        )
        return config

    except ValidationError as e:
        logger.warning(f"Invalid CI config in {config_file}: {e}")
        logger.info("Using default configuration")
        return CIConfig()

    except yaml.YAMLError as e:
        logger.warning(f"Failed to parse config YAML from {config_file}: {e}")
        return CIConfig()

    except OSError as e:
        logger.warning(f"Failed to read config from {config_file}: {e}")
        return CIConfig()


def save_ci_config(project_root: Path, config: CIConfig) -> None:
    """Save Codebase Intelligence configuration to project.

    Updates the 'codebase_intelligence' key in .oak/config.yaml.

    Args:
        project_root: Project root directory.
        config: Configuration to save.
    """
    config_file = project_root / OAK_DIR / "config.yaml"

    # Load existing config
    existing_config: dict[str, Any] = {}
    if config_file.exists():
        try:
            with open(config_file, encoding="utf-8") as f:
                existing_config = yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"Failed to read existing config: {e}")

    # Update codebase_intelligence section
    existing_config["codebase_intelligence"] = config.to_dict()

    # Write back
    config_file.parent.mkdir(parents=True, exist_ok=True)
    with open(config_file, "w", encoding="utf-8") as f:
        yaml.dump(existing_config, f, default_flow_style=False, sort_keys=False)

    logger.info(f"Saved CI config to {config_file}")
