/**
 * UI constants: step states, test results, message types, form defaults,
 * display constants, pagination, and fallback messages.
 */

// =============================================================================
// Step States
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

// =============================================================================
// Test Results
// =============================================================================

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

/** Character limit for agent run task before truncation in Run History */
export const RUN_TASK_TRUNCATION_LIMIT = 300;

/** Character limit for agent run result before truncation in Run History */
export const RUN_RESULT_TRUNCATION_LIMIT = 500;

/** Maximum length for session title display */
export const SESSION_TITLE_MAX_LENGTH = 60;

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
// Fallback Messages
// =============================================================================

// =============================================================================
// Config Origin Badges
// =============================================================================

/** CSS classes for config origin badges (user overlay vs project vs default) */
export const ORIGIN_BADGE_CLASSES = {
    user: "bg-blue-500/10 text-blue-700 dark:text-blue-400",
    project: "bg-zinc-500/10 text-zinc-600 dark:text-zinc-400",
    default: "bg-zinc-500/10 text-zinc-500 dark:text-zinc-500",
} as const;

/** Display labels for config origin badges */
export const ORIGIN_BADGE_LABELS = {
    user: "User Override",
    project: "Project",
    default: "Default",
} as const;

// =============================================================================
// Fallback Messages
// =============================================================================

/** Fallback messages for empty states */
export const FALLBACK_MESSAGES = {
    NO_PREVIEW: "No preview available",
    NO_SESSIONS: "No sessions recorded yet",
    NO_RESULTS: "No results found",
    LOADING: "Loading...",
} as const;
