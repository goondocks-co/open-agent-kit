import { useQuery } from "@tanstack/react-query";
import { fetchJson } from "@/lib/api";

export interface CodeResult {
    id: string;
    chunk_type: string;
    name: string | null;
    filepath: string;
    start_line: number;
    end_line: number;
    relevance: number;
    preview: string | null;
}

export interface MemoryResult {
    id: string;
    memory_type: string;
    summary: string;
    relevance: number;
}

export interface SearchResponse {
    query: string;
    code: CodeResult[];
    memory: MemoryResult[];
    total_tokens_available: number;
}

export function useSearch(query: string) {
    return useQuery<SearchResponse>({
        queryKey: ["search", query],
        queryFn: () => fetchJson(`/api/search?query=${encodeURIComponent(query)}`),
        enabled: query.length > 2,
        staleTime: 60000,
    });
}
