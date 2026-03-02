"""Team sync configuration for Codebase Intelligence."""

import logging
import os
from dataclasses import dataclass
from typing import Any

from open_agent_kit.features.codebase_intelligence.constants.team import (
    CI_CONFIG_TEAM_KEY_API_KEY,
    CI_CONFIG_TEAM_KEY_AUTO_SYNC,
    CI_CONFIG_TEAM_KEY_KEEP_RELAY_ALIVE,
    CI_CONFIG_TEAM_KEY_PROJECT_SLUG,
    CI_CONFIG_TEAM_KEY_RELAY_WORKER_NAME,
    CI_CONFIG_TEAM_KEY_RELAY_WORKER_URL,
    CI_CONFIG_TEAM_KEY_SERVER_URL,
    CI_CONFIG_TEAM_KEY_SYNC_INTERVAL,
    TEAM_DEFAULT_SYNC_INTERVAL_SECONDS,
    TEAM_ERROR_SYNC_INTERVAL_RANGE,
    TEAM_MAX_SYNC_INTERVAL_SECONDS,
    TEAM_MIN_SYNC_INTERVAL_SECONDS,
)
from open_agent_kit.features.codebase_intelligence.exceptions import (
    ValidationError,
)

logger = logging.getLogger(__name__)


@dataclass
class TeamConfig:
    """Configuration for Oak Teams sync.

    Allows syncing observations between team members via a cloud relay.

    Attributes:
        server_url: URL of the team server.
        api_key: Team API key (supports ${ENV_VAR} syntax).
        auto_sync: Whether to start sync automatically on daemon startup.
        sync_interval_seconds: Seconds between outbox flush cycles.
        project_slug: Project identifier override (defaults to directory name).
        relay_worker_url: URL of the relay worker.
        relay_worker_name: Name of the relay worker.
        keep_relay_alive: If True, skip suspending team subsystems during
            power sleep states. Keeps the relay connected and sync worker
            running so the daemon stays reachable by teammates.
    """

    server_url: str | None = None
    api_key: str | None = None
    auto_sync: bool = False
    sync_interval_seconds: int = TEAM_DEFAULT_SYNC_INTERVAL_SECONDS
    project_slug: str | None = None
    relay_worker_url: str | None = None
    relay_worker_name: str | None = None
    keep_relay_alive: bool = False

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        self._validate()

    def _validate(self) -> None:
        """Validate configuration values.

        Raises:
            ValidationError: If any configuration value is invalid.
        """
        if not (
            TEAM_MIN_SYNC_INTERVAL_SECONDS
            <= self.sync_interval_seconds
            <= TEAM_MAX_SYNC_INTERVAL_SECONDS
        ):
            raise ValidationError(
                TEAM_ERROR_SYNC_INTERVAL_RANGE.format(
                    min=TEAM_MIN_SYNC_INTERVAL_SECONDS,
                    max=TEAM_MAX_SYNC_INTERVAL_SECONDS,
                ),
                field=CI_CONFIG_TEAM_KEY_SYNC_INTERVAL,
                value=self.sync_interval_seconds,
                expected=f"{TEAM_MIN_SYNC_INTERVAL_SECONDS}-{TEAM_MAX_SYNC_INTERVAL_SECONDS}",
            )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TeamConfig":
        """Create config from dictionary.

        Args:
            data: Configuration dictionary.

        Returns:
            TeamConfig instance.
        """
        # Resolve environment variables in team API key
        api_key = data.get(CI_CONFIG_TEAM_KEY_API_KEY)
        if api_key and api_key.startswith("${") and api_key.endswith("}"):
            env_var = api_key[2:-1]
            api_key = os.environ.get(env_var)

        return cls(
            server_url=data.get(CI_CONFIG_TEAM_KEY_SERVER_URL),
            api_key=api_key,
            auto_sync=data.get(CI_CONFIG_TEAM_KEY_AUTO_SYNC, False),
            sync_interval_seconds=data.get(
                CI_CONFIG_TEAM_KEY_SYNC_INTERVAL,
                TEAM_DEFAULT_SYNC_INTERVAL_SECONDS,
            ),
            project_slug=data.get(CI_CONFIG_TEAM_KEY_PROJECT_SLUG),
            relay_worker_url=data.get(CI_CONFIG_TEAM_KEY_RELAY_WORKER_URL),
            relay_worker_name=data.get(CI_CONFIG_TEAM_KEY_RELAY_WORKER_NAME),
            keep_relay_alive=data.get(CI_CONFIG_TEAM_KEY_KEEP_RELAY_ALIVE, False),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            CI_CONFIG_TEAM_KEY_SERVER_URL: self.server_url,
            CI_CONFIG_TEAM_KEY_API_KEY: self.api_key,
            CI_CONFIG_TEAM_KEY_AUTO_SYNC: self.auto_sync,
            CI_CONFIG_TEAM_KEY_SYNC_INTERVAL: self.sync_interval_seconds,
            CI_CONFIG_TEAM_KEY_PROJECT_SLUG: self.project_slug,
            CI_CONFIG_TEAM_KEY_RELAY_WORKER_URL: self.relay_worker_url,
            CI_CONFIG_TEAM_KEY_RELAY_WORKER_NAME: self.relay_worker_name,
            CI_CONFIG_TEAM_KEY_KEEP_RELAY_ALIVE: self.keep_relay_alive,
        }
