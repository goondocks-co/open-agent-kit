/**
 * React Query hooks for agent schedules API.
 *
 * Provides hooks for:
 * - Listing schedules with their status
 * - Getting individual schedule details
 * - Enabling/disabling schedules
 * - Manually triggering scheduled runs
 * - Syncing schedules from YAML
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { API_ENDPOINTS } from "@/lib/constants";

// =============================================================================
// Types
// =============================================================================

export interface ScheduleStatus {
    instance_name: string;
    has_definition: boolean;
    has_db_record: boolean;
    cron: string | null;
    description: string | null;
    enabled: boolean | null;
    last_run_at: string | null;
    last_run_id: string | null;
    next_run_at: string | null;
}

export interface ScheduleListResponse {
    schedules: ScheduleStatus[];
    total: number;
    scheduler_running: boolean;
}

export interface ScheduleSyncResponse {
    created: number;
    updated: number;
    removed: number;
    total: number;
}

export interface ScheduleRunResponse {
    instance_name: string;
    run_id: string | null;
    status: string | null;
    error: string | null;
    message: string;
}

// =============================================================================
// Query Keys
// =============================================================================

const scheduleKeys = {
    all: ["schedules"] as const,
    list: () => [...scheduleKeys.all, "list"] as const,
    detail: (instanceName: string) => [...scheduleKeys.all, "detail", instanceName] as const,
};

// =============================================================================
// API Functions
// =============================================================================

async function fetchSchedules(): Promise<ScheduleListResponse> {
    const response = await fetch(API_ENDPOINTS.SCHEDULES);
    if (!response.ok) {
        throw new Error(`Failed to fetch schedules: ${response.statusText}`);
    }
    return response.json();
}

async function fetchScheduleDetail(instanceName: string): Promise<ScheduleStatus> {
    const response = await fetch(`${API_ENDPOINTS.SCHEDULES}/${instanceName}`);
    if (!response.ok) {
        throw new Error(`Failed to fetch schedule: ${response.statusText}`);
    }
    return response.json();
}

async function updateSchedule(
    instanceName: string,
    data: { enabled?: boolean }
): Promise<ScheduleStatus> {
    const response = await fetch(`${API_ENDPOINTS.SCHEDULES}/${instanceName}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    });
    if (!response.ok) {
        throw new Error(`Failed to update schedule: ${response.statusText}`);
    }
    return response.json();
}

async function runSchedule(instanceName: string): Promise<ScheduleRunResponse> {
    const response = await fetch(`${API_ENDPOINTS.SCHEDULES}/${instanceName}/run`, {
        method: "POST",
    });
    if (!response.ok) {
        throw new Error(`Failed to run schedule: ${response.statusText}`);
    }
    return response.json();
}

async function syncSchedules(): Promise<ScheduleSyncResponse> {
    const response = await fetch(API_ENDPOINTS.SCHEDULES_SYNC, {
        method: "POST",
    });
    if (!response.ok) {
        throw new Error(`Failed to sync schedules: ${response.statusText}`);
    }
    return response.json();
}

// =============================================================================
// Hooks
// =============================================================================

/**
 * Hook to fetch all schedules with their status.
 */
export function useSchedules() {
    return useQuery({
        queryKey: scheduleKeys.list(),
        queryFn: fetchSchedules,
        refetchInterval: 30000, // Refresh every 30 seconds
    });
}

/**
 * Hook to fetch a single schedule's detail.
 */
export function useScheduleDetail(instanceName: string) {
    return useQuery({
        queryKey: scheduleKeys.detail(instanceName),
        queryFn: () => fetchScheduleDetail(instanceName),
        enabled: !!instanceName,
    });
}

/**
 * Hook to update a schedule (enable/disable).
 */
export function useUpdateSchedule() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ instanceName, enabled }: { instanceName: string; enabled: boolean }) =>
            updateSchedule(instanceName, { enabled }),
        onSuccess: (data) => {
            // Update the list cache
            queryClient.invalidateQueries({ queryKey: scheduleKeys.list() });
            // Update the specific schedule cache
            queryClient.setQueryData(scheduleKeys.detail(data.instance_name), data);
        },
    });
}

/**
 * Hook to manually trigger a scheduled agent run.
 */
export function useRunSchedule() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (instanceName: string) => runSchedule(instanceName),
        onSuccess: () => {
            // Refresh schedules list to show updated last_run
            queryClient.invalidateQueries({ queryKey: scheduleKeys.list() });
            // Also refresh agent runs to show the new run
            queryClient.invalidateQueries({ queryKey: ["agent-runs"] });
        },
    });
}

/**
 * Hook to sync schedules from YAML definitions.
 */
export function useSyncSchedules() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: syncSchedules,
        onSuccess: () => {
            // Refresh the schedules list
            queryClient.invalidateQueries({ queryKey: scheduleKeys.list() });
        },
    });
}
