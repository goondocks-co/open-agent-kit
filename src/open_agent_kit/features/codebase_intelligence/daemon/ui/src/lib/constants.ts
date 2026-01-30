/**
 * Shared constants for the CI daemon UI.
 *
 * Constants-first approach per .constitution.md §IV:
 * - Magic numbers and strings should be defined as constants
 * - Constants provide single source of truth for configuration values
 */

// =============================================================================
// Provider Configuration
// =============================================================================

/** Supported embedding/LLM provider types */
export const PROVIDER_TYPES = {
    OLLAMA: "ollama",
    LMSTUDIO: "lmstudio",
    OPENAI: "openai",
} as const;

export type ProviderType = typeof PROVIDER_TYPES[keyof typeof PROVIDER_TYPES];

/** Default base URLs for each provider */
export const DEFAULT_PROVIDER_URLS: Record<ProviderType, string> = {
    [PROVIDER_TYPES.OLLAMA]: "http://localhost:11434",
    [PROVIDER_TYPES.LMSTUDIO]: "http://localhost:1234",
    [PROVIDER_TYPES.OPENAI]: "http://localhost:1234",
};

/** Human-readable provider display names */
export const PROVIDER_DISPLAY_NAMES: Record<ProviderType, string> = {
    [PROVIDER_TYPES.OLLAMA]: "Ollama",
    [PROVIDER_TYPES.LMSTUDIO]: "LM Studio",
    [PROVIDER_TYPES.OPENAI]: "OpenAI Compatible",
};

/** Provider options for Select dropdowns */
export const PROVIDER_OPTIONS = [
    { value: PROVIDER_TYPES.OLLAMA, label: PROVIDER_DISPLAY_NAMES.ollama },
    { value: PROVIDER_TYPES.LMSTUDIO, label: PROVIDER_DISPLAY_NAMES.lmstudio },
    { value: PROVIDER_TYPES.OPENAI, label: PROVIDER_DISPLAY_NAMES.openai },
] as const;


// =============================================================================
// Field Name Mappings (UI <-> API)
// =============================================================================

/**
 * Maps UI field names to API field names.
 * UI uses user-friendly names, API uses technical names.
 */
export const FIELD_MAPPINGS = {
    /** UI 'max_tokens' maps to API 'context_tokens' */
    MAX_TOKENS_TO_CONTEXT: {
        ui: "max_tokens",
        api: "context_tokens",
    },
    /** UI 'chunk_size' maps to API 'max_chunk_chars' */
    CHUNK_SIZE_TO_MAX_CHUNK: {
        ui: "chunk_size",
        api: "max_chunk_chars",
    },
} as const;


// =============================================================================
// Configuration Sections
// =============================================================================

export const CONFIG_SECTIONS = {
    EMBEDDING: "embedding",
    SUMMARIZATION: "summarization",
} as const;

export type ConfigSection = typeof CONFIG_SECTIONS[keyof typeof CONFIG_SECTIONS];


// =============================================================================
// Validation Constants
// =============================================================================

/** Chunk size as a percentage of context window (80% is recommended) */
export const CHUNK_SIZE_PERCENTAGE = 0.8;

/** Warning threshold - warn if chunk size > this percentage of context */
export const CHUNK_SIZE_WARNING_THRESHOLD = 0.9;


// =============================================================================
// UI Constants
// =============================================================================

/** Step states for the guided configuration flow */
export const STEP_STATES = {
    INCOMPLETE: "incomplete",
    COMPLETE: "complete",
} as const;

/** CSS classes for step badge states */
export const STEP_BADGE_CLASSES = {
    complete: "bg-green-600 text-white",
    incomplete: "bg-muted-foreground/20",
} as const;

/** Test result types */
export const TEST_RESULT_TYPES = {
    SUCCESS: "success",
    PENDING_LOAD: "pending_load",
    ERROR: "error",
} as const;

/** CSS classes for test result states */
export const TEST_RESULT_CLASSES = {
    success: "bg-green-500/10 text-green-700",
    pending_load: "bg-yellow-500/10 text-yellow-700",
    error: "bg-red-500/10 text-red-700",
} as const;

/** Message types for alerts */
export const MESSAGE_TYPES = {
    SUCCESS: "success",
    ERROR: "error",
} as const;


// =============================================================================
// Default Form Values
// =============================================================================

/** Default embedding model placeholder */
export const DEFAULT_EMBEDDING_MODEL_PLACEHOLDER = "e.g. nomic-embed-text";

/** Default summarization model placeholder */
export const DEFAULT_SUMMARIZATION_MODEL_PLACEHOLDER = "e.g. qwen2.5:3b";

/** Default context window placeholder */
export const DEFAULT_CONTEXT_WINDOW_PLACEHOLDER = "e.g. 8192";

