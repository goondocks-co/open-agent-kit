/**
 * Bulk actions, date ranges, delete confirmations.
 */

// =============================================================================
// Bulk Actions
// =============================================================================

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
// Date Range Presets
// =============================================================================

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
