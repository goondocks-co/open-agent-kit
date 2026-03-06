/**
 * Oak Cloud Relay — Cloudflare Worker entry point.
 *
 * Routes:
 *   POST /mcp            — cloud agents send MCP JSON-RPC requests (agent_token auth)
 *   GET  /ws             — local Oak CI daemon connects WebSocket (relay_token auth)
 *   POST /search         — federated search fan-out to connected peers (relay_token auth)
 *   POST /federate-tool  — generic federated tool fan-out to peers (relay_token auth)
 *   POST /tool-call      — node-to-node tool call routing (relay_token auth)
 *   GET  /metrics        — federation cache + latency metrics (relay_token auth)
 *   GET  /swarm/advisories — cached swarm advisories (relay_token auth)
 *   POST /health-check   — swarm-initiated health check (callback_token auth via DO)
 *   GET  /health         — status check
 */

import { validateAgentToken, validateRelayToken, validateRelayTokenHttp } from "./auth";
import { handleMcpRequest } from "./mcp-handler";
import type { Env } from "./types";

// Re-export the Durable Object class so the runtime can find it.
export { RelayObject } from "./relay-object";

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
    "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
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

    // ----- POST /mcp or /sse — cloud agent tool calls -----
    if ((path === "/mcp" || path === "/sse") && request.method === "POST") {
      const authErr = validateAgentToken(request, env);
      if (authErr) return withCors(authErr, request);

      let body: unknown;
      try {
        body = await request.json();
      } catch {
        return withCors(
          Response.json(
            { jsonrpc: "2.0", id: null, error: { code: -32700, message: "parse error" } },
            { status: 400 },
          ),
          request,
        );
      }

      const doStub = getDurableObject(env);
      const result = await handleMcpRequest(body, doStub);
      return withCors(Response.json(result), request);
    }

    // ----- GET /ws — local daemon WebSocket upgrade -----
    if (path === "/ws" && request.headers.get("Upgrade") === "websocket") {
      const authErr = validateRelayToken(request, env);
      if (authErr) return authErr;

      const doStub = getDurableObject(env);
      return doStub.fetch(request);
    }

    // ----- /api/team/* — HTTP proxy to local daemon via Durable Object -----
    if (path.startsWith("/api/team/")) {
      const authErr = validateRelayTokenHttp(request, env);
      if (authErr) return withCors(authErr, request);

      const doStub = getDurableObject(env);
      return withCors(await doStub.fetch(request), request);
    }

    // ----- GET /obs/pending — drain buffered obs for a reconnecting node -----
    if (path === "/obs/pending" && request.method === "GET") {
      const authErr = validateRelayTokenHttp(request, env);
      if (authErr) return authErr;
      const doStub = getDurableObject(env);
      return doStub.fetch(request);
    }

    // ----- POST /search — federated search fan-out to connected peers -----
    // Auth delegated to DO (accepts both relay_token and swarm callback_token).
    if (path === "/search" && request.method === "POST") {
      const doStub = getDurableObject(env);
      return withCors(await doStub.fetch(request), request);
    }

    // ----- POST /fetch — fetch items by ID from connected peers -----
    // Auth delegated to DO (accepts both relay_token and swarm callback_token).
    if (path === "/fetch" && request.method === "POST") {
      const doStub = getDurableObject(env);
      return withCors(await doStub.fetch(request), request);
    }

    // ----- POST /federate-tool — generic federated tool fan-out to peers -----
    // Auth delegated to DO (accepts both relay_token and swarm callback_token).
    if (path === "/federate-tool" && request.method === "POST") {
      const doStub = getDurableObject(env);
      return withCors(await doStub.fetch(request), request);
    }

    // ----- POST /tool-call — node-to-node tool call (relay-token auth) -----
    // Auth delegated to DO (accepts both relay_token and swarm callback_token).
    if (path === "/tool-call" && request.method === "POST") {
      const doStub = getDurableObject(env);
      return withCors(await doStub.fetch(request), request);
    }

    // ----- GET /obs/history — historical obs for new-node catch-up -----
    if (path === "/obs/history" && request.method === "GET") {
      const authErr = validateRelayTokenHttp(request, env);
      if (authErr) return authErr;
      const doStub = getDurableObject(env);
      return doStub.fetch(request);
    }

    // ----- GET /obs/stats — pending obs counts per offline node -----
    if (path === "/obs/stats" && request.method === "GET") {
      const authErr = validateRelayTokenHttp(request, env);
      if (authErr) return authErr;
      const doStub = getDurableObject(env);
      return doStub.fetch(request);
    }

    // ----- GET /metrics — federation cache + latency metrics -----
    if (path === "/metrics" && request.method === "GET") {
      const authErr = validateRelayTokenHttp(request, env);
      if (authErr) return authErr;
      const doStub = getDurableObject(env);
      return doStub.fetch(request);
    }

    // ----- /api/swarm/config — swarm configuration (relay_token auth) -----
    if (path === "/api/swarm/config" && (request.method === "PUT" || request.method === "GET")) {
      const authErr = validateRelayTokenHttp(request, env);
      if (authErr) return withCors(authErr, request);
      const doStub = getDurableObject(env);
      return withCors(await doStub.fetch(request), request);
    }

    // ----- GET /swarm/advisories — cached swarm advisories from last heartbeat -----
    if (path === "/swarm/advisories" && request.method === "GET") {
      const authErr = validateRelayTokenHttp(request, env);
      if (authErr) return withCors(authErr, request);
      const doStub = getDurableObject(env);
      return withCors(await doStub.fetch(request), request);
    }

    // ----- POST /health-check — swarm-initiated health check -----
    if (path === "/health-check" && request.method === "POST") {
      const doStub = getDurableObject(env);
      return withCors(await doStub.fetch(request), request);
    }

    // ----- GET /health -----
    if (path === "/health") {
      const doStub = getDurableObject(env);
      return doStub.fetch(new Request("https://relay/health"));
    }

    return new Response("not found", { status: 404 });
  },
};

function getDurableObject(env: Env): DurableObjectStub {
  const id = env.RELAY.idFromName(DO_ID_KEY);
  return env.RELAY.get(id);
}
