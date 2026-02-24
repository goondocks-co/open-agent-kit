"""Agent Client Protocol (ACP) Server feature.

Provides ACP integration for stateful editor interactions using the
official agent-client-protocol SDK. Editors like Zed can connect to
OAK as a first-class coding agent.

The ACP process is a thin protocol bridge: it translates between
ACP JSON-RPC (over stdio) and the OAK daemon's HTTP/NDJSON API.
All session lifecycle, tool execution, and activity recording
happen in the daemon.
"""

from open_agent_kit.features.acp_server.agent import OakAcpAgent
from open_agent_kit.features.acp_server.daemon_client import DaemonClient

__all__ = [
    "DaemonClient",
    "OakAcpAgent",
]
