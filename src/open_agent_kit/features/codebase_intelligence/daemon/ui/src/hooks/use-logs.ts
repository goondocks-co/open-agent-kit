import { useQuery } from "@tanstack/react-query";
import { fetchJson } from "@/lib/api";
import { API_ENDPOINTS, LOGS_POLL_INTERVAL_MS, LOG_FILES } from "@/lib/constants";
import type { LogFileType } from "@/lib/constants";

export interface LogResponse {
    log_file: string | null;
    log_type: string;
    log_type_display: string;
    lines: number;
    content: string;
    available_logs: Array<{ id: string; name: string }>;
}

/** Default number of log lines to fetch */
export const DEFAULT_LOG_LINES = 100;

/** Default log file to display */
export const DEFAULT_LOG_FILE = LOG_FILES.DAEMON;

export function useLogs(lines: number = DEFAULT_LOG_LINES, file: LogFileType = DEFAULT_LOG_FILE) {
    return useQuery<LogResponse>({
        queryKey: ["logs", lines, file],
        queryFn: () => fetchJson(`${API_ENDPOINTS.LOGS}?lines=${lines}&file=${file}`),
        refetchInterval: LOGS_POLL_INTERVAL_MS,
    });
}
