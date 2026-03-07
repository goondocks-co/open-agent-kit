import { useQuery } from "@tanstack/react-query";
import { fetchJson, putJson } from "@/lib/api";
import { API_ENDPOINTS } from "@/lib/constants";

export interface LogRotationConfig {
    enabled: boolean;
    max_size_mb: number;
    backup_count: number;
}

export interface SwarmConfig {
    log_level: string;
    log_rotation: LogRotationConfig;
}

interface ConfigUpdateResponse {
    message?: string;
    log_level?: string;
    log_rotation?: LogRotationConfig;
    changed?: boolean;
}

export function useConfig() {
    return useQuery<SwarmConfig>({
        queryKey: ["config"],
        queryFn: ({ signal }) => fetchJson(API_ENDPOINTS.CONFIG, { signal }),
    });
}

export async function updateConfig(data: Partial<{ log_level: string; log_rotation: Partial<LogRotationConfig> }>): Promise<ConfigUpdateResponse> {
    return putJson(API_ENDPOINTS.CONFIG, data);
}

export async function toggleDebugLogging(currentLevel: string): Promise<ConfigUpdateResponse> {
    const newLevel = currentLevel === "DEBUG" ? "INFO" : "DEBUG";
    return updateConfig({ log_level: newLevel });
}

export async function restartDaemon(): Promise<{ status?: string }> {
    return fetchJson(API_ENDPOINTS.RESTART, { method: "POST" });
}