/** Default chunk size placeholder */
export const DEFAULT_CHUNK_SIZE_PLACEHOLDER = "e.g. 512";

/** Default dimensions placeholder */
export const DEFAULT_DIMENSIONS_PLACEHOLDER = "Auto-detect";

/** Large context window placeholder (for summarization) */
export const LARGE_CONTEXT_WINDOW_PLACEHOLDER = "e.g. 32768";


// =============================================================================
// Helper Functions
// =============================================================================

/**
 * Get the default URL for a provider type.
 */
export function getDefaultProviderUrl(provider: string): string {
    return DEFAULT_PROVIDER_URLS[provider as ProviderType] ?? DEFAULT_PROVIDER_URLS.ollama;
}

/**
 * Calculate chunk size from context window using the standard percentage.
 */
export function calculateChunkSize(contextWindow: number): number {
    return Math.floor(contextWindow * CHUNK_SIZE_PERCENTAGE);
}

/**
 * Convert a value to an API-safe number (null for empty/invalid values).
 */
export function toApiNumber(value: unknown): number | null {
    if (value === "" || value === undefined || value === null) return null;
    const num = typeof value === "number" ? value : parseInt(String(value), 10);
    return isNaN(num) ? null : num;
}


// =============================================================================
// API Endpoints
// =============================================================================

/** API endpoint paths */
export const API_ENDPOINTS = {
    // Agent endpoints
    AGENTS: "/api/agents",
    AGENT_RUNS: "/api/agents/runs",
    SAVED_TASKS: "/api/saved-tasks",

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
    LOGS: "/api/logs",

    // Activity endpoints
    ACTIVITY_SESSIONS: "/api/activity/sessions",
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

    // Backup endpoints
    BACKUP_STATUS: "/api/backup/status",
    BACKUP_CREATE: "/api/backup/create",
    BACKUP_RESTORE: "/api/backup/restore",
    BACKUP_RESTORE_ALL: "/api/backup/restore-all",
} as const;

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

/** Build promote batch endpoint */
export function getPromoteBatchEndpoint(batchId: number): string {
    return `/api/activity/prompt-batches/${batchId}/promote`;
}

/** Build session lineage endpoint */
export function getSessionLineageEndpoint(sessionId: string): string {
    return `${API_ENDPOINTS.ACTIVITY_SESSIONS}/${sessionId}/lineage`;
}

/** Build link session endpoint */
export function getLinkSessionEndpoint(sessionId: string): string {
    return `${API_ENDPOINTS.ACTIVITY_SESSIONS}/${sessionId}/link`;
}

/** Build regenerate summary endpoint */
export function getRegenerateSummaryEndpoint(sessionId: string): string {
    return `${API_ENDPOINTS.ACTIVITY_SESSIONS}/${sessionId}/regenerate-summary`;
}


// =============================================================================
// Server Configuration
// =============================================================================

/** Development server port */
export const DEV_SERVER_PORT = 37800;

/** Development API base URL */
export const DEV_API_BASE = `http://localhost:${DEV_SERVER_PORT}`;


// =============================================================================
// Polling & Timing
// =============================================================================

/** Status polling interval in milliseconds */
export const STATUS_POLL_INTERVAL_MS = 2000;

/** Log polling interval in milliseconds */
export const LOGS_POLL_INTERVAL_MS = 3000;

/** Memory processing cycle interval in seconds (backend) */
export const MEMORY_PROCESS_INTERVAL_SECONDS = 60;


// =============================================================================
// Session & Activity Status
// =============================================================================

/** Session status values */
export const SESSION_STATUS = {
    ACTIVE: "active",
    COMPLETED: "completed",
} as const;

export type SessionStatusType = typeof SESSION_STATUS[keyof typeof SESSION_STATUS];

/** Session status display labels */
export const SESSION_STATUS_LABELS = {
    [SESSION_STATUS.ACTIVE]: "active",
    [SESSION_STATUS.COMPLETED]: "done",
} as const;

/** Session link reason values */
export const SESSION_LINK_REASONS = {
    CLEAR: "clear",
    COMPACT: "compact",
    INFERRED: "inferred",
    MANUAL: "manual",
} as const;

export type SessionLinkReason = typeof SESSION_LINK_REASONS[keyof typeof SESSION_LINK_REASONS];

/** Human-readable session link reason labels */
export const SESSION_LINK_REASON_LABELS: Record<SessionLinkReason, string> = {
    [SESSION_LINK_REASONS.CLEAR]: "Continued after clear",
    [SESSION_LINK_REASONS.COMPACT]: "Compacted from",
    [SESSION_LINK_REASONS.INFERRED]: "Automatically linked",
    [SESSION_LINK_REASONS.MANUAL]: "Manually linked",
} as const;

