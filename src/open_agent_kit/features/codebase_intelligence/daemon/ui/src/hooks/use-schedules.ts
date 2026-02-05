/**
 * React Query hooks for agent schedules API.
 *
 * Provides hooks for:
 * - Listing schedules with their status
 * - Getting individual schedule details
 * - Creating new schedules
 * - Updating schedules (enable/disable, cron, description)
 * - Deleting schedules
 * - Manually triggering scheduled runs
 * - Cleaning up orphaned schedules
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { API_ENDPOINTS } from "@/lib/constants";

// =============================================================================
// Types
// =============================================================================

export interface ScheduleStatus {
    task_name: string;
    has_definition: boolean;
    has_db_record: boolean;
    has_task: boolean;
    cron: string | null;
    description: string | null;
    trigger_type: string;
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

export interface ScheduleCreateRequest {
    task_name: string;
    cron_expression?: string;
    description?: string;
    trigger_type?: string;
}

export interface ScheduleUpdateRequest {
    enabled?: boolean;
    cron_expression?: string;
    description?: string;
    trigger_type?: string;
}

export interface ScheduleSyncResponse {
    created: number;
    updated: number;
    removed: number;
    total: number;
}

export interface ScheduleRunResponse {
    task_name: string;
    run_id: string | null;
    status: string | null;
    error: string | null;
    skipped: boolean;
    message: string;
}

export interface ScheduleDeleteResponse {
    task_name: string;
    deleted: boolean;
    message: string;
}

// =============================================================================
// Query Keys
// =============================================================================

const scheduleKeys = {
    all: ["schedules"] as const,
    list: () => [...scheduleKeys.all, "list"] as const,
    detail: (taskName: string) => [...scheduleKeys.all, "detail", taskName] as const,
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

async function fetchScheduleDetail(taskName: string): Promise<ScheduleStatus> {
    const response = await fetch(`${API_ENDPOINTS.SCHEDULES}/${taskName}`);
    if (!response.ok) {
        throw new Error(`Failed to fetch schedule: ${response.statusText}`);
    }
    return response.json();
}

async function createSchedule(data: ScheduleCreateRequest): Promise<ScheduleStatus> {
    const response = await fetch(API_ENDPOINTS.SCHEDULES, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to create schedule: ${response.statusText}`);
    }
    return response.json();
}

async function updateSchedule(
    taskName: string,
    data: ScheduleUpdateRequest
): Promise<ScheduleStatus> {
    const response = await fetch(`${API_ENDPOINTS.SCHEDULES}/${taskName}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to update schedule: ${response.statusText}`);
    }
    return response.json();
}

async function deleteSchedule(taskName: string): Promise<ScheduleDeleteResponse> {
    const response = await fetch(`${API_ENDPOINTS.SCHEDULES}/${taskName}`, {
        method: "DELETE",
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to delete schedule: ${response.statusText}`);
    }
    return response.json();
}

async function runSchedule(taskName: string): Promise<ScheduleRunResponse> {
    const response = await fetch(`${API_ENDPOINTS.SCHEDULES}/${taskName}/run`, {
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
export function useScheduleDetail(taskName: string) {
    return useQuery({
        queryKey: scheduleKeys.detail(taskName),
        queryFn: () => fetchScheduleDetail(taskName),
        enabled: !!taskName,
    });
}

/**
 * Hook to create a new schedule.
 */
export function useCreateSchedule() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (data: ScheduleCreateRequest) => createSchedule(data),
        onSuccess: (data) => {
            // Refresh the schedules list
            queryClient.invalidateQueries({ queryKey: scheduleKeys.list() });
            // Set the specific schedule cache
            queryClient.setQueryData(scheduleKeys.detail(data.task_name), data);
        },
    });
}

/**
 * Hook to update a schedule (enable/disable, cron, description).
 */
export function useUpdateSchedule() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ taskName, ...data }: { taskName: string } & ScheduleUpdateRequest) =>
            updateSchedule(taskName, data),
        onSuccess: (data) => {
            // Update the list cache
            queryClient.invalidateQueries({ queryKey: scheduleKeys.list() });
            // Update the specific schedule cache
            queryClient.setQueryData(scheduleKeys.detail(data.task_name), data);
        },
    });
}

/**
 * Hook to delete a schedule.
 */
export function useDeleteSchedule() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (taskName: string) => deleteSchedule(taskName),
        onSuccess: (_data, taskName) => {
            // Refresh the schedules list
            queryClient.invalidateQueries({ queryKey: scheduleKeys.list() });
            // Remove the specific schedule from cache
            queryClient.removeQueries({ queryKey: scheduleKeys.detail(taskName) });
        },
    });
}

/**
 * Hook to manually trigger a scheduled agent run.
 */
export function useRunSchedule() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (taskName: string) => runSchedule(taskName),
        onSuccess: () => {
            // Refresh schedules list to show updated last_run
            queryClient.invalidateQueries({ queryKey: scheduleKeys.list() });
            // Also refresh agent runs to show the new run
            queryClient.invalidateQueries({ queryKey: ["agent-runs"] });
        },
    });
}

/**
 * Hook to clean up orphaned schedules (tasks that no longer exist).
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
