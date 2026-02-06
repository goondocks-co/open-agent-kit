"""Tests for tunnel provider factory."""

import pytest

from open_agent_kit.features.codebase_intelligence.constants import (
    TUNNEL_ERROR_UNKNOWN_PROVIDER,
    TUNNEL_PROVIDER_CLOUDFLARED,
    TUNNEL_PROVIDER_NGROK,
)
from open_agent_kit.features.codebase_intelligence.exceptions import ValidationError
from open_agent_kit.features.codebase_intelligence.tunnel.cloudflared import (
    CloudflaredProvider,
)
from open_agent_kit.features.codebase_intelligence.tunnel.factory import (
    create_tunnel_provider,
)
from open_agent_kit.features.codebase_intelligence.tunnel.ngrok_provider import (
    NgrokProvider,
)

from .fixtures import (
    TEST_CLOUDFLARED_CUSTOM_PATH,
    TEST_NGROK_CUSTOM_PATH,
    TEST_PROVIDER_UNKNOWN,
)


class TestCreateTunnelProvider:
    """Tests for create_tunnel_provider factory function."""

    def test_create_cloudflared(self) -> None:
        """Creates CloudflaredProvider for 'cloudflared'."""
        provider = create_tunnel_provider(TUNNEL_PROVIDER_CLOUDFLARED)
        assert isinstance(provider, CloudflaredProvider)
        assert provider.name == "cloudflared"

    def test_create_cloudflared_with_path(self) -> None:
        """Passes binary path to CloudflaredProvider."""
        provider = create_tunnel_provider(
            TUNNEL_PROVIDER_CLOUDFLARED,
            cloudflared_path=TEST_CLOUDFLARED_CUSTOM_PATH,
        )
        assert isinstance(provider, CloudflaredProvider)
        assert provider._binary_path == TEST_CLOUDFLARED_CUSTOM_PATH

    def test_create_ngrok(self) -> None:
        """Creates NgrokProvider for 'ngrok'."""
        provider = create_tunnel_provider(TUNNEL_PROVIDER_NGROK)
        assert isinstance(provider, NgrokProvider)
        assert provider.name == "ngrok"

    def test_create_ngrok_with_path(self) -> None:
        """Passes binary path to NgrokProvider."""
        provider = create_tunnel_provider(
            TUNNEL_PROVIDER_NGROK,
            ngrok_path=TEST_NGROK_CUSTOM_PATH,
        )
        assert isinstance(provider, NgrokProvider)
        assert provider._binary_path == TEST_NGROK_CUSTOM_PATH

    def test_unknown_provider_raises(self) -> None:
        """Unknown provider raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            create_tunnel_provider(TEST_PROVIDER_UNKNOWN)
        assert TUNNEL_ERROR_UNKNOWN_PROVIDER.format(provider=TEST_PROVIDER_UNKNOWN) in str(
            exc_info.value
        )
