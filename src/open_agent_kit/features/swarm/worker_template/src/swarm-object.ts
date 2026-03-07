/**
 * Swarm Durable Object — manages team registry and routes swarm operations.
 *
 * Architecture:
 *   Team Worker --HTTP POST /api/swarm/register--> Swarm Worker --> DO.fetch() --> SQLite registry
 *   Team Worker --HTTP POST /api/swarm/search----> Swarm Worker --> DO.fetch() --> fan-out to all teams
 *
 * Unlike the Relay DO, the Swarm DO is purely HTTP — no WebSocket management.
 * It manages Team registration and routes search/tool requests to registered
 * Team Workers via their callback URLs.
 *
 * Auth model:
 *   - Inbound: SWARM_TOKEN validated by the Worker entry point (index.ts)
 *   - Outbound: per-team callback_token issued at registration time
 */

import type {
  Env,
  SwarmTeam,
  RegisterRequest,
  SwarmSearchRequest,
  SwarmBroadcastRequest,
  SwarmFetchRequest,
  HeartbeatRequest,
  UnregisterRequest,
  SwarmAdvisory,
  SwarmHealthCheckResponse,
} from "./types";

const STALE_THRESHOLD_MS = 300_000; // 5 minutes
const SEARCH_TIMEOUT_MS = 10_000;
const TOOL_CALL_TIMEOUT_MS = 30_000;
const CALLBACK_TOKEN_LENGTH = 32;
const DEFAULT_PAGE_LIMIT = 50;
const MAX_PAGE_LIMIT = 100;
const RATE_LIMIT_WINDOW_MS = 60_000; // 1 minute
const RATE_LIMIT_MAX_REGISTRATIONS = 10; // per IP per window
/**
 * Schema version — bump whenever DDL changes.
 * Checked via KV so DDL only runs once per deployment, not on every wake.
 */
const SWARM_SCHEMA_VERSION = 3;

/** Capability identifier constants — must match Python SWARM_CAPABILITY_* values. */
const CAPABILITY_SEARCH = "swarm_search_v1";
const CAPABILITY_MANAGEMENT = "swarm_management_v1";

/** Swarm config keys stored in swarm_config table. */
const CONFIG_KEY_MIN_OAK_VERSION = "min_oak_version";

/** Canonical set of swarm capabilities — unknown strings are stripped on registration. */
const KNOWN_CAPABILITIES = new Set([
  CAPABILITY_SEARCH,
  CAPABILITY_MANAGEMENT,
]);

/** Private/reserved IPv4 CIDR ranges that must be blocked for SSRF prevention. */
const PRIVATE_IP_RANGES: Array<{ base: number; mask: number }> = [
  { base: 0x7f000000, mask: 0xff000000 }, // 127.0.0.0/8
  { base: 0x0a000000, mask: 0xff000000 }, // 10.0.0.0/8
  { base: 0xac100000, mask: 0xfff00000 }, // 172.16.0.0/12
  { base: 0xc0a80000, mask: 0xffff0000 }, // 192.168.0.0/16
  { base: 0xa9fe0000, mask: 0xffff0000 }, // 169.254.0.0/16
  { base: 0x00000000, mask: 0xffffffff }, // 0.0.0.0/32
];

/**
 * Validate a callback URL to prevent SSRF attacks.
 * Returns an error message string if invalid, or null if the URL is safe.
 */
function validateCallbackUrl(raw: string): string | null {
  let parsed: URL;
  try {
    parsed = new URL(raw);
  } catch {
    return "callback_url is not a valid URL";
  }

  if (parsed.protocol !== "https:") {
    return "callback_url must use https: protocol";
  }

  if (parsed.hostname === "localhost" || parsed.hostname.endsWith(".localhost")) {
    return "callback_url must not target localhost";
  }

  // Check for IPv4 addresses in private/reserved ranges.
  const ipv4Match = parsed.hostname.match(
    /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/,
  );
  if (ipv4Match) {
    const [, a, b, c, d] = ipv4Match;
    const numeric =
      ((Number(a) << 24) | (Number(b) << 16) | (Number(c) << 8) | Number(d)) >>> 0;
    for (const range of PRIVATE_IP_RANGES) {
      if ((numeric & range.mask) === range.base) {
        return "callback_url must not target a private or reserved IP address";
      }
    }
  }

  // Reject IPv6 loopback (e.g. [::1]).
  if (parsed.hostname === "[::1]" || parsed.hostname === "::1") {
    return "callback_url must not target a loopback address";
  }

  return null;
}