/** CSS classes for session link reason badges */
export const SESSION_LINK_REASON_BADGE_CLASSES: Record<SessionLinkReason, string> = {
    [SESSION_LINK_REASONS.CLEAR]: "bg-blue-500/10 text-blue-600",
    [SESSION_LINK_REASONS.COMPACT]: "bg-purple-500/10 text-purple-600",
    [SESSION_LINK_REASONS.INFERRED]: "bg-gray-500/10 text-gray-600",
    [SESSION_LINK_REASONS.MANUAL]: "bg-green-500/10 text-green-600",
} as const;

/** Session link reason options for Select dropdowns */
export const SESSION_LINK_REASON_OPTIONS = [
    { value: SESSION_LINK_REASONS.MANUAL, label: "Manual link" },
    { value: SESSION_LINK_REASONS.INFERRED, label: "Inferred relationship" },
] as const;

/** Daemon system status values */
export const DAEMON_STATUS = {
    HEALTHY: "healthy",
    RUNNING: "running",
    INDEXING: "indexing",
} as const;

/** System status display labels */
export const SYSTEM_STATUS_LABELS = {
    ready: "System Ready",
    indexing: "Indexing...",
} as const;

/** Memory sync status values */
export const MEMORY_SYNC_STATUS = {
    SYNCED: "synced",
    PENDING_EMBED: "pending_embed",
    OUT_OF_SYNC: "out_of_sync",
} as const;

export type MemorySyncStatusType = typeof MEMORY_SYNC_STATUS[keyof typeof MEMORY_SYNC_STATUS];


// =============================================================================
// Log Levels
// =============================================================================

/** Available log levels */
export const LOG_LEVELS = {
    DEBUG: "DEBUG",
    INFO: "INFO",
    WARNING: "WARNING",
    ERROR: "ERROR",
} as const;

export type LogLevel = typeof LOG_LEVELS[keyof typeof LOG_LEVELS];


// =============================================================================
// Log Rotation Configuration
// =============================================================================

/** Default log rotation settings (must match Python constants) */
export const LOG_ROTATION_DEFAULTS = {
    ENABLED: true,
    MAX_SIZE_MB: 10,
    BACKUP_COUNT: 3,
} as const;

/** Log rotation validation limits (must match Python constants) */
export const LOG_ROTATION_LIMITS = {
    MIN_SIZE_MB: 1,
    MAX_SIZE_MB: 100,
    MAX_BACKUP_COUNT: 10,
} as const;

/**
 * Calculate total maximum disk usage for log files.
 * @param maxSizeMb Maximum size of each log file in MB
 * @param backupCount Number of backup files to keep
 * @returns Total max disk usage in MB (current + backups)
 */
export function calculateMaxLogDiskUsage(maxSizeMb: number, backupCount: number): number {
    // Total = current file + backup files
    return maxSizeMb * (1 + backupCount);
}


// =============================================================================
// Log Files
// =============================================================================

/** Available log files for viewing */
export const LOG_FILES = {
    DAEMON: "daemon",
    HOOKS: "hooks",
} as const;

export type LogFileType = typeof LOG_FILES[keyof typeof LOG_FILES];

/** Human-readable log file display names */
export const LOG_FILE_DISPLAY_NAMES: Record<LogFileType, string> = {
    [LOG_FILES.DAEMON]: "Daemon Log",
    [LOG_FILES.HOOKS]: "Hook Events",
} as const;

/** Log file options for Select dropdowns */
export const LOG_FILE_OPTIONS = [
    { value: LOG_FILES.DAEMON, label: LOG_FILE_DISPLAY_NAMES.daemon },
    { value: LOG_FILES.HOOKS, label: LOG_FILE_DISPLAY_NAMES.hooks },
] as const;

/** Default log file to display */
export const DEFAULT_LOG_FILE = LOG_FILES.DAEMON;


// =============================================================================
// Log Tag Filtering
// =============================================================================

/** Log tags for filtering log content */
export const LOG_TAGS = {
    // Hook lifecycle
    SESSION_START: "[SESSION-START]",
    SESSION_END: "[SESSION-END]",
    PROMPT_SUBMIT: "[PROMPT-SUBMIT]",
    TOOL_USE: "[TOOL-USE]",
    SUBAGENT_START: "[SUBAGENT-START]",
    SUBAGENT_STOP: "[SUBAGENT-STOP]",
    // Search & injection (debug mode)
    SEARCH_MEMORY: "[SEARCH:memory",
    SEARCH_CODE: "[SEARCH:code",
    SEARCH_FILE: "[SEARCH:file-context",
    FILTER: "[FILTER]",
    INJECT: "[INJECT:",
} as const;

