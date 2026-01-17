import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchJson } from "@/lib/api";

export interface Config {
    embedding: {
        provider: string;
        model: string;
        base_url: string;
        dimensions: number | null;
        max_chunk_chars: number | null;
        context_tokens: number | null;
    };
    summarization: {
        enabled: boolean;
        provider: string;
        model: string;
        base_url: string;
        context_tokens: number | null;
    };
    log_level: string;
}

export function useConfig() {
    return useQuery<Config>({
        queryKey: ["config"],
        queryFn: () => fetchJson("/api/config"),
    });
}

// Discovery API helpers
export async function listProviderModels(provider: string, baseUrl: string, apiKey?: string) {
    const params = new URLSearchParams({ provider, base_url: baseUrl });
    if (apiKey) params.append("api_key", apiKey);
    return fetchJson(`/api/providers/models?${params.toString()}`);
}

export async function listSummarizationModels(provider: string, baseUrl: string, apiKey?: string) {
    const params = new URLSearchParams({ provider, base_url: baseUrl });
    if (apiKey) params.append("api_key", apiKey);
    return fetchJson(`/api/providers/summarization-models?${params.toString()}`);
}

export async function testEmbeddingConfig(config: any) {
    return fetchJson("/api/config/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
    });
}

export async function testSummarizationConfig(config: any) {
    return fetchJson("/api/config/test-summarization", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
    });
}

export function useUpdateConfig() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (newConfig: Partial<Config>) =>
            fetchJson("/api/config", {
                method: "PUT",
                body: JSON.stringify(newConfig),
            }),
        onSuccess: (data) => {
            queryClient.invalidateQueries({ queryKey: ["config"] });
            return data;
        },
    });
}

// Toggle debug logging
export async function toggleDebugLogging(currentLevel: string): Promise<any> {
    const newLevel = currentLevel === "DEBUG" ? "INFO" : "DEBUG";
    return fetchJson("/api/config", {
        method: "PUT",
        body: JSON.stringify({ log_level: newLevel }),
    });
}

// Restart daemon to apply config changes
export async function restartDaemon(): Promise<any> {
    return fetchJson("/api/restart", {
        method: "POST",
    });
}

// =============================================================================
// Exclusions API
// =============================================================================

export interface ExclusionsResponse {
    user_patterns: string[];
    default_patterns: string[];
    all_patterns: string[];
}

export function useExclusions() {
    return useQuery<ExclusionsResponse>({
        queryKey: ["exclusions"],
        queryFn: () => fetchJson("/api/config/exclusions"),
    });
}

export function useUpdateExclusions() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (data: { add?: string[]; remove?: string[] }) =>
            fetchJson("/api/config/exclusions", {
                method: "PUT",
                body: JSON.stringify(data),
            }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["exclusions"] });
        },
    });
}

export async function resetExclusions(): Promise<any> {
    return fetchJson("/api/config/exclusions/reset", {
        method: "POST",
    });
}
