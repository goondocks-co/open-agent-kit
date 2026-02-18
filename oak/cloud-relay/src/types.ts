/**
 * Wire protocol types for Oak Cloud Relay.
 *
 * MUST match protocol.py models exactly. Any change here requires a
 * corresponding change in the Python side (and vice-versa).
 */

// ---------------------------------------------------------------------------
// Message type discriminator — values match constants.py
// ---------------------------------------------------------------------------

export const RelayMessageType = {
  REGISTER: "register",
  REGISTERED: "registered",
  TOOL_CALL: "tool_call",
  TOOL_RESULT: "tool_result",
  HEARTBEAT: "heartbeat",
  HEARTBEAT_ACK: "heartbeat_ack",
  ERROR: "error",
} as const;

export type RelayMessageType =
  (typeof RelayMessageType)[keyof typeof RelayMessageType];

// ---------------------------------------------------------------------------
// Wire messages — Daemon -> Worker
// ---------------------------------------------------------------------------

/** Sent by daemon to register after connecting (includes auth token + tool list). */
export interface RegisterMessage {
  type: typeof RelayMessageType.REGISTER;
  token: string;
  tools: Array<Record<string, unknown>>;
}

/** Sent by daemon in response to a tool call request. */
export interface ToolCallResponse {
  type: typeof RelayMessageType.TOOL_RESULT;
  call_id: string;
  result: unknown;
  error: string | null;
}

/** Sent by daemon in response to a heartbeat ping. */
export interface HeartbeatPong {
  type: typeof RelayMessageType.HEARTBEAT_ACK;
  timestamp: string; // ISO 8601
}

// ---------------------------------------------------------------------------
// Wire messages — Worker -> Daemon
// ---------------------------------------------------------------------------

/** Sent by worker to confirm successful registration. */
export interface RegisteredMessage {
  type: typeof RelayMessageType.REGISTERED;
}

/** Sent by worker when a remote client invokes an MCP tool. */
export interface ToolCallRequest {
  type: typeof RelayMessageType.TOOL_CALL;
  call_id: string;
  tool_name: string;
  arguments: Record<string, unknown>;
  timeout_ms: number;
}

/** Sent by worker to check if the daemon is still alive. */
export interface HeartbeatPing {
  type: typeof RelayMessageType.HEARTBEAT;
  timestamp: string; // ISO 8601
}

/** Sent by worker when an error occurs (e.g., auth failure). */
export interface RelayError {
  type: typeof RelayMessageType.ERROR;
  message: string;
  code: string | null;
}

// ---------------------------------------------------------------------------
// Union of all message types
// ---------------------------------------------------------------------------

export type RelayMessage =
  | RegisterMessage
  | RegisteredMessage
  | ToolCallRequest
  | ToolCallResponse
  | HeartbeatPing
  | HeartbeatPong
  | RelayError;

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/** Pending request waiting for a response from the local daemon. */
export interface PendingRequest {
  resolve: (response: ToolCallResponse) => void;
  reject: (reason: Error) => void;
  timer: ReturnType<typeof setTimeout>;
}

/** Cached tool list from daemon registration. */
export interface ToolInfo {
  name: string;
  description?: string;
  inputSchema?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Cloudflare environment bindings
// ---------------------------------------------------------------------------

export interface Env {
  RELAY: DurableObjectNamespace;
  AGENT_TOKEN: string;
  RELAY_TOKEN: string;
}