export type LogTagType = typeof LOG_TAGS[keyof typeof LOG_TAGS];

/** Tag categories for UI grouping */
export const LOG_TAG_CATEGORIES = {
    lifecycle: {
        label: "Lifecycle",
        tags: [LOG_TAGS.SESSION_START, LOG_TAGS.SESSION_END, LOG_TAGS.PROMPT_SUBMIT] as LogTagType[],
    },
    tools: {
        label: "Tools",
        tags: [LOG_TAGS.TOOL_USE, LOG_TAGS.SUBAGENT_START, LOG_TAGS.SUBAGENT_STOP] as LogTagType[],
    },
    search: {
        label: "Search (Debug)",
        tags: [LOG_TAGS.SEARCH_MEMORY, LOG_TAGS.SEARCH_CODE, LOG_TAGS.SEARCH_FILE, LOG_TAGS.FILTER] as LogTagType[],
    },
} as const;

export type LogTagCategory = keyof typeof LOG_TAG_CATEGORIES;

/** Tag display names (short labels for chips) */
export const LOG_TAG_DISPLAY_NAMES: Record<LogTagType, string> = {
    [LOG_TAGS.SESSION_START]: "Session Start",
    [LOG_TAGS.SESSION_END]: "Session End",
    [LOG_TAGS.PROMPT_SUBMIT]: "Prompt",
    [LOG_TAGS.TOOL_USE]: "Tool Use",
    [LOG_TAGS.SUBAGENT_START]: "Agent Start",
    [LOG_TAGS.SUBAGENT_STOP]: "Agent Stop",
    [LOG_TAGS.SEARCH_MEMORY]: "Search Memory",
    [LOG_TAGS.SEARCH_CODE]: "Search Code",
    [LOG_TAGS.SEARCH_FILE]: "Search File",
    [LOG_TAGS.FILTER]: "Filter",
    [LOG_TAGS.INJECT]: "Inject",
} as const;


// =============================================================================
// Pagination Defaults
// =============================================================================

/** Default pagination values */
export const PAGINATION = {
    DEFAULT_LIMIT: 20,
    DEFAULT_OFFSET: 0,
    MAX_LIMIT_SMALL: 50,
    MAX_LIMIT_MEDIUM: 100,
    MAX_LIMIT_LARGE: 200,
    DASHBOARD_SESSION_LIMIT: 5,
} as const;


// =============================================================================
// Session Sort Options
// =============================================================================

/**
 * Sort options for session listings.
 * - last_activity: Sessions with most recent activity first (default)
 * - created: Sessions by creation time (newest first)
 * - status: Active sessions first, then by creation time
 */
export const SESSION_SORT_OPTIONS = {
    LAST_ACTIVITY: "last_activity",
    CREATED: "created",
    STATUS: "status",
} as const;

export type SessionSortOption = typeof SESSION_SORT_OPTIONS[keyof typeof SESSION_SORT_OPTIONS];

/** Human-readable session sort labels */
export const SESSION_SORT_LABELS: Record<SessionSortOption, string> = {
    [SESSION_SORT_OPTIONS.LAST_ACTIVITY]: "Last Activity",
    [SESSION_SORT_OPTIONS.CREATED]: "Created",
    [SESSION_SORT_OPTIONS.STATUS]: "Status",
} as const;

/** Session sort options for Select dropdowns */
export const SESSION_SORT_DROPDOWN_OPTIONS = [
    { value: SESSION_SORT_OPTIONS.LAST_ACTIVITY, label: SESSION_SORT_LABELS.last_activity },
    { value: SESSION_SORT_OPTIONS.CREATED, label: SESSION_SORT_LABELS.created },
    { value: SESSION_SORT_OPTIONS.STATUS, label: SESSION_SORT_LABELS.status },
] as const;

/** Default session sort option */
export const DEFAULT_SESSION_SORT = SESSION_SORT_OPTIONS.LAST_ACTIVITY;


// =============================================================================
// Plan Sort Options
// =============================================================================

/**
 * Sort options for plan listings.
 * - created: Plans by creation time (newest first, default)
 * - created_asc: Plans by creation time (oldest first)
 */
export const PLAN_SORT_OPTIONS = {
    CREATED: "created",
    CREATED_ASC: "created_asc",
} as const;

export type PlanSortOption = typeof PLAN_SORT_OPTIONS[keyof typeof PLAN_SORT_OPTIONS];

/** Human-readable plan sort labels */
export const PLAN_SORT_LABELS: Record<PlanSortOption, string> = {
    [PLAN_SORT_OPTIONS.CREATED]: "Newest First",
    [PLAN_SORT_OPTIONS.CREATED_ASC]: "Oldest First",
} as const;

