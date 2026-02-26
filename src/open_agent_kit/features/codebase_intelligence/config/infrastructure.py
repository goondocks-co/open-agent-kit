"""Infrastructure configuration for Codebase Intelligence.

Contains LogRotationConfig, BackupConfig, TunnelConfig, and CloudRelayConfig.
"""

import logging
import os
from dataclasses import dataclass
from typing import Any

from open_agent_kit.features.codebase_intelligence.constants import (
    BACKUP_AUTO_ENABLED_DEFAULT,
    BACKUP_INCLUDE_ACTIVITIES_DEFAULT,
    BACKUP_INTERVAL_MINUTES_DEFAULT,
    BACKUP_INTERVAL_MINUTES_MAX,
    BACKUP_INTERVAL_MINUTES_MIN,
    BACKUP_ON_UPGRADE_DEFAULT,
    CI_CONFIG_CLOUD_RELAY_KEY_AGENT_TOKEN,
    CI_CONFIG_CLOUD_RELAY_KEY_AUTO_CONNECT,
    CI_CONFIG_CLOUD_RELAY_KEY_CUSTOM_DOMAIN,
    CI_CONFIG_CLOUD_RELAY_KEY_RECONNECT_MAX,
    CI_CONFIG_CLOUD_RELAY_KEY_TOKEN,
    CI_CONFIG_CLOUD_RELAY_KEY_TOOL_TIMEOUT,
    CI_CONFIG_CLOUD_RELAY_KEY_WORKER_NAME,
    CI_CONFIG_CLOUD_RELAY_KEY_WORKER_URL,
    CI_CONFIG_TUNNEL_KEY_AUTO_START,
    CI_CONFIG_TUNNEL_KEY_CLOUDFLARED_PATH,
    CI_CONFIG_TUNNEL_KEY_NGROK_PATH,
    CI_CONFIG_TUNNEL_KEY_PROVIDER,
    CI_TUNNEL_ERROR_INVALID_PROVIDER,
    CI_TUNNEL_ERROR_INVALID_PROVIDER_EXPECTED,
    CLOUD_RELAY_DEFAULT_RECONNECT_MAX_SECONDS,
    CLOUD_RELAY_DEFAULT_TOOL_TIMEOUT_SECONDS,
    DEFAULT_LOG_BACKUP_COUNT,
    DEFAULT_LOG_MAX_SIZE_MB,
    DEFAULT_LOG_ROTATION_ENABLED,
    DEFAULT_TUNNEL_PROVIDER,
    MAX_LOG_BACKUP_COUNT,
    MAX_LOG_MAX_SIZE_MB,
    MIN_LOG_MAX_SIZE_MB,
    VALID_TUNNEL_PROVIDERS,
)
from open_agent_kit.features.codebase_intelligence.exceptions import (
    ValidationError,
)

