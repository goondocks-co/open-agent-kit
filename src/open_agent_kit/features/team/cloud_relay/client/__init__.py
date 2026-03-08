"""CloudRelayClient package — split from monolithic client.py for maintainability.

Re-exports the public API so that existing imports continue to work:

    from open_agent_kit.features.team.cloud_relay.client import CloudRelayClient
"""

from open_agent_kit.features.team.cloud_relay.client._core import (
    CloudRelayClient,
)
from open_agent_kit.features.team.cloud_relay.client._helpers import (
    _is_auth_failure,
)

__all__ = ["CloudRelayClient", "_is_auth_failure"]
