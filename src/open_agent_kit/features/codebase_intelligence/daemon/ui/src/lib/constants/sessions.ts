/**
 * Session and activity status constants, sort options,
 * link reasons, relationships, and suggestion confidence.
 */

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
    OUT_OF_SYNC: "out_of_sync",  // Legacy - kept for backwards compatibility
    ORPHANED: "orphaned",  // ChromaDB has more entries than SQLite expects
    MISSING: "missing",  // ChromaDB has fewer entries than SQLite expects
} as const;

export type MemorySyncStatusType = typeof MEMORY_SYNC_STATUS[keyof typeof MEMORY_SYNC_STATUS];

// =============================================================================
// Session Sort Options
// =============================================================================

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
// Session Quality Configuration
// =============================================================================

/** Default session quality settings (must match Python constants) */
export const SESSION_QUALITY_DEFAULTS = {
    MIN_ACTIVITIES: 3,
    STALE_TIMEOUT_SECONDS: 3600,  // 1 hour
} as const;

/** Session quality validation limits (must match Python constants) */
export const SESSION_QUALITY_LIMITS = {
    MIN_ACTIVITY_THRESHOLD: 1,
    MAX_ACTIVITY_THRESHOLD: 20,
    MIN_STALE_TIMEOUT: 300,      // 5 minutes
    MAX_STALE_TIMEOUT: 86400,    // 24 hours
} as const;

/**
 * Format stale timeout in human-readable form.
 */
export function formatStaleTimeout(seconds: number): string {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    if (hours >= 1 && minutes === 0) {
        return hours === 1 ? "1 hour" : `${hours} hours`;
    }
    if (hours >= 1) {
        return `${hours}h ${minutes}m`;
    }
    return minutes === 1 ? "1 minute" : `${minutes} minutes`;
}

// =============================================================================
// Session Suggestion Constants
// =============================================================================

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

// =============================================================================
// Session Relationships (many-to-many semantic links)
// =============================================================================

export const RELATIONSHIP_TYPES = {
    RELATED: "related",
} as const;

export type RelationshipType = typeof RELATIONSHIP_TYPES[keyof typeof RELATIONSHIP_TYPES];

export const RELATIONSHIP_CREATED_BY = {
    SUGGESTION: "suggestion",
    MANUAL: "manual",
} as const;

export type RelationshipCreatedBy = typeof RELATIONSHIP_CREATED_BY[keyof typeof RELATIONSHIP_CREATED_BY];

/** Human-readable labels for relationship created_by */
export const RELATIONSHIP_CREATED_BY_LABELS: Record<RelationshipCreatedBy, string> = {
    [RELATIONSHIP_CREATED_BY.SUGGESTION]: "From Suggestion",
    [RELATIONSHIP_CREATED_BY.MANUAL]: "Manually Added",
} as const;

/** CSS classes for relationship created_by badges */
export const RELATIONSHIP_CREATED_BY_BADGE_CLASSES: Record<RelationshipCreatedBy, string> = {
    [RELATIONSHIP_CREATED_BY.SUGGESTION]: "bg-amber-500/10 text-amber-600",
    [RELATIONSHIP_CREATED_BY.MANUAL]: "bg-green-500/10 text-green-600",
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
