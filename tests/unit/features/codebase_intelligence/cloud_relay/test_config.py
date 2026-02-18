"""Tests for CloudRelayConfig in CIConfig."""

import pytest

from open_agent_kit.features.codebase_intelligence.config import (
    USER_CLASSIFIED_PATHS,
    CIConfig,
    CloudRelayConfig,
)
from open_agent_kit.features.codebase_intelligence.constants import (
    CI_CONFIG_CLOUD_RELAY_KEY_AGENT_TOKEN,
    CI_CONFIG_CLOUD_RELAY_KEY_AUTO_CONNECT,
    CI_CONFIG_CLOUD_RELAY_KEY_CUSTOM_DOMAIN,
    CI_CONFIG_CLOUD_RELAY_KEY_RECONNECT_MAX,
    CI_CONFIG_CLOUD_RELAY_KEY_TOKEN,
    CI_CONFIG_CLOUD_RELAY_KEY_TOOL_TIMEOUT,
    CI_CONFIG_CLOUD_RELAY_KEY_WORKER_NAME,
    CI_CONFIG_CLOUD_RELAY_KEY_WORKER_URL,
    CI_CONFIG_KEY_CLOUD_RELAY,
    CLOUD_RELAY_DEFAULT_RECONNECT_MAX_SECONDS,
    CLOUD_RELAY_DEFAULT_TOOL_TIMEOUT_SECONDS,
)
from open_agent_kit.features.codebase_intelligence.exceptions import ValidationError

from .fixtures import (
    TEST_AGENT_TOKEN,
    TEST_RELAY_TOKEN,
    TEST_WORKER_URL,
)


class TestCloudRelayConfigDefaults:
    """Tests for default CloudRelayConfig values."""

    def test_defaults(self) -> None:
        config = CloudRelayConfig()
        assert config.worker_url is None
        assert config.worker_name is None
        assert config.token is None
        assert config.auto_connect is False
        assert config.tool_timeout_seconds == CLOUD_RELAY_DEFAULT_TOOL_TIMEOUT_SECONDS
        assert config.reconnect_max_seconds == CLOUD_RELAY_DEFAULT_RECONNECT_MAX_SECONDS

    def test_ci_config_includes_cloud_relay(self) -> None:
        ci = CIConfig()
        assert isinstance(ci.cloud_relay, CloudRelayConfig)
        assert ci.cloud_relay.worker_url is None


