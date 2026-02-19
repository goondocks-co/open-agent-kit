/**
 * API endpoint paths and builder functions.
 */

// =============================================================================
// API Endpoints
// =============================================================================

/** API endpoint paths */
export const API_ENDPOINTS = {
    // Agent endpoints
    AGENTS: "/api/agents",
    AGENT_RUNS: "/api/agents/runs",
    AGENT_SETTINGS: "/api/agents/settings",
    AGENT_PROVIDER_MODELS: "/api/agents/provider-models",
    AGENT_TEST_PROVIDER: "/api/agents/test-provider",

    // Schedule endpoints
    SCHEDULES: "/api/schedules",
    SCHEDULES_SYNC: "/api/schedules/sync",

    // Config endpoints
    CONFIG: "/api/config",
    CONFIG_TEST: "/api/config/test",
    CONFIG_TEST_SUMMARIZATION: "/api/config/test-summarization",
    CONFIG_EXCLUSIONS: "/api/config/exclusions",
    CONFIG_EXCLUSIONS_RESET: "/api/config/exclusions/reset",

    // Provider discovery
    PROVIDERS_MODELS: "/api/providers/models",
    PROVIDERS_SUMMARIZATION_MODELS: "/api/providers/summarization-models",

    // System endpoints
    STATUS: "/api/status",
    HEALTH: "/api/health",
    RESTART: "/api/restart",
    SELF_RESTART: "/api/self-restart",
    LOGS: "/api/logs",

    // Activity endpoints
    ACTIVITY_SESSIONS: "/api/activity/sessions",
    ACTIVITY_SESSION_AGENTS: "/api/activity/session-agents",
    ACTIVITY_PLANS: "/api/activity/plans",
    ACTIVITY_STATS: "/api/activity/stats",
    ACTIVITY_SEARCH: "/api/activity/search",
    ACTIVITY_REPROCESS: "/api/activity/reprocess-memories",

    // Search endpoint
    SEARCH: "/api/search",

    // Index endpoints
    INDEX_REBUILD: "/api/index/rebuild",
    INDEX_STATUS: "/api/index/status",

    // Memory endpoints
    MEMORIES: "/api/memories",
    MEMORIES_TAGS: "/api/memories/tags",
    MEMORIES_BULK: "/api/memories/bulk",

    // DevTools endpoints
    DEVTOOLS_MEMORY_STATS: "/api/devtools/memory-stats",
    DEVTOOLS_REBUILD_INDEX: "/api/devtools/rebuild-index",
    DEVTOOLS_REBUILD_MEMORIES: "/api/devtools/rebuild-memories",
    DEVTOOLS_TRIGGER_PROCESSING: "/api/devtools/trigger-processing",
    DEVTOOLS_RESET_PROCESSING: "/api/devtools/reset-processing",
    DEVTOOLS_REGENERATE_SUMMARIES: "/api/devtools/regenerate-summaries",
    DEVTOOLS_REPROCESS_OBSERVATIONS: "/api/devtools/reprocess-observations",
    DEVTOOLS_DATABASE_MAINTENANCE: "/api/devtools/database-maintenance",
    DEVTOOLS_BACKFILL_HASHES: "/api/devtools/backfill-hashes",
    DEVTOOLS_REEMBED_SESSIONS: "/api/activity/reembed-sessions",
    DEVTOOLS_COMPACT_CHROMADB: "/api/devtools/compact-chromadb",
    DEVTOOLS_CLEANUP_MINIMAL_SESSIONS: "/api/devtools/cleanup-minimal-sessions",
    DEVTOOLS_CLEANUP_ORPHANS: "/api/devtools/cleanup-orphans",

    // Backup endpoints
    BACKUP_STATUS: "/api/backup/status",
    BACKUP_CREATE: "/api/backup/create",
    BACKUP_RESTORE: "/api/backup/restore",
    BACKUP_RESTORE_ALL: "/api/backup/restore-all",

    // Tunnel endpoints
    TUNNEL_START: "/api/tunnel/start",
    TUNNEL_STOP: "/api/tunnel/stop",
    TUNNEL_STATUS: "/api/tunnel/status",

    // Governance endpoints
    GOVERNANCE_CONFIG: "/api/governance/config",
    GOVERNANCE_AUDIT: "/api/governance/audit",
    GOVERNANCE_AUDIT_SUMMARY: "/api/governance/audit/summary",
    GOVERNANCE_TEST: "/api/governance/test",
    GOVERNANCE_AUDIT_PRUNE: "/api/governance/audit/prune",

    // Cloud relay endpoints
    CLOUD_RELAY_STATUS: "/api/cloud/status",
    CLOUD_RELAY_START: "/api/cloud/start",
    CLOUD_RELAY_STOP: "/api/cloud/stop",
    CLOUD_RELAY_PREFLIGHT: "/api/cloud/preflight",
    CLOUD_RELAY_SETTINGS: "/api/cloud/settings",
} as const;

// =============================================================================
// Endpoint Builder Functions
// =============================================================================

/** Build session detail endpoint */
export function getSessionDetailEndpoint(sessionId: string): string {
    return `${API_ENDPOINTS.ACTIVITY_SESSIONS}/${sessionId}`;
}

