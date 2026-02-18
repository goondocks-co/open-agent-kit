/**
 * Token validation for Oak Cloud Relay.
 *
 * Two separate auth schemes:
 *   - agent_token: cloud agents authenticate via Authorization: Bearer header
 *   - relay_token: local Oak CI daemon authenticates via Sec-WebSocket-Protocol
 */

import type { Env } from "./types";

const BEARER_PREFIX = "Bearer ";

/**
 * Validate a cloud agent request against the configured agent token.
 * Accepts both ``Authorization: Bearer <token>`` (standard) and
 * ``Authorization: <token>`` (convenience for tools that paste raw tokens).
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

  // Accept both "Bearer <token>" and raw "<token>".
  const token = header.startsWith(BEARER_PREFIX)
    ? header.slice(BEARER_PREFIX.length)
    : header;

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
 * The relay token is sent in the Sec-WebSocket-Protocol header.
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
 * Constant-time string comparison to prevent timing attacks.
 * Falls back to byte-by-byte XOR when crypto.subtle is unavailable.
 */
function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) {
    return false;
  }
  const encoder = new TextEncoder();
  const bufA = encoder.encode(a);
  const bufB = encoder.encode(b);
  let mismatch = 0;
  for (let i = 0; i < bufA.length; i++) {
    mismatch |= bufA[i] ^ bufB[i];
  }
  return mismatch === 0;
}
