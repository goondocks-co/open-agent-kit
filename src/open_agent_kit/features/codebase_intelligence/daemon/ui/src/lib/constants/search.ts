/**
 * Search types, confidence levels, document types, memory types, and filters.
 */

// =============================================================================
// Confidence Levels
// =============================================================================

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
// Document Types
// =============================================================================

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

// =============================================================================
// Search Types
// =============================================================================

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
// Memory Types
// =============================================================================

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

/** Memory type filter options for Select dropdowns */
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
// Observation Lifecycle Statuses
// =============================================================================

export const OBSERVATION_STATUSES = {
    ACTIVE: "active",
    RESOLVED: "resolved",
    SUPERSEDED: "superseded",
} as const;

export type ObservationStatus = typeof OBSERVATION_STATUSES[keyof typeof OBSERVATION_STATUSES];

export const OBSERVATION_STATUS_LABELS: Record<ObservationStatus, string> = {
    [OBSERVATION_STATUSES.ACTIVE]: "Active",
    [OBSERVATION_STATUSES.RESOLVED]: "Resolved",
    [OBSERVATION_STATUSES.SUPERSEDED]: "Superseded",
};

export const OBSERVATION_STATUS_BADGE_CLASSES: Record<ObservationStatus, string> = {
    [OBSERVATION_STATUSES.ACTIVE]: "bg-green-500/10 text-green-600",
    [OBSERVATION_STATUSES.RESOLVED]: "bg-blue-500/10 text-blue-600",
    [OBSERVATION_STATUSES.SUPERSEDED]: "bg-gray-500/10 text-gray-500",
};

export const OBSERVATION_STATUS_FILTER_OPTIONS = [
    { value: "all", label: "All Statuses" },
    { value: OBSERVATION_STATUSES.ACTIVE, label: "Active" },
    { value: OBSERVATION_STATUSES.RESOLVED, label: "Resolved" },
    { value: OBSERVATION_STATUSES.SUPERSEDED, label: "Superseded" },
] as const;

export type ObservationStatusFilter = "all" | ObservationStatus;
