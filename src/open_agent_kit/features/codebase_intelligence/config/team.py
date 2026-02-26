"""Team sync configuration for Codebase Intelligence."""

import logging
import os
from dataclasses import dataclass
from typing import Any

from open_agent_kit.features.codebase_intelligence.constants.team import (
    CI_CONFIG_TEAM_KEY_AUTO_SYNC,
    CI_CONFIG_TEAM_KEY_BIND_HOST,
    CI_CONFIG_TEAM_KEY_BIND_PORT,
    CI_CONFIG_TEAM_KEY_PROJECT_SLUG,
    CI_CONFIG_TEAM_KEY_PULL_INTERVAL,
    CI_CONFIG_TEAM_KEY_RELAY_WORKER_NAME,
    CI_CONFIG_TEAM_KEY_RELAY_WORKER_URL,
    CI_CONFIG_TEAM_KEY_SERVER_MODE,
    CI_CONFIG_TEAM_KEY_SERVER_SIDE_LLM,
    CI_CONFIG_TEAM_KEY_SERVER_URL,
    CI_CONFIG_TEAM_KEY_SYNC_INTERVAL,
    CI_CONFIG_TEAM_KEY_TOKEN,
    CI_CONFIG_TEAM_KEY_TRANSPORT,
    TEAM_DEFAULT_BIND_HOST,
    TEAM_DEFAULT_BIND_PORT,
    TEAM_DEFAULT_PULL_INTERVAL_SECONDS,
    TEAM_DEFAULT_SYNC_INTERVAL_SECONDS,
    TEAM_ERROR_INVALID_TRANSPORT,
    TEAM_ERROR_INVALID_TRANSPORT_EXPECTED,
    TEAM_ERROR_PULL_INTERVAL_RANGE,
    TEAM_ERROR_RELAY_URL_REQUIRED,
    TEAM_ERROR_SYNC_INTERVAL_RANGE,
    TEAM_MAX_PULL_INTERVAL_SECONDS,
    TEAM_MAX_SYNC_INTERVAL_SECONDS,
    TEAM_MIN_PULL_INTERVAL_SECONDS,
    TEAM_MIN_SYNC_INTERVAL_SECONDS,
    TEAM_TRANSPORT_DIRECT,
    TEAM_TRANSPORT_RELAY,
    VALID_TEAM_TRANSPORTS,
)
from open_agent_kit.features.codebase_intelligence.exceptions import (
    ValidationError,
)

logger = logging.getLogger(__name__)


