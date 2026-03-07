/**
 * Oak CI Swarm — Cloudflare Worker entry point.
 *
 * Routes:
 *   POST /api/swarm/register    — register a team in the swarm (swarm_token auth)
 *   POST /api/swarm/heartbeat   — team heartbeat (swarm_token auth)
 *   POST /api/swarm/search      — federated search across swarm (swarm_token auth)
 *   POST /api/swarm/broadcast   — internal fetch fan-out to all teams (swarm_token auth)
 *   GET  /api/swarm/nodes       — list registered teams (swarm_token auth)
 *   POST /api/swarm/unregister  — remove a team from the swarm (swarm_token auth)
 *   POST /api/swarm/health-check — health check for a specific team (swarm_token auth)
 *   GET|PUT /api/swarm/config/min-oak-version — version policy config (swarm_token auth)
 *   GET  /api/swarm/agent-token — retrieve agent token (swarm_token auth)
 *   POST /mcp                   — MCP JSON-RPC endpoint (agent_token auth)
 *   GET  /health                — status check
 */

import { validateAgentToken, validateSwarmToken } from "./auth";
import { handleMcpRequest } from "./mcp-handler";
import type { Env } from "./types";

// Re-export the Durable Object class so the runtime can find it.
export { SwarmObject } from "./swarm-object";

// Single Durable Object ID — one DO per deployment.
const DO_ID_KEY = "singleton";

// Localhost origin pattern for CORS (local daemon UIs only).
const LOCALHOST_ORIGIN_RE = /^https?:\/\/localhost(:\d+)?$/;

/** Build CORS headers scoped to the request origin, if it matches localhost. */
function corsHeaders(request: Request): Record<string, string> {
  const origin = request.headers.get("Origin");
  if (!origin || !LOCALHOST_ORIGIN_RE.test(origin)) return {};
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Methods": "POST, GET, PUT, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
  };
}

/** Add CORS headers to an existing Response (only when Origin matches). */
function withCors(response: Response, request: Request): Response {
  const headers = corsHeaders(request);
  if (Object.keys(headers).length === 0) return response;
  const patched = new Response(response.body, response);
  for (const [k, v] of Object.entries(headers)) {
    patched.headers.set(k, v);
  }
  return patched;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const path = url.pathname;

    // ----- OPTIONS preflight (CORS) -----
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders(request) });
    }

    // ----- POST /mcp — cloud agent tool calls -----
    if (path === "/mcp" && request.method === "POST") {
      const authErr = validateAgentToken(request, env);
      if (authErr) return authErr;

      let body: unknown;
      try {
        body = await request.json();
      } catch {
        return new Response(
          JSON.stringify({ error: "invalid JSON body" }),
          { status: 400, headers: { "Content-Type": "application/json" } },
        );
      }

      const doStub = getDurableObject(env);
      const result = await handleMcpRequest(body, doStub);
      return Response.json(result);
    }

    // ----- POST /api/swarm/register — register a team -----
    if (path === "/api/swarm/register" && request.method === "POST") {
      const authErr = validateSwarmToken(request, env);
      if (authErr) return withCors(authErr, request);
      const doStub = getDurableObject(env);
      return withCors(await doStub.fetch(request), request);
    }

    // ----- POST /api/swarm/heartbeat — team heartbeat -----
    if (path === "/api/swarm/heartbeat" && request.method === "POST") {
      const authErr = validateSwarmToken(request, env);
      if (authErr) return withCors(authErr, request);
      const doStub = getDurableObject(env);
      return withCors(await doStub.fetch(request), request);
    }

    // ----- POST /api/swarm/search — federated search across swarm -----
    if (path === "/api/swarm/search" && request.method === "POST") {
      const authErr = validateSwarmToken(request, env);
      if (authErr) return withCors(authErr, request);
      const doStub = getDurableObject(env);
      return withCors(await doStub.fetch(request), request);
    }

    // ----- POST /api/swarm/fetch — fetch items by ID from teams -----
    if (path === "/api/swarm/fetch" && request.method === "POST") {
      const authErr = validateSwarmToken(request, env);
      if (authErr) return withCors(authErr, request);
      const doStub = getDurableObject(env);
      return withCors(await doStub.fetch(request), request);
    }

    // ----- POST /api/swarm/broadcast — internal fetch fan-out to all teams -----
    if (path === "/api/swarm/broadcast" && request.method === "POST") {
      const authErr = validateSwarmToken(request, env);
      if (authErr) return withCors(authErr, request);
      const doStub = getDurableObject(env);
      return withCors(await doStub.fetch(request), request);
    }

    // ----- GET /api/swarm/nodes — list registered teams -----
    if (path === "/api/swarm/nodes" && request.method === "GET") {
      const authErr = validateSwarmToken(request, env);
      if (authErr) return withCors(authErr, request);
      const doStub = getDurableObject(env);
      return withCors(await doStub.fetch(request), request);
    }

    // ----- POST /api/swarm/unregister — remove a team from the swarm -----
    if (path === "/api/swarm/unregister" && request.method === "POST") {
      const authErr = validateSwarmToken(request, env);
      if (authErr) return withCors(authErr, request);
      const doStub = getDurableObject(env);
      return withCors(await doStub.fetch(request), request);
    }

    // ----- POST /api/swarm/health-check — health check for a specific team -----
    if (path === "/api/swarm/health-check" && request.method === "POST") {
      const authErr = validateSwarmToken(request, env);
      if (authErr) return withCors(authErr, request);
      const doStub = getDurableObject(env);
      return withCors(await doStub.fetch(request), request);
    }

    // ----- GET/PUT /api/swarm/config/min-oak-version — version policy config -----
    if (path === "/api/swarm/config/min-oak-version" && (request.method === "GET" || request.method === "PUT")) {
      const authErr = validateSwarmToken(request, env);
      if (authErr) return withCors(authErr, request);
      const doStub = getDurableObject(env);
      return withCors(await doStub.fetch(request), request);
    }

    // ----- GET /api/swarm/agent-token — retrieve agent token for MCP access -----
    if (path === "/api/swarm/agent-token" && request.method === "GET") {
      const authErr = validateSwarmToken(request, env);
      if (authErr) return withCors(authErr, request);
      return withCors(
        Response.json({ agent_token: env.AGENT_TOKEN }),
        request,
      );
    }

    // ----- GET /health -----
    if (path === "/health") {
      const doStub = getDurableObject(env);
      return doStub.fetch(new Request("https://swarm/health"));
    }

    return new Response("not found", { status: 404 });
  },
};

function getDurableObject(env: Env): DurableObjectStub {
  const id = env.SWARM.idFromName(DO_ID_KEY);
  return env.SWARM.get(id);
}
