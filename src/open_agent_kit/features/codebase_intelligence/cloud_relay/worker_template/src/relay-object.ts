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
  type FederatedToolCallMessage,
  type FederatedToolResultMessage,
  type HeartbeatPing,
  type HttpRequestMessage,
  type HttpResponseMessage,
  type NodeListMessage,
  type ObsBatchMessage,
  type ObsPushMessage,
  type PendingFederatedTool,
  type PendingHttpRequest,
  type PendingRequest,
  type PendingSearch,
  type RegisterMessage,
  type RegisteredMessage,
  type RelayMessage,
  type SearchQueryMessage,
  type SearchResultMessage,
  type RelayMetricsResponse,
  type ToolCallRequest,
  type ToolCallResponse,
  type ToolInfo,
} from "./types";

const HEARTBEAT_INTERVAL_MS = 30_000;
const HEARTBEAT_TIMEOUT_MS = 10_000;
const DEFAULT_TOOL_TIMEOUT_MS = 30_000;
const PENDING_OBS_DRAIN_LIMIT = 500;
const OBS_HISTORY_RETENTION_DAYS = 7;
const OBS_HISTORY_DEFAULT_LIMIT = 500;
const MS_PER_DAY = 86_400_000;
const FEDERATED_SEARCH_TIMEOUT_MS = 3_000;
const FEDERATED_SEARCH_DEFAULT_LIMIT = 10;
const FEDERATED_SEARCH_MAX_RESULTS = 50;
const CAPABILITY_FEDERATED_TOOLS = "federated_tools_v1";
const FEDERATED_TOOL_TIMEOUT_MS = 10_000;
const FEDERATED_TOOL_MAX_RESULTS = 50;
/** Probability of running TTL cleanup on each obs push (1%). */
const OBS_HISTORY_CLEANUP_PROBABILITY = 0.01;

/** Cache TTL (in seconds) for federated tool calls, keyed by tool name. */
const CACHE_TTL_BY_TOOL: Record<string, number> = {
  oak_stats: 120,
  oak_sessions: 60,
  oak_memories: 60,
};
/** Probability of running expired-cache cleanup on each cache write (2%). */
const CACHE_CLEANUP_PROBABILITY = 0.02;
/** Maximum rows kept in relay_metrics before trimming oldest. */
const METRICS_MAX_ROWS = 10_000;
/** Probability of trimming relay_metrics on each metric insert (1%). */
const METRICS_CLEANUP_PROBABILITY = 0.01;
/** Metric event types recorded in relay_metrics. */
const METRIC_EVENT_FAN_OUT = "fan_out";
const METRIC_EVENT_CACHE_HIT = "cache_hit";

export class RelayObject implements DurableObject {
  private state: DurableObjectState;
  private env: Env;

  /** Tool lists from each node's register message, keyed by machine_id. */
  private nodeTools: Map<string, ToolInfo[]> = new Map();

  /** Pending tool call requests awaiting a response from the local daemon. */
  private pending: Map<string, PendingRequest> = new Map();

  /** Pending HTTP proxy requests awaiting a response from the local daemon. */
  private pendingHttp: Map<string, PendingHttpRequest> = new Map();

  /** Per-connection heartbeat interval handles, keyed by machine_id. */
  private heartbeatTimers: Map<string, ReturnType<typeof setInterval>> = new Map();

  /** Per-connection pong timeout handles, keyed by machine_id. */
  private pongTimers: Map<string, ReturnType<typeof setTimeout>> = new Map();

  /** Version metadata from each node's register message, keyed by machine_id. */
  private nodeMetadata: Map<string, { oak_version?: string; template_hash?: string; capabilities?: string[] }> = new Map();

  /** Pending federated search requests awaiting results from peer nodes. */
  private pendingSearch: Map<string, PendingSearch> = new Map();

  /** Pending federated tool call requests awaiting results from peer nodes. */
  private pendingFederatedTool: Map<string, PendingFederatedTool> = new Map();

  /** Machine ID of the first node to register (preferred target for unrouted calls). */
  private homeMachineId: string | null = null;

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

    // Observation history table for new-node catch-up.
    this.state.storage.sql.exec(`
      CREATE TABLE IF NOT EXISTS obs_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_machine_id TEXT NOT NULL,
        payload TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
      )
    `);
    this.state.storage.sql.exec(
      "CREATE UNIQUE INDEX IF NOT EXISTS idx_obs_history_hash ON obs_history(content_hash)"
    );
    this.state.storage.sql.exec(
      "CREATE INDEX IF NOT EXISTS idx_obs_history_created ON obs_history(created_at)"
    );

