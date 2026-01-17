import { useQuery } from "@tanstack/react-query";
import { fetchJson } from "@/lib/api";

export interface MemoryListItem {
    id: string;
    memory_type: string;
    observation: string;
    context: string | null;
    tags: string[];
    created_at: string;
}

export interface MemoriesListResponse {
    memories: MemoryListItem[];
    total: number;
    limit: number;
    offset: number;
}

export function useMemories(limit: number = 50, offset: number = 0) {
    return useQuery<MemoriesListResponse>({
        queryKey: ["memories", limit, offset],
        queryFn: () => fetchJson(`/api/memories?limit=${limit}&offset=${offset}`),
    });
}
