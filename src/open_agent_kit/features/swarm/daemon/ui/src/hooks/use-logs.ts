import { usePowerQuery } from "@oak/ui/hooks/use-power-query";
import { fetchJson } from "@/lib/api";
import { API_ENDPOINTS, LOGS_POLL_MS } from "@/lib/constants";

interface LogsResponse {
    lines: string[];
    path: string | null;
    total_lines?: number;
    error?: string;
}

export function useLogs(lines: number = 500, enabled: boolean = true) {
    return usePowerQuery<LogsResponse>({
        queryKey: ["logs", lines],
        queryFn: ({ signal }) => fetchJson(`${API_ENDPOINTS.LOGS}?lines=${lines}`, { signal }),
        refetchInterval: enabled ? LOGS_POLL_MS : false,
        pollCategory: "realtime",
    });
}