/** Plan sort options for Select dropdowns */
export const PLAN_SORT_DROPDOWN_OPTIONS = [
    { value: PLAN_SORT_OPTIONS.CREATED, label: PLAN_SORT_LABELS.created },
    { value: PLAN_SORT_OPTIONS.CREATED_ASC, label: PLAN_SORT_LABELS.created_asc },
] as const;

/** Default plan sort option */
export const DEFAULT_PLAN_SORT = PLAN_SORT_OPTIONS.CREATED;


// =============================================================================
// Display Constants
// =============================================================================

/** Default agent name when not specified */
export const DEFAULT_AGENT_NAME = "claude-code";

/** Score display precision (decimal places) */
export const SCORE_DISPLAY_PRECISION = 4;

/** Character limit for activity content before truncation */
export const ACTIVITY_TRUNCATION_LIMIT = 100;

/** Character limit for memory observation before truncation */
export const MEMORY_OBSERVATION_TRUNCATION_LIMIT = 200;

/** Maximum length for session title display */
export const SESSION_TITLE_MAX_LENGTH = 60;


// =============================================================================
// Confidence Levels (model-agnostic filtering)
// =============================================================================

/**
 * Confidence levels for search results.
 *
 * These are model-agnostic confidence levels based on relative positioning
 * within the result set, not absolute similarity scores (which vary significantly
 * across embedding models like nomic-embed-text vs bge-m3).
 */
export const CONFIDENCE_LEVELS = {
    HIGH: "high",
    MEDIUM: "medium",
    LOW: "low",
} as const;

export type ConfidenceLevel = typeof CONFIDENCE_LEVELS[keyof typeof CONFIDENCE_LEVELS];

/** Confidence filter options for search UI */
export const CONFIDENCE_FILTER_OPTIONS = [
    { value: "all", label: "All Results" },
    { value: CONFIDENCE_LEVELS.HIGH, label: "High Confidence" },
    { value: CONFIDENCE_LEVELS.MEDIUM, label: "Medium+" },
    { value: CONFIDENCE_LEVELS.LOW, label: "Low+" },
] as const;

export type ConfidenceFilter = "all" | ConfidenceLevel;

/** CSS classes for confidence badges */
export const CONFIDENCE_BADGE_CLASSES: Record<ConfidenceLevel, string> = {
    [CONFIDENCE_LEVELS.HIGH]: "bg-green-500/10 text-green-600",
    [CONFIDENCE_LEVELS.MEDIUM]: "bg-yellow-500/10 text-yellow-600",
    [CONFIDENCE_LEVELS.LOW]: "bg-gray-500/10 text-gray-500",
} as const;


// =============================================================================
// Document Types (for filtering/weighting)
// =============================================================================

/**
 * Document type classification for search results.
 * Used for filtering and visual indication of result type.
 */
export const DOC_TYPES = {
    CODE: "code",
    I18N: "i18n",
    CONFIG: "config",
    TEST: "test",
    DOCS: "docs",
} as const;

export type DocType = typeof DOC_TYPES[keyof typeof DOC_TYPES];

/** CSS classes for doc_type badges */
export const DOC_TYPE_BADGE_CLASSES: Record<DocType, string> = {
    [DOC_TYPES.CODE]: "bg-blue-500/10 text-blue-600",
    [DOC_TYPES.I18N]: "bg-purple-500/10 text-purple-600",
    [DOC_TYPES.CONFIG]: "bg-orange-500/10 text-orange-600",
    [DOC_TYPES.TEST]: "bg-cyan-500/10 text-cyan-600",
    [DOC_TYPES.DOCS]: "bg-emerald-500/10 text-emerald-600",
} as const;

/** Human-readable doc_type labels */
export const DOC_TYPE_LABELS: Record<DocType, string> = {
    [DOC_TYPES.CODE]: "Code",
    [DOC_TYPES.I18N]: "i18n",
    [DOC_TYPES.CONFIG]: "Config",
    [DOC_TYPES.TEST]: "Test",
    [DOC_TYPES.DOCS]: "Docs",
} as const;


/** Fallback messages for empty states */
export const FALLBACK_MESSAGES = {
    NO_PREVIEW: "No preview available",
    NO_SESSIONS: "No sessions recorded yet",
    NO_RESULTS: "No results found",
    LOADING: "Loading...",
} as const;


// =============================================================================
// Search Types (for filtering by category)
// =============================================================================

/**
 * Search type options for filtering by category.
 * - all: Search code, memories, plans, and sessions
 * - code: Code chunks only
 * - memory: Memory observations only
 * - plans: Plans only (intention/design documents)
 * - sessions: Sessions only (via embedded summaries)
 */
