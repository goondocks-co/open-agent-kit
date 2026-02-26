"""Tests for TeamConfig dataclass.

Tests cover:
- TeamConfig initialization with defaults
- TeamConfig validation: invalid transport raises ValidationError
- TeamConfig validation: relay requires relay_worker_url
- TeamConfig validation: sync_interval out of range raises
- TeamConfig validation: pull_interval out of range raises
- from_dict() / to_dict() round-trip
- from_dict() with ${ENV_VAR} token resolution
- from_dict() with empty dict returns defaults
"""

import pytest

from open_agent_kit.features.codebase_intelligence.config.team import TeamConfig
from open_agent_kit.features.codebase_intelligence.constants.team import (
    CI_CONFIG_TEAM_KEY_RELAY_WORKER_URL,
    CI_CONFIG_TEAM_KEY_SERVER_URL,
    CI_CONFIG_TEAM_KEY_SYNC_INTERVAL,
    CI_CONFIG_TEAM_KEY_TOKEN,
    CI_CONFIG_TEAM_KEY_TRANSPORT,
    TEAM_DEFAULT_BIND_HOST,
    TEAM_DEFAULT_BIND_PORT,
    TEAM_DEFAULT_PULL_INTERVAL_SECONDS,
    TEAM_DEFAULT_SYNC_INTERVAL_SECONDS,
    TEAM_MAX_PULL_INTERVAL_SECONDS,
    TEAM_MAX_SYNC_INTERVAL_SECONDS,
    TEAM_MIN_PULL_INTERVAL_SECONDS,
    TEAM_MIN_SYNC_INTERVAL_SECONDS,
    TEAM_TRANSPORT_DIRECT,
    TEAM_TRANSPORT_RELAY,
)
from open_agent_kit.features.codebase_intelligence.exceptions import (
    ValidationError,
)

# =============================================================================
# TeamConfig Initialization
# =============================================================================


class TestTeamConfigInit:
    """Test TeamConfig initialization and defaults."""

    def test_init_with_defaults(self):
        """Test default values are applied correctly."""
        config = TeamConfig()
        assert config.server_url is None
        assert config.token is None
        assert config.auto_sync is False
        assert config.sync_interval_seconds == TEAM_DEFAULT_SYNC_INTERVAL_SECONDS
        assert config.pull_interval_seconds == TEAM_DEFAULT_PULL_INTERVAL_SECONDS
        assert config.project_slug is None
        assert config.transport == TEAM_TRANSPORT_DIRECT
        assert config.server_mode is False
        assert config.bind_host == TEAM_DEFAULT_BIND_HOST
        assert config.bind_port == TEAM_DEFAULT_BIND_PORT
        assert config.relay_worker_url is None
        assert config.relay_worker_name is None
        assert config.server_side_llm is False

    def test_init_with_custom_values(self):
        """Test initialization with explicit values."""
        config = TeamConfig(
            server_url="https://team.example.com",
            token="secret-token",
            auto_sync=True,
            sync_interval_seconds=10,
            pull_interval_seconds=30,
            project_slug="my-project",
            transport=TEAM_TRANSPORT_DIRECT,
            server_mode=True,
            bind_host="0.0.0.0",
            bind_port=9000,
            server_side_llm=True,
        )
        assert config.server_url == "https://team.example.com"
        assert config.token == "secret-token"
        assert config.auto_sync is True
        assert config.sync_interval_seconds == 10
        assert config.pull_interval_seconds == 30
        assert config.project_slug == "my-project"
        assert config.server_mode is True
        assert config.bind_host == "0.0.0.0"
        assert config.bind_port == 9000
        assert config.server_side_llm is True


# =============================================================================
# TeamConfig Validation
# =============================================================================


