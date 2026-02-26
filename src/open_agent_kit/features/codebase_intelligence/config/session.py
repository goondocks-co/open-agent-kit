"""Session quality and auto-resolve configuration for Codebase Intelligence."""

from dataclasses import dataclass
from typing import Any

from open_agent_kit.features.codebase_intelligence.constants import (
    AUTO_RESOLVE_SEARCH_LIMIT,
    AUTO_RESOLVE_SEARCH_LIMIT_MAX,
    AUTO_RESOLVE_SEARCH_LIMIT_MIN,
    AUTO_RESOLVE_SIMILARITY_MAX,
    AUTO_RESOLVE_SIMILARITY_MIN,
    AUTO_RESOLVE_SIMILARITY_THRESHOLD,
    AUTO_RESOLVE_SIMILARITY_THRESHOLD_NO_CONTEXT,
    MIN_SESSION_ACTIVITIES,
    SESSION_INACTIVE_TIMEOUT_SECONDS,
)
from open_agent_kit.features.codebase_intelligence.exceptions import (
    ValidationError,
)

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
class AutoResolveConfig:
    """Configuration for automatic observation supersession.

    When a new observation is stored, the system searches for semantically
    similar active observations and marks them as superseded.

    Attributes:
        enabled: Whether auto-resolve is enabled.
        similarity_threshold: Similarity threshold for observations with matching context.
        similarity_threshold_no_context: Similarity threshold when context is absent.
        search_limit: Maximum candidates to search per new observation.
    """

    enabled: bool = True
    similarity_threshold: float = AUTO_RESOLVE_SIMILARITY_THRESHOLD
    similarity_threshold_no_context: float = AUTO_RESOLVE_SIMILARITY_THRESHOLD_NO_CONTEXT
    search_limit: int = AUTO_RESOLVE_SEARCH_LIMIT

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        self._validate()

    def _validate(self) -> None:
        """Validate configuration values.

        Raises:
            ValidationError: If any configuration value is invalid.
        """
        for field_name, value in [
            ("similarity_threshold", self.similarity_threshold),
            ("similarity_threshold_no_context", self.similarity_threshold_no_context),
        ]:
            if not (AUTO_RESOLVE_SIMILARITY_MIN <= value <= AUTO_RESOLVE_SIMILARITY_MAX):
                raise ValidationError(
                    f"{field_name} must be between {AUTO_RESOLVE_SIMILARITY_MIN} "
                    f"and {AUTO_RESOLVE_SIMILARITY_MAX}",
                    field=field_name,
                    value=value,
                    expected=f">= {AUTO_RESOLVE_SIMILARITY_MIN} and <= {AUTO_RESOLVE_SIMILARITY_MAX}",
                )
        if self.similarity_threshold_no_context < self.similarity_threshold:
            raise ValidationError(
                "similarity_threshold_no_context must be >= similarity_threshold",
                field="similarity_threshold_no_context",
                value=self.similarity_threshold_no_context,
                expected=f">= {self.similarity_threshold}",
            )
        if not (
            AUTO_RESOLVE_SEARCH_LIMIT_MIN <= self.search_limit <= AUTO_RESOLVE_SEARCH_LIMIT_MAX
        ):
            raise ValidationError(
                f"search_limit must be between {AUTO_RESOLVE_SEARCH_LIMIT_MIN} "
                f"and {AUTO_RESOLVE_SEARCH_LIMIT_MAX}",
                field="search_limit",
                value=self.search_limit,
                expected=f">= {AUTO_RESOLVE_SEARCH_LIMIT_MIN} and <= {AUTO_RESOLVE_SEARCH_LIMIT_MAX}",
            )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AutoResolveConfig":
        """Create config from dictionary.

        Args:
            data: Configuration dictionary.

        Returns:
            AutoResolveConfig instance.
        """
        return cls(
            enabled=data.get("enabled", True),
            similarity_threshold=data.get(
                "similarity_threshold", AUTO_RESOLVE_SIMILARITY_THRESHOLD
            ),
            similarity_threshold_no_context=data.get(
                "similarity_threshold_no_context", AUTO_RESOLVE_SIMILARITY_THRESHOLD_NO_CONTEXT
            ),
            search_limit=data.get("search_limit", AUTO_RESOLVE_SEARCH_LIMIT),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "enabled": self.enabled,
            "similarity_threshold": self.similarity_threshold,
            "similarity_threshold_no_context": self.similarity_threshold_no_context,
            "search_limit": self.search_limit,
        }
