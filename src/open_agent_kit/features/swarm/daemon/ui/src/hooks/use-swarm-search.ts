import { useMutation } from "@tanstack/react-query";
import { postJson } from "@/lib/api";
import { API_ENDPOINTS } from "@/lib/constants";

export interface SearchMatch {
    id?: string;
    type: string;
    content: string;
    score?: number;
    file_path?: string;
    doc_type?: string;
}

export interface ProjectResult {
    project_slug: string;
    matches: SearchMatch[];
}

export interface SearchResult {
    results: ProjectResult[];
    error?: string;
}

export interface SearchParams {
    query: string;
    search_type?: string;
    limit?: number;
}

export function useSwarmSearch() {
    return useMutation<SearchResult, Error, SearchParams>({
        mutationFn: (params) =>
            postJson(API_ENDPOINTS.SWARM_SEARCH, {
                query: params.query,
                search_type: params.search_type ?? "all",
                limit: params.limit ?? 10,
            }),
    });
}
