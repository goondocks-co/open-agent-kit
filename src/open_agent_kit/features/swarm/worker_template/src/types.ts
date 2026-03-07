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
  AGENT_TOKEN: string;
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
  required_capabilities?: string[];
}

/** Broadcast request body (internal: used by fetch fan-out) */
export interface SwarmBroadcastRequest {
  tool_name: string;
  arguments: Record<string, unknown>;
  required_capabilities?: string[];
}

/** Fetch request body */
export interface SwarmFetchRequest {
  ids: string[];
  project_slug?: string;
}

/** Heartbeat request body */
export interface HeartbeatRequest {
  team_id: string;
  capabilities: string[];
  node_count: number;
  oak_version: string;
  tool_names: string[];
}

/** Unregister request body */
export interface UnregisterRequest {
  team_id: string;
}

// ---------------------------------------------------------------------------
// Advisory system
// ---------------------------------------------------------------------------

/** Advisory severity levels */
export type AdvisorySeverity = "info" | "warning" | "critical";

/** Advisory type identifiers */
export type AdvisoryType = "version_drift" | "capability_gap" | "general";

/** A swarm advisory returned in heartbeat responses */
export interface SwarmAdvisory {
  type: AdvisoryType;
  severity: AdvisorySeverity;
  message: string;
  metadata?: Record<string, unknown>;
}

/** Heartbeat response body (enriched with advisories) */
export interface HeartbeatResponse {
  status: string;
  advisories: SwarmAdvisory[];
}

// ---------------------------------------------------------------------------
// Health check
// ---------------------------------------------------------------------------

/** Health check request body */
export interface SwarmHealthCheckRequest {
  team_slug: string;
}

/** Per-node health data returned from a team relay */
export interface NodeHealthData {
  machine_id: string;
  oak_version: string;
  uptime_seconds: number;
  db_size?: number;
  schema_version?: number;
  indexing_status?: string;
}

/** Health check response for a single team */
export interface SwarmHealthCheckResponse {
  team_id: string;
  project_slug: string;
  nodes: NodeHealthData[];
  error?: string;
}
