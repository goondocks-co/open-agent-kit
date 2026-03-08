import { useMutation } from "@tanstack/react-query";
import { postJson } from "@/lib/api";
import { API_ENDPOINTS } from "@/lib/constants";

export interface FetchedChunk {
    id: string;
    content: string;
    tokens: number;
}

export interface FetchResult {
    results: FetchedChunk[];
    total_tokens: number;
}

export interface FetchParams {
    ids: string[];
    project_slug: string;
}

/**
 * Fetch full content for chunk IDs via the swarm daemon.
 *
 * The daemon now calls the swarm DO's `/api/swarm/fetch` directly (the same
 * path the MCP `swarm_fetch` tool uses), so the response is plain JSON —
 * no MCP envelope unwrapping needed.
 */
export function useSwarmFetch() {
    return useMutation<FetchResult, Error, FetchParams>({
        mutationFn: async (params) => {
            const raw = await postJson(API_ENDPOINTS.SWARM_FETCH, {
                ids: params.ids,
                project_slug: params.project_slug,
            });

            const obj = raw as Record<string, unknown>;

            // Direct error from swarm daemon
            if (obj.error && typeof obj.error === "string") {
                throw new Error(obj.error);
            }

            const results = obj.results;
            if (!Array.isArray(results)) {
                throw new Error("Unexpected response shape from swarm fetch");
            }

            const result = raw as unknown as FetchResult;
            if (result.results.length === 0) {
                throw new Error("No results returned for the requested IDs");
            }

            return result;
        },
    });
}
