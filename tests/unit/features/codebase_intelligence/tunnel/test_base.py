"""Tests for tunnel base classes."""

from open_agent_kit.features.codebase_intelligence.constants import (
    TUNNEL_RESPONSE_KEY_ACTIVE,
    TUNNEL_RESPONSE_KEY_ERROR,
    TUNNEL_RESPONSE_KEY_PROVIDER,
    TUNNEL_RESPONSE_KEY_PUBLIC_URL,
    TUNNEL_RESPONSE_KEY_STARTED_AT,
)
from open_agent_kit.features.codebase_intelligence.tunnel.base import (
    TunnelProvider,
    TunnelStatus,
)

from .fixtures import (
    TEST_ERROR_BINARY_NOT_FOUND,
    TEST_ERROR_GENERIC,
    TEST_PORT,
    TEST_PROVIDER_CLOUDFLARED,
    TEST_PROVIDER_FAKE,
    TEST_STARTED_AT,
    TEST_URL_CLOUDFLARE,
    TEST_URL_FAKE,
)


class TestTunnelStatus:
    """Tests for TunnelStatus dataclass."""

    def test_active_status(self) -> None:
        """Active status has all fields populated."""
        status = TunnelStatus(
            active=True,
            public_url=TEST_URL_CLOUDFLARE,
            provider_name=TEST_PROVIDER_CLOUDFLARED,
            started_at=TEST_STARTED_AT,
        )
        assert status.active is True
        assert status.public_url == TEST_URL_CLOUDFLARE
        assert status.provider_name == TEST_PROVIDER_CLOUDFLARED
        assert status.started_at == TEST_STARTED_AT
        assert status.error is None

    def test_inactive_status_defaults(self) -> None:
        """Inactive status has sensible defaults."""
        status = TunnelStatus(active=False)
        assert status.active is False
        assert status.public_url is None
        assert status.provider_name is None
        assert status.started_at is None
        assert status.error is None

    def test_error_status(self) -> None:
        """Error status includes error message."""
        status = TunnelStatus(
            active=False,
            provider_name=TEST_PROVIDER_CLOUDFLARED,
            error=TEST_ERROR_BINARY_NOT_FOUND,
        )
        assert status.active is False
        assert status.error == TEST_ERROR_BINARY_NOT_FOUND

    def test_to_dict(self) -> None:
        """to_dict returns proper dictionary for API responses."""
        status = TunnelStatus(
            active=True,
            public_url=TEST_URL_CLOUDFLARE,
            provider_name=TEST_PROVIDER_CLOUDFLARED,
            started_at=TEST_STARTED_AT,
        )
        d = status.to_dict()
        assert d == {
            TUNNEL_RESPONSE_KEY_ACTIVE: True,
            TUNNEL_RESPONSE_KEY_PUBLIC_URL: TEST_URL_CLOUDFLARE,
            TUNNEL_RESPONSE_KEY_PROVIDER: TEST_PROVIDER_CLOUDFLARED,
            TUNNEL_RESPONSE_KEY_STARTED_AT: TEST_STARTED_AT,
            TUNNEL_RESPONSE_KEY_ERROR: None,
        }

    def test_to_dict_inactive(self) -> None:
        """to_dict handles inactive status."""
        status = TunnelStatus(active=False, error=TEST_ERROR_GENERIC)
        d = status.to_dict()
        assert d[TUNNEL_RESPONSE_KEY_ACTIVE] is False
        assert d[TUNNEL_RESPONSE_KEY_ERROR] == TEST_ERROR_GENERIC
        assert d[TUNNEL_RESPONSE_KEY_PUBLIC_URL] is None


class TestTunnelProviderABC:
    """Tests for TunnelProvider abstract class."""

    def test_cannot_instantiate(self) -> None:
        """Cannot instantiate abstract class directly."""
        import pytest

        with pytest.raises(TypeError):
            TunnelProvider()  # type: ignore[abstract]

    def test_concrete_subclass(self) -> None:
        """Concrete subclass must implement all abstract methods."""

        class FakeProvider(TunnelProvider):
            @property
            def name(self) -> str:
                return TEST_PROVIDER_FAKE

            @property
            def is_available(self) -> bool:
                return True

            def start(self, local_port: int) -> TunnelStatus:
                return TunnelStatus(active=True, public_url=TEST_URL_FAKE)

            def stop(self) -> None:
                pass

            def get_status(self) -> TunnelStatus:
                return TunnelStatus(active=False)

        provider = FakeProvider()
        assert provider.name == TEST_PROVIDER_FAKE
        assert provider.is_available is True
        status = provider.start(TEST_PORT)
        assert status.active is True
