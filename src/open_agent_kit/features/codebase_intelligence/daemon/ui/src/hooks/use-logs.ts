import { useQuery } from "@tanstack/react-query";
import { fetchJson } from "@/lib/api";

export interface LogResponse {
    log_file: string | null;
    lines: number;
    content: string;
}

export function useLogs(lines: number = 100) {
    return useQuery<LogResponse>({
        queryKey: ["logs", lines],
        queryFn: () => fetchJson(`/api/logs?lines=${lines}`),
        refetchInterval: 3000, // Poll every 3s
    });
}
