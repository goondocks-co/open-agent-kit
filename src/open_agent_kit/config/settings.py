"""Runtime configuration settings for open-agent-kit.

This module uses Pydantic Settings for configuration that can be
overridden via environment variables. This provides:
- Type validation
- Environment variable support (OAK_ prefix)
- Default values
- Easy testing via dependency injection
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class IssueProviderSettings(BaseSettings):
    """Issue provider API settings.

    These settings control HTTP behavior for issue provider APIs.
    Can be overridden via environment variables with OAK_ prefix.

    Example:
        OAK_ISSUE_TIMEOUT_SECONDS=30.0
        OAK_ISSUE_MAX_RETRIES=5
    """

    model_config = SettingsConfigDict(env_prefix="OAK_ISSUE_")

    timeout_seconds: float = Field(
        default=20.0,
        description="HTTP request timeout in seconds",
    )
    max_retries: int = Field(
        default=3,
        description="Maximum retry attempts for failed requests",
    )
    retry_min_wait_seconds: float = Field(
        default=1.0,
        description="Minimum wait time between retries",
    )
    retry_max_wait_seconds: float = Field(
        default=10.0,
        description="Maximum wait time between retries",
    )
    user_agent: str = Field(
        default="open-agent-kit/{version}",
        description="User-Agent header template (format with VERSION at runtime)",
    )


class GitSettings(BaseSettings):
    """Git operation settings.

    These settings control git command behavior.
    Can be overridden via environment variables with OAK_GIT_ prefix.
    """

    model_config = SettingsConfigDict(env_prefix="OAK_GIT_")

    command_timeout_seconds: float = Field(
        default=30.0,
        description="Git command timeout in seconds",
    )


class ValidationSettings(BaseSettings):
    """Validation settings.

    These settings control validation behavior.
    Can be overridden via environment variables with OAK_VALIDATION_ prefix.
    """

    model_config = SettingsConfigDict(env_prefix="OAK_VALIDATION_")

    issue_notes_max_length: int = Field(
        default=10000,
        description="Maximum characters for issue notes",
    )
    rfc_stale_draft_days: int = Field(
        default=60,
        description="Days after which a draft RFC is considered stale",
    )
    constitution_min_sentences: int = Field(
        default=2,
        description="Minimum sentences per constitution section",
    )


# Singleton instances for easy import
issue_provider_settings = IssueProviderSettings()
git_settings = GitSettings()
validation_settings = ValidationSettings()
