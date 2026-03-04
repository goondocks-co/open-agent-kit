import { useMutation } from "@tanstack/react-query";
import { postJson } from "@/lib/api";
import { API_ENDPOINTS } from "@/lib/constants";

interface SearchResult {
    results: Array<{
        project_slug: string;
        matches: Array<{
            type: string;
            content: string;
            score?: number;
        }>;
    }>;
    error?: string;
}

export function useSwarmSearch() {
    return useMutation<SearchResult, Error, { query: string; search_type?: string; limit?: number }>({
        mutationFn: (params) =>
            postJson(API_ENDPOINTS.SWARM_SEARCH, {
                query: params.query,
                search_type: params.search_type ?? "all",
                limit: params.limit ?? 10,
            }),
    });
}
