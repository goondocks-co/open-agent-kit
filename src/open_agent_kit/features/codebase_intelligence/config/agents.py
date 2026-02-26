"""Agent configuration for Codebase Intelligence."""

from dataclasses import dataclass
from typing import Any

from open_agent_kit.features.codebase_intelligence.constants import (
    DEFAULT_AGENT_MAX_TURNS,
    DEFAULT_AGENT_TIMEOUT_SECONDS,
    DEFAULT_BACKGROUND_PROCESSING_INTERVAL_SECONDS,
    DEFAULT_BACKGROUND_PROCESSING_WORKERS,
    DEFAULT_EXECUTOR_CACHE_SIZE,
    DEFAULT_SCHEDULER_INTERVAL_SECONDS,
    MAX_AGENT_MAX_TURNS,
    MAX_AGENT_TIMEOUT_SECONDS,
    MAX_BACKGROUND_PROCESSING_INTERVAL_SECONDS,
    MAX_BACKGROUND_PROCESSING_WORKERS,
    MAX_EXECUTOR_CACHE_SIZE,
    MAX_SCHEDULER_INTERVAL_SECONDS,
    MIN_AGENT_TIMEOUT_SECONDS,
    MIN_BACKGROUND_PROCESSING_INTERVAL_SECONDS,
    MIN_BACKGROUND_PROCESSING_WORKERS,
    MIN_EXECUTOR_CACHE_SIZE,
    MIN_SCHEDULER_INTERVAL_SECONDS,
)
from open_agent_kit.features.codebase_intelligence.exceptions import (
    ValidationError,
)


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
        background_processing_workers: Number of parallel threads for batch processing.
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
    background_processing_workers: int = DEFAULT_BACKGROUND_PROCESSING_WORKERS
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
        # Validate background processing workers
        if self.background_processing_workers < MIN_BACKGROUND_PROCESSING_WORKERS:
            raise ValidationError(
                f"background_processing_workers must be at least "
                f"{MIN_BACKGROUND_PROCESSING_WORKERS}",
                field="background_processing_workers",
                value=self.background_processing_workers,
                expected=f">= {MIN_BACKGROUND_PROCESSING_WORKERS}",
            )
        if self.background_processing_workers > MAX_BACKGROUND_PROCESSING_WORKERS:
            raise ValidationError(
                f"background_processing_workers must be at most "
                f"{MAX_BACKGROUND_PROCESSING_WORKERS}",
                field="background_processing_workers",
                value=self.background_processing_workers,
                expected=f"<= {MAX_BACKGROUND_PROCESSING_WORKERS}",
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
            background_processing_workers=data.get(
                "background_processing_workers",
                DEFAULT_BACKGROUND_PROCESSING_WORKERS,
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
            "background_processing_workers": self.background_processing_workers,
            "provider_type": self.provider_type,
            "provider_base_url": self.provider_base_url,
            "provider_model": self.provider_model,
        }
