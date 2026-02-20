import { fetchJson } from "@/lib/api";
import { API_ENDPOINTS, LOGS_POLL_INTERVAL_MS, LOG_FILES } from "@/lib/constants";
import type { LogFileType } from "@/lib/constants";
import { usePowerQuery } from "./use-power-query";

export interface LogResponse {
    log_file: string | null;
    log_type: string;
    log_type_display: string;
    lines: number;
    content: string;
    available_logs: Array<{ id: string; name: string }>;
}

/** Default number of log lines to fetch */
export const DEFAULT_LOG_LINES = 500;

/** Default log file to display */
export const DEFAULT_LOG_FILE = LOG_FILES.DAEMON;

export function useLogs(lines: number = DEFAULT_LOG_LINES, file: LogFileType = DEFAULT_LOG_FILE, enabled: boolean = true) {
    return usePowerQuery<LogResponse>({
        queryKey: ["logs", lines, file],
        queryFn: ({ signal }) => fetchJson(`${API_ENDPOINTS.LOGS}?lines=${lines}&file=${file}`, { signal }),
        refetchInterval: enabled ? LOGS_POLL_INTERVAL_MS : false,
        pollCategory: "realtime",
    });
}
