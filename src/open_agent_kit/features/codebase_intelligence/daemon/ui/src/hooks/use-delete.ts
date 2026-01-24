import { useMutation, useQueryClient } from "@tanstack/react-query";
import { API_BASE } from "@/lib/api";
import {
    getDeleteSessionEndpoint,
    getDeleteBatchEndpoint,
    getDeleteActivityEndpoint,
    getDeleteMemoryEndpoint,
    getPromoteBatchEndpoint,
} from "@/lib/constants";

// =============================================================================
// Response Types
// =============================================================================

interface DeleteResponse {
    success: boolean;
    deleted_count: number;
    message: string;
}

interface DeleteSessionResponse extends DeleteResponse {
    batches_deleted: number;
    activities_deleted: number;
    memories_deleted: number;
}

interface DeleteBatchResponse extends DeleteResponse {
    activities_deleted: number;
    memories_deleted: number;
}

interface DeleteActivityResponse extends DeleteResponse {
    memory_deleted: boolean;
}

type DeleteMemoryResponse = DeleteResponse;

// =============================================================================
// Delete Functions
// =============================================================================

async function deleteResource<T>(endpoint: string): Promise<T> {
    const url = `${API_BASE}${endpoint}`;
    const response = await fetch(url, { method: "DELETE" });

    if (!response.ok) {
        const error = await response.text();
        throw new Error(`Delete failed: ${response.status} - ${error}`);
    }

    return response.json();
}

// =============================================================================
// Delete Hooks
// =============================================================================

/**
 * Hook to delete a session and all related data.
 * Invalidates sessions query on success.
 */
export function useDeleteSession() {
    const queryClient = useQueryClient();

    return useMutation<DeleteSessionResponse, Error, string>({
        mutationFn: (sessionId: string) =>
            deleteResource<DeleteSessionResponse>(getDeleteSessionEndpoint(sessionId)),
        onSuccess: () => {
            // Invalidate sessions list
            queryClient.invalidateQueries({ queryKey: ["sessions"] });
            // Invalidate activity stats
            queryClient.invalidateQueries({ queryKey: ["activity_stats"] });
            // Invalidate memories (session deletion removes memories)
            queryClient.invalidateQueries({ queryKey: ["memories"] });
        },
    });
}

/**
 * Hook to delete a prompt batch and related data.
 * Invalidates session detail query on success.
 */
export function useDeletePromptBatch() {
    const queryClient = useQueryClient();

    return useMutation<DeleteBatchResponse, Error, { batchId: number; sessionId: string }>({
        mutationFn: ({ batchId }) =>
            deleteResource<DeleteBatchResponse>(getDeleteBatchEndpoint(batchId)),
        onSuccess: (_data, { sessionId }) => {
            // Invalidate session detail
            queryClient.invalidateQueries({ queryKey: ["session", sessionId] });
            // Invalidate memories
            queryClient.invalidateQueries({ queryKey: ["memories"] });
        },
    });
}

/**
 * Hook to delete a single activity.
 * Invalidates batch activities query on success.
 */
export function useDeleteActivity() {
    const queryClient = useQueryClient();

    return useMutation<DeleteActivityResponse, Error, { activityId: number; batchId: string }>({
        mutationFn: ({ activityId }) =>
            deleteResource<DeleteActivityResponse>(getDeleteActivityEndpoint(activityId)),
        onSuccess: (_data, { batchId }) => {
            // Invalidate batch activities
            queryClient.invalidateQueries({ queryKey: ["batch_activities", batchId] });
            // Invalidate memories if activity had linked memory
            queryClient.invalidateQueries({ queryKey: ["memories"] });
        },
    });
}

/**
 * Hook to delete a memory observation.
 * Invalidates memories query on success.
 */
export function useDeleteMemory() {
    const queryClient = useQueryClient();

    return useMutation<DeleteMemoryResponse, Error, string>({
        mutationFn: (memoryId: string) =>
            deleteResource<DeleteMemoryResponse>(getDeleteMemoryEndpoint(memoryId)),
        onSuccess: () => {
            // Invalidate memories list
            queryClient.invalidateQueries({ queryKey: ["memories"] });
        },
    });
}


// =============================================================================
// Promote Hook (POST action)
// =============================================================================

interface PromoteBatchResponse {
    success: boolean;
    batch_id: number;
    observations_extracted: number;
    activities_processed: number;
    classification: string | null;
    duration_ms: number;
    message: string;
}

async function postResource<T>(endpoint: string): Promise<T> {
    const url = `${API_BASE}${endpoint}`;
    const response = await fetch(url, { method: "POST" });

    if (!response.ok) {
        const error = await response.text();
        throw new Error(`Promote failed: ${response.status} - ${error}`);
    }

    return response.json();
}

/**
 * Hook to promote an agent batch to extract memories.
 * Forces user-style LLM extraction on batches that were previously skipped.
 * Invalidates session detail and memories queries on success.
 */
export function usePromoteBatch() {
    const queryClient = useQueryClient();

    return useMutation<PromoteBatchResponse, Error, { batchId: number; sessionId: string }>({
        mutationFn: ({ batchId }) =>
            postResource<PromoteBatchResponse>(getPromoteBatchEndpoint(batchId)),
        onSuccess: (_data, { sessionId }) => {
            // Invalidate session detail to refresh batch classification
            queryClient.invalidateQueries({ queryKey: ["session", sessionId] });
            // Invalidate memories (promotion creates new memories)
            queryClient.invalidateQueries({ queryKey: ["memories"] });
        },
    });
}
