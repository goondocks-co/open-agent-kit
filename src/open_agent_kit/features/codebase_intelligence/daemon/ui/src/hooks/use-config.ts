import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchJson } from "@/lib/api";
import {
    API_ENDPOINTS,
    LOG_LEVELS,
} from "@/lib/constants";

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
        queryFn: () => fetchJson(API_ENDPOINTS.CONFIG),
    });
}

// Discovery API helpers
export async function listProviderModels(provider: string, baseUrl: string, apiKey?: string) {
    const params = new URLSearchParams({ provider, base_url: baseUrl });
    if (apiKey) params.append("api_key", apiKey);
    return fetchJson(`${API_ENDPOINTS.PROVIDERS_MODELS}?${params.toString()}`);
}

export async function listSummarizationModels(provider: string, baseUrl: string, apiKey?: string) {
    const params = new URLSearchParams({ provider, base_url: baseUrl });
    if (apiKey) params.append("api_key", apiKey);
    return fetchJson(`${API_ENDPOINTS.PROVIDERS_SUMMARIZATION_MODELS}?${params.toString()}`);
}

export interface TestConfigRequest {
    provider: string;
    base_url: string;
    model: string;
    api_key?: string;
}

export interface TestConfigResponse {
    success: boolean;
    message?: string;
    error?: string;
    suggestion?: string;
    dimensions?: number;
    context_window?: number;
    pending_load?: boolean;
}

export async function testEmbeddingConfig(config: TestConfigRequest): Promise<TestConfigResponse> {
    return fetchJson(API_ENDPOINTS.CONFIG_TEST, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
    });
}

export async function testSummarizationConfig(config: TestConfigRequest): Promise<TestConfigResponse> {
    return fetchJson(API_ENDPOINTS.CONFIG_TEST_SUMMARIZATION, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
    });
}

export function useUpdateConfig() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (newConfig: Partial<Config>) =>
            fetchJson(API_ENDPOINTS.CONFIG, {
                method: "PUT",
                body: JSON.stringify(newConfig),
            }),
        onSuccess: (data) => {
            queryClient.invalidateQueries({ queryKey: ["config"] });
            return data;
        },
    });
}

export interface ConfigUpdateResponse {
    message?: string;
    log_level?: string;
}

export interface RestartResponse {
    message?: string;
    indexing_started?: boolean;
}

// Toggle debug logging
export async function toggleDebugLogging(currentLevel: string): Promise<ConfigUpdateResponse> {
    const newLevel = currentLevel === LOG_LEVELS.DEBUG ? LOG_LEVELS.INFO : LOG_LEVELS.DEBUG;
    return fetchJson(API_ENDPOINTS.CONFIG, {
        method: "PUT",
        body: JSON.stringify({ log_level: newLevel }),
    });
}

// Restart daemon to apply config changes
export async function restartDaemon(): Promise<RestartResponse> {
    return fetchJson(API_ENDPOINTS.RESTART, {
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
        queryFn: () => fetchJson(API_ENDPOINTS.CONFIG_EXCLUSIONS),
    });
}

export function useUpdateExclusions() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (data: { add?: string[]; remove?: string[] }) =>
            fetchJson(API_ENDPOINTS.CONFIG_EXCLUSIONS, {
                method: "PUT",
                body: JSON.stringify(data),
            }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["exclusions"] });
        },
    });
}

export interface ResetExclusionsResponse {
    message?: string;
    patterns?: string[];
}

export async function resetExclusions(): Promise<ResetExclusionsResponse> {
    return fetchJson(API_ENDPOINTS.CONFIG_EXCLUSIONS_RESET, {
        method: "POST",
    });
}
