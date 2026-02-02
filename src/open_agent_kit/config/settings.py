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

    rfc_stale_draft_days: int = Field(
        default=60,
        description="Days after which a draft RFC is considered stale",
    )
    constitution_min_sentences: int = Field(
        default=2,
        description="Minimum sentences per constitution section",
    )


# Singleton instances for easy import
git_settings = GitSettings()
validation_settings = ValidationSettings()
