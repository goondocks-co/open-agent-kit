/**
 * Token validation for Oak CI Swarm Worker.
 *
 * Single auth scheme:
 *   - swarm_token: Teams authenticate via Authorization: Bearer header
 */

import type { Env } from "./types";

/**
 * Validate a swarm request against the configured swarm token.
 * Requires standard ``Authorization: Bearer <token>`` format.
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

  const [scheme, token] = header.split(" ", 2);
  if (scheme !== "Bearer" || !token) {
    return new Response(
      JSON.stringify({ error: "invalid Authorization header format" }),
      { status: 401, headers: { "Content-Type": "application/json" } },
    );
  }

  if (!timingSafeEqual(token, env.SWARM_TOKEN)) {
    return new Response(JSON.stringify({ error: "invalid swarm token" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    });
  }

  return null;
}

/**
 * Validate a cloud agent request against the configured agent token.
 *
 * Returns null on success, or a 401 Response on failure.
 */
export function validateAgentToken(
  request: Request,
  env: Env,
): Response | null {
  const authHeader = request.headers.get("Authorization");
  if (!authHeader) {
    return new Response(
      JSON.stringify({
        error: "missing Authorization header",
        hint: "Set header: Authorization: Bearer <agent-token>",
      }),
      { status: 401, headers: { "Content-Type": "application/json" } },
    );
  }

  const [scheme, token] = authHeader.split(" ", 2);
  if (scheme !== "Bearer" || !token) {
    return new Response(
      JSON.stringify({ error: "invalid Authorization header format" }),
      { status: 401, headers: { "Content-Type": "application/json" } },
    );
  }

  if (!env.AGENT_TOKEN) {
    return new Response(
      JSON.stringify({ error: "agent token not configured" }),
      { status: 500, headers: { "Content-Type": "application/json" } },
    );
  }

  if (!timingSafeEqual(token, env.AGENT_TOKEN)) {
    return new Response(
      JSON.stringify({ error: "invalid agent token" }),
      { status: 401, headers: { "Content-Type": "application/json" } },
    );
  }

  return null;
}

/**
 * Constant-time string comparison to prevent timing attacks.
 * Pads to max length and XORs all bytes to avoid leaking length via early return.
 *
 * NOTE: This function is intentionally duplicated in
 * `features/team/cloud_relay/worker_template/src/auth.ts` because the two workers
 * are deployed independently and cannot share a runtime import.  Keep both copies
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
