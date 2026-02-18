/**
 * Oak Cloud Relay — Cloudflare Worker entry point.
 *
 * Routes:
 *   POST /mcp    — cloud agents send MCP JSON-RPC requests (agent_token auth)
 *   GET  /ws     — local Oak CI daemon connects WebSocket (relay_token auth)
 *   GET  /health — status check
 */

import { validateAgentToken, validateRelayToken } from "./auth";
import { handleMcpRequest } from "./mcp-handler";
import type { Env } from "./types";

// Re-export the Durable Object class so the runtime can find it.
export { RelayObject } from "./relay-object";

// Single Durable Object ID — one DO per deployment.
const DO_ID_KEY = "singleton";

// CORS headers for browser-based MCP clients (MCP Inspector, etc.).
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

    // ----- POST /mcp or /sse — cloud agent tool calls -----
    if ((path === "/mcp" || path === "/sse") && request.method === "POST") {
      const authErr = validateAgentToken(request, env);
      if (authErr) return withCors(authErr);

      let body: unknown;
      try {
        body = await request.json();
      } catch {
        return withCors(
          Response.json(
            { jsonrpc: "2.0", id: null, error: { code: -32700, message: "parse error" } },
            { status: 400 },
          ),
        );
      }

      const doStub = getDurableObject(env);
      const result = await handleMcpRequest(body, doStub);
      return withCors(Response.json(result));
    }

    // ----- GET /ws — local daemon WebSocket upgrade -----
    if (path === "/ws" && request.headers.get("Upgrade") === "websocket") {
      const authErr = validateRelayToken(request, env);
      if (authErr) return authErr;

      const doStub = getDurableObject(env);
      return doStub.fetch(request);
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
