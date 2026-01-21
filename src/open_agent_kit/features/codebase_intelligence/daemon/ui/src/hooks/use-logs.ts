import { useQuery } from "@tanstack/react-query";
import { fetchJson } from "@/lib/api";
import { API_ENDPOINTS, LOGS_POLL_INTERVAL_MS } from "@/lib/constants";

export interface LogResponse {
    log_file: string | null;
    lines: number;
    content: string;
}

/** Default number of log lines to fetch */
const DEFAULT_LOG_LINES = 100;

export function useLogs(lines: number = DEFAULT_LOG_LINES) {
    return useQuery<LogResponse>({
        queryKey: ["logs", lines],
        queryFn: () => fetchJson(`${API_ENDPOINTS.LOGS}?lines=${lines}`),
        refetchInterval: LOGS_POLL_INTERVAL_MS,
    });
}