export const SEARCH_TYPES = {
    ALL: "all",
    CODE: "code",
    MEMORY: "memory",
    PLANS: "plans",
    SESSIONS: "sessions",
} as const;

export type SearchType = typeof SEARCH_TYPES[keyof typeof SEARCH_TYPES];

/** Search type options for Select dropdowns */
export const SEARCH_TYPE_OPTIONS = [
    { value: SEARCH_TYPES.ALL, label: "All Categories" },
    { value: SEARCH_TYPES.CODE, label: "Code Only" },
    { value: SEARCH_TYPES.MEMORY, label: "Memories Only" },
    { value: SEARCH_TYPES.PLANS, label: "Plans Only" },
    { value: SEARCH_TYPES.SESSIONS, label: "Sessions Only" },
] as const;


// =============================================================================
// Memory Types (for filtering memories list)
// =============================================================================

/**
 * Memory observation types.
 * These match the memory_type values stored in the database.
 */
export const MEMORY_TYPES = {
    GOTCHA: "gotcha",
    DISCOVERY: "discovery",
    BUG_FIX: "bug_fix",
    DECISION: "decision",
    TRADE_OFF: "trade_off",
    SESSION_SUMMARY: "session_summary",
    PLAN: "plan",
} as const;

export type MemoryType = typeof MEMORY_TYPES[keyof typeof MEMORY_TYPES];

/** Human-readable memory type labels */
export const MEMORY_TYPE_LABELS: Record<MemoryType, string> = {
    [MEMORY_TYPES.GOTCHA]: "Gotcha",
    [MEMORY_TYPES.DISCOVERY]: "Discovery",
    [MEMORY_TYPES.BUG_FIX]: "Bug Fix",
    [MEMORY_TYPES.DECISION]: "Decision",
    [MEMORY_TYPES.TRADE_OFF]: "Trade-off",
    [MEMORY_TYPES.SESSION_SUMMARY]: "Session Summary",
    [MEMORY_TYPES.PLAN]: "Plan",
} as const;

/** CSS classes for memory type badges */
export const MEMORY_TYPE_BADGE_CLASSES: Record<MemoryType, string> = {
    [MEMORY_TYPES.GOTCHA]: "bg-red-500/10 text-red-600",
    [MEMORY_TYPES.DISCOVERY]: "bg-blue-500/10 text-blue-600",
    [MEMORY_TYPES.BUG_FIX]: "bg-green-500/10 text-green-600",
    [MEMORY_TYPES.DECISION]: "bg-purple-500/10 text-purple-600",
    [MEMORY_TYPES.TRADE_OFF]: "bg-orange-500/10 text-orange-600",
    [MEMORY_TYPES.SESSION_SUMMARY]: "bg-gray-500/10 text-gray-600",
    [MEMORY_TYPES.PLAN]: "bg-amber-500/10 text-amber-600",
} as const;

/** Memory type filter options for Select dropdowns.
 * Note: Plan is excluded here as plans have their own dedicated tab in Data Explorer.
 * MEMORY_TYPES.PLAN and MEMORY_TYPE_BADGE_CLASSES.plan are kept for search result display.
 */
export const MEMORY_TYPE_FILTER_OPTIONS = [
    { value: "all", label: "All Types" },
    { value: MEMORY_TYPES.GOTCHA, label: MEMORY_TYPE_LABELS.gotcha },
    { value: MEMORY_TYPES.DISCOVERY, label: MEMORY_TYPE_LABELS.discovery },
    { value: MEMORY_TYPES.BUG_FIX, label: MEMORY_TYPE_LABELS.bug_fix },
    { value: MEMORY_TYPES.DECISION, label: MEMORY_TYPE_LABELS.decision },
    { value: MEMORY_TYPES.TRADE_OFF, label: MEMORY_TYPE_LABELS.trade_off },
    { value: MEMORY_TYPES.SESSION_SUMMARY, label: MEMORY_TYPE_LABELS.session_summary },
] as const;

export type MemoryTypeFilter = "all" | MemoryType;


// =============================================================================
// Bulk Actions (for batch operations on memories)
// =============================================================================

/**
 * Bulk action types for memory operations.
 * These match the BulkAction enum on the backend.
 */
export const BULK_ACTIONS = {
    DELETE: "delete",
    ARCHIVE: "archive",
    UNARCHIVE: "unarchive",
    ADD_TAG: "add_tag",
    REMOVE_TAG: "remove_tag",
} as const;

export type BulkAction = typeof BULK_ACTIONS[keyof typeof BULK_ACTIONS];

