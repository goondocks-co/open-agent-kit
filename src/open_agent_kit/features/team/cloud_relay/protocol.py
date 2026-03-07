"""Wire protocol models for Cloud MCP Relay.

Defines Pydantic models for JSON messages exchanged over the WebSocket
connection between the daemon and the Cloudflare Worker.

Message flow:
    Daemon -> Worker: register, tool_call_response, heartbeat_pong
    Worker -> Daemon: registered, tool_call_request, heartbeat_ping, error
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from open_agent_kit.features.team.constants import (
    CLOUD_RELAY_DEFAULT_TOOL_TIMEOUT_SECONDS,
    CLOUD_RELAY_FEDERATED_SEARCH_DEFAULT_LIMIT,
    CLOUD_RELAY_WS_TYPE_ERROR,
    CLOUD_RELAY_WS_TYPE_FEDERATED_TOOL_CALL,
    CLOUD_RELAY_WS_TYPE_FEDERATED_TOOL_RESULT,
    CLOUD_RELAY_WS_TYPE_HEARTBEAT,
    CLOUD_RELAY_WS_TYPE_HEARTBEAT_ACK,
    CLOUD_RELAY_WS_TYPE_HTTP_REQUEST,
    CLOUD_RELAY_WS_TYPE_HTTP_RESPONSE,
    CLOUD_RELAY_WS_TYPE_NODE_LIST,
    CLOUD_RELAY_WS_TYPE_OBS_BATCH,
    CLOUD_RELAY_WS_TYPE_OBS_PUSH,
    CLOUD_RELAY_WS_TYPE_REGISTER,
    CLOUD_RELAY_WS_TYPE_REGISTERED,
    CLOUD_RELAY_WS_TYPE_SEARCH_QUERY,
    CLOUD_RELAY_WS_TYPE_SEARCH_RESULT,
    CLOUD_RELAY_WS_TYPE_TOOL_CALL,
    CLOUD_RELAY_WS_TYPE_TOOL_RESULT,
    SWARM_WS_TYPE_NODE_LIST,
    SWARM_WS_TYPE_NODES,
    SWARM_WS_TYPE_SEARCH,
    SWARM_WS_TYPE_SEARCH_RESULT,
)

# Timeout in milliseconds (wire protocol uses ms, config uses seconds)
_DEFAULT_TIMEOUT_MS = CLOUD_RELAY_DEFAULT_TOOL_TIMEOUT_SECONDS * 1000


class RelayMessageType(str, Enum):
    """Types of messages in the cloud relay WebSocket protocol."""

    REGISTER = CLOUD_RELAY_WS_TYPE_REGISTER
    REGISTERED = CLOUD_RELAY_WS_TYPE_REGISTERED
    TOOL_CALL = CLOUD_RELAY_WS_TYPE_TOOL_CALL
    TOOL_RESULT = CLOUD_RELAY_WS_TYPE_TOOL_RESULT
    HEARTBEAT = CLOUD_RELAY_WS_TYPE_HEARTBEAT
    HEARTBEAT_ACK = CLOUD_RELAY_WS_TYPE_HEARTBEAT_ACK
    ERROR = CLOUD_RELAY_WS_TYPE_ERROR
    HTTP_REQUEST = CLOUD_RELAY_WS_TYPE_HTTP_REQUEST
    HTTP_RESPONSE = CLOUD_RELAY_WS_TYPE_HTTP_RESPONSE
    OBS_PUSH = CLOUD_RELAY_WS_TYPE_OBS_PUSH
    OBS_BATCH = CLOUD_RELAY_WS_TYPE_OBS_BATCH
    NODE_LIST = CLOUD_RELAY_WS_TYPE_NODE_LIST
    SEARCH_QUERY = CLOUD_RELAY_WS_TYPE_SEARCH_QUERY
    SEARCH_RESULT = CLOUD_RELAY_WS_TYPE_SEARCH_RESULT
    FEDERATED_TOOL_CALL = CLOUD_RELAY_WS_TYPE_FEDERATED_TOOL_CALL
    FEDERATED_TOOL_RESULT = CLOUD_RELAY_WS_TYPE_FEDERATED_TOOL_RESULT
    SWARM_SEARCH = SWARM_WS_TYPE_SEARCH
    SWARM_SEARCH_RESULT = SWARM_WS_TYPE_SEARCH_RESULT
    SWARM_NODES = SWARM_WS_TYPE_NODES
    SWARM_NODE_LIST = SWARM_WS_TYPE_NODE_LIST


# ---- Daemon -> Worker messages ----


class RegisterMessage(BaseModel):
    """Sent by daemon to register with the worker after connecting.

    Includes the authentication token, list of available MCP tools, and
    version metadata so peers can detect when teammates need to update.
    """

    type: str = CLOUD_RELAY_WS_TYPE_REGISTER
    token: str
    tools: list[dict[str, Any]] = Field(default_factory=list)
    machine_id: str = ""
    oak_version: str = ""
    template_hash: str = ""
    capabilities: list[str] = Field(default_factory=list)


class ToolCallResponse(BaseModel):
    """Sent by daemon in response to a tool call request.

    The call_id must match the corresponding ToolCallRequest.
    Exactly one of result or error should be set.
    """

    type: str = CLOUD_RELAY_WS_TYPE_TOOL_RESULT
    call_id: str
    result: Any | None = None
    error: str | None = None


class HeartbeatPong(BaseModel):
    """Sent by daemon in response to a heartbeat ping."""

    type: str = CLOUD_RELAY_WS_TYPE_HEARTBEAT_ACK
    timestamp: str  # ISO 8601 format


# ---- Worker -> Daemon messages ----


class RegisteredMessage(BaseModel):
    """Sent by worker to confirm successful registration."""

    type: str = CLOUD_RELAY_WS_TYPE_REGISTERED


class ToolCallRequest(BaseModel):
    """Sent by worker when a remote client invokes an MCP tool.

    The daemon should execute the tool and respond with a ToolCallResponse
    using the same call_id.
    """

    type: str = CLOUD_RELAY_WS_TYPE_TOOL_CALL
    call_id: str
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    timeout_ms: int = _DEFAULT_TIMEOUT_MS


class HeartbeatPing(BaseModel):
    """Sent by worker to check if the daemon is still alive."""

    type: str = CLOUD_RELAY_WS_TYPE_HEARTBEAT
    timestamp: str  # ISO 8601 format


class RelayError(BaseModel):
    """Sent by worker when an error occurs (e.g., auth failure)."""

    type: str = CLOUD_RELAY_WS_TYPE_ERROR
    message: str
    code: str | None = None


# ---- HTTP proxy messages (bidirectional) ----


class HttpRequestMessage(BaseModel):
    """Sent by worker to forward an HTTP request to the local daemon.

    The daemon should execute the request locally and respond with an
    HttpResponseMessage using the same request_id.
    """

    type: str = CLOUD_RELAY_WS_TYPE_HTTP_REQUEST
    request_id: str
    method: str
    path: str
    headers: dict[str, str] = Field(default_factory=dict)
    body: str | None = None


class HttpResponseMessage(BaseModel):
    """Sent by daemon in response to an HTTP proxy request.

    The request_id must match the corresponding HttpRequestMessage.
    """

    type: str = CLOUD_RELAY_WS_TYPE_HTTP_RESPONSE
    request_id: str
    status: int
    headers: dict[str, str] = Field(default_factory=dict)
    body: str = ""


# ---- Observation sync messages (bidirectional) ----


class ObsPushMessage(BaseModel):
    """Sent by daemon to push observations to peer nodes via relay."""

    type: str = CLOUD_RELAY_WS_TYPE_OBS_PUSH
    observations: list[dict[str, Any]] = Field(default_factory=list)


# ---- Federated search messages (bidirectional) ----


class SearchQueryMessage(BaseModel):
    """Sent to request a federated search across connected nodes.

    The relay fans this out to all nodes with the ``federated_tools_v1``
    capability and collects results.
    """

    type: str = CLOUD_RELAY_WS_TYPE_SEARCH_QUERY
    request_id: str
    query: str
    search_type: str = "all"
    limit: int = CLOUD_RELAY_FEDERATED_SEARCH_DEFAULT_LIMIT
    from_machine_id: str = ""


class SearchResultMessage(BaseModel):
    """Sent by a node in response to a SearchQueryMessage."""

    type: str = CLOUD_RELAY_WS_TYPE_SEARCH_RESULT
    request_id: str
    results: list[dict[str, Any]] = Field(default_factory=list)
    from_machine_id: str = ""
    error: str | None = None


# ---- Federated tool call messages (generic fan-out) ----


class FederatedToolCallMessage(BaseModel):
    """Sent to request a tool call be executed on peer nodes.

    The relay fans this out to all nodes with the ``federated_tools_v1``
    capability and collects results.
    """

    type: str = CLOUD_RELAY_WS_TYPE_FEDERATED_TOOL_CALL
    request_id: str
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    from_machine_id: str = ""


class FederatedToolResultMessage(BaseModel):
    """Sent by a node in response to a FederatedToolCallMessage."""

    type: str = CLOUD_RELAY_WS_TYPE_FEDERATED_TOOL_RESULT
    request_id: str
    result: Any | None = None
    from_machine_id: str = ""
    error: str | None = None


# ---- Swarm messages (bidirectional) ----


class SwarmSearchMessage(BaseModel):
    """Sent by node to request a cross-project search via the swarm."""

    type: str = SWARM_WS_TYPE_SEARCH
    request_id: str
    query: str
    search_type: str = "all"
    limit: int = 10


class SwarmSearchResultMessage(BaseModel):
    """Sent by worker with aggregated cross-project search results."""

    type: str = SWARM_WS_TYPE_SEARCH_RESULT
    request_id: str
    results: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None


class SwarmNodesMessage(BaseModel):
    """Sent by node to request the swarm membership list."""

    type: str = SWARM_WS_TYPE_NODES
    request_id: str


class SwarmNodeListMessage(BaseModel):
    """Sent by worker with the list of teams in the swarm."""

    type: str = SWARM_WS_TYPE_NODE_LIST
    request_id: str
    nodes: list[dict[str, Any]] = Field(default_factory=list)
