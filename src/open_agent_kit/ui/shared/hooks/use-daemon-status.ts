/**
 * Generic daemon health/status polling hook.
 *
 * Usage:
 * ```ts
 * const { data, isLoading, error } = useDaemonStatus(fetchJson, "/api/health");
 * ```
 */

import { usePowerQuery } from "./use-power-query";

const DEFAULT_POLL_MS = 10_000;

interface DaemonStatusOptions<T> {
    /** Fetch function bound to the app's API client */
    fetchFn: (endpoint: string, options?: RequestInit) => Promise<T>;
    /** Health/status endpoint path */
    endpoint: string;
    /** Polling interval in ms (default: 10000) */
    pollMs?: number;
    /** React Query key prefix (default: ["daemon", "status"]) */
    queryKey?: string[];
}

export function useDaemonStatus<T = { status: string }>({
    fetchFn,
    endpoint,
    pollMs = DEFAULT_POLL_MS,
    queryKey = ["daemon", "status"],
}: DaemonStatusOptions<T>) {
    return usePowerQuery<T>({
        queryKey,
        queryFn: ({ signal }) => fetchFn(endpoint, { signal }),
        refetchInterval: pollMs,
        pollCategory: "heartbeat",
    });
}
