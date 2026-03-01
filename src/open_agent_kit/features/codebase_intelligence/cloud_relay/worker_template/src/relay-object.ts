/**
 * Durable Object that bridges cloud agent requests and the local Oak CI daemon.
 *
 * Architecture (multi-node):
 *   Cloud Agent --HTTP POST /mcp--> Worker --> DO.fetch() --> WebSocket --> Local Daemon
 *   Cloud Agent <--HTTP response--- Worker <-- DO.fetch() <-- WebSocket <-- Local Daemon
 *
 * Multiple local daemons can connect simultaneously, each identified by a
 * unique machine_id. The DO uses Cloudflare WebSocket tags to track connections
 * and DO SQLite to buffer observations for offline nodes.
 *
 * Connection lifecycle:
 *   1. Local daemon connects via WebSocket at GET /ws
 *   2. Daemon sends "register" message with token + machine_id + available tools
 *   3. DO validates token, accepts WS with machine_id tag, stores tools
 *   4. DO sends "registered" confirmation + broadcasts node_list to all peers
 *   5. DO drains any pending observations buffered for this machine
 *   6. DO sends heartbeat pings per connection; daemon replies with heartbeat_ack
 *   7. Cloud agent POST /mcp creates tool_call, sent over WS, daemon replies with tool_result
 */

