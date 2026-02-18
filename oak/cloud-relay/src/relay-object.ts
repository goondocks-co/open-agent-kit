/**
 * Durable Object that bridges cloud agent requests and the local Oak CI daemon.
 *
 * Architecture:
 *   Cloud Agent --HTTP POST /mcp--> Worker --> DO.fetch() --> WebSocket --> Local Daemon
 *   Cloud Agent <--HTTP response--- Worker <-- DO.fetch() <-- WebSocket <-- Local Daemon
 *
 * Connection lifecycle:
 *   1. Local daemon connects via WebSocket at GET /ws
 *   2. Daemon sends "register" message with token + available tools
 *   3. DO validates token, stores tool list, sends "registered" confirmation
 *   4. DO sends heartbeat pings; daemon replies with heartbeat_ack
 *   5. Cloud agent POST /mcp creates tool_call, sent over WS, daemon replies with tool_result
 */

import {
  RelayMessageType,
  type Env,
  type HeartbeatPing,
  type PendingRequest,
  type RegisterMessage,
  type RegisteredMessage,
  type RelayMessage,
  type ToolCallRequest,
  type ToolCallResponse,
  type ToolInfo,
} from "./types";

const HEARTBEAT_INTERVAL_MS = 30_000;
const HEARTBEAT_TIMEOUT_MS = 10_000;
const DEFAULT_TOOL_TIMEOUT_MS = 30_000;

export class RelayObject implements DurableObject {
  private state: DurableObjectState;
  private env: Env;

  /** The single WebSocket connection from the local Oak CI daemon. */
  private ws: WebSocket | null = null;

  /** Whether the local instance is registered and reachable. */
  private instanceConnected = false;

  /** Cached tool list from the daemon's register message. */
  private tools: ToolInfo[] = [];

  /** Pending tool call requests awaiting a response from the local daemon. */
  private pending: Map<string, PendingRequest> = new Map();

  /** Heartbeat interval handle. */
  private heartbeatTimer: ReturnType<typeof setTimeout> | null = null;

  /** Timer that fires when a heartbeat_ack is overdue. */
  private pongTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(state: DurableObjectState, env: Env) {
    this.state = state;
    this.env = env;
  }

