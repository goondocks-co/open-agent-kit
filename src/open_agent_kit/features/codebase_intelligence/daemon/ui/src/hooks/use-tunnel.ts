/**
 * React Query hooks for tunnel sharing operations.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchJson } from "@/lib/api";
import { API_ENDPOINTS } from "@/lib/constants";
import { usePowerQuery } from "./use-power-query";

/** Tunnel status response from API */
export interface TunnelStatus {
    active: boolean;
    public_url: string | null;
    provider: string | null;
    started_at: string | null;
    error: string | null;
}

/** Tunnel start response */
interface TunnelStartResponse {
    status: string;
    active: boolean;
    public_url: string | null;
    provider: string | null;
    started_at: string | null;
    error: string | null;
}

/** Tunnel stop response */
interface TunnelStopResponse {
    status: string;
}

/** Polling interval for tunnel status (30 seconds) */
const TUNNEL_STATUS_REFETCH_INTERVAL_MS = 30000;

/**
 * Hook to get current tunnel status.
 */
export function useTunnelStatus() {
    return usePowerQuery<TunnelStatus>({
        queryKey: ["tunnel-status"],
        queryFn: ({ signal }) => fetchJson(API_ENDPOINTS.TUNNEL_STATUS, { signal }),
        refetchInterval: TUNNEL_STATUS_REFETCH_INTERVAL_MS,
        pollCategory: "standard",
    });
}

/**
 * Hook to start a tunnel.
 */
export function useTunnelStart() {
    const queryClient = useQueryClient();
    return useMutation<TunnelStartResponse, Error, void>({
        mutationFn: () =>
            fetchJson(API_ENDPOINTS.TUNNEL_START, {
                method: "POST",
            }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["tunnel-status"] });
            queryClient.invalidateQueries({ queryKey: ["status"] });
        },
    });
}

/**
 * Hook to stop a tunnel.
 */
export function useTunnelStop() {
    const queryClient = useQueryClient();
    return useMutation<TunnelStopResponse, Error, void>({
        mutationFn: () =>
            fetchJson(API_ENDPOINTS.TUNNEL_STOP, {
                method: "POST",
            }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["tunnel-status"] });
            queryClient.invalidateQueries({ queryKey: ["status"] });
        },
    });
}