    // Persisted node state — survives DO hibernation and Worker redeployment.
    // Stores tool lists and metadata (capabilities, version) for each node.
    this.state.storage.sql.exec(`
      CREATE TABLE IF NOT EXISTS node_state (
        machine_id TEXT PRIMARY KEY,
        tools_json TEXT NOT NULL,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        is_home INTEGER NOT NULL DEFAULT 0,
        registered_at TEXT NOT NULL
      )
    `);
    // Migration: drop old table name if it exists from a prior deploy.
    this.state.storage.sql.exec("DROP TABLE IF EXISTS node_tools");

    // Federated tool call cache — short-TTL results keyed by tool+args+peer set.
    this.state.storage.sql.exec(`
      CREATE TABLE IF NOT EXISTS tool_cache (
        cache_key TEXT PRIMARY KEY,
        tool_name TEXT NOT NULL,
        result_json TEXT NOT NULL,
        node_set_hash TEXT NOT NULL,
        created_at TEXT NOT NULL,
        ttl_seconds INTEGER NOT NULL
      )
    `);

    // Relay metrics — fan-out and cache-hit counters + latency.
    this.state.storage.sql.exec(`
      CREATE TABLE IF NOT EXISTS relay_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tool_name TEXT NOT NULL,
        event_type TEXT NOT NULL,
        latency_ms INTEGER,
        node_count INTEGER,
        created_at TEXT NOT NULL
      )
    `);
    this.state.storage.sql.exec(
      "CREATE INDEX IF NOT EXISTS idx_relay_metrics_tool_event ON relay_metrics(tool_name, event_type, latency_ms)"
    );
    // Drop legacy index superseded by the composite index above.
    this.state.storage.sql.exec("DROP INDEX IF EXISTS idx_relay_metrics_created");

