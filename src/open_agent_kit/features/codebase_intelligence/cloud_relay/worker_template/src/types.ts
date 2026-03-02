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
  HTTP_REQUEST: "http_request",
  HTTP_RESPONSE: "http_response",
  OBS_PUSH: "obs_push",
  OBS_BATCH: "obs_batch",
  NODE_LIST: "node_list",
  SEARCH_QUERY: "search_query",
  SEARCH_RESULT: "search_result",
  FEDERATED_TOOL_CALL: "federated_tool_call",
  FEDERATED_TOOL_RESULT: "federated_tool_result",
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
  machine_id: string;
  tools: Array<Record<string, unknown>>;
  oak_version?: string;
  template_hash?: string;
  capabilities?: string[];
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
// Wire messages — HTTP proxy (bidirectional)
// ---------------------------------------------------------------------------

/** Sent by worker to forward an HTTP request to the local daemon. */
export interface HttpRequestMessage {
  type: typeof RelayMessageType.HTTP_REQUEST;
  request_id: string;
  method: string;
  path: string;
  headers: Record<string, string>;
  body: string | null;
}

/** Sent by daemon in response to an HTTP proxy request. */
export interface HttpResponseMessage {
  type: typeof RelayMessageType.HTTP_RESPONSE;
  request_id: string;
  status: number;
  headers: Record<string, string>;
  body: string;
}

// ---------------------------------------------------------------------------
// Wire messages — Observation sync (multi-node)
// ---------------------------------------------------------------------------

/** Sent by daemon to push observations to all other connected nodes. */
export interface ObsPushMessage {
  type: typeof RelayMessageType.OBS_PUSH;
  observations: unknown[];
}

/** Sent by worker to deliver observations from another node. */
export interface ObsBatchMessage {
  type: typeof RelayMessageType.OBS_BATCH;
  from_machine_id: string;
  observations: unknown[];
}

/** Sent by worker to inform all nodes of the current node list. */
export interface NodeListMessage {
  type: typeof RelayMessageType.NODE_LIST;
  nodes: { machine_id: string; online: boolean; oak_version?: string; template_hash?: string; capabilities?: string[] }[];
  home_machine_id?: string;
}

// ---------------------------------------------------------------------------
// Wire messages — Federated search
// ---------------------------------------------------------------------------

/** Sent to request a federated search across connected nodes. */
export interface SearchQueryMessage {
  type: typeof RelayMessageType.SEARCH_QUERY;
  request_id: string;
  query: string;
  search_type?: string;
  limit?: number;
  from_machine_id?: string;
}

/** Sent by a node in response to a SearchQueryMessage. */
export interface SearchResultMessage {
  type: typeof RelayMessageType.SEARCH_RESULT;
  request_id: string;
  results: Record<string, unknown>[];
  from_machine_id?: string;
  error?: string;
}

/** Sent to request a tool call be executed on peer nodes. */
export interface FederatedToolCallMessage {
  type: typeof RelayMessageType.FEDERATED_TOOL_CALL;
  request_id: string;
  tool_name: string;
  arguments: Record<string, unknown>;
  from_machine_id?: string;
}

/** Sent by a node in response to a FederatedToolCallMessage. */
export interface FederatedToolResultMessage {
  type: typeof RelayMessageType.FEDERATED_TOOL_RESULT;
  request_id: string;
  result?: unknown;
  from_machine_id?: string;
  error?: string;
}

/** Tracks pending federated tool call state in the DO. */
export interface PendingFederatedTool {
  results: FederatedToolResultMessage[];
  expectedCount: number;
  resolve: (value: FederatedToolResultMessage[]) => void;
  timer: ReturnType<typeof setTimeout>;
}

/** Tracks pending federated search state in the DO. */
export interface PendingSearch {
  results: SearchResultMessage[];
  expectedCount: number;
  resolve: (value: SearchResultMessage[]) => void;
  timer: ReturnType<typeof setTimeout>;
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
  | RelayError
  | HttpRequestMessage
  | HttpResponseMessage
  | ObsPushMessage
  | ObsBatchMessage
  | NodeListMessage
  | SearchQueryMessage
  | SearchResultMessage
  | FederatedToolCallMessage
  | FederatedToolResultMessage;

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/** Pending request waiting for a response from the local daemon. */
export interface PendingRequest {
  resolve: (response: ToolCallResponse) => void;
  reject: (reason: Error) => void;
  timer: ReturnType<typeof setTimeout>;
}

/** Pending HTTP proxy request waiting for a response from the local daemon. */
export interface PendingHttpRequest {
  resolve: (response: HttpResponseMessage) => void;
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
