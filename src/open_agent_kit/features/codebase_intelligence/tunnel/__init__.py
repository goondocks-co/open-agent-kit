"""Tunnel sharing for Codebase Intelligence daemon.

Provides tunnel-based session sharing via cloudflared or ngrok,
allowing teams to share the daemon UI through public URLs.
"""

from open_agent_kit.features.codebase_intelligence.tunnel.base import (
    TunnelProvider,
    TunnelStatus,
)
from open_agent_kit.features.codebase_intelligence.tunnel.factory import (
    create_tunnel_provider,
)

__all__ = [
    "TunnelProvider",
    "TunnelStatus",
    "create_tunnel_provider",
]
