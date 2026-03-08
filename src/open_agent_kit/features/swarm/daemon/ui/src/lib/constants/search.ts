/**
 * Search UI constants — doc type colors, confidence thresholds, and search types.
 */

/** Doc type badge colors */
export const DOC_TYPE_COLORS = {
    memory: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400",
    sessions: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
    plans: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
} as const;

/** Confidence score thresholds */
export const CONFIDENCE_THRESHOLDS = {
    HIGH: 0.8,
    MEDIUM: 0.5,
} as const;

/** Confidence badge colors */
export const CONFIDENCE_BADGES = {
    high: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
    medium: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400",
    low: "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400",
} as const;

/** Available search types — must match the worker's MCP schema enum */
export const SEARCH_TYPES = ["all", "memory", "sessions", "plans"] as const;
export type SearchType = (typeof SEARCH_TYPES)[number];

/** Default result limit options */
export const RESULT_LIMIT_OPTIONS = [10, 25, 50] as const;

/** Default number of visible matches before collapsing */
export const COLLAPSE_THRESHOLD = 5;
