import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchJson, postJson } from "@/lib/api";
import { API_ENDPOINTS, getArchiveMemoryEndpoint, getUnarchiveMemoryEndpoint } from "@/lib/constants";
import type { MemoryTypeFilter, BulkAction } from "@/lib/constants";

export interface MemoryListItem {
    id: string;
    memory_type: string;
    observation: string;
    context: string | null;
    tags: string[];
    created_at: string;
    archived?: boolean;
}

export interface MemoriesListResponse {
    memories: MemoryListItem[];
    total: number;
    limit: number;
    offset: number;
}

export interface MemoryTagsResponse {
    tags: string[];
}

export interface UseMemoriesOptions {
    limit?: number;
    offset?: number;
    memoryType?: MemoryTypeFilter;
    tag?: string;
    startDate?: string;
    endDate?: string;
    includeArchived?: boolean;
}

export function useMemories(options: UseMemoriesOptions = {}) {
    const { limit = 50, offset = 0, memoryType = "all", tag = "", startDate = "", endDate = "", includeArchived = false } = options;

    return useQuery<MemoriesListResponse>({
        queryKey: ["memories", limit, offset, memoryType, tag, startDate, endDate, includeArchived],
        queryFn: () => {
            const params = new URLSearchParams({
                limit: String(limit),
                offset: String(offset),
            });
            if (memoryType && memoryType !== "all") {
                params.set("memory_type", memoryType);
            }
            if (tag) {
                params.set("tag", tag);
            }
            if (startDate) {
                params.set("start_date", startDate);
            }
            if (endDate) {
                params.set("end_date", endDate);
            }
            if (includeArchived) {
                params.set("include_archived", "true");
            }
            return fetchJson(`${API_ENDPOINTS.MEMORIES}?${params.toString()}`);
        },
    });
}

export function useMemoryTags() {
    return useQuery<MemoryTagsResponse>({
        queryKey: ["memory-tags"],
        queryFn: () => fetchJson(API_ENDPOINTS.MEMORIES_TAGS),
        staleTime: 60000, // Cache for 1 minute
    });
}

export function useArchiveMemory() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (memoryId: string) => postJson(getArchiveMemoryEndpoint(memoryId), {}),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["memories"] });
        },
    });
}

export function useUnarchiveMemory() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (memoryId: string) => postJson(getUnarchiveMemoryEndpoint(memoryId), {}),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["memories"] });
        },
    });
}

export interface BulkMemoriesRequest {
    memory_ids: string[];
    action: BulkAction;
    tag?: string;
}

export interface BulkMemoriesResponse {
    success: boolean;
    affected_count: number;
    message: string;
}

export function useBulkMemories() {
    const queryClient = useQueryClient();

    return useMutation<BulkMemoriesResponse, Error, BulkMemoriesRequest>({
        mutationFn: (request) => postJson(API_ENDPOINTS.MEMORIES_BULK, request),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["memories"] });
            queryClient.invalidateQueries({ queryKey: ["memory-tags"] });
        },
    });
}
