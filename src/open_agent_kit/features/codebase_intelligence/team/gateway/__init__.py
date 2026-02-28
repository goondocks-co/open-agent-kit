"""Team gateway abstraction — server vs client mode dispatch."""

from open_agent_kit.features.codebase_intelligence.team.gateway.base import TeamGateway
from open_agent_kit.features.codebase_intelligence.team.gateway.factory import create_gateway

__all__ = ["TeamGateway", "create_gateway"]