  // -----------------------------------------------------------------------
  // fetch() -- called by the Worker for /mcp, /ws, /health, /tools
  // -----------------------------------------------------------------------

  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname === "/ws") {
      return this.handleWebSocketUpgrade(request);
    }

    if (url.pathname === "/mcp" && request.method === "POST") {
      return this.handleToolCall(request);
    }

    if (url.pathname === "/health") {
      return Response.json({
        status: "ok",
        instance_connected: this.instanceConnected,
      });
    }

    if (url.pathname === "/tools") {
      return Response.json({ tools: this.tools });
    }

    return new Response("not found", { status: 404 });
  }

  // -----------------------------------------------------------------------
  // WebSocket lifecycle (local Oak CI daemon)
  // -----------------------------------------------------------------------

  private handleWebSocketUpgrade(request: Request): Response {
    // If there is already a connection, close the old one.
    if (this.ws) {
      try {
        this.ws.close(1000, "replaced by new connection");
      } catch {
        // already closed
      }
      this.cleanupConnection();
    }

    const pair = new WebSocketPair();
    const [client, server] = Object.values(pair);

    this.state.acceptWebSocket(server);
    this.ws = server;
    // Not yet connected -- wait for register message before marking online.

    // Echo the relay token as negotiated sub-protocol (standard WS handshake).
    const protocol = request.headers
      .get("Sec-WebSocket-Protocol")
      ?.split(",")[0]
      .trim();
    const headers: HeadersInit = {};
    if (protocol) {
      headers["Sec-WebSocket-Protocol"] = protocol;
    }

    return new Response(null, { status: 101, webSocket: client, headers });
  }

  webSocketMessage(_ws: WebSocket, data: string | ArrayBuffer): void {
    if (typeof data !== "string") return;

    let msg: RelayMessage;
    try {
      msg = JSON.parse(data) as RelayMessage;
    } catch {
      return; // malformed -- drop silently
    }

    switch (msg.type) {
      case RelayMessageType.REGISTER:
        this.handleRegister(msg as RegisterMessage);
        break;
      case RelayMessageType.TOOL_RESULT:
        this.resolveToolCall(msg as ToolCallResponse);
        break;
      case RelayMessageType.HEARTBEAT_ACK:
        this.handleHeartbeatAck();
        break;
      default:
        break;
    }
  }

  webSocketClose(
    _ws: WebSocket,
    _code: number,
    _reason: string,
    _wasClean: boolean,
  ): void {
    this.cleanupConnection();
  }

  webSocketError(_ws: WebSocket, _error: unknown): void {
    this.cleanupConnection();
  }

  // -----------------------------------------------------------------------
  // Registration
  // -----------------------------------------------------------------------

  private handleRegister(msg: RegisterMessage): void {
    if (!this.ws) return;

    // Validate the relay token sent inside the register message.
    if (msg.token !== this.env.RELAY_TOKEN) {
      const error = JSON.stringify({
        type: RelayMessageType.ERROR,
        message: "invalid relay token",
        code: "auth_failed",
      });
      this.ws.send(error);
      this.ws.close(4003, "invalid token");
      this.cleanupConnection();
      return;
    }

    // Store the tool list from the daemon.
    this.tools = (msg.tools || []).map((t) => ({
      name: (t as Record<string, unknown>).name as string,
      description: (t as Record<string, unknown>).description as string | undefined,
      inputSchema: (t as Record<string, unknown>).inputSchema as
        | Record<string, unknown>
        | undefined,
    }));

    this.instanceConnected = true;

    // Send registered confirmation.
    const registered: RegisteredMessage = {
      type: RelayMessageType.REGISTERED,
    };
    this.ws.send(JSON.stringify(registered));

    // Start heartbeat now that the daemon is registered.
    this.startHeartbeat();
  }

  // -----------------------------------------------------------------------
  // Tool call request/response flow
  // -----------------------------------------------------------------------

  private async handleToolCall(request: Request): Promise<Response> {
    if (!this.instanceConnected || !this.ws) {
      return Response.json({ error: "instance offline" }, { status: 502 });
    }

    let body: ToolCallRequest;
    try {
      body = (await request.json()) as ToolCallRequest;
    } catch {
      return Response.json({ error: "invalid request body" }, { status: 400 });
    }

    const timeoutMs = body.timeout_ms ?? DEFAULT_TOOL_TIMEOUT_MS;

    const responsePromise = new Promise<ToolCallResponse>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(body.call_id);
        reject(new Error("tool call timed out"));
      }, timeoutMs);

      this.pending.set(body.call_id, { resolve, reject, timer });
    });

    // Send the request over WebSocket to the local daemon.
    try {
      this.ws.send(JSON.stringify(body));
    } catch {
      this.pending.delete(body.call_id);
      return Response.json(
        { error: "failed to send to local instance" },
        { status: 502 },
      );
    }

    try {
      const response = await responsePromise;
      return Response.json(response);
    } catch (err) {
      const message = err instanceof Error ? err.message : "unknown error";
      return Response.json({ error: message }, { status: 504 });
    }
  }

  private resolveToolCall(msg: ToolCallResponse): void {
    const entry = this.pending.get(msg.call_id);
    if (!entry) return;

    clearTimeout(entry.timer);
    this.pending.delete(msg.call_id);
    entry.resolve(msg);
  }

  // -----------------------------------------------------------------------
  // Heartbeat
  // -----------------------------------------------------------------------

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      this.sendPing();
    }, HEARTBEAT_INTERVAL_MS);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
    if (this.pongTimer) {
      clearTimeout(this.pongTimer);
      this.pongTimer = null;
    }
  }

  private sendPing(): void {
    if (!this.ws) return;

    const ping: HeartbeatPing = {
      type: RelayMessageType.HEARTBEAT,
      timestamp: new Date().toISOString(),
    };

    try {
      this.ws.send(JSON.stringify(ping));
    } catch {
      this.cleanupConnection();
      return;
    }

    this.pongTimer = setTimeout(() => {
      this.cleanupConnection();
    }, HEARTBEAT_TIMEOUT_MS);
  }

  private handleHeartbeatAck(): void {
    if (this.pongTimer) {
      clearTimeout(this.pongTimer);
      this.pongTimer = null;
    }
  }

  // -----------------------------------------------------------------------
  // Connection cleanup
  // -----------------------------------------------------------------------

  private cleanupConnection(): void {
    this.stopHeartbeat();
    this.instanceConnected = false;
    this.tools = [];

    if (this.ws) {
      try {
        this.ws.close(1000, "cleanup");
      } catch {
        // already closed
      }
      this.ws = null;
    }

    for (const [id, entry] of this.pending) {
      clearTimeout(entry.timer);
      entry.reject(new Error("instance offline"));
      this.pending.delete(id);
    }
  }
}
