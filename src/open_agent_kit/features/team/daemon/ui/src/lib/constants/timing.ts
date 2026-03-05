/**
 * Polling intervals and time constants for the team daemon UI.
 *
 * Time formatting utilities and power management constants are
 * re-exported from shared modules to avoid duplication.
 */

// Re-export shared time utilities
export { TIME_UNITS, formatRelativeTime, formatUptime } from "@oak/ui/lib/time-utils";

// Re-export shared power management constants
export {
    POWER_IDLE_THRESHOLD_MS,
    POWER_DEEP_SLEEP_THRESHOLD_MS,
    POWER_ACTIVITY_DEBOUNCE_MS,
    POWER_MULTIPLIERS,
    HEARTBEAT_HIDDEN_CAP_MS,
    HEARTBEAT_DEEP_SLEEP_CAP_MS,
} from "@oak/ui/lib/constants";

// =============================================================================
// Polling & Timing (team-specific)
// =============================================================================

/** Status polling interval when actively indexing (5 seconds) */
export const STATUS_POLL_ACTIVE_MS = 5000;

/** Status polling interval when idle (30 seconds) */
export const STATUS_POLL_IDLE_MS = 30000;

/** Log polling interval in milliseconds */
export const LOGS_POLL_INTERVAL_MS = 3000;

/** Memory processing cycle interval in seconds (backend) */
export const MEMORY_PROCESS_INTERVAL_SECONDS = 60;

/** Polling interval while waiting for daemon restart (2 seconds) */
export const RESTART_POLL_INTERVAL_MS = 2000;

/** Maximum time to wait for daemon restart before showing fallback (60 seconds) */
export const RESTART_TIMEOUT_MS = 60000;

/** Duration to show "Copied!" feedback after clipboard copy (2 seconds) */
export const COPIED_FEEDBACK_DURATION_MS = 2000;

/** last_seen threshold for considering a team member "online" (60 seconds) */
export const MEMBER_ONLINE_THRESHOLD_MS = 60 * 1000;

/** Swarm status polling interval (10 seconds) */
export const SWARM_STATUS_POLL_MS = 10_000;
