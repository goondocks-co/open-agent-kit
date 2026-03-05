/**
 * Swarm-specific types for Oak CI Swarm Worker.
 *
 * MUST match the Python-side models exactly. Any change here requires a
 * corresponding change in the Python side (and vice-versa).
 */

// ---------------------------------------------------------------------------
// Cloudflare environment bindings
// ---------------------------------------------------------------------------

/** Cloudflare environment bindings */
export interface Env {
  SWARM: DurableObjectNamespace;
  SWARM_TOKEN: string;
}

// ---------------------------------------------------------------------------
// Swarm team registry
// ---------------------------------------------------------------------------

/** Registered team in the swarm */
export interface SwarmTeam {
  team_id: string;
  project_slug: string;
  callback_url: string;
  capabilities: string[];
  tool_names: string[];
  node_count: number;
  oak_version: string;
  registered_at: string;
  last_heartbeat: string;
  callback_token: string;
  sensitivity: string;
}

// ---------------------------------------------------------------------------
// Request bodies
// ---------------------------------------------------------------------------

/** Registration request body */
export interface RegisterRequest {
  token: string;
  team_id: string;
  project_slug: string;
  callback_url: string;
  capabilities: string[];
  tool_names: string[];
  node_count: number;
  oak_version: string;
  sensitivity?: string;
}

/** Search request body */
export interface SwarmSearchRequest {
  query: string;
  search_type?: string;
  limit?: number;
}

/** Tool call request body */
export interface SwarmToolCallRequest {
  tool_name: string;
  arguments: Record<string, unknown>;
  target_project: string;
}

/** Broadcast request body */
export interface SwarmBroadcastRequest {
  tool_name: string;
  arguments: Record<string, unknown>;
}

/** Heartbeat request body */
export interface HeartbeatRequest {
  team_id: string;
  capabilities?: string[];
  tool_names?: string[];
  node_count?: number;
  oak_version?: string;
}

/** Unregister request body */
export interface UnregisterRequest {
  team_id: string;
}
