"""CIConfig — top-level Team configuration."""

import os
import re
from dataclasses import dataclass, field
from typing import Any

from open_agent_kit.features.team.config.agents import AgentConfig
from open_agent_kit.features.team.config.embedding import EmbeddingConfig
from open_agent_kit.features.team.config.governance import GovernanceConfig
from open_agent_kit.features.team.config.infrastructure import (
    BackupConfig,
    CloudRelayConfig,
    LogRotationConfig,
)
from open_agent_kit.features.team.config.io import DEFAULT_EXCLUDE_PATTERNS
from open_agent_kit.features.team.config.session import (
    AutoResolveConfig,
    SessionQualityConfig,
)
from open_agent_kit.features.team.config.summarization import SummarizationConfig
from open_agent_kit.features.team.config.team import TeamConfig
from open_agent_kit.features.team.constants import (
    AUTO_RESOLVE_CONFIG_KEY,
    BACKUP_CONFIG_KEY,
    CI_CLI_COMMAND_DEFAULT,
    CI_CLI_COMMAND_VALIDATION_PATTERN,
    CI_CONFIG_KEY_AGENTS,
    CI_CONFIG_KEY_CLI_COMMAND,
    CI_CONFIG_KEY_CLOUD_RELAY,
    CI_CONFIG_KEY_EMBEDDING,
    CI_CONFIG_KEY_EXCLUDE_PATTERNS,
    CI_CONFIG_KEY_GOVERNANCE,
    CI_CONFIG_KEY_LOG_LEVEL,
    CI_CONFIG_KEY_LOG_ROTATION,
    CI_CONFIG_KEY_SESSION_QUALITY,
    CI_CONFIG_KEY_SUMMARIZATION,
    CI_CONFIG_KEY_TEAM,
    LOG_LEVEL_DEBUG,
    LOG_LEVEL_INFO,
    VALID_LOG_LEVELS,
)
from open_agent_kit.features.team.exceptions import (
    ValidationError,
)


@dataclass
class CIConfig:
    """Team configuration.

    Attributes:
        embedding: Embedding provider configuration.
        summarization: LLM summarization configuration.
        agents: Agent subsystem configuration.
        session_quality: Session quality threshold configuration.
        cloud_relay: Cloud MCP Relay configuration.
        team: Oak Teams sync configuration.
        backup: Backup behavior configuration.
        auto_resolve: Auto-resolve (supersession) configuration.
        governance: Agent governance (observability and enforcement) configuration.
        exclude_patterns: Glob patterns to exclude from indexing.
        cli_command: CLI executable used for CI-managed integrations.
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR).
        log_rotation: Log file rotation configuration.
    """

    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    summarization: SummarizationConfig = field(default_factory=SummarizationConfig)
    agents: AgentConfig = field(default_factory=AgentConfig)
    session_quality: SessionQualityConfig = field(default_factory=SessionQualityConfig)
    cloud_relay: CloudRelayConfig = field(default_factory=CloudRelayConfig)
    team: TeamConfig = field(default_factory=TeamConfig)
    backup: BackupConfig = field(default_factory=BackupConfig)
    auto_resolve: AutoResolveConfig = field(default_factory=AutoResolveConfig)
    governance: GovernanceConfig = field(default_factory=GovernanceConfig)
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
                field=CI_CONFIG_KEY_LOG_LEVEL,
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
        embedding_data = data.get(CI_CONFIG_KEY_EMBEDDING, {})
        summarization_data = data.get(CI_CONFIG_KEY_SUMMARIZATION, {})
        agents_data = data.get(CI_CONFIG_KEY_AGENTS, {})
        session_quality_data = data.get(CI_CONFIG_KEY_SESSION_QUALITY, {})
        cloud_relay_data = data.get(CI_CONFIG_KEY_CLOUD_RELAY, {})
        team_data = data.get(CI_CONFIG_KEY_TEAM, {})
        backup_data = data.get(BACKUP_CONFIG_KEY, {})
        auto_resolve_data = data.get(AUTO_RESOLVE_CONFIG_KEY, {})
        governance_data = data.get(CI_CONFIG_KEY_GOVERNANCE, {})
        log_rotation_data = data.get(CI_CONFIG_KEY_LOG_ROTATION, {})
        return cls(
            embedding=EmbeddingConfig.from_dict(embedding_data),
            summarization=SummarizationConfig.from_dict(summarization_data),
            agents=AgentConfig.from_dict(agents_data),
            session_quality=SessionQualityConfig.from_dict(session_quality_data),
            cloud_relay=CloudRelayConfig.from_dict(cloud_relay_data),
            team=TeamConfig.from_dict(team_data),
            backup=BackupConfig.from_dict(backup_data),
            auto_resolve=AutoResolveConfig.from_dict(auto_resolve_data),
            governance=GovernanceConfig.from_dict(governance_data),
            exclude_patterns=data.get(
                CI_CONFIG_KEY_EXCLUDE_PATTERNS, DEFAULT_EXCLUDE_PATTERNS.copy()
            ),
            cli_command=data.get(CI_CONFIG_KEY_CLI_COMMAND, CI_CLI_COMMAND_DEFAULT),
            log_level=data.get(CI_CONFIG_KEY_LOG_LEVEL, LOG_LEVEL_INFO),
            log_rotation=LogRotationConfig.from_dict(log_rotation_data),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            CI_CONFIG_KEY_EMBEDDING: self.embedding.to_dict(),
            CI_CONFIG_KEY_SUMMARIZATION: self.summarization.to_dict(),
            CI_CONFIG_KEY_AGENTS: self.agents.to_dict(),
            CI_CONFIG_KEY_SESSION_QUALITY: self.session_quality.to_dict(),
            CI_CONFIG_KEY_CLOUD_RELAY: self.cloud_relay.to_dict(),
            CI_CONFIG_KEY_TEAM: self.team.to_dict(),
            BACKUP_CONFIG_KEY: self.backup.to_dict(),
            AUTO_RESOLVE_CONFIG_KEY: self.auto_resolve.to_dict(),
            CI_CONFIG_KEY_GOVERNANCE: self.governance.to_dict(),
            CI_CONFIG_KEY_EXCLUDE_PATTERNS: self.exclude_patterns,
            CI_CONFIG_KEY_CLI_COMMAND: self.cli_command,
            CI_CONFIG_KEY_LOG_LEVEL: self.log_level,
            CI_CONFIG_KEY_LOG_ROTATION: self.log_rotation.to_dict(),
        }

    def resolve_relay_credentials(self) -> tuple[str | None, str | None]:
        """Resolve relay URL and token from publisher or consumer config.

        Publisher stores credentials in ``cloud_relay.*``; consumer stores
        in ``team.*``.  Returns whichever source has them, preferring the
        canonical (custom-domain) URL when available.

        Returns:
            (worker_url, token) — either or both may be ``None``.
        """
        worker_url = self.cloud_relay.canonical_url or self.team.relay_worker_url
        token = self.cloud_relay.token or self.team.api_key
        return worker_url, token

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
        1. OAK_CI_DEBUG=1 -> DEBUG
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