    // Rehydrate in-memory maps from SQLite on wake.
    this.rehydrateNodeState();
  }

  // -----------------------------------------------------------------------
  // fetch() -- called by the Worker for /mcp, /ws, /health, /tools, /obs/*
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

    if (url.pathname === "/obs/history" && request.method === "GET") {
      return this.handleObsHistory(url);
    }

    if (url.pathname === "/obs/stats" && request.method === "GET") {
      return this.handleObsStats();
    }

    if (url.pathname === "/search" && request.method === "POST") {
      return this.handleSearchFanout(request);
    }

    if (url.pathname === "/federate-tool" && request.method === "POST") {
      return this.handleFederatedToolFanout(request);
    }

    if (url.pathname === "/metrics" && request.method === "GET") {
      return this.handleMetrics();
    }

    if (url.pathname === "/tool-call" && request.method === "POST") {
      return this.handleToolCall(request);
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
      return Response.json({ tools: this.getAggregatedTools() });
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
      case RelayMessageType.SEARCH_RESULT:
        this.resolveSearchResult(msg as SearchResultMessage);
        break;
      case RelayMessageType.FEDERATED_TOOL_RESULT:
        this.resolveFederatedToolResult(msg as FederatedToolResultMessage);
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
      // Only clean up node state if this socket is still the active one for
      // this machine.  When a node re-registers, handleRegister() closes the
      // old socket *after* storing metadata for the new one.  If we
      // unconditionally delete here, the new metadata is wiped.
      if (this.isActiveSocket(_ws, machineId)) {
        this.nodeMetadata.delete(machineId);
        this.nodeTools.delete(machineId);
        this.removeNodeState(machineId);
        if (machineId === this.homeMachineId) {
          this.homeMachineId = null;
        }
      }
    }
    this.broadcastNodeList();
  }

  webSocketError(_ws: WebSocket, _error: unknown): void {
    const machineId = this.getMachineId(_ws);
    if (machineId) {
      this.stopHeartbeat(machineId);
      if (this.isActiveSocket(_ws, machineId)) {
        this.nodeMetadata.delete(machineId);
        this.nodeTools.delete(machineId);
        this.removeNodeState(machineId);
        if (machineId === this.homeMachineId) {
          this.homeMachineId = null;
        }
      }
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

    // Tag the new socket with machine_id BEFORE closing the old one.
    // This ensures webSocketClose on the stale socket sees a newer active
    // socket and skips metadata cleanup (via isActiveSocket).
    ws.serializeAttachment({ machineId });

    // Close any existing connection for this machine_id.
    // NOTE: sockets are accepted without a CF tag (tag must be known at accept
    // time; machine_id arrives later in the register message). We use
    // serializeAttachment to store machine_id, so we must iterate all sockets
    // and filter by getMachineId() rather than using getWebSockets(machineId).
    for (const old of this.state.getWebSockets()) {
      if (old !== ws && this.getMachineId(old) === machineId) {
        try {
          old.close(1000, "replaced by new connection");
        } catch (err) {
          console.error("Failed to close old WS for machine", machineId, err);
        }
      }
    }

    // First node to register becomes the home node (preferred for unrouted calls).
    if (!this.homeMachineId) {
      this.homeMachineId = machineId;
    }

    // Store version metadata and capabilities for this node.
    this.nodeMetadata.set(machineId, {
      oak_version: msg.oak_version,
      template_hash: msg.template_hash,
      capabilities: msg.capabilities,
    });

    // Store the tool list from this node (keyed by machine_id).
    const parsed: ToolInfo[] = (msg.tools || []).map((t) => ({
      name: (t as Record<string, unknown>).name as string,
      description: (t as Record<string, unknown>).description as string | undefined,
      inputSchema: (t as Record<string, unknown>).inputSchema as
        | Record<string, unknown>
        | undefined,
    }));
    this.nodeTools.set(machineId, parsed);

    // Persist to SQLite so tools/metadata survive DO hibernation and Worker redeploys.
    this.persistNodeState(machineId);
    // If this node is home, clear any stale is_home flags from other nodes.
    if (machineId === this.homeMachineId) {
      try {
        this.state.storage.sql.exec(
          "UPDATE node_state SET is_home = 0 WHERE machine_id != ?",
          machineId,
        );
      } catch (err) {
        console.error("Failed to clear stale is_home flags:", err);
      }
    }

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
    } catch (err) {
      console.error("Failed to send tool call to daemon:", err);
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
    } catch (err) {
      console.error("Failed to send HTTP proxy request to daemon:", err);
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

  private async handleObsPush(msg: ObsPushMessage, senderWs: WebSocket): Promise<void> {
    const senderMachineId = this.getMachineId(senderWs) ?? "unknown";
    const allSockets = this.state.getWebSockets();
    const now = new Date().toISOString();

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
      } catch (sendErr) {
        // WS closed — buffer all observations for this peer in one bulk INSERT.
        console.error("Failed to send obs batch to peer", machineId, sendErr);
        if (machineId && msg.observations.length > 0) {
          const placeholders = msg.observations.map(() => "(?, ?, ?, ?)").join(", ");
          const values: unknown[] = [];
          for (const obs of msg.observations) {
            values.push(senderMachineId, JSON.stringify(obs), now, machineId);
          }
          try {
            this.state.storage.sql.exec(
              `INSERT INTO pending_obs (from_machine_id, payload, created_at, for_machine_id) VALUES ${placeholders}`,
              ...values,
            );
          } catch (sqlErr) {
            console.error("Failed to buffer pending_obs for peer", machineId, sqlErr);
          }
        }
      }
    }

    // Store in obs_history for new-node catch-up (dedup by content_hash via UNIQUE index).
    if (msg.observations.length > 0) {
      const placeholders = msg.observations.map(() => "(?, ?, ?, ?)").join(", ");
      const values: unknown[] = [];
      for (const obs of msg.observations) {
        const record = obs as Record<string, unknown>;
        const contentHash = typeof record.content_hash === "string"
          ? record.content_hash
          : await this.sha256Payload(JSON.stringify(obs));
        values.push(senderMachineId, JSON.stringify(obs), contentHash, now);
      }
      try {
        this.state.storage.sql.exec(
          `INSERT OR IGNORE INTO obs_history (from_machine_id, payload, content_hash, created_at) VALUES ${placeholders}`,
          ...values,
        );
      } catch (err) {
        console.error("Failed to insert obs_history batch:", err);
      }

      // TTL cleanup — run probabilistically to avoid per-push overhead.
      if (Math.random() < OBS_HISTORY_CLEANUP_PROBABILITY) {
        const cutoff = new Date(Date.now() - OBS_HISTORY_RETENTION_DAYS * MS_PER_DAY).toISOString();
        try {
          this.state.storage.sql.exec(
            "DELETE FROM obs_history WHERE created_at < ?",
            cutoff,
          );
        } catch (err) {
          console.error("Failed to clean up expired obs_history:", err);
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
      const placeholders = ids.map(() => "?").join(", ");
      this.state.storage.sql.exec(
        `DELETE FROM pending_obs WHERE id IN (${placeholders})`,
        ...ids,
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

  private handleObsHistory(url: URL): Response {
    const machineId = url.searchParams.get("machine_id");
    if (!machineId) {
      return Response.json({ error: "missing machine_id" }, { status: 400 });
    }

    const since = url.searchParams.get("since");
    const limit = Math.min(
      parseInt(url.searchParams.get("limit") ?? String(OBS_HISTORY_DEFAULT_LIMIT), 10) || OBS_HISTORY_DEFAULT_LIMIT,
      OBS_HISTORY_DEFAULT_LIMIT,
    );
    const offset = parseInt(url.searchParams.get("offset") ?? "0", 10) || 0;

    let rows;
    if (since) {
      rows = this.state.storage.sql.exec(
        "SELECT from_machine_id, payload, created_at FROM obs_history WHERE from_machine_id != ? AND created_at >= ? ORDER BY id ASC LIMIT ? OFFSET ?",
        machineId,
        since,
        limit,
        offset,
      ).toArray();
    } else {
      rows = this.state.storage.sql.exec(
        "SELECT from_machine_id, payload, created_at FROM obs_history WHERE from_machine_id != ? ORDER BY id ASC LIMIT ? OFFSET ?",
        machineId,
        limit,
        offset,
      ).toArray();
    }

    return Response.json({
      observations: rows.map((r) => ({
        from_machine_id: r.from_machine_id,
        obs: JSON.parse(r.payload as string),
        created_at: r.created_at,
      })),
      count: rows.length,
      limit,
      offset,
    });
  }

  /** SHA-256 hash fallback for observations missing content_hash. */
  private async sha256Payload(payload: string): Promise<string> {
    const data = new TextEncoder().encode(payload);
    const hashBuffer = await crypto.subtle.digest("SHA-256", data);
    const hashArray = new Uint8Array(hashBuffer);
    return Array.from(hashArray, (b) => b.toString(16).padStart(2, "0")).join("");
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
      } catch (err) {
        // If send fails during drain, leave the rows — they'll be picked up later.
        console.error("Failed to send drain batch to machine", machineId, err);
        return;
      }
    }

    // All sent successfully — delete drained rows.
    if (ids.length) {
      const placeholders = ids.map(() => "?").join(", ");
      this.state.storage.sql.exec(
        `DELETE FROM pending_obs WHERE id IN (${placeholders})`,
        ...ids,
      );
    }
  }

  // -----------------------------------------------------------------------
  // Federated search fan-out
  // -----------------------------------------------------------------------

  private async handleSearchFanout(request: Request): Promise<Response> {
    const url = new URL(request.url);
    const requesterMachineId = url.searchParams.get("machine_id");

    let body: { query: string; search_type?: string; limit?: number };
    try {
      body = (await request.json()) as { query: string; search_type?: string; limit?: number };
    } catch {
      return Response.json({ error: "invalid request body" }, { status: 400 });
    }

    if (!body.query) {
      return Response.json({ error: "missing query" }, { status: 400 });
    }

    const capablePeers = this.getCapablePeers(requesterMachineId, CAPABILITY_FEDERATED_TOOLS);

    if (capablePeers.length === 0) {
      return Response.json({ results: [] });
    }

    const requestId = crypto.randomUUID();
    const queryMsg: SearchQueryMessage = {
      type: RelayMessageType.SEARCH_QUERY,
      request_id: requestId,
      query: body.query,
      search_type: body.search_type ?? "all",
      limit: body.limit ?? FEDERATED_SEARCH_DEFAULT_LIMIT,
      from_machine_id: requesterMachineId ?? "",
    };
    const serialized = JSON.stringify(queryMsg);

    let sentCount = 0;
    for (const { machineId: peerId, ws } of capablePeers) {
      try {
        ws.send(serialized);
        sentCount++;
      } catch (err) {
        console.error("Failed to send search query to peer", peerId, err);
      }
    }

    if (sentCount === 0) {
      return Response.json({ results: [] });
    }

    const resultsPromise = new Promise<SearchResultMessage[]>((resolve) => {
      const timer = setTimeout(() => {
        const entry = this.pendingSearch.get(requestId);
        if (entry) {
          this.pendingSearch.delete(requestId);
          resolve(entry.results);
        } else {
          resolve([]);
        }
      }, FEDERATED_SEARCH_TIMEOUT_MS);

      this.pendingSearch.set(requestId, {
        results: [],
        expectedCount: sentCount,
        resolve,
        timer,
      });
    });

    const searchResults = await resultsPromise;

    const merged: Record<string, unknown>[] = [];
    for (const sr of searchResults) {
      for (const item of sr.results) {
        if (merged.length >= FEDERATED_SEARCH_MAX_RESULTS) break;
        merged.push({ ...item, machine_id: sr.from_machine_id });
      }
      if (merged.length >= FEDERATED_SEARCH_MAX_RESULTS) break;
    }

    return Response.json({ results: merged });
  }

  private resolveSearchResult(msg: SearchResultMessage): void {
    const entry = this.pendingSearch.get(msg.request_id);
    if (!entry) return;

    entry.results.push(msg);

    if (entry.results.length >= entry.expectedCount) {
      clearTimeout(entry.timer);
      this.pendingSearch.delete(msg.request_id);
      entry.resolve(entry.results);
    }
  }

  // -----------------------------------------------------------------------
  // Federated tool call fan-out (with caching)
  // -----------------------------------------------------------------------

  private async handleFederatedToolFanout(request: Request): Promise<Response> {
    const startTime = Date.now();
    const url = new URL(request.url);
    const requesterMachineId = url.searchParams.get("machine_id");

    let body: { tool_name: string; arguments?: Record<string, unknown>; no_cache?: boolean };
    try {
      body = (await request.json()) as { tool_name: string; arguments?: Record<string, unknown>; no_cache?: boolean };
    } catch {
      return Response.json({ error: "invalid request body" }, { status: 400 });
    }

    if (!body.tool_name) {
      return Response.json({ error: "missing tool_name" }, { status: 400 });
    }

    const capablePeers = this.getCapablePeers(requesterMachineId, CAPABILITY_FEDERATED_TOOLS);

    if (capablePeers.length === 0) {
      return Response.json({ results: [] });
    }

    // Check cache for cacheable tools.
    const ttl = CACHE_TTL_BY_TOOL[body.tool_name];
    let cacheKey: string | undefined;
    let nodeSetHash: string | undefined;

    if (ttl && !body.no_cache) {
      const peerMachineIds = capablePeers.map((p) => p.machineId);
      const keyResult = await this.buildCacheKey(body.tool_name, body.arguments ?? {}, peerMachineIds);
      cacheKey = keyResult.cacheKey;
      nodeSetHash = keyResult.nodeSetHash;
      const cached = this.getCachedResult(cacheKey);
      if (cached) {
        this.recordMetric(body.tool_name, METRIC_EVENT_CACHE_HIT, Date.now() - startTime, 0);
        return Response.json({ ...cached, _cache: { hit: true } });
      }
    }

    const requestId = crypto.randomUUID();
    const callMsg: FederatedToolCallMessage = {
      type: RelayMessageType.FEDERATED_TOOL_CALL,
      request_id: requestId,
      tool_name: body.tool_name,
      arguments: body.arguments ?? {},
      from_machine_id: requesterMachineId ?? "",
    };
    const serialized = JSON.stringify(callMsg);

    let sentCount = 0;
    for (const { machineId: peerId, ws } of capablePeers) {
      try {
        ws.send(serialized);
        sentCount++;
      } catch (err) {
        console.error("Failed to send federated tool call to peer", peerId, err);
      }
    }

    if (sentCount === 0) {
      return Response.json({ results: [] });
    }

    const resultsPromise = new Promise<FederatedToolResultMessage[]>((resolve) => {
      const timer = setTimeout(() => {
        const entry = this.pendingFederatedTool.get(requestId);
        if (entry) {
          this.pendingFederatedTool.delete(requestId);
          resolve(entry.results);
        } else {
          resolve([]);
        }
      }, FEDERATED_TOOL_TIMEOUT_MS);

      this.pendingFederatedTool.set(requestId, {
        results: [],
        expectedCount: sentCount,
        resolve,
        timer,
      });
    });

    const toolResults = await resultsPromise;
    const latencyMs = Date.now() - startTime;

    const merged: { from_machine_id: string; result?: unknown; error?: string }[] = [];
    for (const tr of toolResults) {
      if (merged.length >= FEDERATED_TOOL_MAX_RESULTS) break;
      merged.push({
        from_machine_id: tr.from_machine_id ?? "unknown",
        result: tr.result,
        error: tr.error,
      });
    }

    const responseBody = { results: merged };

    // Record fan-out metric and cache result if cacheable.
    this.recordMetric(body.tool_name, METRIC_EVENT_FAN_OUT, latencyMs, sentCount);
    if (cacheKey && nodeSetHash) {
      this.setCachedResult(cacheKey, body.tool_name, responseBody, nodeSetHash, ttl);
    }

    return Response.json({ ...responseBody, _cache: { hit: false } });
  }

  private resolveFederatedToolResult(msg: FederatedToolResultMessage): void {
    const entry = this.pendingFederatedTool.get(msg.request_id);
    if (!entry) return;

    entry.results.push(msg);

    if (entry.results.length >= entry.expectedCount) {
      clearTimeout(entry.timer);
      this.pendingFederatedTool.delete(msg.request_id);
      entry.resolve(entry.results);
    }
  }

  // -----------------------------------------------------------------------
  // Metrics endpoint
  // -----------------------------------------------------------------------

  private handleMetrics(): Response {
    try {
      // Aggregate counts by event type in a single query.
      const aggRows = this.state.storage.sql.exec(
        `SELECT event_type, COUNT(*) as cnt FROM relay_metrics
         WHERE event_type IN (?, ?)
         GROUP BY event_type`,
        METRIC_EVENT_CACHE_HIT,
        METRIC_EVENT_FAN_OUT,
      ).toArray();

      let cacheHits = 0;
      let fanOutCount = 0;
      for (const row of aggRows) {
        if (row.event_type === METRIC_EVENT_CACHE_HIT) cacheHits = row.cnt as number;
        else if (row.event_type === METRIC_EVENT_FAN_OUT) fanOutCount = row.cnt as number;
      }
      const totalCalls = cacheHits + fanOutCount;
      const cacheHitRate = totalCalls > 0 ? cacheHits / totalCalls : 0;

      // Per-tool breakdown with p95 computed via NTILE to avoid N+1 queries.
      const perToolRows = this.state.storage.sql.exec(`
        SELECT tool_name,
               COUNT(*) as total,
               SUM(CASE WHEN event_type = ? THEN 1 ELSE 0 END) as hits,
               SUM(CASE WHEN event_type = ? THEN 1 ELSE 0 END) as misses,
               AVG(CASE WHEN event_type = ? THEN latency_ms END) as avg_latency_ms
        FROM relay_metrics
        GROUP BY tool_name`,
        METRIC_EVENT_CACHE_HIT,
        METRIC_EVENT_FAN_OUT,
        METRIC_EVENT_FAN_OUT,
      ).toArray();

      // Compute p95 latency per tool in a single query using NTILE window function.
      const p95Rows = this.state.storage.sql.exec(`
        SELECT tool_name, latency_ms FROM (
          SELECT tool_name, latency_ms,
                 NTILE(20) OVER (PARTITION BY tool_name ORDER BY latency_ms) as tile
          FROM relay_metrics
          WHERE event_type = ? AND latency_ms IS NOT NULL
        ) WHERE tile = 20
        GROUP BY tool_name`,
        METRIC_EVENT_FAN_OUT,
      ).toArray();

      const p95Map = new Map<string, number>();
      for (const row of p95Rows) {
        p95Map.set(row.tool_name as string, row.latency_ms as number);
      }

      const perTool: Record<string, {
        total: number; hits: number; misses: number;
        avg_latency_ms: number | null; p95_latency_ms: number | null;
      }> = {};

      for (const row of perToolRows) {
        const toolName = row.tool_name as string;
        perTool[toolName] = {
          total: row.total as number,
          hits: row.hits as number,
          misses: row.misses as number,
          avg_latency_ms: row.avg_latency_ms != null ? Math.round(row.avg_latency_ms as number) : null,
          p95_latency_ms: p95Map.get(toolName) ?? null,
        };
      }

      // Recent latencies (last 20 fan-out events).
      const recentRows = this.state.storage.sql.exec(
        "SELECT tool_name, latency_ms, created_at FROM relay_metrics WHERE event_type = ? ORDER BY id DESC LIMIT 20",
        METRIC_EVENT_FAN_OUT,
      ).toArray();

      const body: RelayMetricsResponse = {
        total_federated_calls: totalCalls,
        cache_hits: cacheHits,
        cache_misses: fanOutCount,
        cache_hit_rate: Math.round(cacheHitRate * 1000) / 1000,
        per_tool: perTool,
        recent_latencies: recentRows.map((r) => ({
          tool_name: r.tool_name as string,
          latency_ms: r.latency_ms as number,
          created_at: r.created_at as string,
        })),
      };
      return Response.json(body);
    } catch (err) {
      console.error("Failed to compute relay metrics:", err);
      return Response.json({ error: "metrics computation failed" }, { status: 500 });
    }
  }

  // -----------------------------------------------------------------------
  // Cache helpers
  // -----------------------------------------------------------------------

  /** Find all connected peers with a given capability, excluding the requester. */
  private getCapablePeers(
    excludeMachineId: string | null,
    capability: string,
  ): { machineId: string; ws: WebSocket }[] {
    const peers: { machineId: string; ws: WebSocket }[] = [];
    const allSockets = this.state.getWebSockets();
    const seen = new Set<string>();

    for (const ws of allSockets) {
      const machineId = this.getMachineId(ws);
      if (!machineId || machineId === excludeMachineId || seen.has(machineId)) continue;
      seen.add(machineId);

      const meta = this.nodeMetadata.get(machineId);
      if (meta?.capabilities?.includes(capability)) {
        peers.push({ machineId, ws });
      }
    }
    return peers;
  }

  /** Build a deterministic cache key from tool name, args, and sorted peer IDs. */
  private async buildCacheKey(
    toolName: string,
    args: Record<string, unknown>,
    peerMachineIds: string[],
  ): Promise<{ cacheKey: string; nodeSetHash: string }> {
    const argsStr = JSON.stringify(args, Object.keys(args).sort());
    const argsHex = (await this.sha256Payload(argsStr)).slice(0, 16);

    const nodeStr = [...peerMachineIds].sort().join(",");
    const nodeSetHash = (await this.sha256Payload(nodeStr)).slice(0, 8);

    return { cacheKey: `fedcache:${toolName}:${argsHex}:${nodeSetHash}`, nodeSetHash };
  }

  /** Look up a cached result, returning null if expired or missing. */
  private getCachedResult(cacheKey: string): Record<string, unknown> | null {
    try {
      const rows = this.state.storage.sql.exec(
        "SELECT result_json, created_at, ttl_seconds FROM tool_cache WHERE cache_key = ?",
        cacheKey,
      ).toArray();

      if (rows.length === 0) return null;

      const row = rows[0];
      const createdAt = new Date(row.created_at as string).getTime();
      const ttl = (row.ttl_seconds as number) * 1000;
      if (Date.now() - createdAt > ttl) {
        // Expired — delete and return miss.
        this.state.storage.sql.exec("DELETE FROM tool_cache WHERE cache_key = ?", cacheKey);
        return null;
      }

      return JSON.parse(row.result_json as string) as Record<string, unknown>;
    } catch (err) {
      console.error("Cache lookup failed:", err);
      return null;
    }
  }

  /** Upsert a cached result and probabilistically clean expired entries. */
  private setCachedResult(
    cacheKey: string,
    toolName: string,
    result: unknown,
    nodeSetHash: string,
    ttlSeconds: number,
  ): void {
    try {
      this.state.storage.sql.exec(
        `INSERT INTO tool_cache (cache_key, tool_name, result_json, node_set_hash, created_at, ttl_seconds)
         VALUES (?, ?, ?, ?, ?, ?)
         ON CONFLICT(cache_key) DO UPDATE SET
           result_json = excluded.result_json,
           node_set_hash = excluded.node_set_hash,
           created_at = excluded.created_at,
           ttl_seconds = excluded.ttl_seconds`,
        cacheKey,
        toolName,
        JSON.stringify(result),
        nodeSetHash,
        new Date().toISOString(),
        ttlSeconds,
      );
    } catch (err) {
      console.error("Cache write failed:", err);
    }

    // Probabilistic cleanup of expired entries.
    if (Math.random() < CACHE_CLEANUP_PROBABILITY) {
      try {
        // Delete entries older than their TTL.
        this.state.storage.sql.exec(
          "DELETE FROM tool_cache WHERE (julianday('now') - julianday(created_at)) * 86400 > ttl_seconds",
        );
      } catch (err) {
        console.error("Cache cleanup failed:", err);
      }
    }
  }

  /** Record a metric event (fan_out or cache_hit) with probabilistic trimming. */
  private recordMetric(
    toolName: string,
    eventType: typeof METRIC_EVENT_FAN_OUT | typeof METRIC_EVENT_CACHE_HIT,
    latencyMs: number,
    nodeCount: number,
  ): void {
    try {
      this.state.storage.sql.exec(
        "INSERT INTO relay_metrics (tool_name, event_type, latency_ms, node_count, created_at) VALUES (?, ?, ?, ?, ?)",
        toolName,
        eventType,
        latencyMs,
        nodeCount,
        new Date().toISOString(),
      );
    } catch (err) {
      console.error("Metric insert failed:", err);
    }

    // Probabilistic trim to keep table bounded.
    if (Math.random() < METRICS_CLEANUP_PROBABILITY) {
      try {
        this.state.storage.sql.exec(
          `DELETE FROM relay_metrics WHERE id NOT IN (
             SELECT id FROM relay_metrics ORDER BY id DESC LIMIT ?
           )`,
          METRICS_MAX_ROWS,
        );
      } catch (err) {
        console.error("Metrics cleanup failed:", err);
      }
    }
  }

  // -----------------------------------------------------------------------
  // Node list broadcast
  // -----------------------------------------------------------------------

  private broadcastNodeList(): void {
    const allSockets = this.state.getWebSockets();
    const nodes: { machine_id: string; online: boolean; oak_version?: string; template_hash?: string; capabilities?: string[] }[] = [];
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
      home_machine_id: this.homeMachineId ?? undefined,
    };
    const payload = JSON.stringify(msg);

    for (const ws of allSockets) {
      try {
        ws.send(payload);
      } catch (err) {
        console.error("Failed to broadcast node list:", err);
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
    } catch (err) {
      console.error("Failed to send heartbeat ping to", machineId, err);
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
          } catch (err) {
            console.error("Failed to close dead WS for", machineId, err);
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

  /** Check if a socket is still the active (newest) connection for a machineId.
   *  Returns false if another socket has since replaced it (e.g., re-register). */
  private isActiveSocket(ws: WebSocket, machineId: string): boolean {
    const current = this.getSocketByMachineId(machineId);
    // If no socket found for this machine, the node is fully gone — treat as active
    // so the close handler can clean up.  If a different socket owns the machine_id,
    // this is a stale close and we should skip cleanup.
    return current === null || current === ws;
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

  /** Get the target socket for a request — specific machine, home node, or first available. */
  private getTargetSocket(machineId: string | null): WebSocket | null {
    if (machineId) {
      return this.getSocketByMachineId(machineId);
    }
    // Prefer the home node (first registrant) for stable routing.
    if (this.homeMachineId) {
      const homeWs = this.getSocketByMachineId(this.homeMachineId);
      if (homeWs) return homeWs;
    }
    // Fallback: first connected socket that has a machine_id (registered).
    const allSockets = this.state.getWebSockets();
    for (const ws of allSockets) {
      if (this.getMachineId(ws)) {
        return ws;
      }
    }
    return null;
  }

  /** Rehydrate in-memory nodeTools, nodeMetadata, and homeMachineId from SQLite. */
  private rehydrateNodeState(): void {
    try {
      const rows = this.state.storage.sql.exec(
        "SELECT machine_id, tools_json, metadata_json, is_home FROM node_state ORDER BY registered_at ASC",
      ).toArray();

      for (const row of rows) {
        const machineId = row.machine_id as string;

        try {
          const tools = JSON.parse(row.tools_json as string) as ToolInfo[];
          this.nodeTools.set(machineId, tools);
        } catch {
          console.error("Failed to parse tools_json for", machineId);
        }

        try {
          const meta = JSON.parse(row.metadata_json as string) as {
            oak_version?: string;
            template_hash?: string;
            capabilities?: string[];
          };
          this.nodeMetadata.set(machineId, meta);
        } catch {
          console.error("Failed to parse metadata_json for", machineId);
        }

        if ((row.is_home as number) === 1) {
          this.homeMachineId = machineId;
        }
      }
    } catch (err) {
      console.error("Failed to rehydrate node state from SQLite:", err);
    }
  }

  /** Persist node state to SQLite (upsert). */
  private persistNodeState(machineId: string): void {
    const tools = this.nodeTools.get(machineId) ?? [];
    const meta = this.nodeMetadata.get(machineId) ?? {};
    const isHome = machineId === this.homeMachineId ? 1 : 0;

    try {
      this.state.storage.sql.exec(
        `INSERT INTO node_state (machine_id, tools_json, metadata_json, is_home, registered_at)
         VALUES (?, ?, ?, ?, ?)
         ON CONFLICT(machine_id) DO UPDATE SET
           tools_json = excluded.tools_json,
           metadata_json = excluded.metadata_json,
           is_home = excluded.is_home,
           registered_at = excluded.registered_at`,
        machineId,
        JSON.stringify(tools),
        JSON.stringify(meta),
        isHome,
        new Date().toISOString(),
      );
    } catch (err) {
      console.error("Failed to persist node state for", machineId, err);
    }
  }

  /** Remove node state from SQLite. */
  private removeNodeState(machineId: string): void {
    try {
      this.state.storage.sql.exec(
        "DELETE FROM node_state WHERE machine_id = ?",
        machineId,
      );
    } catch (err) {
      console.error("Failed to remove node state for", machineId, err);
    }
  }

  /** Compute the union of tool lists from all connected nodes, deduplicated by name. */
  private getAggregatedTools(): ToolInfo[] {
    const seen = new Set<string>();
    const merged: ToolInfo[] = [];
    for (const tools of this.nodeTools.values()) {
      for (const tool of tools) {
        if (!seen.has(tool.name)) {
          seen.add(tool.name);
          merged.push(tool);
        }
      }
    }
    return merged;
  }

}