/** Build session activities endpoint */
export function getSessionActivitiesEndpoint(sessionId: string): string {
    return `${API_ENDPOINTS.ACTIVITY_SESSIONS}/${sessionId}/activities`;
}

/** Build prompt batch activities endpoint */
export function getPromptBatchActivitiesEndpoint(batchId: number): string {
    return `/api/activity/prompt-batches/${batchId}/activities`;
}

/** Build delete session endpoint */
export function getDeleteSessionEndpoint(sessionId: string): string {
    return `${API_ENDPOINTS.ACTIVITY_SESSIONS}/${sessionId}`;
}

/** Build delete prompt batch endpoint */
export function getDeleteBatchEndpoint(batchId: number): string {
    return `/api/activity/prompt-batches/${batchId}`;
}

/** Build delete activity endpoint */
export function getDeleteActivityEndpoint(activityId: number): string {
    return `/api/activity/activities/${activityId}`;
}

/** Build delete memory endpoint */
export function getDeleteMemoryEndpoint(memoryId: string): string {
    return `${API_ENDPOINTS.MEMORIES}/${memoryId}`;
}

/** Build archive memory endpoint */
export function getArchiveMemoryEndpoint(memoryId: string): string {
    return `${API_ENDPOINTS.MEMORIES}/${memoryId}/archive`;
}

/** Build unarchive memory endpoint */
export function getUnarchiveMemoryEndpoint(memoryId: string): string {
    return `${API_ENDPOINTS.MEMORIES}/${memoryId}/unarchive`;
}

/** Build memory status endpoint */
export function getMemoryStatusEndpoint(memoryId: string): string {
    return `${API_ENDPOINTS.MEMORIES}/${memoryId}/status`;
}

/** Build promote batch endpoint */
export function getPromoteBatchEndpoint(batchId: number): string {
    return `/api/activity/prompt-batches/${batchId}/promote`;
}

/** Build plan refresh endpoint */
export function getPlanRefreshEndpoint(batchId: number, graceful = false): string {
    const base = `${API_ENDPOINTS.ACTIVITY_PLANS}/${batchId}/refresh`;
    return graceful ? `${base}?graceful=true` : base;
}

/** Build session lineage endpoint */
export function getSessionLineageEndpoint(sessionId: string): string {
    return `${API_ENDPOINTS.ACTIVITY_SESSIONS}/${sessionId}/lineage`;
}

/** Build link session endpoint */
export function getLinkSessionEndpoint(sessionId: string): string {
    return `${API_ENDPOINTS.ACTIVITY_SESSIONS}/${sessionId}/link`;
}

/** Build complete session endpoint */
export function getCompleteSessionEndpoint(sessionId: string): string {
    return `${API_ENDPOINTS.ACTIVITY_SESSIONS}/${sessionId}/complete`;
}

/** Build regenerate summary endpoint */
export function getRegenerateSummaryEndpoint(sessionId: string): string {
    return `${API_ENDPOINTS.ACTIVITY_SESSIONS}/${sessionId}/regenerate-summary`;
}

/** Build update session title endpoint */
export function getUpdateSessionTitleEndpoint(sessionId: string): string {
    return `${API_ENDPOINTS.ACTIVITY_SESSIONS}/${sessionId}/title`;
}

/** Build suggested parent endpoint */
export function getSuggestedParentEndpoint(sessionId: string): string {
    return `${API_ENDPOINTS.ACTIVITY_SESSIONS}/${sessionId}/suggested-parent`;
}

/** Build dismiss suggestion endpoint */
export function getDismissSuggestionEndpoint(sessionId: string): string {
    return `${API_ENDPOINTS.ACTIVITY_SESSIONS}/${sessionId}/dismiss-suggestion`;
}

/** Re-embed sessions endpoint */
export const REEMBED_SESSIONS_ENDPOINT = "/api/activity/reembed-sessions";

/** Build related sessions endpoint */
export function getRelatedSessionsEndpoint(sessionId: string): string {
    return `${API_ENDPOINTS.ACTIVITY_SESSIONS}/${sessionId}/related`;
}

/** Build add related session endpoint */
export function getAddRelatedEndpoint(sessionId: string): string {
    return `${API_ENDPOINTS.ACTIVITY_SESSIONS}/${sessionId}/related`;
}

/** Build remove related session endpoint */
export function getRemoveRelatedEndpoint(sessionId: string, relatedSessionId: string): string {
    return `${API_ENDPOINTS.ACTIVITY_SESSIONS}/${sessionId}/related/${relatedSessionId}`;
}

/** Build suggested related sessions endpoint */
export function getSuggestedRelatedEndpoint(sessionId: string): string {
    return `${API_ENDPOINTS.ACTIVITY_SESSIONS}/${sessionId}/suggested-related`;
}

// =============================================================================
// Server Configuration
// =============================================================================

/** Development server port */
export const DEV_SERVER_PORT = 37800;

/** Development API base URL */
export const DEV_API_BASE = `http://localhost:${DEV_SERVER_PORT}`;
