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

from open_agent_kit.features.codebase_intelligence.constants import (
    CLOUD_RELAY_DEFAULT_TOOL_TIMEOUT_SECONDS,
    CLOUD_RELAY_WS_TYPE_ERROR,
    CLOUD_RELAY_WS_TYPE_HEARTBEAT,
    CLOUD_RELAY_WS_TYPE_HEARTBEAT_ACK,
    CLOUD_RELAY_WS_TYPE_REGISTER,
    CLOUD_RELAY_WS_TYPE_REGISTERED,
    CLOUD_RELAY_WS_TYPE_TOOL_CALL,
    CLOUD_RELAY_WS_TYPE_TOOL_RESULT,
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


# ---- Daemon -> Worker messages ----


class RegisterMessage(BaseModel):
    """Sent by daemon to register with the worker after connecting.

    Includes the authentication token and the list of available MCP tools.
    """

    type: str = CLOUD_RELAY_WS_TYPE_REGISTER
    token: str
    tools: list[dict[str, Any]] = Field(default_factory=list)


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
