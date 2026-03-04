/**
 * React Query hooks for ACP server management.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchJson } from "@/lib/api";
import { API_ENDPOINTS } from "@/lib/constants";
import { usePowerQuery } from "@oak/ui/hooks/use-power-query";

/** ACP server status response */
export interface AcpStatus {
    running: boolean;
    pid: number | null;
    transport: string | null;
}

/** ACP logs response */
export interface AcpLogs {
    lines: string[];
    log_file: string;
}

const ACP_STATUS_REFETCH_INTERVAL_MS = 10000;

export function useAcpStatus() {
    return usePowerQuery<AcpStatus>({
        queryKey: ["acp-status"],
        queryFn: ({ signal }) => fetchJson(API_ENDPOINTS.ACP_STATUS, { signal }),
        refetchInterval: ACP_STATUS_REFETCH_INTERVAL_MS,
        pollCategory: "standard",
    });
}

export function useAcpStart() {
    const queryClient = useQueryClient();
    return useMutation<{ status: string }, Error, void>({
        mutationFn: () => fetchJson(API_ENDPOINTS.ACP_START, { method: "POST" }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["acp-status"] });
        },
    });
}

export function useAcpStop() {
    const queryClient = useQueryClient();
    return useMutation<{ status: string }, Error, void>({
        mutationFn: () => fetchJson(API_ENDPOINTS.ACP_STOP, { method: "POST" }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["acp-status"] });
        },
    });
}

export function useAcpLogs(lines: number = 100) {
    return useQuery<AcpLogs>({
        queryKey: ["acp-logs", lines],
        queryFn: ({ signal }) => fetchJson(`${API_ENDPOINTS.ACP_LOGS}?lines=${lines}`, { signal }),
        refetchInterval: 5000,
    });
}