@dataclass
class TeamConfig:
    """Configuration for Oak Teams sync.

    Allows syncing observations and session summaries between team members
    via a shared team server or relay.

    Attributes:
        server_url: URL of the team server.
        token: Authentication token (supports ${ENV_VAR} syntax).
        auto_sync: Whether to start sync automatically on daemon startup.
        sync_interval_seconds: Seconds between outbox flush cycles.
        pull_interval_seconds: Seconds between pull cycles.
        project_slug: Project identifier override (defaults to directory name).
        transport: Transport type (direct or relay).
        server_mode: Whether this instance acts as the team server.
        bind_host: Host to bind server on (server mode only).
        bind_port: Port to bind server on (server mode only).
        relay_worker_url: URL of the relay worker (relay transport only).
        relay_worker_name: Name of the relay worker.
        server_side_llm: Whether the server provides LLM summarization.
    """

    server_url: str | None = None
    token: str | None = None
    auto_sync: bool = False
    sync_interval_seconds: int = TEAM_DEFAULT_SYNC_INTERVAL_SECONDS
    pull_interval_seconds: int = TEAM_DEFAULT_PULL_INTERVAL_SECONDS
    project_slug: str | None = None
    transport: str = TEAM_TRANSPORT_DIRECT
    server_mode: bool = False
    bind_host: str = TEAM_DEFAULT_BIND_HOST
    bind_port: int = TEAM_DEFAULT_BIND_PORT
    relay_worker_url: str | None = None
    relay_worker_name: str | None = None
    server_side_llm: bool = False

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        self._validate()

    def _validate(self) -> None:
        """Validate configuration values.

        Raises:
            ValidationError: If any configuration value is invalid.
        """
        if self.transport not in VALID_TEAM_TRANSPORTS:
            raise ValidationError(
                TEAM_ERROR_INVALID_TRANSPORT.format(transport=self.transport),
                field=CI_CONFIG_TEAM_KEY_TRANSPORT,
                value=self.transport,
                expected=TEAM_ERROR_INVALID_TRANSPORT_EXPECTED.format(
                    transports=VALID_TEAM_TRANSPORTS
                ),
            )

        if self.transport == TEAM_TRANSPORT_RELAY and not self.relay_worker_url:
            raise ValidationError(
                TEAM_ERROR_RELAY_URL_REQUIRED,
                field=CI_CONFIG_TEAM_KEY_RELAY_WORKER_URL,
                value=self.relay_worker_url,
                expected="non-empty URL",
            )

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

        if not (
            TEAM_MIN_PULL_INTERVAL_SECONDS
            <= self.pull_interval_seconds
            <= TEAM_MAX_PULL_INTERVAL_SECONDS
        ):
            raise ValidationError(
                TEAM_ERROR_PULL_INTERVAL_RANGE.format(
                    min=TEAM_MIN_PULL_INTERVAL_SECONDS,
                    max=TEAM_MAX_PULL_INTERVAL_SECONDS,
                ),
                field=CI_CONFIG_TEAM_KEY_PULL_INTERVAL,
                value=self.pull_interval_seconds,
                expected=f"{TEAM_MIN_PULL_INTERVAL_SECONDS}-{TEAM_MAX_PULL_INTERVAL_SECONDS}",
            )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TeamConfig":
        """Create config from dictionary.

        Args:
            data: Configuration dictionary.

        Returns:
            TeamConfig instance.
        """
        # Resolve environment variables in token
        token = data.get(CI_CONFIG_TEAM_KEY_TOKEN)
        if token and token.startswith("${") and token.endswith("}"):
            env_var = token[2:-1]
            token = os.environ.get(env_var)

        return cls(
            server_url=data.get(CI_CONFIG_TEAM_KEY_SERVER_URL),
            token=token,
            auto_sync=data.get(CI_CONFIG_TEAM_KEY_AUTO_SYNC, False),
            sync_interval_seconds=data.get(
                CI_CONFIG_TEAM_KEY_SYNC_INTERVAL,
                TEAM_DEFAULT_SYNC_INTERVAL_SECONDS,
            ),
            pull_interval_seconds=data.get(
                CI_CONFIG_TEAM_KEY_PULL_INTERVAL,
                TEAM_DEFAULT_PULL_INTERVAL_SECONDS,
            ),
            project_slug=data.get(CI_CONFIG_TEAM_KEY_PROJECT_SLUG),
            transport=data.get(CI_CONFIG_TEAM_KEY_TRANSPORT, TEAM_TRANSPORT_DIRECT),
            server_mode=data.get(CI_CONFIG_TEAM_KEY_SERVER_MODE, False),
            bind_host=data.get(CI_CONFIG_TEAM_KEY_BIND_HOST, TEAM_DEFAULT_BIND_HOST),
            bind_port=data.get(CI_CONFIG_TEAM_KEY_BIND_PORT, TEAM_DEFAULT_BIND_PORT),
            relay_worker_url=data.get(CI_CONFIG_TEAM_KEY_RELAY_WORKER_URL),
            relay_worker_name=data.get(CI_CONFIG_TEAM_KEY_RELAY_WORKER_NAME),
            server_side_llm=data.get(CI_CONFIG_TEAM_KEY_SERVER_SIDE_LLM, False),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            CI_CONFIG_TEAM_KEY_SERVER_URL: self.server_url,
            CI_CONFIG_TEAM_KEY_TOKEN: self.token,
            CI_CONFIG_TEAM_KEY_AUTO_SYNC: self.auto_sync,
            CI_CONFIG_TEAM_KEY_SYNC_INTERVAL: self.sync_interval_seconds,
            CI_CONFIG_TEAM_KEY_PULL_INTERVAL: self.pull_interval_seconds,
            CI_CONFIG_TEAM_KEY_PROJECT_SLUG: self.project_slug,
            CI_CONFIG_TEAM_KEY_TRANSPORT: self.transport,
            CI_CONFIG_TEAM_KEY_SERVER_MODE: self.server_mode,
            CI_CONFIG_TEAM_KEY_BIND_HOST: self.bind_host,
            CI_CONFIG_TEAM_KEY_BIND_PORT: self.bind_port,
            CI_CONFIG_TEAM_KEY_RELAY_WORKER_URL: self.relay_worker_url,
            CI_CONFIG_TEAM_KEY_RELAY_WORKER_NAME: self.relay_worker_name,
            CI_CONFIG_TEAM_KEY_SERVER_SIDE_LLM: self.server_side_llm,
        }
