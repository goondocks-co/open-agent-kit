/**
 * React Query hook for federated network search via the cloud relay.
 *
 * Sends a POST to /api/search/network and returns results from peer nodes.
 * Only fires when explicitly enabled and when the query is long enough.
 */

import { useQuery } from "@tanstack/react-query";
import { postJson } from "@/lib/api";
import { API_ENDPOINTS } from "@/lib/constants";

/** Minimum query length before firing a network search */
const MIN_NETWORK_SEARCH_QUERY_LENGTH = 2;

/** How long network search results stay fresh (1 minute) */
const NETWORK_SEARCH_STALE_TIME_MS = 60000;

export interface NetworkSearchResult {
    machine_id: string;
    observation?: string;
    summary?: string;
    memory_type?: string;
    relevance?: number;
    confidence?: string;
}

export interface NetworkSearchResponse {
    results: NetworkSearchResult[];
    error?: string;
}

/**
 * Hook for searching across the team network via the cloud relay.
 *
 * @param query - Search query string.
 * @param searchType - Type of search (all, memory, plans, sessions). Code is rejected.
 * @param limit - Maximum results per node.
 * @param enabled - Whether to fire the search (false disables it).
 */
export function useNetworkSearch(
    query: string,
    searchType: string,
    limit: number,
    enabled: boolean,
) {
    return useQuery<NetworkSearchResponse>({
        queryKey: ["network-search", query, searchType, limit],
        queryFn: ({ signal }) =>
            postJson<NetworkSearchResponse>(API_ENDPOINTS.SEARCH_NETWORK, {
                query,
                search_type: searchType,
                limit,
            }, { signal }),
        enabled: enabled && query.length > MIN_NETWORK_SEARCH_QUERY_LENGTH,
        staleTime: NETWORK_SEARCH_STALE_TIME_MS,
        retry: false,
    });
}
