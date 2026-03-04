/**
 * Swarm Durable Object — manages team registry and routes swarm operations.
 *
 * Architecture:
 *   Team Worker --HTTP POST /api/swarm/register--> Swarm Worker --> DO.fetch() --> SQLite registry
 *   Team Worker --HTTP POST /api/swarm/search----> Swarm Worker --> DO.fetch() --> fan-out to all teams
 *   Team Worker --HTTP POST /api/swarm/tool-call-> Swarm Worker --> DO.fetch() --> targeted team callback
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
  SwarmToolCallRequest,
  SwarmBroadcastRequest,
  HeartbeatRequest,
  UnregisterRequest,
} from "./types";

const STALE_THRESHOLD_MS = 300_000; // 5 minutes
const SEARCH_TIMEOUT_MS = 10_000;
const TOOL_CALL_TIMEOUT_MS = 30_000;
const CALLBACK_TOKEN_LENGTH = 32;

export class SwarmObject implements DurableObject {
  private state: DurableObjectState;
  private env: Env;

  constructor(state: DurableObjectState, env: Env) {
    this.state = state;
    this.env = env;

    // Initialize DO SQLite tables
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

      // --- Targeted tool call ---
      if (path === "/api/swarm/tool-call" && request.method === "POST") {
        return this.handleToolCall(request);
      }

      // --- Broadcast tool call ---
      if (path === "/api/swarm/broadcast" && request.method === "POST") {
        return this.handleBroadcast(request);
      }

      // --- List teams ---
      if (path === "/api/swarm/nodes" && request.method === "GET") {
        return this.handleNodes();
      }

      // --- Unregister ---
      if (path === "/api/swarm/unregister" && request.method === "POST") {
        return this.handleUnregister(request);
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
    const body = (await request.json()) as RegisterRequest;

    if (!body.team_id || !body.project_slug || !body.callback_url) {
      return Response.json(
        { error: "missing required fields: team_id, project_slug, callback_url" },
        { status: 400 },
      );
    }

    const now = new Date().toISOString();
    const callbackToken = this.generateCallbackToken();

    this.state.storage.sql.exec(
      `INSERT OR REPLACE INTO teams
        (team_id, project_slug, callback_url, capabilities, node_count, oak_version, registered_at, last_heartbeat, callback_token, sensitivity)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      body.team_id,
      body.project_slug,
      body.callback_url,
      JSON.stringify(body.capabilities ?? []),
      body.node_count ?? 1,
      body.oak_version ?? "",
      now,
      now,
      callbackToken,
      body.sensitivity ?? "standard",
    );

    const count = this.getTeamCount();
    return Response.json({
      swarm_id: "swarm",
      team_count: count,
      callback_token: callbackToken,
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
    this.state.storage.sql.exec(
      `UPDATE teams SET last_heartbeat = ? WHERE team_id = ?`,
      now,
      body.team_id,
    );

    return Response.json({ status: "ok" });
  }

  private async handleSearch(request: Request): Promise<Response> {
    const body = (await request.json()) as SwarmSearchRequest;

    if (!body.query) {
      return Response.json(
        { error: "missing required field: query" },
        { status: 400 },
      );
    }

    // Exclude restricted teams from search fan-out.
    const teams = this.getAllTeams().filter((t) => t.sensitivity !== "restricted");
    if (teams.length === 0) {
      return Response.json({ results: [] });
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

    for (const outcome of settled) {
      if (outcome.status === "fulfilled" && outcome.value.results) {
        allResults.push(...outcome.value.results);
      }
    }

    return Response.json({ results: allResults });
  }

  private async handleToolCall(request: Request): Promise<Response> {
    const body = (await request.json()) as SwarmToolCallRequest;

    if (!body.target_project || !body.tool_name) {
      return Response.json(
        { error: "missing required fields: target_project, tool_name" },
        { status: 400 },
      );
    }

    const team = this.findTeamByProject(body.target_project);
    if (!team) {
      return Response.json(
        { error: `no team registered for project: ${body.target_project}` },
        { status: 404 },
      );
    }

    try {
      const response = await this.fetchWithTimeout(
        `${team.callback_url}/tool-call`,
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
        { error: `tool call failed: ${message}` },
        { status: 502 },
      );
    }
  }

  private async handleBroadcast(request: Request): Promise<Response> {
    const body = (await request.json()) as SwarmBroadcastRequest;

    if (!body.tool_name) {
      return Response.json(
        { error: "missing required field: tool_name" },
        { status: 400 },
      );
    }

    // Exclude restricted teams from broadcast fan-out.
    const teams = this.getAllTeams().filter((t) => t.sensitivity !== "restricted");
    if (teams.length === 0) {
      return Response.json({ results: [] });
    }

    // Fan out tool call to all eligible teams
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

  private handleNodes(): Response {
    const teams = this.getAllTeams();
    const now = Date.now();

    const enriched = teams.map((team) => {
      const lastBeat = new Date(team.last_heartbeat).getTime();
      const stale = now - lastBeat > STALE_THRESHOLD_MS;
      return {
        team_id: team.team_id,
        project_slug: team.project_slug,
        callback_url: team.callback_url,
        capabilities: team.capabilities,
        node_count: team.node_count,
        oak_version: team.oak_version,
        registered_at: team.registered_at,
        last_heartbeat: team.last_heartbeat,
        sensitivity: team.sensitivity,
        stale,
      };
    });

    return Response.json({ teams: enriched, team_count: enriched.length });
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

  /** Retrieve all registered teams from SQLite. */
  private getAllTeams(): SwarmTeam[] {
    const cursor = this.state.storage.sql.exec(`SELECT * FROM teams`);
    const teams: SwarmTeam[] = [];
    for (const row of cursor) {
      teams.push({
        team_id: row.team_id as string,
        project_slug: row.project_slug as string,
        callback_url: row.callback_url as string,
        capabilities: JSON.parse((row.capabilities as string) || "[]"),
        node_count: row.node_count as number,
        oak_version: row.oak_version as string,
        registered_at: row.registered_at as string,
        last_heartbeat: row.last_heartbeat as string,
        callback_token: row.callback_token as string,
        sensitivity: (row.sensitivity as string) || "standard",
      });
    }
    return teams;
  }

  /** Find a team by project_slug. */
  private findTeamByProject(projectSlug: string): SwarmTeam | null {
    const cursor = this.state.storage.sql.exec(
      `SELECT * FROM teams WHERE project_slug = ? LIMIT 1`,
      projectSlug,
    );
    const row = [...cursor][0];
    if (!row) return null;
    return {
      team_id: row.team_id as string,
      project_slug: row.project_slug as string,
      callback_url: row.callback_url as string,
      capabilities: JSON.parse((row.capabilities as string) || "[]"),
      node_count: row.node_count as number,
      oak_version: row.oak_version as string,
      registered_at: row.registered_at as string,
      last_heartbeat: row.last_heartbeat as string,
      callback_token: row.callback_token as string,
      sensitivity: (row.sensitivity as string) || "standard",
    };
  }
}