class TestCloudRelayConfigFromDict:
    """Tests for CloudRelayConfig.from_dict()."""

    def test_all_fields(self) -> None:
        data = {
            CI_CONFIG_CLOUD_RELAY_KEY_WORKER_URL: TEST_WORKER_URL,
            CI_CONFIG_CLOUD_RELAY_KEY_TOKEN: TEST_RELAY_TOKEN,
            CI_CONFIG_CLOUD_RELAY_KEY_AUTO_CONNECT: True,
            CI_CONFIG_CLOUD_RELAY_KEY_TOOL_TIMEOUT: 60,
            CI_CONFIG_CLOUD_RELAY_KEY_RECONNECT_MAX: 120,
        }
        config = CloudRelayConfig.from_dict(data)
        assert config.worker_url == TEST_WORKER_URL
        assert config.token == TEST_RELAY_TOKEN
        assert config.auto_connect is True
        assert config.tool_timeout_seconds == 60
        assert config.reconnect_max_seconds == 120

    def test_empty_dict_uses_defaults(self) -> None:
        config = CloudRelayConfig.from_dict({})
        assert config.worker_url is None
        assert config.token is None
        assert config.auto_connect is False

    def test_env_var_token_resolution(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Token with ${ENV_VAR} syntax is resolved from environment."""
        monkeypatch.setenv("OAK_RELAY_SECRET", TEST_RELAY_TOKEN)
        data = {CI_CONFIG_CLOUD_RELAY_KEY_TOKEN: "${OAK_RELAY_SECRET}"}
        config = CloudRelayConfig.from_dict(data)
        assert config.token == TEST_RELAY_TOKEN

    def test_env_var_token_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Unset env var resolves to None."""
        monkeypatch.delenv("MISSING_VAR", raising=False)
        data = {CI_CONFIG_CLOUD_RELAY_KEY_TOKEN: "${MISSING_VAR}"}
        config = CloudRelayConfig.from_dict(data)
        assert config.token is None

    def test_literal_token_kept(self) -> None:
        """Plain string token is kept as-is."""
        data = {CI_CONFIG_CLOUD_RELAY_KEY_TOKEN: TEST_RELAY_TOKEN}
        config = CloudRelayConfig.from_dict(data)
        assert config.token == TEST_RELAY_TOKEN


class TestCloudRelayConfigToDict:
    """Tests for CloudRelayConfig.to_dict()."""

    def test_roundtrip(self) -> None:
        config = CloudRelayConfig(
            worker_url=TEST_WORKER_URL,
            worker_name="oak-relay-my-project",
            token=TEST_RELAY_TOKEN,
            auto_connect=True,
            tool_timeout_seconds=45,
            reconnect_max_seconds=90,
        )
        d = config.to_dict()
        assert d == {
            CI_CONFIG_CLOUD_RELAY_KEY_WORKER_URL: TEST_WORKER_URL,
            CI_CONFIG_CLOUD_RELAY_KEY_WORKER_NAME: "oak-relay-my-project",
            CI_CONFIG_CLOUD_RELAY_KEY_TOKEN: TEST_RELAY_TOKEN,
            CI_CONFIG_CLOUD_RELAY_KEY_AGENT_TOKEN: None,
            CI_CONFIG_CLOUD_RELAY_KEY_CUSTOM_DOMAIN: None,
            CI_CONFIG_CLOUD_RELAY_KEY_AUTO_CONNECT: True,
            CI_CONFIG_CLOUD_RELAY_KEY_TOOL_TIMEOUT: 45,
            CI_CONFIG_CLOUD_RELAY_KEY_RECONNECT_MAX: 90,
        }

    def test_default_to_dict(self) -> None:
        d = CloudRelayConfig().to_dict()
        assert d[CI_CONFIG_CLOUD_RELAY_KEY_WORKER_URL] is None
        assert d[CI_CONFIG_CLOUD_RELAY_KEY_WORKER_NAME] is None
        assert d[CI_CONFIG_CLOUD_RELAY_KEY_TOKEN] is None
        assert d[CI_CONFIG_CLOUD_RELAY_KEY_AUTO_CONNECT] is False

    def test_ci_config_to_dict_includes_cloud_relay(self) -> None:
        ci = CIConfig()
        d = ci.to_dict()
        assert CI_CONFIG_KEY_CLOUD_RELAY in d


class TestCloudRelayConfigValidation:
    """Tests for CloudRelayConfig validation."""

    def test_invalid_tool_timeout(self) -> None:
        with pytest.raises(ValidationError):
            CloudRelayConfig(tool_timeout_seconds=0)

    def test_invalid_reconnect_max(self) -> None:
        with pytest.raises(ValidationError):
            CloudRelayConfig(reconnect_max_seconds=0)

    def test_negative_tool_timeout(self) -> None:
        with pytest.raises(ValidationError):
            CloudRelayConfig(tool_timeout_seconds=-5)

    def test_valid_minimum_values(self) -> None:
        """Minimum valid values (1) should not raise."""
        config = CloudRelayConfig(tool_timeout_seconds=1, reconnect_max_seconds=1)
        assert config.tool_timeout_seconds == 1
        assert config.reconnect_max_seconds == 1


class TestCloudRelayConfigAgentToken:
    """Tests for agent_token field on CloudRelayConfig."""

    def test_default_none(self) -> None:
        config = CloudRelayConfig()
        assert config.agent_token is None

    def test_from_dict(self) -> None:
        data = {CI_CONFIG_CLOUD_RELAY_KEY_AGENT_TOKEN: TEST_AGENT_TOKEN}
        config = CloudRelayConfig.from_dict(data)
        assert config.agent_token == TEST_AGENT_TOKEN

    def test_to_dict(self) -> None:
        config = CloudRelayConfig(agent_token=TEST_AGENT_TOKEN)
        d = config.to_dict()
        assert d[CI_CONFIG_CLOUD_RELAY_KEY_AGENT_TOKEN] == TEST_AGENT_TOKEN

    def test_roundtrip(self) -> None:
        config = CloudRelayConfig(
            worker_url=TEST_WORKER_URL,
            token=TEST_RELAY_TOKEN,
            agent_token=TEST_AGENT_TOKEN,
        )
        d = config.to_dict()
        restored = CloudRelayConfig.from_dict(d)
        assert restored.agent_token == TEST_AGENT_TOKEN
        assert restored.worker_url == TEST_WORKER_URL
        assert restored.token == TEST_RELAY_TOKEN

    def test_env_var_resolution(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """agent_token with ${ENV_VAR} syntax is resolved from environment."""
        monkeypatch.setenv("OAK_AGENT_SECRET", TEST_AGENT_TOKEN)
        data = {CI_CONFIG_CLOUD_RELAY_KEY_AGENT_TOKEN: "${OAK_AGENT_SECRET}"}
        config = CloudRelayConfig.from_dict(data)
        assert config.agent_token == TEST_AGENT_TOKEN

    def test_env_var_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Unset env var resolves to None."""
        monkeypatch.delenv("MISSING_AGENT_VAR", raising=False)
        data = {CI_CONFIG_CLOUD_RELAY_KEY_AGENT_TOKEN: "${MISSING_AGENT_VAR}"}
        config = CloudRelayConfig.from_dict(data)
        assert config.agent_token is None


class TestCloudRelayConfigWorkerName:
    """Tests for worker_name field on CloudRelayConfig."""

    def test_default_none(self) -> None:
        config = CloudRelayConfig()
        assert config.worker_name is None

    def test_from_dict(self) -> None:
        data = {CI_CONFIG_CLOUD_RELAY_KEY_WORKER_NAME: "oak-relay-my-app"}
        config = CloudRelayConfig.from_dict(data)
        assert config.worker_name == "oak-relay-my-app"

    def test_to_dict(self) -> None:
        config = CloudRelayConfig(worker_name="oak-relay-my-app")
        d = config.to_dict()
        assert d[CI_CONFIG_CLOUD_RELAY_KEY_WORKER_NAME] == "oak-relay-my-app"

    def test_roundtrip(self) -> None:
        config = CloudRelayConfig(
            worker_url=TEST_WORKER_URL,
            worker_name="oak-relay-my-app",
            token=TEST_RELAY_TOKEN,
        )
        d = config.to_dict()
        restored = CloudRelayConfig.from_dict(d)
        assert restored.worker_name == "oak-relay-my-app"
        assert restored.worker_url == TEST_WORKER_URL


class TestMakeWorkerName:
    """Tests for make_worker_name()."""

    def test_simple_name(self) -> None:
        from open_agent_kit.features.codebase_intelligence.cloud_relay.scaffold import (
            make_worker_name,
        )

        assert make_worker_name("my-project") == "oak-relay-my-project"

    def test_uppercase_lowered(self) -> None:
        from open_agent_kit.features.codebase_intelligence.cloud_relay.scaffold import (
            make_worker_name,
        )

        assert make_worker_name("My-Project") == "oak-relay-my-project"

    def test_underscores_replaced(self) -> None:
        from open_agent_kit.features.codebase_intelligence.cloud_relay.scaffold import (
            make_worker_name,
        )

        assert make_worker_name("my_cool_app") == "oak-relay-my-cool-app"

    def test_dots_replaced(self) -> None:
        from open_agent_kit.features.codebase_intelligence.cloud_relay.scaffold import (
            make_worker_name,
        )

        assert make_worker_name("open.agent.kit") == "oak-relay-open-agent-kit"

    def test_consecutive_special_chars_collapsed(self) -> None:
        from open_agent_kit.features.codebase_intelligence.cloud_relay.scaffold import (
            make_worker_name,
        )

        assert make_worker_name("my---project___v2") == "oak-relay-my-project-v2"

    def test_empty_name_uses_default(self) -> None:
        from open_agent_kit.features.codebase_intelligence.cloud_relay.scaffold import (
            make_worker_name,
        )

        assert make_worker_name("") == "oak-relay-default"

    def test_all_special_chars_uses_default(self) -> None:
        from open_agent_kit.features.codebase_intelligence.cloud_relay.scaffold import (
            make_worker_name,
        )

        assert make_worker_name("!!!") == "oak-relay-default"

    def test_long_name_truncated(self) -> None:
        from open_agent_kit.features.codebase_intelligence.cloud_relay.scaffold import (
            make_worker_name,
        )

        result = make_worker_name("a" * 100)
        assert len(result) <= 63
        assert result.startswith("oak-relay-")


class TestCloudRelayConfigCustomDomain:
    """Tests for custom_domain field on CloudRelayConfig."""

    def test_default_none(self) -> None:
        config = CloudRelayConfig()
        assert config.custom_domain is None

    def test_from_dict(self) -> None:
        data = {CI_CONFIG_CLOUD_RELAY_KEY_CUSTOM_DOMAIN: "relay.example.com"}
        config = CloudRelayConfig.from_dict(data)
        assert config.custom_domain == "relay.example.com"

    def test_from_dict_none(self) -> None:
        data = {CI_CONFIG_CLOUD_RELAY_KEY_CUSTOM_DOMAIN: None}
        config = CloudRelayConfig.from_dict(data)
        assert config.custom_domain is None

    def test_to_dict(self) -> None:
        config = CloudRelayConfig(custom_domain="relay.example.com")
        d = config.to_dict()
        assert d[CI_CONFIG_CLOUD_RELAY_KEY_CUSTOM_DOMAIN] == "relay.example.com"

    def test_to_dict_none(self) -> None:
        config = CloudRelayConfig()
        d = config.to_dict()
        assert d[CI_CONFIG_CLOUD_RELAY_KEY_CUSTOM_DOMAIN] is None

    def test_roundtrip(self) -> None:
        config = CloudRelayConfig(
            worker_url=TEST_WORKER_URL,
            token=TEST_RELAY_TOKEN,
            custom_domain="relay.example.com",
        )
        d = config.to_dict()
        restored = CloudRelayConfig.from_dict(d)
        assert restored.custom_domain == "relay.example.com"
        assert restored.worker_url == TEST_WORKER_URL

    def test_strips_https_prefix(self) -> None:
        """Validation strips https:// prefix for lenient input."""
        config = CloudRelayConfig(custom_domain="https://relay.example.com")
        assert config.custom_domain == "relay.example.com"

    def test_strips_http_prefix(self) -> None:
        """Validation strips http:// prefix for lenient input."""
        config = CloudRelayConfig(custom_domain="http://relay.example.com")
        assert config.custom_domain == "relay.example.com"

    def test_strips_trailing_slash(self) -> None:
        """Validation strips trailing slashes."""
        config = CloudRelayConfig(custom_domain="relay.example.com/")
        assert config.custom_domain == "relay.example.com"

    def test_rejects_path(self) -> None:
        """Validation rejects domains with paths."""
        with pytest.raises(ValidationError):
            CloudRelayConfig(custom_domain="relay.example.com/some/path")

    def test_empty_string_becomes_none(self) -> None:
        """Empty string is treated as clearing the domain."""
        config = CloudRelayConfig(custom_domain="")
        assert config.custom_domain is None

    def test_whitespace_only_becomes_none(self) -> None:
        """Whitespace-only string is treated as clearing the domain."""
        config = CloudRelayConfig(custom_domain="   ")
        assert config.custom_domain is None

    def test_with_port(self) -> None:
        """Domain with port is valid."""
        config = CloudRelayConfig(custom_domain="relay.example.com:8443")
        assert config.custom_domain == "relay.example.com:8443"

    def test_strips_prefix_and_trailing_slash(self) -> None:
        """Handles combined cleanup: prefix + trailing slash."""
        config = CloudRelayConfig(custom_domain="https://relay.example.com/")
        assert config.custom_domain == "relay.example.com"


class TestCloudRelayInUserClassifiedPaths:
    """Tests that cloud_relay is in USER_CLASSIFIED_PATHS."""

    def test_cloud_relay_is_user_classified(self) -> None:
        """Cloud relay config is machine-local (token, worker URL)."""
        assert CI_CONFIG_KEY_CLOUD_RELAY in USER_CLASSIFIED_PATHS