export class SwarmObject implements DurableObject {
  private state: DurableObjectState;
  private env: Env;
  /** In-memory rate limiter: IP -> list of registration timestamps. */
  private registrationTimestamps: Map<string, number[]> = new Map();
  /** Cached min_oak_version — avoids SQL read on every heartbeat. null = not loaded yet. */
  private cachedMinOakVersion: string | null | undefined = undefined;

  constructor(state: DurableObjectState, env: Env) {
    this.state = state;
    this.env = env;

    // Guard DDL behind a schema version to avoid rows_read on every wake.
    this.state.blockConcurrencyWhile(async () => {
      const version = await this.state.storage.get<number>("_schema_version");
      if (version !== SWARM_SCHEMA_VERSION) {
        this.initSchema();
        await this.state.storage.put("_schema_version", SWARM_SCHEMA_VERSION);
      }
    });
  }

  /** Run all DDL — only called when SWARM_SCHEMA_VERSION changes. */
  private initSchema(): void {
    this.state.storage.sql.exec(`
      CREATE TABLE IF NOT EXISTS teams (
        team_id TEXT PRIMARY KEY,
        project_slug TEXT NOT NULL,
        callback_url TEXT NOT NULL,
        capabilities TEXT NOT NULL DEFAULT '[]',
        node_count INTEGER NOT NULL DEFAULT 1,
        oak_version TEXT NOT NULL DEFAULT '',
        registered_at TEXT NOT NULL,
        last_heartbeat TEXT NOT NULL,
        callback_token TEXT NOT NULL,
        sensitivity TEXT NOT NULL DEFAULT 'standard'
      )
    `);

    // Migration: add sensitivity column for existing DOs.
    try {
      this.state.storage.sql.exec(
        `ALTER TABLE teams ADD COLUMN sensitivity TEXT NOT NULL DEFAULT 'standard'`,
      );
    } catch {
      // Column already exists — expected after first migration.
    }

    // Migration: add tool_names column for capability-aware routing.
    try {
      this.state.storage.sql.exec(
        `ALTER TABLE teams ADD COLUMN tool_names TEXT NOT NULL DEFAULT '[]'`,
      );
    } catch {
      // Column already exists — expected after first migration.
    }

    this.state.storage.sql.exec(
      `CREATE INDEX IF NOT EXISTS idx_teams_project ON teams(project_slug)`,
    );

    this.state.storage.sql.exec(`
      CREATE TABLE IF NOT EXISTS swarm_config (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
      )
    `);
  }

  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);
    const path = url.pathname;

    try {
      // --- Health check ---
      if (path === "/health") {
        return this.handleHealth();
      }

      // --- Team registration ---
      if (path === "/api/swarm/register" && request.method === "POST") {
        return this.handleRegister(request);
      }

      // --- Heartbeat ---
      if (path === "/api/swarm/heartbeat" && request.method === "POST") {
        return this.handleHeartbeat(request);
      }

      // --- Search fan-out ---
      if (path === "/api/swarm/search" && request.method === "POST") {
        return this.handleSearch(request);
      }

      // --- Fetch by ID ---
      if (path === "/api/swarm/fetch" && request.method === "POST") {
        return this.handleFetch(request);
      }

      // --- Broadcast (internal: used by fetch fan-out) ---
      if (path === "/api/swarm/broadcast" && request.method === "POST") {
        return this.handleBroadcast(request);
      }

      // --- List teams ---
      if (path === "/api/swarm/nodes" && request.method === "GET") {
        const limitParam = url.searchParams.get("limit");
        const offsetParam = url.searchParams.get("offset");
        const limit = Math.min(
          Math.max(1, Number(limitParam) || DEFAULT_PAGE_LIMIT),
          MAX_PAGE_LIMIT,
        );
        const offset = Math.max(0, Number(offsetParam) || 0);
        return this.handleNodes(limit, offset);
      }

      // --- Unregister ---
      if (path === "/api/swarm/unregister" && request.method === "POST") {
        return this.handleUnregister(request);
      }

      // --- Health check (targeted at a specific team) ---
      if (path === "/api/swarm/health-check" && request.method === "POST") {
        return this.handleHealthCheck(request);
      }

      // --- Config: min_oak_version ---
      if (path === "/api/swarm/config/min-oak-version") {
        if (request.method === "GET") {
          return this.handleGetMinOakVersion();
        }
        if (request.method === "PUT") {
          return this.handleSetMinOakVersion(request);
        }
      }

      return Response.json({ error: "not found" }, { status: 404 });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Internal error";
      return Response.json({ error: message }, { status: 500 });
    }
  }

  // -------------------------------------------------------------------------
  // Route handlers
  // -------------------------------------------------------------------------

  private handleHealth(): Response {
    const count = this.getTeamCount();
    return Response.json({ status: "ok", team_count: count });
  }

  private async handleRegister(request: Request): Promise<Response> {
    // --- Rate limiting (per-IP sliding window) ---
    const clientIp = request.headers.get("CF-Connecting-IP") ?? "unknown";
    const rateLimitError = this.checkRateLimit(clientIp);
    if (rateLimitError) {
      return Response.json({ error: rateLimitError }, { status: 429 });
    }

    const body = (await request.json()) as RegisterRequest;

    if (!body.team_id || !body.project_slug || !body.callback_url) {
      return Response.json(
        { error: "missing required fields: team_id, project_slug, callback_url" },
        { status: 400 },
      );
    }

    const urlError = validateCallbackUrl(body.callback_url);
    if (urlError) {
      return Response.json({ error: urlError }, { status: 400 });
    }

    const now = new Date().toISOString();
    const callbackToken = this.generateCallbackToken();

    // Use COALESCE to preserve existing callback_token and registered_at
    // when re-registering a known team_id.
    this.state.storage.sql.exec(
      `INSERT OR REPLACE INTO teams
        (team_id, project_slug, callback_url, capabilities, tool_names, node_count, oak_version, registered_at, last_heartbeat, callback_token, sensitivity)
       VALUES (?, ?, ?, ?, ?, ?, ?,
         COALESCE((SELECT registered_at FROM teams WHERE team_id = ?), ?),
         ?,
         COALESCE((SELECT callback_token FROM teams WHERE team_id = ?), ?),
         ?)`,
      body.team_id,
      body.project_slug,
      body.callback_url,
      JSON.stringify(this.validateCapabilities(body.capabilities ?? [])),
      JSON.stringify(body.tool_names ?? []),
      body.node_count ?? 1,
      body.oak_version ?? "",
      body.team_id,
      now,
      now,
      body.team_id,
      callbackToken,
      body.sensitivity ?? "standard",
    );

    // Retrieve the actual token (may be the preserved existing one).
    const team = this.findTeamByProject(body.project_slug);
    const actualToken = team?.callback_token ?? callbackToken;

    const count = this.getTeamCount();
    return Response.json({
      swarm_id: "swarm",
      team_count: count,
      callback_token: actualToken,
    });
  }

  private async handleHeartbeat(request: Request): Promise<Response> {
    const body = (await request.json()) as HeartbeatRequest;

    if (!body.team_id) {
      return Response.json(
        { error: "missing required field: team_id" },
        { status: 400 },
      );
    }

    const now = new Date().toISOString();

    // Build a dynamic UPDATE that only touches columns present in the body,
    // so a bare heartbeat (team_id only) doesn't clobber registration data.
    const setClauses: string[] = ["last_heartbeat = ?"];
    const params: unknown[] = [now];

    if (body.capabilities !== undefined) {
      setClauses.push("capabilities = ?");
      params.push(JSON.stringify(this.validateCapabilities(body.capabilities)));
    }
    if (body.node_count !== undefined) {
      setClauses.push("node_count = ?");
      params.push(body.node_count);
    }
    if (body.oak_version !== undefined) {
      setClauses.push("oak_version = ?");
      params.push(body.oak_version);
    }
    if (body.tool_names !== undefined) {
      setClauses.push("tool_names = ?");
      params.push(JSON.stringify(body.tool_names));
    }

    params.push(body.team_id);
    this.state.storage.sql.exec(
      `UPDATE teams SET ${setClauses.join(", ")} WHERE team_id = ?`,
      ...params,
    );

    // Generate advisories for this team based on current state.
    const team = this.findTeamById(body.team_id);
    const advisories = team ? this.generateAdvisories(team) : [];

    return Response.json({ status: "ok", advisories });
  }

  private async handleSearch(request: Request): Promise<Response> {
    const body = (await request.json()) as SwarmSearchRequest;

    if (!body.query) {
      return Response.json(
        { error: "missing required field: query" },
        { status: 400 },
      );
    }

    // Only fan out to teams that advertise search capability (and any extra required caps).
    const teams = this.getTeamsWithCapability(CAPABILITY_SEARCH, body.required_capabilities);
    if (teams.length === 0) {
      return Response.json({ results: [], warning: "no teams with required capability" });
    }

    // Fan out search to all eligible teams
    const promises = teams.map(async (team) => {
      try {
        const response = await this.fetchWithTimeout(
          `${team.callback_url}/search`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${team.callback_token}`,
            },
            body: JSON.stringify({
              query: body.query,
              search_type: body.search_type,
              limit: body.limit,
            }),
          },
          SEARCH_TIMEOUT_MS,
        );

        if (!response.ok) {
          return {
            project_slug: team.project_slug,
            results: [],
            error: `HTTP ${response.status}`,
          };
        }

        const data = (await response.json()) as { results?: Record<string, unknown>[] };
        const results = (data.results ?? []).map((r) => ({
          ...r,
          project_slug: team.project_slug,
        }));
        return { project_slug: team.project_slug, results, error: null };
      } catch (err) {
        const message = err instanceof Error ? err.message : "unknown error";
        return { project_slug: team.project_slug, results: [], error: message };
      }
    });

    const settled = await Promise.allSettled(promises);
    const allResults: Record<string, unknown>[] = [];
    const errors: { project_slug: string; error: string }[] = [];

    for (const outcome of settled) {
      if (outcome.status === "fulfilled") {
        if (outcome.value.error) {
          errors.push({ project_slug: outcome.value.project_slug, error: outcome.value.error });
        }
        if (outcome.value.results) {
          allResults.push(...outcome.value.results);
        }
      }
    }

    return Response.json({
      results: allResults,
      ...(errors.length > 0 ? { errors } : {}),
    });
  }

  private async handleFetch(request: Request): Promise<Response> {
    const body = (await request.json()) as SwarmFetchRequest;

    if (!body.ids || !Array.isArray(body.ids) || body.ids.length === 0) {
      return Response.json(
        { error: "missing required field: ids (non-empty array)" },
        { status: 400 },
      );
    }

    // If project_slug is provided, target that specific team
    if (body.project_slug) {
      const team = this.findTeamByProject(body.project_slug);
      if (!team) {
        return Response.json(
          { error: `no team registered for project: ${body.project_slug}` },
          { status: 404 },
        );
      }

      try {
        const response = await this.fetchWithTimeout(
          `${team.callback_url}/fetch`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${team.callback_token}`,
            },
            body: JSON.stringify({ ids: body.ids }),
          },
          SEARCH_TIMEOUT_MS,
        );

        if (!response.ok) {
          const text = await response.text();
          return Response.json(
            { error: `team returned HTTP ${response.status}`, detail: text },
            { status: 502 },
          );
        }

        const result = await response.json();
        return Response.json(result);
      } catch (err) {
        const message = err instanceof Error ? err.message : "unknown error";
        return Response.json(
          { error: `fetch failed: ${message}` },
          { status: 502 },
        );
      }
    }

    // No project_slug — fan out to all search-capable teams
    const teams = this.getTeamsWithCapability(CAPABILITY_SEARCH);
    if (teams.length === 0) {
      return Response.json({ results: [], total_tokens: 0 });
    }

    const promises = teams.map(async (team) => {
      try {
        const response = await this.fetchWithTimeout(
          `${team.callback_url}/fetch`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${team.callback_token}`,
            },
            body: JSON.stringify({ ids: body.ids }),
          },
          SEARCH_TIMEOUT_MS,
        );

        if (!response.ok) {
          return { project_slug: team.project_slug, results: [], error: `HTTP ${response.status}` };
        }

        const data = (await response.json()) as { results?: Record<string, unknown>[]; total_tokens?: number };
        const results = (data.results ?? []).map((r) => ({
          ...r,
          project_slug: team.project_slug,
        }));
        return { project_slug: team.project_slug, results, total_tokens: data.total_tokens ?? 0, error: null };
      } catch (err) {
        const message = err instanceof Error ? err.message : "unknown error";
        return { project_slug: team.project_slug, results: [], error: message };
      }
    });

    const settled = await Promise.allSettled(promises);
    const allResults: Record<string, unknown>[] = [];
    const errors: { project_slug: string; error: string }[] = [];
    let totalTokens = 0;

    for (const outcome of settled) {
      if (outcome.status === "fulfilled") {
        if (outcome.value.error) {
          errors.push({ project_slug: outcome.value.project_slug, error: outcome.value.error });
        }
        if (outcome.value.results) {
          allResults.push(...outcome.value.results);
        }
        totalTokens += (outcome.value as { total_tokens?: number }).total_tokens ?? 0;
      }
    }

    return Response.json({
      results: allResults,
      total_tokens: totalTokens,
      ...(errors.length > 0 ? { errors } : {}),
    });
  }

  /**
   * Broadcast a tool call to all teams with search capability.
   * Used internally by the fetch fan-out (swarm_fetch calls broadcast
   * because chunk IDs are local to each node's vector store).
   */
  private async handleBroadcast(request: Request): Promise<Response> {
    const body = (await request.json()) as SwarmBroadcastRequest;

    if (!body.tool_name) {
      return Response.json(
        { error: "missing required field: tool_name" },
        { status: 400 },
      );
    }

    // Fan out to all teams with search capability (broadcast is used for fetch).
    const teams = this.getTeamsWithCapability(CAPABILITY_SEARCH, body.required_capabilities);
    if (teams.length === 0) {
      return Response.json({ results: [], warning: "no teams with required capability" });
    }

    const promises = teams.map(async (team) => {
      try {
        const response = await this.fetchWithTimeout(
          `${team.callback_url}/federate-tool`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${team.callback_token}`,
            },
            body: JSON.stringify({
              tool_name: body.tool_name,
              arguments: body.arguments ?? {},
            }),
          },
          TOOL_CALL_TIMEOUT_MS,
        );

        if (!response.ok) {
          return {
            project_slug: team.project_slug,
            result: null,
            error: `HTTP ${response.status}`,
          };
        }

        const result = await response.json();
        return { project_slug: team.project_slug, result, error: null };
      } catch (err) {
        const message = err instanceof Error ? err.message : "unknown error";
        return { project_slug: team.project_slug, result: null, error: message };
      }
    });

    const settled = await Promise.allSettled(promises);
    const results: Array<{ project_slug: string; result: unknown; error: string | null }> = [];

    for (const outcome of settled) {
      if (outcome.status === "fulfilled") {
        results.push(outcome.value);
      } else {
        results.push({
          project_slug: "unknown",
          result: null,
          error: outcome.reason instanceof Error ? outcome.reason.message : "unknown error",
        });
      }
    }

    return Response.json({ results });
  }

  private handleNodes(limit: number, offset: number): Response {
    const teams = this.getAllTeamsPaginated(limit, offset);
    const totalCount = this.getTeamCount();
    const now = Date.now();

    // Strip sensitive fields (callback_token, callback_url) from public response.
    const enriched = teams.map((team) => {
      const lastBeat = new Date(team.last_heartbeat).getTime();
      const stale = now - lastBeat > STALE_THRESHOLD_MS;
      return {
        team_id: team.team_id,
        project_slug: team.project_slug,
        capabilities: team.capabilities,
        tool_names: team.tool_names,
        node_count: team.node_count,
        oak_version: team.oak_version,
        registered_at: team.registered_at,
        last_heartbeat: team.last_heartbeat,
        sensitivity: team.sensitivity,
        stale,
      };
    });

    return Response.json({
      teams: enriched,
      team_count: totalCount,
      limit,
      offset,
    });
  }

  private async handleUnregister(request: Request): Promise<Response> {
    const body = (await request.json()) as UnregisterRequest;

    if (!body.team_id) {
      return Response.json(
        { error: "missing required field: team_id" },
        { status: 400 },
      );
    }

    this.state.storage.sql.exec(
      `DELETE FROM teams WHERE team_id = ?`,
      body.team_id,
    );

    return Response.json({ status: "ok" });
  }

  // -------------------------------------------------------------------------
  // Helpers
  // -------------------------------------------------------------------------

  /** Timeout-wrapped fetch. Aborts if the request exceeds `timeoutMs`. */
  private async fetchWithTimeout(
    url: string,
    init: RequestInit,
    timeoutMs: number,
  ): Promise<Response> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      return await fetch(url, { ...init, signal: controller.signal });
    } finally {
      clearTimeout(timer);
    }
  }

  /** Generate a cryptographically random callback token (hex-encoded). */
  private generateCallbackToken(): string {
    const bytes = new Uint8Array(CALLBACK_TOKEN_LENGTH);
    crypto.getRandomValues(bytes);
    return Array.from(bytes)
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
  }

  /** Get total count of registered teams. */
  private getTeamCount(): number {
    const cursor = this.state.storage.sql.exec(
      `SELECT COUNT(*) as cnt FROM teams`,
    );
    const row = cursor.one();
    return (row.cnt as number) ?? 0;
  }

  /** Retrieve all registered teams from SQLite (includes sensitive fields for internal use). */
  private getAllTeams(): SwarmTeam[] {
    const cursor = this.state.storage.sql.exec(`SELECT * FROM teams`);
    return this.rowsToTeams(cursor);
  }

  /** Retrieve a page of registered teams from SQLite (for external listing). */
  private getAllTeamsPaginated(limit: number, offset: number): SwarmTeam[] {
    const cursor = this.state.storage.sql.exec(
      `SELECT * FROM teams ORDER BY registered_at DESC LIMIT ? OFFSET ?`,
      limit,
      offset,
    );
    return this.rowsToTeams(cursor);
  }

  /** Convert SQL cursor rows to SwarmTeam objects. */
  private rowsToTeams(cursor: Iterable<Record<string, unknown>>): SwarmTeam[] {
    const teams: SwarmTeam[] = [];
    for (const row of cursor) {
      teams.push(this.rowToTeam(row));
    }
    return teams;
  }

  /**
   * Check per-IP registration rate limit (sliding window).
   * Returns an error message if rate limited, null if allowed.
   */
  private checkRateLimit(ip: string): string | null {
    const now = Date.now();
    const windowStart = now - RATE_LIMIT_WINDOW_MS;

    let timestamps = this.registrationTimestamps.get(ip);
    if (timestamps) {
      // Evict entries outside the sliding window.
      timestamps = timestamps.filter((t) => t > windowStart);
      if (timestamps.length === 0) {
        this.registrationTimestamps.delete(ip);
        timestamps = [];
      } else {
        this.registrationTimestamps.set(ip, timestamps);
      }
    } else {
      timestamps = [];
    }

    if (timestamps.length >= RATE_LIMIT_MAX_REGISTRATIONS) {
      return "rate limit exceeded: too many registrations, try again later";
    }

    timestamps.push(now);
    return null;
  }

  /** Find a team by project_slug. */
  private findTeamByProject(projectSlug: string): SwarmTeam | null {
    const cursor = this.state.storage.sql.exec(
      `SELECT * FROM teams WHERE project_slug = ? LIMIT 1`,
      projectSlug,
    );
    const row = [...cursor][0];
    return row ? this.rowToTeam(row) : null;
  }

  /**
   * Filter capabilities to the known set.
   * Unknown capabilities are logged and stripped.
   */
  private validateCapabilities(caps: string[]): string[] {
    for (const cap of caps) {
      if (!KNOWN_CAPABILITIES.has(cap)) {
        console.warn(`Unknown capability rejected: ${cap}`);
      }
    }
    return caps.filter((cap) => KNOWN_CAPABILITIES.has(cap));
  }

  /** Return non-restricted teams that advertise the given capability (plus any extras). */
  private getTeamsWithCapability(
    capability: string,
    requiredCapabilities?: string[],
  ): SwarmTeam[] {
    const caps = requiredCapabilities?.length
      ? [capability, ...requiredCapabilities]
      : [capability];
    return this.getAllTeams().filter(
      (t) =>
        t.sensitivity !== "restricted" &&
        caps.every((c) => t.capabilities.includes(c)),
    );
  }

  /** Find a team by team_id. */
  private findTeamById(teamId: string): SwarmTeam | null {
    const cursor = this.state.storage.sql.exec(
      `SELECT * FROM teams WHERE team_id = ? LIMIT 1`,
      teamId,
    );
    const row = [...cursor][0];
    return row ? this.rowToTeam(row) : null;
  }

  /** Convert a single SQL row to a SwarmTeam object. */
  private rowToTeam(row: Record<string, unknown>): SwarmTeam {
    return {
      team_id: row.team_id as string,
      project_slug: row.project_slug as string,
      callback_url: row.callback_url as string,
      capabilities: JSON.parse((row.capabilities as string) || "[]"),
      tool_names: JSON.parse((row.tool_names as string) || "[]"),
      node_count: row.node_count as number,
      oak_version: row.oak_version as string,
      registered_at: row.registered_at as string,
      last_heartbeat: row.last_heartbeat as string,
      callback_token: row.callback_token as string,
      sensitivity: (row.sensitivity as string) || "standard",
    };
  }

  // -------------------------------------------------------------------------
  // Config helpers (swarm_config table)
  // -------------------------------------------------------------------------

  /** Get a value from the swarm_config table. */
  private getConfig(key: string): string | null {
    const cursor = this.state.storage.sql.exec(
      `SELECT value FROM swarm_config WHERE key = ?`,
      key,
    );
    const row = [...cursor][0];
    return row ? (row.value as string) : null;
  }

  /** Set a value in the swarm_config table. */
  private setConfig(key: string, value: string): void {
    this.state.storage.sql.exec(
      `INSERT OR REPLACE INTO swarm_config (key, value) VALUES (?, ?)`,
      key,
      value,
    );
  }

  /** Delete a value from the swarm_config table. */
  private deleteConfig(key: string): void {
    this.state.storage.sql.exec(
      `DELETE FROM swarm_config WHERE key = ?`,
      key,
    );
  }

  /** Return cached min_oak_version, loading from DB on first call. */
  private getMinOakVersionCached(): string | null {
    if (this.cachedMinOakVersion === undefined) {
      this.cachedMinOakVersion = this.getConfig(CONFIG_KEY_MIN_OAK_VERSION);
    }
    return this.cachedMinOakVersion;
  }

  // -------------------------------------------------------------------------
  // min_oak_version config endpoints
  // -------------------------------------------------------------------------

  private handleGetMinOakVersion(): Response {
    const value = this.getConfig(CONFIG_KEY_MIN_OAK_VERSION);
    return Response.json({ min_oak_version: value ?? "" });
  }

  private async handleSetMinOakVersion(request: Request): Promise<Response> {
    const body = (await request.json()) as { min_oak_version?: string };
    const version = body.min_oak_version?.trim() ?? "";

    if (version && !isValidSemver(version)) {
      return Response.json(
        { error: "invalid version format — expected major.minor.patch (e.g. 1.4.0)" },
        { status: 400 },
      );
    }

    if (version) {
      this.setConfig(CONFIG_KEY_MIN_OAK_VERSION, version);
      this.cachedMinOakVersion = version;
    } else {
      this.deleteConfig(CONFIG_KEY_MIN_OAK_VERSION);
      this.cachedMinOakVersion = null;
    }

    return Response.json({ min_oak_version: version });
  }

  // -------------------------------------------------------------------------
  // Advisory generation
  // -------------------------------------------------------------------------

  /** Generate advisories for a team based on current swarm configuration. */
  private generateAdvisories(team: SwarmTeam): SwarmAdvisory[] {
    const advisories: SwarmAdvisory[] = [];

    // Version drift: team is running below the configured minimum.
    // Use cached value to avoid SQL read on every heartbeat (rows_read quota).
    const minVersion = this.getMinOakVersionCached();
    if (minVersion && team.oak_version && isVersionBelow(team.oak_version, minVersion)) {
      advisories.push({
        type: "version_drift",
        severity: "warning",
        message: `OAK version ${team.oak_version} is below the swarm minimum ${minVersion}. Please upgrade.`,
        metadata: { current: team.oak_version, minimum: minVersion },
      });
    }

    // Capability gap: team does not have management capability.
    if (!team.capabilities.includes(CAPABILITY_MANAGEMENT)) {
      advisories.push({
        type: "capability_gap",
        severity: "info",
        message: "Upgrade to enable health monitoring (swarm_management_v1).",
      });
    }

    return advisories;
  }

  // -------------------------------------------------------------------------
  // Health check
  // -------------------------------------------------------------------------

  private async handleHealthCheck(request: Request): Promise<Response> {
    const body = (await request.json()) as { team_slug?: string };

    if (!body.team_slug) {
      return Response.json(
        { error: "missing required field: team_slug" },
        { status: 400 },
      );
    }

    const team = this.findTeamByProject(body.team_slug);
    if (!team) {
      return Response.json(
        { error: `no team registered for project: ${body.team_slug}` },
        { status: 404 },
      );
    }

    if (!team.capabilities.includes(CAPABILITY_MANAGEMENT)) {
      return Response.json(
        {
          error: `team '${body.team_slug}' does not advertise capability: ${CAPABILITY_MANAGEMENT}`,
          team_capabilities: team.capabilities,
        },
        { status: 422 },
      );
    }

    try {
      const response = await this.fetchWithTimeout(
        `${team.callback_url}/health-check`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${team.callback_token}`,
          },
          body: JSON.stringify({ team_id: team.team_id }),
        },
        TOOL_CALL_TIMEOUT_MS,
      );

      if (!response.ok) {
        const text = await response.text();
        return Response.json(
          { error: `team returned HTTP ${response.status}`, detail: text },
          { status: 502 },
        );
      }

      const result = (await response.json()) as SwarmHealthCheckResponse;
      return Response.json({
        team_id: team.team_id,
        project_slug: team.project_slug,
        nodes: result.nodes ?? [],
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "unknown error";
      return Response.json(
        { error: `health check failed: ${message}` },
        { status: 502 },
      );
    }
  }
}

// ---------------------------------------------------------------------------
// Semver utilities (outside class — pure functions)
// ---------------------------------------------------------------------------

/** Parse a version string into numeric parts. Handles dev suffixes like "1.4.3.dev2+g...". */
function parseSemver(version: string): [number, number, number] | null {
  // Strip common suffixes: .devN, +hash, -rc1, etc.
  const cleaned = version.replace(/[.+\-](dev|rc|alpha|beta|pre).*$/i, "");
  const match = cleaned.match(/^(\d+)\.(\d+)\.(\d+)/);
  if (!match) return null;
  return [Number(match[1]), Number(match[2]), Number(match[3])];
}

/** Check if a version string is a valid semver-like format. */
function isValidSemver(version: string): boolean {
  return parseSemver(version) !== null;
}

/** Return true if `version` is strictly below `minVersion`. */
function isVersionBelow(version: string, minVersion: string): boolean {
  const v = parseSemver(version);
  const m = parseSemver(minVersion);
  if (!v || !m) return false;
  for (let i = 0; i < 3; i++) {
    if (v[i] < m[i]) return true;
    if (v[i] > m[i]) return false;
  }
  return false; // equal
}
