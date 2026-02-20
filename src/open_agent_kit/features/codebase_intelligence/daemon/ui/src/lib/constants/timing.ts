/**
 * Polling intervals, time constants, and time formatting helpers.
 */

// =============================================================================
// Polling & Timing
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

// =============================================================================
// Power Management
// =============================================================================

/** How long without user activity before entering idle state (1 minute) */
export const POWER_IDLE_THRESHOLD_MS = 60_000;

/** How long without user activity before entering deep sleep (5 minutes) */
export const POWER_DEEP_SLEEP_THRESHOLD_MS = 300_000;

/** Debounce interval for user activity events to avoid thrash (1 second) */
export const POWER_ACTIVITY_DEBOUNCE_MS = 1_000;

/** Poll rate multipliers per power state */
export const POWER_MULTIPLIERS = {
    active: 1,
    idle: 2,
    deep_sleep: Infinity, // stops polling (except heartbeat)
    hidden: Infinity,     // stops polling (except heartbeat)
} as const;

/** Maximum heartbeat poll interval when tab is hidden (60 seconds) */
export const HEARTBEAT_HIDDEN_CAP_MS = 60_000;

/** Maximum heartbeat poll interval in deep sleep (120 seconds) */
export const HEARTBEAT_DEEP_SLEEP_CAP_MS = 120_000;

// =============================================================================
// Formatting
// =============================================================================

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