/** Human-readable bulk action labels */
export const BULK_ACTION_LABELS: Record<BulkAction, string> = {
    [BULK_ACTIONS.DELETE]: "Delete",
    [BULK_ACTIONS.ARCHIVE]: "Archive",
    [BULK_ACTIONS.UNARCHIVE]: "Unarchive",
    [BULK_ACTIONS.ADD_TAG]: "Add Tag",
    [BULK_ACTIONS.REMOVE_TAG]: "Remove Tag",
} as const;


// =============================================================================
// Date Range Presets (for filtering by time period)
// =============================================================================

/**
 * Date range preset values for quick filtering.
 */
export const DATE_RANGE_PRESETS = {
    ALL: "all",
    TODAY: "today",
    WEEK: "week",
    MONTH: "month",
    CUSTOM: "custom",
} as const;

export type DateRangePreset = typeof DATE_RANGE_PRESETS[keyof typeof DATE_RANGE_PRESETS];

/** Date range filter options for Select dropdowns */
export const DATE_RANGE_OPTIONS = [
    { value: DATE_RANGE_PRESETS.ALL, label: "All Time" },
    { value: DATE_RANGE_PRESETS.TODAY, label: "Today" },
    { value: DATE_RANGE_PRESETS.WEEK, label: "This Week" },
    { value: DATE_RANGE_PRESETS.MONTH, label: "This Month" },
] as const;

/**
 * Calculate start date for a given preset.
 * Returns ISO date string (YYYY-MM-DD) or empty string for "all".
 */
export function getDateRangeStart(preset: DateRangePreset): string {
    const now = new Date();
    switch (preset) {
        case DATE_RANGE_PRESETS.TODAY:
            return now.toISOString().split("T")[0];
        case DATE_RANGE_PRESETS.WEEK: {
            const weekAgo = new Date(now);
            weekAgo.setDate(weekAgo.getDate() - 7);
            return weekAgo.toISOString().split("T")[0];
        }
        case DATE_RANGE_PRESETS.MONTH: {
            const monthAgo = new Date(now);
            monthAgo.setMonth(monthAgo.getMonth() - 1);
            return monthAgo.toISOString().split("T")[0];
        }
        default:
            return "";
    }
}


// =============================================================================
// Delete Confirmation Messages
// =============================================================================

/** Confirmation dialog content for delete operations */
export const DELETE_CONFIRMATIONS = {
    SESSION: {
        title: "Delete Session",
        description: "This will permanently delete this session and all its prompt batches, activities, and memories. This action cannot be undone.",
    },
    BATCH: {
        title: "Delete Prompt Batch",
        description: "This will permanently delete this prompt batch and all its activities and memories. This action cannot be undone.",
    },
    ACTIVITY: {
        title: "Delete Activity",
        description: "This will permanently delete this activity. If it has an associated memory, that will also be removed.",
    },
    MEMORY: {
        title: "Delete Memory",
        description: "This will permanently delete this memory observation from the system. This action cannot be undone.",
    },
} as const;


// =============================================================================
// Time Constants
// =============================================================================

/** Time unit conversions */
export const TIME_UNITS = {
    SECONDS_PER_MINUTE: 60,
    MINUTES_PER_HOUR: 60,
    HOURS_PER_DAY: 24,
    MS_PER_SECOND: 1000,
} as const;

/**
 * Format a date string as relative time (e.g., "5m ago", "2h ago").
 */
export function formatRelativeTime(dateString: string): string {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffSeconds = Math.floor(diffMs / TIME_UNITS.MS_PER_SECOND);
    const diffMinutes = Math.floor(diffSeconds / TIME_UNITS.SECONDS_PER_MINUTE);
    const diffHours = Math.floor(diffMinutes / TIME_UNITS.MINUTES_PER_HOUR);
    const diffDays = Math.floor(diffHours / TIME_UNITS.HOURS_PER_DAY);

    if (diffSeconds < TIME_UNITS.SECONDS_PER_MINUTE) return "just now";
    if (diffMinutes < TIME_UNITS.MINUTES_PER_HOUR) return `${diffMinutes}m ago`;
    if (diffHours < TIME_UNITS.HOURS_PER_DAY) return `${diffHours}h ago`;
    if (diffDays === 1) return "yesterday";
    return `${diffDays}d ago`;
}

/**
 * Format uptime in seconds to a human-readable string.
 */
export function formatUptime(uptimeSeconds: number): string {
    const minutes = Math.floor(uptimeSeconds / TIME_UNITS.SECONDS_PER_MINUTE);
    if (minutes < TIME_UNITS.MINUTES_PER_HOUR) {
        return `${minutes}m`;
    }
    const hours = Math.floor(minutes / TIME_UNITS.MINUTES_PER_HOUR);
    const remainingMinutes = minutes % TIME_UNITS.MINUTES_PER_HOUR;
    return remainingMinutes > 0 ? `${hours}h ${remainingMinutes}m` : `${hours}h`;
}


