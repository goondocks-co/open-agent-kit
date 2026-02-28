"""Factory for creating the appropriate TeamGateway instance."""

from __future__ import annotations

from typing import TYPE_CHECKING

from open_agent_kit.features.codebase_intelligence.team.gateway.base import TeamGateway

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.daemon.state import DaemonState


def create_gateway(state: DaemonState) -> TeamGateway | None:
    """Create a TeamGateway based on current daemon state.

    Args:
        state: The daemon state containing config and stores.

    Returns:
        A LocalTeamGateway for server mode, RemoteTeamGateway for client
        mode, or None if team is not configured.
    """
    ci_config = state.ci_config
    if ci_config is None:
        return None

    # Server mode: query DB directly
    if ci_config.team.server_mode and state.activity_store:
        from open_agent_kit.features.codebase_intelligence.team.gateway.local import (
            LocalTeamGateway,
        )

        return LocalTeamGateway(conn_factory=state.activity_store._get_connection)

    # Client mode: proxy to remote server
    if ci_config.team.server_url:
        from open_agent_kit.features.codebase_intelligence.team.gateway.remote import (
            RemoteTeamGateway,
        )

        return RemoteTeamGateway(
            server_url=ci_config.team.server_url,
            api_key=ci_config.team.api_key,
        )

    return None
