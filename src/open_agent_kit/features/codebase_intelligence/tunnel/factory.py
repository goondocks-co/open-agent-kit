"""Factory for creating tunnel providers from configuration."""

import logging

from open_agent_kit.features.codebase_intelligence.constants import (
    TUNNEL_ERROR_UNKNOWN_PROVIDER,
    TUNNEL_ERROR_UNKNOWN_PROVIDER_EXPECTED,
    TUNNEL_PROVIDER_CLOUDFLARED,
    TUNNEL_PROVIDER_NGROK,
)
from open_agent_kit.features.codebase_intelligence.exceptions import ValidationError
from open_agent_kit.features.codebase_intelligence.tunnel.base import TunnelProvider
from open_agent_kit.features.codebase_intelligence.tunnel.cloudflared import (
    CloudflaredProvider,
)
from open_agent_kit.features.codebase_intelligence.tunnel.ngrok_provider import (
    NgrokProvider,
)

logger = logging.getLogger(__name__)


def create_tunnel_provider(
    provider: str,
    cloudflared_path: str | None = None,
    ngrok_path: str | None = None,
) -> TunnelProvider:
    """Create a tunnel provider from configuration.

    Args:
        provider: Provider name ("cloudflared" or "ngrok").
        cloudflared_path: Custom path to cloudflared binary.
        ngrok_path: Custom path to ngrok binary.

    Returns:
        Configured TunnelProvider instance.

    Raises:
        ValidationError: If the provider name is invalid.
    """
    if provider == TUNNEL_PROVIDER_CLOUDFLARED:
        return CloudflaredProvider(binary_path=cloudflared_path)
    elif provider == TUNNEL_PROVIDER_NGROK:
        return NgrokProvider(binary_path=ngrok_path)
    else:
        raise ValidationError(
            TUNNEL_ERROR_UNKNOWN_PROVIDER.format(provider=provider),
            field="provider",
            value=provider,
            expected=TUNNEL_ERROR_UNKNOWN_PROVIDER_EXPECTED.format(
                cloudflared=TUNNEL_PROVIDER_CLOUDFLARED,
                ngrok=TUNNEL_PROVIDER_NGROK,
            ),
        )