logger = logging.getLogger(__name__)


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
class CloudRelayConfig:
    """Configuration for Cloud MCP Relay.

    Allows exposing the daemon's MCP tools via a Cloudflare Worker,
    enabling remote AI agents to call tools over WebSocket.

    Attributes:
        worker_url: URL of the deployed Cloudflare Worker.
        worker_name: Cloudflare Worker name (derived from project directory).
        token: Shared secret for authenticating with the worker (supports ${ENV_VAR} syntax).
        agent_token: Shared secret for cloud agent authentication (supports ${ENV_VAR} syntax).
        auto_connect: Whether to connect automatically on daemon startup.
        tool_timeout_seconds: Max seconds to wait for a tool call to complete.
        reconnect_max_seconds: Max seconds for exponential backoff between reconnect attempts.
    """

    worker_url: str | None = None
    worker_name: str | None = None
    token: str | None = None
    agent_token: str | None = None
    auto_connect: bool = False
    tool_timeout_seconds: int = CLOUD_RELAY_DEFAULT_TOOL_TIMEOUT_SECONDS
    reconnect_max_seconds: int = CLOUD_RELAY_DEFAULT_RECONNECT_MAX_SECONDS
    custom_domain: str | None = None

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        self._validate()

    def _validate(self) -> None:
        """Validate configuration values.

        Raises:
            ValidationError: If any configuration value is invalid.
        """
        if self.tool_timeout_seconds < 1:
            raise ValidationError(
                "tool_timeout_seconds must be at least 1",
                field=CI_CONFIG_CLOUD_RELAY_KEY_TOOL_TIMEOUT,
                value=self.tool_timeout_seconds,
                expected=">= 1",
            )
        if self.reconnect_max_seconds < 1:
            raise ValidationError(
                "reconnect_max_seconds must be at least 1",
                field=CI_CONFIG_CLOUD_RELAY_KEY_RECONNECT_MAX,
                value=self.reconnect_max_seconds,
                expected=">= 1",
            )
        # Normalize custom_domain: strip protocol prefix, trailing slashes
        if self.custom_domain is not None:
            domain = self.custom_domain.strip()
            # Be lenient: strip https:// or http:// prefix if user includes it
            for prefix in ("https://", "http://"):
                if domain.lower().startswith(prefix):
                    domain = domain[len(prefix) :]
                    break
            # Strip trailing slashes
            domain = domain.rstrip("/")
            # Reject if it contains a path (slash after hostname)
            if "/" in domain:
                raise ValidationError(
                    "custom_domain must be a hostname (optionally with port), not a URL with a path",
                    field=CI_CONFIG_CLOUD_RELAY_KEY_CUSTOM_DOMAIN,
                    value=self.custom_domain,
                    expected="hostname or hostname:port (e.g. relay.example.com)",
                )
            # Store the cleaned value (or None if empty)
            self.custom_domain = domain if domain else None
        # Note: relay tokens are auto-generated by Oak and stored directly in
        # config — hardcoded values are the normal case here, unlike API keys.
        if self.token and not self.token.startswith("${"):
            logger.debug(
                "Cloud relay token is stored directly in config "
                "(use ${ENV_VAR_NAME} syntax for env-var indirection)."
            )
        if self.agent_token and not self.agent_token.startswith("${"):
            logger.debug(
                "Cloud relay agent_token is stored directly in config "
                "(use ${ENV_VAR_NAME} syntax for env-var indirection)."
            )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CloudRelayConfig":
        """Create config from dictionary.

        Args:
            data: Configuration dictionary.

        Returns:
            CloudRelayConfig instance.
        """
        # Resolve environment variables in token
        token = data.get(CI_CONFIG_CLOUD_RELAY_KEY_TOKEN)
        if token and token.startswith("${") and token.endswith("}"):
            env_var = token[2:-1]
            token = os.environ.get(env_var)

        # Resolve environment variables in agent_token
        agent_token = data.get(CI_CONFIG_CLOUD_RELAY_KEY_AGENT_TOKEN)
        if agent_token and agent_token.startswith("${") and agent_token.endswith("}"):
            env_var = agent_token[2:-1]
            agent_token = os.environ.get(env_var)

        return cls(
            worker_url=data.get(CI_CONFIG_CLOUD_RELAY_KEY_WORKER_URL),
            worker_name=data.get(CI_CONFIG_CLOUD_RELAY_KEY_WORKER_NAME),
            token=token,
            agent_token=agent_token,
            auto_connect=data.get(CI_CONFIG_CLOUD_RELAY_KEY_AUTO_CONNECT, False),
            tool_timeout_seconds=data.get(
                CI_CONFIG_CLOUD_RELAY_KEY_TOOL_TIMEOUT,
                CLOUD_RELAY_DEFAULT_TOOL_TIMEOUT_SECONDS,
            ),
            reconnect_max_seconds=data.get(
                CI_CONFIG_CLOUD_RELAY_KEY_RECONNECT_MAX,
                CLOUD_RELAY_DEFAULT_RECONNECT_MAX_SECONDS,
            ),
            custom_domain=data.get(CI_CONFIG_CLOUD_RELAY_KEY_CUSTOM_DOMAIN),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            CI_CONFIG_CLOUD_RELAY_KEY_WORKER_URL: self.worker_url,
            CI_CONFIG_CLOUD_RELAY_KEY_WORKER_NAME: self.worker_name,
            CI_CONFIG_CLOUD_RELAY_KEY_TOKEN: self.token,
            CI_CONFIG_CLOUD_RELAY_KEY_AGENT_TOKEN: self.agent_token,
            CI_CONFIG_CLOUD_RELAY_KEY_AUTO_CONNECT: self.auto_connect,
            CI_CONFIG_CLOUD_RELAY_KEY_TOOL_TIMEOUT: self.tool_timeout_seconds,
            CI_CONFIG_CLOUD_RELAY_KEY_RECONNECT_MAX: self.reconnect_max_seconds,
            CI_CONFIG_CLOUD_RELAY_KEY_CUSTOM_DOMAIN: self.custom_domain,
        }
