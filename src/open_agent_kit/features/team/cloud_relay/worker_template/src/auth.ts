/**
 * Token validation for Oak Cloud Relay.
 *
 * Two separate auth schemes:
 *   - agent_token: cloud agents authenticate via Authorization: Bearer header
 *   - relay_token: local Oak CI daemon authenticates via Sec-WebSocket-Protocol
 */

import type { Env } from "./types";

/**
 * Validate a cloud agent request against the configured agent token.
 * Requires standard ``Authorization: Bearer <token>`` format.
 * Returns null on success, or a 401 Response on failure.
 */
export function validateAgentToken(
  request: Request,
  env: Env,
): Response | null {
  const header = request.headers.get("Authorization");
  if (!header) {
    return new Response(
      JSON.stringify({
        error: "missing authorization",
        hint: "Set header: Authorization: Bearer <agent-token>",
      }),
      { status: 401, headers: { "Content-Type": "application/json" } },
    );
  }

  const [scheme, token] = header.split(" ", 2);
  if (scheme !== "Bearer" || !token) {
    return new Response(
      JSON.stringify({ error: "invalid Authorization header format" }),
      { status: 401, headers: { "Content-Type": "application/json" } },
    );
  }

  if (!timingSafeEqual(token, env.AGENT_TOKEN)) {
    return new Response(JSON.stringify({ error: "invalid agent token" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    });
  }

  return null;
}

/**
 * Validate a local daemon WebSocket upgrade request.
 * The relay token is sent in the Sec-WebSocket-Protocol header
 * (browsers don't allow custom headers on WS upgrades).
 * Returns null on success, or a 401 Response on failure.
 */
export function validateRelayToken(
  request: Request,
  env: Env,
): Response | null {
  const protocols = request.headers.get("Sec-WebSocket-Protocol");
  if (!protocols) {
    return new Response(JSON.stringify({ error: "missing relay token" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    });
  }

  // The relay token is sent as the first (or only) sub-protocol value.
  const token = protocols.split(",")[0].trim();
  if (!timingSafeEqual(token, env.RELAY_TOKEN)) {
    return new Response(JSON.stringify({ error: "invalid relay token" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    });
  }

  return null;
}

/**
 * Validate a plain HTTP request from a local daemon using Authorization: Bearer.
 * Used for HTTP-only relay endpoints (/obs/pending, /obs/stats) where the
 * Sec-WebSocket-Protocol header is not available.
 * Returns null on success, or a 401 Response on failure.
 */
export function validateRelayTokenHttp(
  request: Request,
  env: Env,
): Response | null {
  const header = request.headers.get("Authorization");
  if (!header) {
    return new Response(JSON.stringify({ error: "missing relay token" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    });
  }

  const [scheme, token] = header.split(" ", 2);
  if (scheme !== "Bearer" || !token) {
    return new Response(
      JSON.stringify({ error: "invalid Authorization header format" }),
      { status: 401, headers: { "Content-Type": "application/json" } },
    );
  }

  if (!timingSafeEqual(token, env.RELAY_TOKEN)) {
    return new Response(JSON.stringify({ error: "invalid relay token" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    });
  }

  return null;
}

/**
 * Constant-time string comparison to prevent timing attacks.
 * Pads to max length and XORs all bytes to avoid leaking length via early return.
 *
 * NOTE: This function is intentionally duplicated in
 * `features/swarm/worker_template/src/auth.ts` because the two workers are
 * deployed independently and cannot share a runtime import.  Keep both copies
 * identical; any change here MUST be mirrored there.
 */
function timingSafeEqual(a: string, b: string): boolean {
  const encoder = new TextEncoder();
  const bufA = encoder.encode(a);
  const bufB = encoder.encode(b);
  const maxLen = Math.max(bufA.length, bufB.length);
  let mismatch = bufA.length ^ bufB.length;
  for (let i = 0; i < maxLen; i++) {
    mismatch |= (bufA[i] ?? 0) ^ (bufB[i] ?? 0);
  }
  return mismatch === 0;
}
