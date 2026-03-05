/**
 * Agent run status (re-exported from shared) and team-specific watchdog detection.
 */

// Re-export shared agent status types, labels, and colors
export {
    AGENT_RUN_STATUS,
    type AgentRunStatusType,
    AGENT_RUN_STATUS_LABELS,
    AGENT_RUN_STATUS_COLORS,
} from "@oak/ui/lib/agent-status";

// =============================================================================
// Team-Specific: Watchdog Recovery Detection
// =============================================================================

/** Error message pattern for runs recovered by the watchdog */
export const WATCHDOG_RECOVERY_ERROR_PATTERN = "Recovered by watchdog";

/**
 * Check if a run was recovered by the watchdog process.
 */
export function isWatchdogRecoveredRun(error: string | null | undefined): boolean {
    return error?.includes(WATCHDOG_RECOVERY_ERROR_PATTERN) ?? false;
}
