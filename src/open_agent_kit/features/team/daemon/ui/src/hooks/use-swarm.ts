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
    cli_command: string | null;
    error?: string;
}

export interface SwarmAdvisory {
    type: "version_drift" | "capability_gap" | "general";
    severity: "info" | "warning" | "critical";
    message: string;
    metadata?: Record<string, unknown>;
}

interface SwarmAdvisoriesResponse {
    advisories: SwarmAdvisory[];
    connected: boolean;
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

/** Poll swarm advisories (version drift, capability gaps, etc.). */
export function useSwarmAdvisories() {
    return usePowerQuery<SwarmAdvisoriesResponse>({
        queryKey: ["swarm", "advisories"],
        queryFn: ({ signal }) =>
            fetchJson<SwarmAdvisoriesResponse>(API_ENDPOINTS.SWARM_ADVISORIES, { signal }),
        refetchInterval: SWARM_STATUS_POLL_MS,
        pollCategory: "standard",
    });
}

// ---------------------------------------------------------------------------
// Swarm daemon management (local daemon launch from team UI)
// ---------------------------------------------------------------------------

interface SwarmDaemonStatusResponse {
    configured: boolean;
    running: boolean;
    name?: string;
    url?: string;
    error?: string;
}

interface SwarmDaemonLaunchResponse {
    success: boolean;
    name: string;
    url: string;
}

/** Check if the local swarm daemon config exists and if it's running. */
export function useSwarmDaemonStatus(enabled: boolean) {
    return usePowerQuery<SwarmDaemonStatusResponse>({
        queryKey: ["swarm", "daemon", "status"],
        queryFn: ({ signal }) =>
            fetchJson<SwarmDaemonStatusResponse>(API_ENDPOINTS.SWARM_DAEMON_STATUS, { signal }),
        refetchInterval: SWARM_STATUS_POLL_MS,
        pollCategory: "standard",
        enabled,
    });
}

/** Launch the local swarm daemon (creates config if needed). */
export function useLaunchSwarmDaemon() {
    const queryClient = useQueryClient();
    return useMutation<SwarmDaemonLaunchResponse, Error, void>({
        mutationFn: () => postJson(API_ENDPOINTS.SWARM_DAEMON_LAUNCH, {}),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["swarm", "daemon", "status"] });
        },
    });
}
