"""Factory for creating team transport instances from config."""

from open_agent_kit.features.codebase_intelligence.config.team import TeamConfig
from open_agent_kit.features.codebase_intelligence.constants.team import (
    TEAM_TRANSPORT_RELAY,
)
from open_agent_kit.features.codebase_intelligence.team.transport.base import (
    TeamTransport,
)


def create_transport(config: TeamConfig) -> TeamTransport:
    """Create a transport instance based on configuration.

    Args:
        config: Team configuration specifying transport type.

    Returns:
        A TeamTransport implementation appropriate for the config.
    """
    if config.transport == TEAM_TRANSPORT_RELAY:
        from open_agent_kit.features.codebase_intelligence.team.transport.relay import (
            RelayTransport,
        )

        return RelayTransport(config)

    from open_agent_kit.features.codebase_intelligence.team.transport.http import (
        HttpTransport,
    )

    return HttpTransport(
        server_url=config.server_url or "",
        token=config.api_key or "",
    )
