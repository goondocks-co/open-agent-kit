/**
 * React Query hooks for team-side swarm integration.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchJson, postJson } from "@/lib/api";
import { usePowerQuery } from "@oak/ui/hooks/use-power-query";
import { API_ENDPOINTS, SWARM_STATUS_POLL_MS } from "@/lib/constants";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SwarmStatusResponse {
    joined: boolean;
    swarm_url: string | null;
    error?: string;
}

interface JoinSwarmParams {
    swarm_url: string;
    swarm_token: string;
}

interface SwarmMutationResult {
    success?: boolean;
    swarm_url?: string;
    error?: string;
}

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

/** Poll swarm connection status. */
export function useSwarmStatus() {
    return usePowerQuery<SwarmStatusResponse>({
        queryKey: ["swarm", "status"],
        queryFn: ({ signal }) => fetchJson<SwarmStatusResponse>(API_ENDPOINTS.SWARM_STATUS, { signal }),
        refetchInterval: SWARM_STATUS_POLL_MS,
        pollCategory: "standard",
    });
}

/** Join a swarm. */
export function useJoinSwarm() {
    const queryClient = useQueryClient();
    return useMutation<SwarmMutationResult, Error, JoinSwarmParams>({
        mutationFn: (params) => postJson(API_ENDPOINTS.SWARM_JOIN, params),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["swarm", "status"] });
        },
    });
}

/** Leave the current swarm. */
export function useLeaveSwarm() {
    const queryClient = useQueryClient();
    return useMutation<SwarmMutationResult, Error, void>({
        mutationFn: () => postJson(API_ENDPOINTS.SWARM_LEAVE, {}),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["swarm", "status"] });
        },
    });
}
