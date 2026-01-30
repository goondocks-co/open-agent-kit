/**
 * React hooks for saved task data fetching and mutations.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchJson, postJson, patchJson, deleteJson } from "@/lib/api";
import { API_ENDPOINTS } from "@/lib/constants";

// =============================================================================
// Types
// =============================================================================

/** Saved task from the API */
export interface SavedTask {
    id: string;
    name: string;
    description: string | null;
    agent_name: string;
    task: string;
    schedule_cron: string | null;
    schedule_enabled: boolean;
    last_run_at: string | null;
    last_run_id: string | null;
    total_runs: number;
    created_at: string;
    updated_at: string;
}

/** Saved task list response */
export interface SavedTaskListResponse {
    tasks: SavedTask[];
    total: number;
    limit: number;
    offset: number;
}

/** Create saved task request */
export interface CreateSavedTaskRequest {
    name: string;
    agent_name: string;
    task: string;
    description?: string;
    schedule_cron?: string;
}

/** Update saved task request */
export interface UpdateSavedTaskRequest {
    name?: string;
    description?: string;
    task?: string;
    schedule_cron?: string;
    schedule_enabled?: boolean;
}

/** Run saved task response */
export interface RunSavedTaskResponse {
    run_id: string;
    status: string;
    message: string;
}

// =============================================================================
// Hooks
// =============================================================================

/** Fetch list of saved tasks */
export function useSavedTasks(limit = 50, offset = 0, agentName?: string) {
    const params = new URLSearchParams();
    params.set("limit", String(limit));
    params.set("offset", String(offset));
    if (agentName) params.set("agent_name", agentName);

    return useQuery({
        queryKey: ["saved-tasks", limit, offset, agentName],
        queryFn: () => fetchJson<SavedTaskListResponse>(`${API_ENDPOINTS.SAVED_TASKS}?${params}`),
        staleTime: 30000, // Consider data fresh for 30 seconds
    });
}

/** Fetch a single saved task by ID */
export function useSavedTask(taskId: string | null) {
    return useQuery({
        queryKey: ["saved-tasks", taskId],
        queryFn: () => fetchJson<SavedTask>(`${API_ENDPOINTS.SAVED_TASKS}/${taskId}`),
        enabled: !!taskId,
        staleTime: 10000,
    });
}

/** Create a new saved task */
export function useCreateSavedTask() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (request: CreateSavedTaskRequest) =>
            postJson<SavedTask>(API_ENDPOINTS.SAVED_TASKS, request),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["saved-tasks"] });
        },
    });
}

/** Update a saved task */
export function useUpdateSavedTask() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ taskId, ...request }: UpdateSavedTaskRequest & { taskId: string }) =>
            patchJson<SavedTask>(`${API_ENDPOINTS.SAVED_TASKS}/${taskId}`, request),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["saved-tasks"] });
        },
    });
}

/** Delete a saved task */
export function useDeleteSavedTask() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (taskId: string) =>
            deleteJson<{ success: boolean; message: string }>(`${API_ENDPOINTS.SAVED_TASKS}/${taskId}`),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["saved-tasks"] });
        },
    });
}

/** Run a saved task */
export function useRunSavedTask() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (taskId: string) =>
            postJson<RunSavedTaskResponse>(`${API_ENDPOINTS.SAVED_TASKS}/${taskId}/run`, {}),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["saved-tasks"] });
            queryClient.invalidateQueries({ queryKey: ["agent-runs"] });
        },
    });
}