import {
  RelayMessageType,
  type Env,
  type HeartbeatPing,
  type HttpRequestMessage,
  type HttpResponseMessage,
  type NodeListMessage,
  type ObsBatchMessage,
  type ObsPushMessage,
  type PendingHttpRequest,
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
const PENDING_OBS_DRAIN_LIMIT = 500;

export class RelayObject implements DurableObject {
  private state: DurableObjectState;
  private env: Env;

  /** Cached tool list from the daemon's register message. */
  private tools: ToolInfo[] = [];

  /** Pending tool call requests awaiting a response from the local daemon. */
  private pending: Map<string, PendingRequest> = new Map();

  /** Pending HTTP proxy requests awaiting a response from the local daemon. */
  private pendingHttp: Map<string, PendingHttpRequest> = new Map();

  /** Per-connection heartbeat interval handles, keyed by machine_id. */
  private heartbeatTimers: Map<string, ReturnType<typeof setInterval>> = new Map();

  /** Per-connection pong timeout handles, keyed by machine_id. */
  private pongTimers: Map<string, ReturnType<typeof setTimeout>> = new Map();

  /** Version metadata from each node's register message, keyed by machine_id. */
  private nodeMetadata: Map<string, { oak_version?: string; template_hash?: string }> = new Map();

  constructor(state: DurableObjectState, env: Env) {
    this.state = state;
    this.env = env;

    // Initialize DO SQLite table for buffering observations.
    this.state.storage.sql.exec(`
      CREATE TABLE IF NOT EXISTS pending_obs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_machine_id TEXT NOT NULL,
        payload TEXT NOT NULL,
        created_at TEXT NOT NULL,
        for_machine_id TEXT NOT NULL
      )
    `);
    this.state.storage.sql.exec(
      "CREATE INDEX IF NOT EXISTS idx_pending_for ON pending_obs(for_machine_id)"
    );
  }

  // -----------------------------------------------------------------------
  // fetch() -- called by the Worker for /mcp, /ws, /health, /tools, /obs/pending
  // -----------------------------------------------------------------------

  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname === "/ws") {
      return this.handleWebSocketUpgrade(request);
    }

    if (url.pathname === "/mcp" && request.method === "POST") {
      return this.handleToolCall(request);
    }

    if (url.pathname.startsWith("/api/team/")) {
      return this.handleHttpProxy(request);
    }

    if (url.pathname === "/obs/pending" && request.method === "GET") {
      return this.handleObsPending(url);
    }

    if (url.pathname === "/obs/stats" && request.method === "GET") {
      return this.handleObsStats();
    }

    if (url.pathname === "/health") {
      const allSockets = this.state.getWebSockets();
      return Response.json({
        status: "ok",
        instance_connected: allSockets.length > 0,
        connected_nodes: allSockets.length,
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
    const pair = new WebSocketPair();
    const [client, server] = Object.values(pair);

    // Do NOT call acceptWebSocket yet — wait for the register message so we
    // can tag with machine_id. Store the server side temporarily unaccepted.
    // CF requires us to accept before returning the 101, but we accept without
    // a tag for now and will re-tag after register.
    this.state.acceptWebSocket(server);

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
        this.handleRegister(msg as RegisterMessage, _ws);
        break;
      case RelayMessageType.TOOL_RESULT:
        this.resolveToolCall(msg as ToolCallResponse);
        break;
      case RelayMessageType.HEARTBEAT_ACK:
        this.handleHeartbeatAck(_ws);
        break;
      case RelayMessageType.HTTP_RESPONSE:
        this.resolveHttpProxy(msg as HttpResponseMessage);
        break;
      case RelayMessageType.OBS_PUSH:
        this.handleObsPush(msg as ObsPushMessage, _ws);
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
    const machineId = this.getMachineId(_ws);
    if (machineId) {
      this.stopHeartbeat(machineId);
      this.nodeMetadata.delete(machineId);
    }
    this.broadcastNodeList();
  }

  webSocketError(_ws: WebSocket, _error: unknown): void {
    const machineId = this.getMachineId(_ws);
    if (machineId) {
      this.stopHeartbeat(machineId);
      this.nodeMetadata.delete(machineId);
    }
    this.broadcastNodeList();
  }

  // -----------------------------------------------------------------------
  // Registration
  // -----------------------------------------------------------------------

  private handleRegister(msg: RegisterMessage, ws: WebSocket): void {
    // Validate the relay token sent inside the register message.
    if (msg.token !== this.env.RELAY_TOKEN) {
      const error = JSON.stringify({
        type: RelayMessageType.ERROR,
        message: "invalid relay token",
        code: "auth_failed",
      });
      ws.send(error);
      ws.close(4003, "invalid token");
      return;
    }

    const machineId = msg.machine_id;

    // Close any existing connection for this machine_id.
    // NOTE: sockets are accepted without a CF tag (tag must be known at accept
    // time; machine_id arrives later in the register message). We use
    // serializeAttachment to store machine_id, so we must iterate all sockets
    // and filter by getMachineId() rather than using getWebSockets(machineId).
    for (const old of this.state.getWebSockets()) {
      if (old !== ws && this.getMachineId(old) === machineId) {
        try {
          old.close(1000, "replaced by new connection");
        } catch {
          // already closed
        }
      }
    }

    // Re-accept with machine_id tag. CF DO WS Hibernation API allows
    // calling acceptWebSocket only once per WS. Since we already accepted
    // above without a tag, we use serializeAttachment to store the machine_id.
    ws.serializeAttachment({ machineId });

    // Store version metadata for this node.
    this.nodeMetadata.set(machineId, {
      oak_version: msg.oak_version,
      template_hash: msg.template_hash,
    });

    // Store the tool list from the daemon.
    this.tools = (msg.tools || []).map((t) => ({
      name: (t as Record<string, unknown>).name as string,
      description: (t as Record<string, unknown>).description as string | undefined,
      inputSchema: (t as Record<string, unknown>).inputSchema as
        | Record<string, unknown>
        | undefined,
    }));

    // Send registered confirmation.
    const registered: RegisteredMessage = {
      type: RelayMessageType.REGISTERED,
    };
    ws.send(JSON.stringify(registered));

    // Broadcast updated node list to all connections.
    this.broadcastNodeList();

    // Drain pending observations buffered for this machine.
    this.drainPendingObs(machineId, ws);

    // Start heartbeat for this connection.
    this.startHeartbeat(machineId);
  }

  // -----------------------------------------------------------------------
  // Tool call request/response flow
  // -----------------------------------------------------------------------

  private async handleToolCall(request: Request): Promise<Response> {
    const url = new URL(request.url);
    const targetMachineId = url.searchParams.get("machine_id");

    const ws = this.getTargetSocket(targetMachineId);
    if (!ws) {
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
      ws.send(JSON.stringify(body));
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
  // HTTP proxy request/response flow
  // -----------------------------------------------------------------------

  private async handleHttpProxy(request: Request): Promise<Response> {
    const ws = this.getTargetSocket(null);
    if (!ws) {
      return Response.json({ error: "instance offline" }, { status: 502 });
    }

    const url = new URL(request.url);
    const requestId = crypto.randomUUID();
    const body = await request.text();

    const httpMsg: HttpRequestMessage = {
      type: RelayMessageType.HTTP_REQUEST,
      request_id: requestId,
      method: request.method,
      path: url.pathname + url.search,
      headers: Object.fromEntries(request.headers),
      body: body || null,
    };

    const responsePromise = new Promise<HttpResponseMessage>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pendingHttp.delete(requestId);
        reject(new Error("HTTP proxy request timed out"));
      }, DEFAULT_TOOL_TIMEOUT_MS);

      this.pendingHttp.set(requestId, { resolve, reject, timer });
    });

    try {
      ws.send(JSON.stringify(httpMsg));
    } catch {
      this.pendingHttp.delete(requestId);
      return Response.json(
        { error: "failed to send to local instance" },
        { status: 502 },
      );
    }

    try {
      const msg = await responsePromise;
      return new Response(msg.body, {
        status: msg.status,
        headers: msg.headers,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "unknown error";
      return Response.json({ error: message }, { status: 504 });
    }
  }

  private resolveHttpProxy(msg: HttpResponseMessage): void {
    const entry = this.pendingHttp.get(msg.request_id);
    if (!entry) return;

    clearTimeout(entry.timer);
    this.pendingHttp.delete(msg.request_id);
    entry.resolve(msg);
  }

  // -----------------------------------------------------------------------
  // Observation sync
  // -----------------------------------------------------------------------

  private handleObsPush(msg: ObsPushMessage, senderWs: WebSocket): void {
    const senderMachineId = this.getMachineId(senderWs) ?? "unknown";
    const allSockets = this.state.getWebSockets();

    // Serialize once for all peers.
    const batch: ObsBatchMessage = {
      type: RelayMessageType.OBS_BATCH,
      from_machine_id: senderMachineId,
      observations: msg.observations,
    };
    const serialized = JSON.stringify(batch);

    for (const ws of allSockets) {
      const machineId = this.getMachineId(ws);
      if (machineId === senderMachineId) continue;

      try {
        ws.send(serialized);
      } catch {
        // WS closed — buffer all observations for this peer in one bulk INSERT.
        if (machineId && msg.observations.length > 0) {
          const now = new Date().toISOString();
          const placeholders = msg.observations.map(() => "(?, ?, ?, ?)").join(", ");
          const values: unknown[] = [];
          for (const obs of msg.observations) {
            values.push(senderMachineId, JSON.stringify(obs), now, machineId);
          }
          this.state.storage.sql.exec(
            `INSERT INTO pending_obs (from_machine_id, payload, created_at, for_machine_id) VALUES ${placeholders}`,
            ...values,
          );
        }
      }
    }
  }

  private handleObsPending(url: URL): Response {
    const machineId = url.searchParams.get("machine_id");
    if (!machineId) {
      return Response.json({ error: "missing machine_id" }, { status: 400 });
    }

    const rows = this.state.storage.sql.exec(
      "SELECT id, from_machine_id, payload FROM pending_obs WHERE for_machine_id = ? ORDER BY id ASC LIMIT ?",
      machineId,
      PENDING_OBS_DRAIN_LIMIT,
    ).toArray();

    const ids = rows.map((r) => r.id as number);
    if (ids.length) {
      this.state.storage.sql.exec(
        `DELETE FROM pending_obs WHERE id IN (${ids.join(",")})`,
      );
    }

    return Response.json({
      observations: rows.map((r) => ({
        from_machine_id: r.from_machine_id,
        obs: JSON.parse(r.payload as string),
      })),
    });
  }

  private handleObsStats(): Response {
    const rows = this.state.storage.sql.exec(
      "SELECT for_machine_id, COUNT(*) as cnt FROM pending_obs GROUP BY for_machine_id",
    ).toArray();

    const pending: Record<string, number> = {};
    for (const row of rows) {
      pending[row.for_machine_id as string] = row.cnt as number;
    }

    return Response.json({ pending });
  }

  private drainPendingObs(machineId: string, ws: WebSocket): void {
    const rows = this.state.storage.sql.exec(
      "SELECT id, from_machine_id, payload FROM pending_obs WHERE for_machine_id = ? ORDER BY id ASC LIMIT ?",
      machineId,
      PENDING_OBS_DRAIN_LIMIT,
    ).toArray();

    if (!rows.length) return;

    // Group by from_machine_id for batched delivery.
    const grouped = new Map<string, unknown[]>();
    const ids: number[] = [];

    for (const row of rows) {
      ids.push(row.id as number);
      const fromId = row.from_machine_id as string;
      const obs = JSON.parse(row.payload as string);
      const list = grouped.get(fromId) ?? [];
      list.push(obs);
      grouped.set(fromId, list);
    }

    for (const [fromId, observations] of grouped) {
      const batch: ObsBatchMessage = {
        type: RelayMessageType.OBS_BATCH,
        from_machine_id: fromId,
        observations,
      };
      try {
        ws.send(JSON.stringify(batch));
      } catch {
        // If send fails during drain, leave the rows — they'll be picked up later.
        return;
      }
    }

    // All sent successfully — delete drained rows.
    if (ids.length) {
      this.state.storage.sql.exec(
        `DELETE FROM pending_obs WHERE id IN (${ids.join(",")})`,
      );
    }
  }

  // -----------------------------------------------------------------------
  // Node list broadcast
  // -----------------------------------------------------------------------

  private broadcastNodeList(): void {
    const allSockets = this.state.getWebSockets();
    const nodes: { machine_id: string; online: boolean; oak_version?: string; template_hash?: string }[] = [];
    const seen = new Set<string>();

    for (const ws of allSockets) {
      const machineId = this.getMachineId(ws);
      if (machineId && !seen.has(machineId)) {
        seen.add(machineId);
        const meta = this.nodeMetadata.get(machineId);
        nodes.push({ machine_id: machineId, online: true, ...meta });
      }
    }

    const msg: NodeListMessage = {
      type: RelayMessageType.NODE_LIST,
      nodes,
    };
    const payload = JSON.stringify(msg);

    for (const ws of allSockets) {
      try {
        ws.send(payload);
      } catch {
        // ignore send errors — socket will be cleaned up on next event
      }
    }
  }

  // -----------------------------------------------------------------------
  // Heartbeat (per-connection, keyed by machine_id)
  // -----------------------------------------------------------------------

  private startHeartbeat(machineId: string): void {
    this.stopHeartbeat(machineId);
    this.heartbeatTimers.set(
      machineId,
      setInterval(() => {
        this.sendPing(machineId);
      }, HEARTBEAT_INTERVAL_MS),
    );
  }

  private stopHeartbeat(machineId: string): void {
    const hb = this.heartbeatTimers.get(machineId);
    if (hb) {
      clearInterval(hb);
      this.heartbeatTimers.delete(machineId);
    }
    const pt = this.pongTimers.get(machineId);
    if (pt) {
      clearTimeout(pt);
      this.pongTimers.delete(machineId);
    }
  }

  private sendPing(machineId: string): void {
    const ws = this.getSocketByMachineId(machineId);
    if (!ws) {
      this.stopHeartbeat(machineId);
      return;
    }

    const ping: HeartbeatPing = {
      type: RelayMessageType.HEARTBEAT,
      timestamp: new Date().toISOString(),
    };

    try {
      ws.send(JSON.stringify(ping));
    } catch {
      this.stopHeartbeat(machineId);
      this.broadcastNodeList();
      return;
    }

    this.pongTimers.set(
      machineId,
      setTimeout(() => {
        // Heartbeat ack overdue — close the connection.
        const deadWs = this.getSocketByMachineId(machineId);
        if (deadWs) {
          try {
            deadWs.close(1000, "heartbeat timeout");
          } catch {
            // already closed
          }
        }
        this.stopHeartbeat(machineId);
        this.broadcastNodeList();
      }, HEARTBEAT_TIMEOUT_MS),
    );
  }

  private handleHeartbeatAck(ws: WebSocket): void {
    const machineId = this.getMachineId(ws);
    if (!machineId) return;

    const pt = this.pongTimers.get(machineId);
    if (pt) {
      clearTimeout(pt);
      this.pongTimers.delete(machineId);
    }
  }

  // -----------------------------------------------------------------------
  // Connection helpers
  // -----------------------------------------------------------------------

  /** Get the machine_id from a WebSocket's serialized attachment. */
  private getMachineId(ws: WebSocket): string | null {
    try {
      const attachment = ws.deserializeAttachment() as { machineId?: string } | null;
      return attachment?.machineId ?? null;
    } catch {
      return null;
    }
  }

  /** Get a WebSocket by machine_id, or null if not connected. */
  private getSocketByMachineId(machineId: string): WebSocket | null {
    const allSockets = this.state.getWebSockets();
    for (const ws of allSockets) {
      if (this.getMachineId(ws) === machineId) {
        return ws;
      }
    }
    return null;
  }

  /** Get the target socket for a request — specific machine or first available. */
  private getTargetSocket(machineId: string | null): WebSocket | null {
    if (machineId) {
      return this.getSocketByMachineId(machineId);
    }
    // Return the first connected socket that has a machine_id (registered).
    const allSockets = this.state.getWebSockets();
    for (const ws of allSockets) {
      if (this.getMachineId(ws)) {
        return ws;
      }
    }
    return null;
  }

}
