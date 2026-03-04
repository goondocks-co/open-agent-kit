/**
 * Agent run status, colors, and watchdog detection.
 */

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

/** Error message pattern for runs recovered by the watchdog */
export const WATCHDOG_RECOVERY_ERROR_PATTERN = "Recovered by watchdog";

/**
 * Check if a run was recovered by the watchdog process.
 */
export function isWatchdogRecoveredRun(error: string | null | undefined): boolean {
    return error?.includes(WATCHDOG_RECOVERY_ERROR_PATTERN) ?? false;
}

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