class TestTeamConfigValidation:
    """Test TeamConfig validation rules."""

    def test_invalid_transport_raises_error(self):
        """Test that an invalid transport raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            TeamConfig(transport="invalid_transport")
        assert exc_info.value.field == CI_CONFIG_TEAM_KEY_TRANSPORT
        assert "invalid_transport" in str(exc_info.value)

    def test_relay_requires_relay_worker_url(self):
        """Test that relay transport without relay_worker_url raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            TeamConfig(transport=TEAM_TRANSPORT_RELAY)
        assert exc_info.value.field == CI_CONFIG_TEAM_KEY_RELAY_WORKER_URL

    def test_relay_with_url_succeeds(self):
        """Test that relay transport with relay_worker_url succeeds."""
        config = TeamConfig(
            transport=TEAM_TRANSPORT_RELAY,
            relay_worker_url="https://relay.example.com",
        )
        assert config.transport == TEAM_TRANSPORT_RELAY
        assert config.relay_worker_url == "https://relay.example.com"

    def test_sync_interval_below_min_raises_error(self):
        """Test that sync_interval_seconds below minimum raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            TeamConfig(sync_interval_seconds=TEAM_MIN_SYNC_INTERVAL_SECONDS - 1)
        assert exc_info.value.field == CI_CONFIG_TEAM_KEY_SYNC_INTERVAL

    def test_sync_interval_above_max_raises_error(self):
        """Test that sync_interval_seconds above maximum raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            TeamConfig(sync_interval_seconds=TEAM_MAX_SYNC_INTERVAL_SECONDS + 1)
        assert exc_info.value.field == CI_CONFIG_TEAM_KEY_SYNC_INTERVAL

    def test_sync_interval_at_boundaries_succeeds(self):
        """Test that sync_interval at min and max boundaries succeeds."""
        config_min = TeamConfig(sync_interval_seconds=TEAM_MIN_SYNC_INTERVAL_SECONDS)
        assert config_min.sync_interval_seconds == TEAM_MIN_SYNC_INTERVAL_SECONDS

        config_max = TeamConfig(sync_interval_seconds=TEAM_MAX_SYNC_INTERVAL_SECONDS)
        assert config_max.sync_interval_seconds == TEAM_MAX_SYNC_INTERVAL_SECONDS

    def test_pull_interval_below_min_raises_error(self):
        """Test that pull_interval_seconds below minimum raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            TeamConfig(pull_interval_seconds=TEAM_MIN_PULL_INTERVAL_SECONDS - 1)
        assert "pull_interval_seconds" in str(exc_info.value)

    def test_pull_interval_above_max_raises_error(self):
        """Test that pull_interval_seconds above maximum raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            TeamConfig(pull_interval_seconds=TEAM_MAX_PULL_INTERVAL_SECONDS + 1)
        assert "pull_interval_seconds" in str(exc_info.value)


# =============================================================================
# TeamConfig Serialization
# =============================================================================


class TestTeamConfigSerialization:
    """Test TeamConfig from_dict/to_dict round-trip."""

    def test_from_dict_empty_returns_defaults(self):
        """Test that from_dict with empty dict returns default config."""
        config = TeamConfig.from_dict({})
        default = TeamConfig()
        assert config.server_url == default.server_url
        assert config.token == default.token
        assert config.auto_sync == default.auto_sync
        assert config.sync_interval_seconds == default.sync_interval_seconds
        assert config.pull_interval_seconds == default.pull_interval_seconds
        assert config.transport == default.transport

    def test_round_trip(self):
        """Test that from_dict(to_dict()) produces equivalent config."""
        original = TeamConfig(
            server_url="https://team.example.com",
            token="my-token",
            auto_sync=True,
            sync_interval_seconds=5,
            pull_interval_seconds=30,
            project_slug="test-project",
            transport=TEAM_TRANSPORT_DIRECT,
            server_mode=True,
            bind_host="0.0.0.0",
            bind_port=9000,
            server_side_llm=True,
        )
        restored = TeamConfig.from_dict(original.to_dict())
        assert restored.server_url == original.server_url
        assert restored.token == original.token
        assert restored.auto_sync == original.auto_sync
        assert restored.sync_interval_seconds == original.sync_interval_seconds
        assert restored.pull_interval_seconds == original.pull_interval_seconds
        assert restored.project_slug == original.project_slug
        assert restored.transport == original.transport
        assert restored.server_mode == original.server_mode
        assert restored.bind_host == original.bind_host
        assert restored.bind_port == original.bind_port
        assert restored.relay_worker_url == original.relay_worker_url
        assert restored.relay_worker_name == original.relay_worker_name
        assert restored.server_side_llm == original.server_side_llm

    def test_from_dict_with_env_var_token(self, monkeypatch):
        """Test that ${ENV_VAR} token syntax resolves from environment."""
        monkeypatch.setenv("OAK_TEAM_TOKEN", "resolved-secret")
        config = TeamConfig.from_dict(
            {
                CI_CONFIG_TEAM_KEY_TOKEN: "${OAK_TEAM_TOKEN}",
            }
        )
        assert config.token == "resolved-secret"

    def test_from_dict_with_missing_env_var_token(self, monkeypatch):
        """Test that ${ENV_VAR} with missing env var resolves to None."""
        monkeypatch.delenv("NONEXISTENT_TOKEN_VAR", raising=False)
        config = TeamConfig.from_dict(
            {
                CI_CONFIG_TEAM_KEY_TOKEN: "${NONEXISTENT_TOKEN_VAR}",
            }
        )
        assert config.token is None

    def test_from_dict_with_explicit_values(self):
        """Test from_dict with explicitly provided values."""
        config = TeamConfig.from_dict(
            {
                CI_CONFIG_TEAM_KEY_SERVER_URL: "https://team.example.com",
                CI_CONFIG_TEAM_KEY_SYNC_INTERVAL: 10,
            }
        )
        assert config.server_url == "https://team.example.com"
        assert config.sync_interval_seconds == 10

    def test_to_dict_contains_all_keys(self):
        """Test that to_dict includes all configuration keys."""
        config = TeamConfig()
        d = config.to_dict()
        assert CI_CONFIG_TEAM_KEY_SERVER_URL in d
        assert CI_CONFIG_TEAM_KEY_TOKEN in d
        assert CI_CONFIG_TEAM_KEY_TRANSPORT in d
        assert CI_CONFIG_TEAM_KEY_SYNC_INTERVAL in d
