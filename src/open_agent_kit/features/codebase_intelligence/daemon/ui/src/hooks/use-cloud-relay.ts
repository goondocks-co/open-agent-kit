/**
 * React Query hooks for cloud relay operations.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchJson, postJson } from "@/lib/api";
import { API_ENDPOINTS } from "@/lib/constants";

// =============================================================================
// Interfaces
// =============================================================================

/** Cloud relay status response from API */
export interface CloudRelayStatus {
    connected: boolean;
    worker_url: string | null;
    connected_at: string | null;
    last_heartbeat: string | null;
    error: string | null;
    reconnect_attempts: number;
    agent_token: string | null;
    mcp_endpoint: string | null;
    cf_account_name: string | null;
    custom_domain: string | null;
    worker_name: string | null;
}

/** Cloud relay start response */
export interface CloudRelayStartResponse {
    status: string;
    connected: boolean;
    worker_url: string | null;
    mcp_endpoint: string | null;
    agent_token: string | null;
    phase: string | null;
    cf_account_name: string | null;
    error: string | null;
    suggestion: string | null;
    detail: string | null;
    worker_name: string | null;
}

/** Cloud relay stop response */
interface CloudRelayStopResponse {
    status: string;
}

/** Cloud relay preflight check response */
export interface CloudRelayPreflight {
    npm_available: boolean;
    wrangler_available: boolean;
    wrangler_authenticated: boolean;
    cf_account_name: string | null;
    cf_account_id: string | null;
    scaffolded: boolean;
    installed: boolean;
    deployed: boolean;
    worker_url: string | null;
}

// =============================================================================
// Constants
// =============================================================================

/** Polling interval for cloud relay status (30 seconds) */
const CLOUD_RELAY_STATUS_REFETCH_INTERVAL_MS = 30_000;

// =============================================================================
// Hooks
// =============================================================================

/**
 * Hook to get current cloud relay status.
 */
export function useCloudRelayStatus() {
    return useQuery<CloudRelayStatus>({
        queryKey: ["cloud-relay-status"],
        queryFn: ({ signal }) => fetchJson(API_ENDPOINTS.CLOUD_RELAY_STATUS, { signal }),
        refetchInterval: CLOUD_RELAY_STATUS_REFETCH_INTERVAL_MS,
    });
}

/**
 * Hook to start the cloud relay (scaffold, install, deploy, connect).
 */
export function useCloudRelayStart() {
    const queryClient = useQueryClient();
    return useMutation<CloudRelayStartResponse, Error, void>({
        mutationFn: () =>
            postJson(API_ENDPOINTS.CLOUD_RELAY_START, {}),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["cloud-relay-status"] });
        },
    });
}

/**
 * Hook to stop the cloud relay and undeploy.
 */
export function useCloudRelayStop() {
    const queryClient = useQueryClient();
    return useMutation<CloudRelayStopResponse, Error, void>({
        mutationFn: () =>
            postJson(API_ENDPOINTS.CLOUD_RELAY_STOP, {}),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["cloud-relay-status"] });
        },
    });
}

/**
 * Hook to run preflight checks for cloud relay prerequisites.
 * Fetched once on load (no refetchInterval).
 */
export function useCloudRelayPreflight() {
    return useQuery<CloudRelayPreflight>({
        queryKey: ["cloud-relay-preflight"],
        queryFn: ({ signal }) => fetchJson(API_ENDPOINTS.CLOUD_RELAY_PREFLIGHT, { signal }),
    });
}

/**
 * Hook to update cloud relay settings (e.g. custom_domain).
 */
export function useCloudRelayUpdateSettings() {
    const queryClient = useQueryClient();
    return useMutation<CloudRelayStatus, Error, { custom_domain: string | null }>({
        mutationFn: (settings) =>
            fetchJson(API_ENDPOINTS.CLOUD_RELAY_SETTINGS, {
                method: "PUT",
                body: JSON.stringify(settings),
            }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["cloud-relay-status"] });
        },
    });
}