// =============================================================================
// Status Colors (CSS classes)
// =============================================================================

// =============================================================================
// Agent Run Status
// =============================================================================

/** Agent run status values */
export const AGENT_RUN_STATUS = {
    PENDING: "pending",
    RUNNING: "running",
    COMPLETED: "completed",
    FAILED: "failed",
    CANCELLED: "cancelled",
    TIMEOUT: "timeout",
} as const;

export type AgentRunStatusType = typeof AGENT_RUN_STATUS[keyof typeof AGENT_RUN_STATUS];

/** Agent run status display labels */
export const AGENT_RUN_STATUS_LABELS: Record<AgentRunStatusType, string> = {
    [AGENT_RUN_STATUS.PENDING]: "Pending",
    [AGENT_RUN_STATUS.RUNNING]: "Running",
    [AGENT_RUN_STATUS.COMPLETED]: "Completed",
    [AGENT_RUN_STATUS.FAILED]: "Failed",
    [AGENT_RUN_STATUS.CANCELLED]: "Cancelled",
    [AGENT_RUN_STATUS.TIMEOUT]: "Timeout",
} as const;

/** CSS classes for agent run status badges */
export const AGENT_RUN_STATUS_COLORS: Record<AgentRunStatusType, { dot: string; badge: string }> = {
    [AGENT_RUN_STATUS.PENDING]: {
        dot: "bg-gray-500",
        badge: "bg-gray-500/10 text-gray-600",
    },
    [AGENT_RUN_STATUS.RUNNING]: {
        dot: "bg-yellow-500 animate-pulse",
        badge: "bg-yellow-500/10 text-yellow-600",
    },
    [AGENT_RUN_STATUS.COMPLETED]: {
        dot: "bg-green-500",
        badge: "bg-green-500/10 text-green-600",
    },
    [AGENT_RUN_STATUS.FAILED]: {
        dot: "bg-red-500",
        badge: "bg-red-500/10 text-red-600",
    },
    [AGENT_RUN_STATUS.CANCELLED]: {
        dot: "bg-gray-500",
        badge: "bg-gray-500/10 text-gray-500",
    },
    [AGENT_RUN_STATUS.TIMEOUT]: {
        dot: "bg-orange-500",
        badge: "bg-orange-500/10 text-orange-600",
    },
} as const;


// =============================================================================
// Status Colors (CSS classes)
// =============================================================================

/** Status indicator colors */
export const STATUS_COLORS = {
    active: {
        dot: "bg-yellow-500 animate-pulse",
        badge: "bg-yellow-500/10 text-yellow-600",
    },
    completed: {
        dot: "bg-green-500",
        badge: "bg-green-500/10 text-green-600",
    },
    error: {
        dot: "bg-red-500",
        badge: "bg-red-500/10 text-red-600",
    },
    ready: {
        dot: "bg-green-500",
        badge: "bg-green-500/10 text-green-600",
    },
    indexing: {
        dot: "bg-yellow-500 animate-pulse",
        badge: "bg-yellow-500/10 text-yellow-600",
    },
} as const;


// =============================================================================
// Session Suggestion Constants
// =============================================================================

/**
 * Suggestion confidence levels for parent session suggestions.
 * Used by the user-driven session linking system.
 */
export const SUGGESTION_CONFIDENCE = {
    HIGH: "high",
    MEDIUM: "medium",
    LOW: "low",
} as const;

export type SuggestionConfidence = typeof SUGGESTION_CONFIDENCE[keyof typeof SUGGESTION_CONFIDENCE];

/** Human-readable suggestion confidence labels */
export const SUGGESTION_CONFIDENCE_LABELS: Record<SuggestionConfidence, string> = {
    [SUGGESTION_CONFIDENCE.HIGH]: "High Confidence",
    [SUGGESTION_CONFIDENCE.MEDIUM]: "Medium Confidence",
    [SUGGESTION_CONFIDENCE.LOW]: "Low Confidence",
} as const;

/** CSS classes for suggestion confidence badges */
export const SUGGESTION_CONFIDENCE_BADGE_CLASSES: Record<SuggestionConfidence, string> = {
    [SUGGESTION_CONFIDENCE.HIGH]: "bg-green-500/10 text-green-600",
    [SUGGESTION_CONFIDENCE.MEDIUM]: "bg-yellow-500/10 text-yellow-600",
    [SUGGESTION_CONFIDENCE.LOW]: "bg-gray-500/10 text-gray-500",
} as const;

/** Session link reason for suggestions (distinct from auto-link reasons) */
export const SESSION_LINK_REASON_SUGGESTION = "suggestion" as const;

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
