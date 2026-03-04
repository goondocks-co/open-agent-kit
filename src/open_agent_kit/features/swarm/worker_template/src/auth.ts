/**
 * Token validation for Oak CI Swarm Worker.
 *
 * Single auth scheme:
 *   - swarm_token: Teams authenticate via Authorization: Bearer header
 */

import type { Env } from "./types";

const BEARER_PREFIX = "Bearer ";

/**
 * Validate a swarm request against the configured swarm token.
 * Accepts both ``Authorization: Bearer <token>`` (standard) and
 * ``Authorization: <token>`` (convenience for tools that paste raw tokens).
 * Returns null on success, or a 401 Response on failure.
 */
export function validateSwarmToken(
  request: Request,
  env: Env,
): Response | null {
  const header = request.headers.get("Authorization");
  if (!header) {
    return new Response(
      JSON.stringify({
        error: "missing authorization",
        hint: "Set header: Authorization: Bearer <swarm-token>",
      }),
      { status: 401, headers: { "Content-Type": "application/json" } },
    );
  }

  // Accept both "Bearer <token>" and raw "<token>".
  const token = header.startsWith(BEARER_PREFIX)
    ? header.slice(BEARER_PREFIX.length)
    : header;

  if (!timingSafeEqual(token, env.SWARM_TOKEN)) {
    return new Response(JSON.stringify({ error: "invalid swarm token" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    });
  }

  return null;
}

/**
 * Constant-time string comparison to prevent timing attacks.
 * Pads to max length and XORs all bytes to avoid leaking length via early return.
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
