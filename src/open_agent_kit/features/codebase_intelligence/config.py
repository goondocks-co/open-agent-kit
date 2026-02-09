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
    BACKUP_AUTO_ENABLED_DEFAULT,
    BACKUP_CONFIG_KEY,
    BACKUP_INCLUDE_ACTIVITIES_DEFAULT,
    BACKUP_INTERVAL_MINUTES_DEFAULT,
    BACKUP_INTERVAL_MINUTES_MAX,
    BACKUP_INTERVAL_MINUTES_MIN,
    BACKUP_ON_UPGRADE_DEFAULT,
    CI_CLI_COMMAND_DEFAULT,
    CI_CLI_COMMAND_VALIDATION_PATTERN,
    CI_CONFIG_KEY_CLI_COMMAND,
    CI_CONFIG_KEY_TUNNEL,
    CI_CONFIG_TUNNEL_KEY_AUTO_START,
    CI_CONFIG_TUNNEL_KEY_CLOUDFLARED_PATH,
    CI_CONFIG_TUNNEL_KEY_NGROK_PATH,
    CI_CONFIG_TUNNEL_KEY_PROVIDER,
    CI_TUNNEL_ERROR_INVALID_PROVIDER,
    CI_TUNNEL_ERROR_INVALID_PROVIDER_EXPECTED,
    DEFAULT_AGENT_MAX_TURNS,
    DEFAULT_AGENT_TIMEOUT_SECONDS,
    DEFAULT_BACKGROUND_PROCESSING_INTERVAL_SECONDS,
    DEFAULT_BASE_URL,
    DEFAULT_EXECUTOR_CACHE_SIZE,
    DEFAULT_LOG_BACKUP_COUNT,
    DEFAULT_LOG_MAX_SIZE_MB,
    DEFAULT_LOG_ROTATION_ENABLED,
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
    DEFAULT_SCHEDULER_INTERVAL_SECONDS,
    DEFAULT_SUMMARIZATION_BASE_URL,
    DEFAULT_SUMMARIZATION_MODEL,
    DEFAULT_SUMMARIZATION_PROVIDER,
    DEFAULT_SUMMARIZATION_TIMEOUT,
    DEFAULT_TUNNEL_PROVIDER,
    LOG_LEVEL_DEBUG,
    LOG_LEVEL_INFO,
    MAX_AGENT_MAX_TURNS,
    MAX_AGENT_TIMEOUT_SECONDS,
    MAX_BACKGROUND_PROCESSING_INTERVAL_SECONDS,
    MAX_EXECUTOR_CACHE_SIZE,
    MAX_LOG_BACKUP_COUNT,
    MAX_LOG_MAX_SIZE_MB,
    MAX_SCHEDULER_INTERVAL_SECONDS,
    MIN_AGENT_TIMEOUT_SECONDS,
    MIN_BACKGROUND_PROCESSING_INTERVAL_SECONDS,
    MIN_EXECUTOR_CACHE_SIZE,
    MIN_LOG_MAX_SIZE_MB,
    MIN_SCHEDULER_INTERVAL_SECONDS,
    MIN_SESSION_ACTIVITIES,
    SESSION_INACTIVE_TIMEOUT_SECONDS,
    VALID_LOG_LEVELS,
    VALID_PROVIDERS,
    VALID_SUMMARIZATION_PROVIDERS,
    VALID_TUNNEL_PROVIDERS,
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
class AgentConfig:
    """Configuration for the CI Agent subsystem.

    Attributes:
        enabled: Whether to enable the agent subsystem.
        max_turns: Default maximum turns for agent execution.
        timeout_seconds: Default timeout for agent execution.
        scheduler_interval_seconds: Interval between scheduler checks for due schedules.
        executor_cache_size: Max runs to keep in executor's in-memory cache.
        background_processing_interval_seconds: Interval for activity processor background tasks.
        provider_type: API provider type (cloud, ollama, lmstudio, bedrock, openrouter).
        provider_base_url: Base URL for the provider API (for local providers).
        provider_model: Default model to use for agent execution.

    Provider Configuration:
        The provider settings configure how agents connect to LLM backends.
        - 'cloud': Uses Anthropic cloud API (default, uses logged-in account or ANTHROPIC_API_KEY)
        - 'ollama': Local Ollama server with Anthropic-compatible API (v0.14.0+)
        - 'lmstudio': Local LM Studio server with Anthropic-compatible API
        - 'bedrock': AWS Bedrock
        - 'openrouter': OpenRouter proxy

        Note: Claude Agent SDK requires Anthropic API format. Ollama and LM Studio
        support this format as of their recent versions.
    """

    enabled: bool = True
    max_turns: int = DEFAULT_AGENT_MAX_TURNS
    timeout_seconds: int = DEFAULT_AGENT_TIMEOUT_SECONDS
    scheduler_interval_seconds: int = DEFAULT_SCHEDULER_INTERVAL_SECONDS
    executor_cache_size: int = DEFAULT_EXECUTOR_CACHE_SIZE
    background_processing_interval_seconds: int = DEFAULT_BACKGROUND_PROCESSING_INTERVAL_SECONDS
    # Provider configuration for agent execution
    provider_type: str = "cloud"
    provider_base_url: str | None = None
    provider_model: str | None = None

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        self._validate()

    def _validate(self) -> None:
        """Validate configuration values.

        Raises:
            ValidationError: If any configuration value is invalid.
        """
        if self.max_turns < 1:
            raise ValidationError(
                "max_turns must be at least 1",
                field="max_turns",
                value=self.max_turns,
                expected=">= 1",
            )
        if self.max_turns > MAX_AGENT_MAX_TURNS:
            raise ValidationError(
                f"max_turns must be at most {MAX_AGENT_MAX_TURNS}",
                field="max_turns",
                value=self.max_turns,
                expected=f"<= {MAX_AGENT_MAX_TURNS}",
            )
        if self.timeout_seconds < MIN_AGENT_TIMEOUT_SECONDS:
            raise ValidationError(
                f"timeout_seconds must be at least {MIN_AGENT_TIMEOUT_SECONDS}",
                field="timeout_seconds",
                value=self.timeout_seconds,
                expected=f">= {MIN_AGENT_TIMEOUT_SECONDS}",
            )
        if self.timeout_seconds > MAX_AGENT_TIMEOUT_SECONDS:
            raise ValidationError(
                f"timeout_seconds must be at most {MAX_AGENT_TIMEOUT_SECONDS}",
                field="timeout_seconds",
                value=self.timeout_seconds,
                expected=f"<= {MAX_AGENT_TIMEOUT_SECONDS}",
            )
        # Validate scheduler interval
        if self.scheduler_interval_seconds < MIN_SCHEDULER_INTERVAL_SECONDS:
            raise ValidationError(
                f"scheduler_interval_seconds must be at least {MIN_SCHEDULER_INTERVAL_SECONDS}",
                field="scheduler_interval_seconds",
                value=self.scheduler_interval_seconds,
                expected=f">= {MIN_SCHEDULER_INTERVAL_SECONDS}",
            )
        if self.scheduler_interval_seconds > MAX_SCHEDULER_INTERVAL_SECONDS:
            raise ValidationError(
                f"scheduler_interval_seconds must be at most {MAX_SCHEDULER_INTERVAL_SECONDS}",
                field="scheduler_interval_seconds",
                value=self.scheduler_interval_seconds,
                expected=f"<= {MAX_SCHEDULER_INTERVAL_SECONDS}",
            )
        # Validate executor cache size
        if self.executor_cache_size < MIN_EXECUTOR_CACHE_SIZE:
            raise ValidationError(
                f"executor_cache_size must be at least {MIN_EXECUTOR_CACHE_SIZE}",
                field="executor_cache_size",
                value=self.executor_cache_size,
                expected=f">= {MIN_EXECUTOR_CACHE_SIZE}",
            )
        if self.executor_cache_size > MAX_EXECUTOR_CACHE_SIZE:
            raise ValidationError(
                f"executor_cache_size must be at most {MAX_EXECUTOR_CACHE_SIZE}",
                field="executor_cache_size",
                value=self.executor_cache_size,
                expected=f"<= {MAX_EXECUTOR_CACHE_SIZE}",
            )
        # Validate background processing interval
        if self.background_processing_interval_seconds < MIN_BACKGROUND_PROCESSING_INTERVAL_SECONDS:
            raise ValidationError(
                f"background_processing_interval_seconds must be at least "
                f"{MIN_BACKGROUND_PROCESSING_INTERVAL_SECONDS}",
                field="background_processing_interval_seconds",
                value=self.background_processing_interval_seconds,
                expected=f">= {MIN_BACKGROUND_PROCESSING_INTERVAL_SECONDS}",
            )
        if self.background_processing_interval_seconds > MAX_BACKGROUND_PROCESSING_INTERVAL_SECONDS:
            raise ValidationError(
                f"background_processing_interval_seconds must be at most "
                f"{MAX_BACKGROUND_PROCESSING_INTERVAL_SECONDS}",
                field="background_processing_interval_seconds",
                value=self.background_processing_interval_seconds,
                expected=f"<= {MAX_BACKGROUND_PROCESSING_INTERVAL_SECONDS}",
            )
        # Validate provider type
        valid_provider_types = {"cloud", "ollama", "lmstudio", "bedrock", "openrouter"}
        if self.provider_type not in valid_provider_types:
            raise ValidationError(
                f"Invalid provider_type: {self.provider_type}",
                field="provider_type",
                value=self.provider_type,
                expected=f"one of {valid_provider_types}",
            )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentConfig":
        """Create config from dictionary.

        Args:
            data: Configuration dictionary.

        Returns:
            AgentConfig instance.
        """
        return cls(
            enabled=data.get("enabled", True),
            max_turns=data.get("max_turns", DEFAULT_AGENT_MAX_TURNS),
            timeout_seconds=data.get("timeout_seconds", DEFAULT_AGENT_TIMEOUT_SECONDS),
            scheduler_interval_seconds=data.get(
                "scheduler_interval_seconds", DEFAULT_SCHEDULER_INTERVAL_SECONDS
            ),
            executor_cache_size=data.get("executor_cache_size", DEFAULT_EXECUTOR_CACHE_SIZE),
            background_processing_interval_seconds=data.get(
                "background_processing_interval_seconds",
                DEFAULT_BACKGROUND_PROCESSING_INTERVAL_SECONDS,
            ),
            provider_type=data.get("provider_type", "cloud"),
            provider_base_url=data.get("provider_base_url"),
            provider_model=data.get("provider_model"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "enabled": self.enabled,
            "max_turns": self.max_turns,
            "timeout_seconds": self.timeout_seconds,
            "scheduler_interval_seconds": self.scheduler_interval_seconds,
            "executor_cache_size": self.executor_cache_size,
            "background_processing_interval_seconds": self.background_processing_interval_seconds,
            "provider_type": self.provider_type,
            "provider_base_url": self.provider_base_url,
            "provider_model": self.provider_model,
        }


# =============================================================================
# Session Quality Configuration
# =============================================================================

# Validation limits for session quality settings
MIN_SESSION_ACTIVITY_THRESHOLD: int = 1
MAX_SESSION_ACTIVITY_THRESHOLD: int = 20
MIN_STALE_SESSION_TIMEOUT: int = 300  # 5 minutes minimum
MAX_STALE_SESSION_TIMEOUT: int = 86400  # 24 hours maximum


@dataclass
class SessionQualityConfig:
    """Configuration for session quality thresholds.

    These settings control when sessions are considered "quality" enough
    to be titled, summarized, and embedded. Sessions below the quality
    threshold are cleaned up during stale session recovery.

    Attributes:
        min_activities: Minimum tool calls for a session to be considered quality.
            Sessions below this threshold will not be titled, summarized, or embedded.
        stale_timeout_seconds: How long before an inactive session is considered stale.
            Stale sessions are either marked completed (if quality) or deleted (if not).
    """

    min_activities: int = MIN_SESSION_ACTIVITIES
    stale_timeout_seconds: int = SESSION_INACTIVE_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        self._validate()

    def _validate(self) -> None:
        """Validate configuration values.

        Raises:
            ValidationError: If any configuration value is invalid.
        """
        if self.min_activities < MIN_SESSION_ACTIVITY_THRESHOLD:
            raise ValidationError(
                f"min_activities must be at least {MIN_SESSION_ACTIVITY_THRESHOLD}",
                field="min_activities",
                value=self.min_activities,
                expected=f">= {MIN_SESSION_ACTIVITY_THRESHOLD}",
            )
        if self.min_activities > MAX_SESSION_ACTIVITY_THRESHOLD:
            raise ValidationError(
                f"min_activities must be at most {MAX_SESSION_ACTIVITY_THRESHOLD}",
                field="min_activities",
                value=self.min_activities,
                expected=f"<= {MAX_SESSION_ACTIVITY_THRESHOLD}",
            )
        if self.stale_timeout_seconds < MIN_STALE_SESSION_TIMEOUT:
            raise ValidationError(
                f"stale_timeout_seconds must be at least {MIN_STALE_SESSION_TIMEOUT}",
                field="stale_timeout_seconds",
                value=self.stale_timeout_seconds,
                expected=f">= {MIN_STALE_SESSION_TIMEOUT}",
            )
        if self.stale_timeout_seconds > MAX_STALE_SESSION_TIMEOUT:
            raise ValidationError(
                f"stale_timeout_seconds must be at most {MAX_STALE_SESSION_TIMEOUT}",
                field="stale_timeout_seconds",
                value=self.stale_timeout_seconds,
                expected=f"<= {MAX_STALE_SESSION_TIMEOUT}",
            )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SessionQualityConfig":
        """Create config from dictionary.

        Args:
            data: Configuration dictionary.

        Returns:
            SessionQualityConfig instance.
        """
        return cls(
            min_activities=data.get("min_activities", MIN_SESSION_ACTIVITIES),
            stale_timeout_seconds=data.get(
                "stale_timeout_seconds", SESSION_INACTIVE_TIMEOUT_SECONDS
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "min_activities": self.min_activities,
            "stale_timeout_seconds": self.stale_timeout_seconds,
        }


@dataclass
class LogRotationConfig:
    """Configuration for log file rotation.

    Prevents unbounded growth of daemon.log by rotating files when they
    exceed the configured size limit.

    Attributes:
        enabled: Whether to enable log rotation.
        max_size_mb: Maximum log file size in megabytes before rotation.
        backup_count: Number of backup files to keep (e.g., daemon.log.1, .2, .3).
    """

    enabled: bool = DEFAULT_LOG_ROTATION_ENABLED
    max_size_mb: int = DEFAULT_LOG_MAX_SIZE_MB
    backup_count: int = DEFAULT_LOG_BACKUP_COUNT

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        self._validate()

    def _validate(self) -> None:
        """Validate configuration values.

        Raises:
            ValidationError: If any configuration value is invalid.
        """
        if self.max_size_mb < MIN_LOG_MAX_SIZE_MB:
            raise ValidationError(
                f"max_size_mb must be at least {MIN_LOG_MAX_SIZE_MB}",
                field="max_size_mb",
                value=self.max_size_mb,
                expected=f">= {MIN_LOG_MAX_SIZE_MB}",
            )
        if self.max_size_mb > MAX_LOG_MAX_SIZE_MB:
            raise ValidationError(
                f"max_size_mb must be at most {MAX_LOG_MAX_SIZE_MB}",
                field="max_size_mb",
                value=self.max_size_mb,
                expected=f"<= {MAX_LOG_MAX_SIZE_MB}",
            )
        if self.backup_count < 0:
            raise ValidationError(
                "backup_count cannot be negative",
                field="backup_count",
                value=self.backup_count,
                expected=">= 0",
            )
        if self.backup_count > MAX_LOG_BACKUP_COUNT:
            raise ValidationError(
                f"backup_count must be at most {MAX_LOG_BACKUP_COUNT}",
                field="backup_count",
                value=self.backup_count,
                expected=f"<= {MAX_LOG_BACKUP_COUNT}",
            )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LogRotationConfig":
        """Create config from dictionary.

        Args:
            data: Configuration dictionary.

        Returns:
            LogRotationConfig instance.
        """
        return cls(
            enabled=data.get("enabled", DEFAULT_LOG_ROTATION_ENABLED),
            max_size_mb=data.get("max_size_mb", DEFAULT_LOG_MAX_SIZE_MB),
            backup_count=data.get("backup_count", DEFAULT_LOG_BACKUP_COUNT),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "enabled": self.enabled,
            "max_size_mb": self.max_size_mb,
            "backup_count": self.backup_count,
        }

    def get_max_bytes(self) -> int:
        """Get maximum log file size in bytes.

        Returns:
            Maximum size in bytes (max_size_mb * 1024 * 1024).
        """
        return self.max_size_mb * 1024 * 1024


@dataclass
class BackupConfig:
    """Configuration for backup behavior.

    Controls automatic backups, activity inclusion, and scheduling.

    Attributes:
        auto_enabled: Whether automatic periodic backups are enabled.
        include_activities: Whether to include the activities table in backups.
        interval_minutes: Minutes between automatic backups.
        on_upgrade: Whether to create a backup before upgrades.
    """

    auto_enabled: bool = BACKUP_AUTO_ENABLED_DEFAULT
    include_activities: bool = BACKUP_INCLUDE_ACTIVITIES_DEFAULT
    interval_minutes: int = BACKUP_INTERVAL_MINUTES_DEFAULT
    on_upgrade: bool = BACKUP_ON_UPGRADE_DEFAULT

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        self._validate()

    def _validate(self) -> None:
        """Validate configuration values.

        Raises:
            ValidationError: If any configuration value is invalid.
        """
        if self.interval_minutes < BACKUP_INTERVAL_MINUTES_MIN:
            raise ValidationError(
                f"interval_minutes must be at least {BACKUP_INTERVAL_MINUTES_MIN}",
                field="interval_minutes",
                value=self.interval_minutes,
                expected=f">= {BACKUP_INTERVAL_MINUTES_MIN}",
            )
        if self.interval_minutes > BACKUP_INTERVAL_MINUTES_MAX:
            raise ValidationError(
                f"interval_minutes must be at most {BACKUP_INTERVAL_MINUTES_MAX}",
                field="interval_minutes",
                value=self.interval_minutes,
                expected=f"<= {BACKUP_INTERVAL_MINUTES_MAX}",
            )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BackupConfig":
        """Create config from dictionary.

        Args:
            data: Configuration dictionary.

        Returns:
            BackupConfig instance.
        """
        return cls(
            auto_enabled=data.get("auto_enabled", BACKUP_AUTO_ENABLED_DEFAULT),
            include_activities=data.get("include_activities", BACKUP_INCLUDE_ACTIVITIES_DEFAULT),
            interval_minutes=data.get("interval_minutes", BACKUP_INTERVAL_MINUTES_DEFAULT),
            on_upgrade=data.get("on_upgrade", BACKUP_ON_UPGRADE_DEFAULT),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "auto_enabled": self.auto_enabled,
            "include_activities": self.include_activities,
            "interval_minutes": self.interval_minutes,
            "on_upgrade": self.on_upgrade,
        }


@dataclass
class TunnelConfig:
    """Configuration for tunnel-based session sharing.

    Allows sharing the daemon UI via a public URL through cloudflared or ngrok.

    Attributes:
        provider: Tunnel provider (cloudflared, ngrok).
        auto_start: Whether to start tunnel automatically on daemon startup.
        cloudflared_path: Custom path to cloudflared binary (None = use PATH).
        ngrok_path: Custom path to ngrok binary (None = use PATH).
    """

    provider: str = DEFAULT_TUNNEL_PROVIDER
    auto_start: bool = False
    cloudflared_path: str | None = None
    ngrok_path: str | None = None

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        self._validate()

    def _validate(self) -> None:
        """Validate configuration values."""
        if self.provider not in VALID_TUNNEL_PROVIDERS:
            raise ValidationError(
                CI_TUNNEL_ERROR_INVALID_PROVIDER.format(provider=self.provider),
                field="provider",
                value=self.provider,
                expected=CI_TUNNEL_ERROR_INVALID_PROVIDER_EXPECTED.format(
                    providers=VALID_TUNNEL_PROVIDERS
                ),
            )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TunnelConfig":
        """Create config from dictionary."""
        return cls(
            provider=data.get(CI_CONFIG_TUNNEL_KEY_PROVIDER, DEFAULT_TUNNEL_PROVIDER),
            auto_start=data.get(CI_CONFIG_TUNNEL_KEY_AUTO_START, False),
            cloudflared_path=data.get(CI_CONFIG_TUNNEL_KEY_CLOUDFLARED_PATH),
            ngrok_path=data.get(CI_CONFIG_TUNNEL_KEY_NGROK_PATH),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            CI_CONFIG_TUNNEL_KEY_PROVIDER: self.provider,
            CI_CONFIG_TUNNEL_KEY_AUTO_START: self.auto_start,
            CI_CONFIG_TUNNEL_KEY_CLOUDFLARED_PATH: self.cloudflared_path,
            CI_CONFIG_TUNNEL_KEY_NGROK_PATH: self.ngrok_path,
        }


@dataclass
class CIConfig:
    """Codebase Intelligence configuration.

    Attributes:
        embedding: Embedding provider configuration.
        summarization: LLM summarization configuration.
        agents: Agent subsystem configuration.
        session_quality: Session quality threshold configuration.
        tunnel: Tunnel sharing configuration.
        backup: Backup behavior configuration.
        index_on_startup: Whether to build index when daemon starts.
        watch_files: Whether to watch files for changes.
        exclude_patterns: Glob patterns to exclude from indexing.
        cli_command: CLI executable used for CI-managed integrations.
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR).
        log_rotation: Log file rotation configuration.
    """

    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    summarization: SummarizationConfig = field(default_factory=SummarizationConfig)
    agents: AgentConfig = field(default_factory=AgentConfig)
    session_quality: SessionQualityConfig = field(default_factory=SessionQualityConfig)
    tunnel: TunnelConfig = field(default_factory=TunnelConfig)
    backup: BackupConfig = field(default_factory=BackupConfig)
    index_on_startup: bool = True
    watch_files: bool = True
    exclude_patterns: list[str] = field(default_factory=lambda: DEFAULT_EXCLUDE_PATTERNS.copy())
    cli_command: str = CI_CLI_COMMAND_DEFAULT
    log_level: str = LOG_LEVEL_INFO
    log_rotation: LogRotationConfig = field(default_factory=LogRotationConfig)

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

        if not self.cli_command:
            raise ValidationError(
                "CLI command cannot be empty",
                field=CI_CONFIG_KEY_CLI_COMMAND,
                value=self.cli_command,
                expected="non-empty executable name",
            )

        if not re.fullmatch(CI_CLI_COMMAND_VALIDATION_PATTERN, self.cli_command):
            raise ValidationError(
                f"Invalid CLI command: {self.cli_command}",
                field=CI_CONFIG_KEY_CLI_COMMAND,
                value=self.cli_command,
                expected=f"pattern {CI_CLI_COMMAND_VALIDATION_PATTERN}",
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
        agents_data = data.get("agents", {})
        session_quality_data = data.get("session_quality", {})
        tunnel_data = data.get(CI_CONFIG_KEY_TUNNEL, {})
        backup_data = data.get(BACKUP_CONFIG_KEY, {})
        log_rotation_data = data.get("log_rotation", {})
        return cls(
            embedding=EmbeddingConfig.from_dict(embedding_data),
            summarization=SummarizationConfig.from_dict(summarization_data),
            agents=AgentConfig.from_dict(agents_data),
            session_quality=SessionQualityConfig.from_dict(session_quality_data),
            tunnel=TunnelConfig.from_dict(tunnel_data),
            backup=BackupConfig.from_dict(backup_data),
            index_on_startup=data.get("index_on_startup", True),
            watch_files=data.get("watch_files", True),
            exclude_patterns=data.get("exclude_patterns", DEFAULT_EXCLUDE_PATTERNS.copy()),
            cli_command=data.get(CI_CONFIG_KEY_CLI_COMMAND, CI_CLI_COMMAND_DEFAULT),
            log_level=data.get("log_level", LOG_LEVEL_INFO),
            log_rotation=LogRotationConfig.from_dict(log_rotation_data),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "embedding": self.embedding.to_dict(),
            "summarization": self.summarization.to_dict(),
            "agents": self.agents.to_dict(),
            "session_quality": self.session_quality.to_dict(),
            CI_CONFIG_KEY_TUNNEL: self.tunnel.to_dict(),
            BACKUP_CONFIG_KEY: self.backup.to_dict(),
            "index_on_startup": self.index_on_startup,
            "watch_files": self.watch_files,
            "exclude_patterns": self.exclude_patterns,
            CI_CONFIG_KEY_CLI_COMMAND: self.cli_command,
            "log_level": self.log_level,
            "log_rotation": self.log_rotation.to_dict(),
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


# =============================================================================
# User Config Overlay System (RFC-001 Section 6)
# =============================================================================

# Dot-path notation for config sections/keys classified as user-local.
# Bare names = entire section is user-classified.
# Dotted names = only that leaf key within a mixed section.
# Everything NOT listed here is project-classified (team-shared) by default.
USER_CLASSIFIED_PATHS: frozenset[str] = frozenset(
    {
        "embedding",  # Model choice + dims are machine-dependent; vector DB is local
        "summarization",  # LLM model availability varies per machine
        "agents.provider_type",  # Agent LLM backend varies per machine
        "agents.provider_base_url",  # Agent LLM backend varies per machine
        "agents.provider_model",  # Agent LLM backend varies per machine
        "tunnel",  # Tunnel provider/paths are machine-local
        "log_level",  # Personal debugging preference
        "log_rotation",  # Machine-local log management
        "backup.auto_enabled",  # Personal preference for auto-backup
        "backup.include_activities",  # Personal preference for backup scope
        "backup.interval_minutes",  # Personal preference for backup frequency
    }
)


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge overlay onto base. Overlay wins for scalars/lists.

    Args:
        base: Base dictionary (not mutated).
        overlay: Overlay dictionary whose values take precedence.

    Returns:
        New merged dictionary.
    """
    result = dict(base)
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _split_by_classification(
    ci_dict: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split a CI config dict into user-classified and project-classified parts.

    Uses USER_CLASSIFIED_PATHS to determine classification. Bare names
    (e.g. "embedding") classify the entire section. Dotted names
    (e.g. "agents.provider_type") classify only that leaf key within
    a mixed section.

    Args:
        ci_dict: Full codebase_intelligence config dictionary.

    Returns:
        Tuple of (user_dict, project_dict) -- sparse dicts containing
        only the keys that belong to each classification.
    """
    user_dict: dict[str, Any] = {}
    project_dict: dict[str, Any] = {}

    for key, value in ci_dict.items():
        # Check if the entire section is user-classified
        if key in USER_CLASSIFIED_PATHS:
            user_dict[key] = value
            continue

        # Check if this section has mixed classification (dotted paths)
        dotted_prefix = f"{key}."
        dotted_keys = {
            p[len(dotted_prefix) :] for p in USER_CLASSIFIED_PATHS if p.startswith(dotted_prefix)
        }

        if dotted_keys and isinstance(value, dict):
            # Split the section: user-classified leaves vs project-classified leaves
            user_sub: dict[str, Any] = {}
            project_sub: dict[str, Any] = {}
            for sub_key, sub_value in value.items():
                if sub_key in dotted_keys:
                    user_sub[sub_key] = sub_value
                else:
                    project_sub[sub_key] = sub_value
            if user_sub:
                user_dict[key] = user_sub
            if project_sub:
                project_dict[key] = project_sub
        else:
            # Entirely project-classified
            project_dict[key] = value

    return user_dict, project_dict


def _user_config_path(project_root: Path) -> Path:
    """Get path to user config overlay file.

    Returns .oak/config.{machine_id}.yaml. The machine_id is imported
    lazily from the backup module.

    Args:
        project_root: Project root directory.

    Returns:
        Path to user config overlay file.
    """
    from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
        get_machine_identifier,
    )

    machine_id = get_machine_identifier(project_root)
    return project_root / OAK_DIR / f"config.{machine_id}.yaml"


def _write_yaml_config(path: Path, data: dict[str, Any]) -> None:
    """Write a dictionary to a YAML config file with inline short-list formatting.

    Args:
        path: File path to write.
        data: Dictionary to serialize.
    """

    class InlineListDumper(yaml.SafeDumper):
        pass

    def represent_list(dumper: yaml.SafeDumper, items: list[Any]) -> yaml.nodes.Node:
        # Keep short lists (<=3 items) inline, longer ones multi-line
        if len(items) <= 3:
            return dumper.represent_sequence("tag:yaml.org,2002:seq", items, flow_style=True)
        return dumper.represent_sequence("tag:yaml.org,2002:seq", items, flow_style=False)

    InlineListDumper.add_representer(list, represent_list)

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(
            data,
            f,
            Dumper=InlineListDumper,
            default_flow_style=False,
            sort_keys=False,
        )


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

        # Merge user overlay if it exists (user wins over project)
        user_file = _user_config_path(project_root)
        if user_file.exists():
            try:
                with open(user_file, encoding="utf-8") as f:
                    user_data = yaml.safe_load(f) or {}
                user_ci = user_data.get("codebase_intelligence", {})
                if user_ci:
                    ci_data = _deep_merge(ci_data, user_ci)
                    logger.debug(f"Merged user config overlay from {user_file}")
            except (yaml.YAMLError, OSError) as e:
                logger.warning(f"Corrupted user config overlay {user_file}, ignoring: {e}")

        config = CIConfig.from_dict(ci_data)
        logger.debug(
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


def save_ci_config(
    project_root: Path,
    config: CIConfig,
    *,
    force_project: bool = False,
) -> None:
    """Save Codebase Intelligence configuration to project.

    By default, splits user-classified keys into a machine-local overlay
    file (.oak/config.{machine_id}.yaml) and writes project-classified
    keys to .oak/config.yaml.

    Args:
        project_root: Project root directory.
        config: Configuration to save.
        force_project: If True, write ALL settings to the project config
            (team-shared baseline). Does not touch user overlay.
    """
    config_file = project_root / OAK_DIR / "config.yaml"

    # Load existing project config (preserves non-CI keys)
    existing_config: dict[str, Any] = {}
    if config_file.exists():
        try:
            with open(config_file, encoding="utf-8") as f:
                existing_config = yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"Failed to read existing config: {e}")

    ci_dict = config.to_dict()

    if force_project:
        # Write everything to project config as team baseline
        existing_config["codebase_intelligence"] = ci_dict
        _write_yaml_config(config_file, existing_config)
        logger.info(f"Saved full CI config to project file {config_file}")
    else:
        # Split user/project keys
        user_keys, project_keys = _split_by_classification(ci_dict)

        # Update project-classified keys in .oak/config.yaml while
        # preserving existing user-classified defaults for other machines
        existing_ci = existing_config.get("codebase_intelligence", {})
        if isinstance(existing_ci, dict):
            existing_config["codebase_intelligence"] = _deep_merge(existing_ci, project_keys)
        else:
            existing_config["codebase_intelligence"] = project_keys
        _write_yaml_config(config_file, existing_config)

        # Write user keys to .oak/config.{machine_id}.yaml
        if user_keys:
            user_file = _user_config_path(project_root)
            # Preserve other top-level keys in user overlay
            existing_user: dict[str, Any] = {}
            if user_file.exists():
                try:
                    with open(user_file, encoding="utf-8") as f:
                        existing_user = yaml.safe_load(f) or {}
                except Exception as e:
                    logger.warning(f"Failed to read existing user config: {e}")
            existing_user["codebase_intelligence"] = user_keys
            _write_yaml_config(user_file, existing_user)
            logger.info(f"Saved user CI config to {user_file}")

        logger.info(f"Saved project CI config to {config_file}")


def get_config_origins(project_root: Path) -> dict[str, str]:
    """Compute the origin of each config section for dashboard display.

    For each top-level CI config section, returns whether its current
    value comes from the user overlay, the project config, or defaults.

    For mixed sections (like ``agents``), returns ``"user"`` if any
    user-classified sub-key is present in the user overlay.

    Args:
        project_root: Project root directory.

    Returns:
        Dict mapping section names to ``"user"``, ``"project"``, or ``"default"``.
    """
    config_file = project_root / OAK_DIR / "config.yaml"

    # Load raw project CI data (no merge)
    project_ci: dict[str, Any] = {}
    if config_file.exists():
        try:
            with open(config_file, encoding="utf-8") as f:
                project_data = yaml.safe_load(f) or {}
            project_ci = project_data.get("codebase_intelligence", {})
        except (yaml.YAMLError, OSError):
            pass

    # Load raw user overlay CI data
    user_ci: dict[str, Any] = {}
    try:
        user_file = _user_config_path(project_root)
        if user_file.exists():
            with open(user_file, encoding="utf-8") as f:
                user_data = yaml.safe_load(f) or {}
            user_ci = user_data.get("codebase_intelligence", {})
    except (yaml.YAMLError, OSError):
        pass

    # All top-level sections in CIConfig
    all_sections = [
        "embedding",
        "summarization",
        "agents",
        "session_quality",
        "tunnel",
        "backup",
        "index_on_startup",
        "watch_files",
        "exclude_patterns",
        CI_CONFIG_KEY_CLI_COMMAND,
        "log_level",
        "log_rotation",
    ]

    origins: dict[str, str] = {}
    for section in all_sections:
        # Check if any user-classified key for this section exists in user overlay
        if section in USER_CLASSIFIED_PATHS:
            # Entire section is user-classified
            if section in user_ci:
                origins[section] = "user"
            elif section in project_ci:
                origins[section] = "project"
            else:
                origins[section] = "default"
        else:
            # Check for dotted paths (mixed section like agents)
            dotted_prefix = f"{section}."
            user_sub_keys = {
                p[len(dotted_prefix) :]
                for p in USER_CLASSIFIED_PATHS
                if p.startswith(dotted_prefix)
            }
            if user_sub_keys:
                # Mixed section: "user" if any user-classified sub-key in overlay
                section_user_data = user_ci.get(section, {})
                if isinstance(section_user_data, dict) and any(
                    k in section_user_data for k in user_sub_keys
                ):
                    origins[section] = "user"
                elif section in project_ci:
                    origins[section] = "project"
                else:
                    origins[section] = "default"
            else:
                # Entirely project-classified
                if section in project_ci:
                    origins[section] = "project"
                else:
                    origins[section] = "default"

    return origins
