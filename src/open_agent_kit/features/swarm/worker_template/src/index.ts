/**
 * Oak CI Swarm — Cloudflare Worker entry point.
 *
 * Routes:
 *   POST /api/swarm/register    — register a team in the swarm (swarm_token auth)
 *   POST /api/swarm/heartbeat   — team heartbeat (swarm_token auth)
 *   POST /api/swarm/search      — federated search across swarm (swarm_token auth)
 *   POST /api/swarm/tool-call   — route a tool call to a specific project (swarm_token auth)
 *   POST /api/swarm/broadcast   — broadcast a tool call to all teams (swarm_token auth)
 *   GET  /api/swarm/nodes       — list registered teams (swarm_token auth)
 *   POST /api/swarm/unregister  — remove a team from the swarm (swarm_token auth)
 *   GET  /health                — status check
 */

import { validateSwarmToken } from "./auth";
import type { Env } from "./types";

// Re-export the Durable Object class so the runtime can find it.
export { SwarmObject } from "./swarm-object";

// Single Durable Object ID — one DO per deployment.
const DO_ID_KEY = "singleton";

// CORS headers for browser-based clients.
const CORS_HEADERS: Record<string, string> = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization",
};

/** Add CORS headers to an existing Response. */
function withCors(response: Response): Response {
  const patched = new Response(response.body, response);
  for (const [k, v] of Object.entries(CORS_HEADERS)) {
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
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }

    // ----- POST /api/swarm/register — register a team -----
    if (path === "/api/swarm/register" && request.method === "POST") {
      const authErr = validateSwarmToken(request, env);
      if (authErr) return withCors(authErr);
      const doStub = getDurableObject(env);
      return withCors(await doStub.fetch(request));
    }

    // ----- POST /api/swarm/heartbeat — team heartbeat -----
    if (path === "/api/swarm/heartbeat" && request.method === "POST") {
      const authErr = validateSwarmToken(request, env);
      if (authErr) return withCors(authErr);
      const doStub = getDurableObject(env);
      return withCors(await doStub.fetch(request));
    }

    // ----- POST /api/swarm/search — federated search across swarm -----
    if (path === "/api/swarm/search" && request.method === "POST") {
      const authErr = validateSwarmToken(request, env);
      if (authErr) return withCors(authErr);
      const doStub = getDurableObject(env);
      return withCors(await doStub.fetch(request));
    }

    // ----- POST /api/swarm/tool-call — route tool call to a project -----
    if (path === "/api/swarm/tool-call" && request.method === "POST") {
      const authErr = validateSwarmToken(request, env);
      if (authErr) return withCors(authErr);
      const doStub = getDurableObject(env);
      return withCors(await doStub.fetch(request));
    }

    // ----- POST /api/swarm/broadcast — broadcast tool call to all teams -----
    if (path === "/api/swarm/broadcast" && request.method === "POST") {
      const authErr = validateSwarmToken(request, env);
      if (authErr) return withCors(authErr);
      const doStub = getDurableObject(env);
      return withCors(await doStub.fetch(request));
    }

    // ----- GET /api/swarm/nodes — list registered teams -----
    if (path === "/api/swarm/nodes" && request.method === "GET") {
      const authErr = validateSwarmToken(request, env);
      if (authErr) return withCors(authErr);
      const doStub = getDurableObject(env);
      return withCors(await doStub.fetch(request));
    }

    // ----- POST /api/swarm/unregister — remove a team from the swarm -----
    if (path === "/api/swarm/unregister" && request.method === "POST") {
      const authErr = validateSwarmToken(request, env);
      if (authErr) return withCors(authErr);
      const doStub = getDurableObject(env);
      return withCors(await doStub.fetch(request));
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
