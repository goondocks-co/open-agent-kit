/**
 * React Query hooks for self-update status, check, apply, and channel operations.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchJson, postJson, putJson } from "@/lib/api";
import { API_ENDPOINTS } from "@/lib/constants";

// =============================================================================
// Types
// =============================================================================

/** Staged update waiting to be applied */
interface StagedUpdate {
    version: string;
    wheel_path: string;
    downloaded_at: string;
}

/** Last update check result stored in status */
interface LastCheck {
    timestamp: number;
    version: string;
    update_available: boolean;
}

/** Full update status response from API */
export interface UpdateStatus {
    exempt: boolean;
    reason?: string;
    message?: string;
    running_version?: string;
    channel?: string;
    auto_download?: boolean;
    staged_update?: StagedUpdate | null;
    last_check?: LastCheck | null;
    error?: string | null;
}

/** Result returned by a manual update check */
export interface CheckResult {
    update_available: boolean;
    latest_version: string | null;
    channel: string;
    error: string | null;
}

// =============================================================================
// Polling interval
// =============================================================================

/** Refetch update status every 30 seconds */
const UPDATE_STATUS_REFETCH_INTERVAL_MS = 30_000;

// =============================================================================
// Hooks
// =============================================================================

/**
 * Hook to poll current update status (running version, staged update, last check, etc.).
 */
export function useUpdateStatus() {
    return useQuery<UpdateStatus>({
        queryKey: ["update-status"],
        queryFn: ({ signal }: { signal: AbortSignal }) =>
            fetchJson(API_ENDPOINTS.UPDATE_STATUS, { signal }) as Promise<UpdateStatus>,
        refetchInterval: UPDATE_STATUS_REFETCH_INTERVAL_MS,
    });
}

/**
 * Hook to trigger an on-demand update check against PyPI.
 * Invalidates update-status on success so UI reflects the latest check result.
 */
export function useUpdateCheck() {
    const queryClient = useQueryClient();
    return useMutation<CheckResult>({
        mutationFn: () => postJson(API_ENDPOINTS.UPDATE_CHECK, null) as Promise<CheckResult>,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["update-status"] });
        },
    });
}

/**
 * Hook to apply a staged update (installs the downloaded wheel and restarts).
 */
export function useUpdateApply() {
    return useMutation({
        mutationFn: () => postJson(API_ENDPOINTS.UPDATE_APPLY, null),
    });
}

/**
 * Hook to switch the update channel (e.g. "stable" → "beta").
 * Invalidates update-status on success so the new channel is reflected immediately.
 */
export function useUpdateChannel() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (channel: string) =>
            putJson(API_ENDPOINTS.UPDATE_CHANNEL, { channel }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["update-status"] });
        },
    });
}

// =============================================================================
// Type exports
// =============================================================================

export type { StagedUpdate, LastCheck };
