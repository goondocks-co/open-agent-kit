/**
 * Log levels, files, tags, categories, rotation settings, and helpers.
 */

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
 */
export function calculateMaxLogDiskUsage(maxSizeMb: number, backupCount: number): number {
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

/** Log tags for filtering HOOKS log content (structured tags) */
export const HOOKS_LOG_TAGS = {
    SESSION_START: "[SESSION-START]",
    SESSION_END: "[SESSION-END]",
    PROMPT_SUBMIT: "[PROMPT-SUBMIT]",
    TOOL_USE: "[TOOL-USE]",
    SUBAGENT_START: "[SUBAGENT-START]",
    SUBAGENT_STOP: "[SUBAGENT-STOP]",
    CONTEXT_INJECT: "[CONTEXT-INJECT]",
    OTEL: "[OTEL:",
} as const;

export type HooksLogTagType = typeof HOOKS_LOG_TAGS[keyof typeof HOOKS_LOG_TAGS];

/** Tag categories for hooks log UI grouping */
export const HOOKS_LOG_TAG_CATEGORIES = {
    lifecycle: {
        label: "Lifecycle",
        tags: [HOOKS_LOG_TAGS.SESSION_START, HOOKS_LOG_TAGS.SESSION_END, HOOKS_LOG_TAGS.PROMPT_SUBMIT] as HooksLogTagType[],
    },
    tools: {
        label: "Tools",
        tags: [HOOKS_LOG_TAGS.TOOL_USE, HOOKS_LOG_TAGS.SUBAGENT_START, HOOKS_LOG_TAGS.SUBAGENT_STOP] as HooksLogTagType[],
    },
    context: {
        label: "Context",
        tags: [HOOKS_LOG_TAGS.CONTEXT_INJECT] as HooksLogTagType[],
    },
    otel: {
        label: "OTEL",
        tags: [HOOKS_LOG_TAGS.OTEL] as HooksLogTagType[],
    },
} as const;

export type HooksLogTagCategory = keyof typeof HOOKS_LOG_TAG_CATEGORIES;

/** Tag display names for hooks log (short labels for chips) */
export const HOOKS_LOG_TAG_DISPLAY_NAMES: Record<HooksLogTagType, string> = {
    [HOOKS_LOG_TAGS.SESSION_START]: "Session Start",
    [HOOKS_LOG_TAGS.SESSION_END]: "Session End",
    [HOOKS_LOG_TAGS.PROMPT_SUBMIT]: "Prompt",
    [HOOKS_LOG_TAGS.TOOL_USE]: "Tool Use",
    [HOOKS_LOG_TAGS.SUBAGENT_START]: "Agent Start",
    [HOOKS_LOG_TAGS.SUBAGENT_STOP]: "Agent Stop",
    [HOOKS_LOG_TAGS.CONTEXT_INJECT]: "Context Inject",
    [HOOKS_LOG_TAGS.OTEL]: "OTEL",
} as const;

/** Log tags for filtering DAEMON log content */
export const DAEMON_LOG_TAGS = {
    DEBUG: "[DEBUG]",
    INFO: "[INFO]",
    WARNING: "[WARNING]",
    ERROR: "[ERROR]",
    SEARCH_MEMORY: "[SEARCH:memory",
    SEARCH_CODE: "[SEARCH:code",
    SEARCH_FILE: "[SEARCH:file-context",
    INJECT: "[INJECT:",
} as const;

export type DaemonLogTagType = typeof DAEMON_LOG_TAGS[keyof typeof DAEMON_LOG_TAGS];

/** Tag categories for daemon log UI grouping */
export const DAEMON_LOG_TAG_CATEGORIES = {
    levels: {
        label: "Log Levels",
        tags: [DAEMON_LOG_TAGS.DEBUG, DAEMON_LOG_TAGS.INFO, DAEMON_LOG_TAGS.WARNING, DAEMON_LOG_TAGS.ERROR] as DaemonLogTagType[],
    },
    search: {
        label: "Search & Inject",
        tags: [DAEMON_LOG_TAGS.SEARCH_MEMORY, DAEMON_LOG_TAGS.SEARCH_CODE, DAEMON_LOG_TAGS.SEARCH_FILE, DAEMON_LOG_TAGS.INJECT] as DaemonLogTagType[],
    },
} as const;

export type DaemonLogTagCategory = keyof typeof DAEMON_LOG_TAG_CATEGORIES;

/** Tag display names for daemon log (short labels for chips) */
export const DAEMON_LOG_TAG_DISPLAY_NAMES: Record<DaemonLogTagType, string> = {
    [DAEMON_LOG_TAGS.DEBUG]: "Debug",
    [DAEMON_LOG_TAGS.INFO]: "Info",
    [DAEMON_LOG_TAGS.WARNING]: "Warning",
    [DAEMON_LOG_TAGS.ERROR]: "Error",
    [DAEMON_LOG_TAGS.SEARCH_MEMORY]: "Search Memory",
    [DAEMON_LOG_TAGS.SEARCH_CODE]: "Search Code",
    [DAEMON_LOG_TAGS.SEARCH_FILE]: "Search File",
    [DAEMON_LOG_TAGS.INJECT]: "Inject",
} as const;

// Legacy aliases for backwards compatibility
export const LOG_TAGS = HOOKS_LOG_TAGS;
export type LogTagType = HooksLogTagType;
export const LOG_TAG_CATEGORIES = HOOKS_LOG_TAG_CATEGORIES;
export type LogTagCategory = HooksLogTagCategory;
export const LOG_TAG_DISPLAY_NAMES = HOOKS_LOG_TAG_DISPLAY_NAMES;
