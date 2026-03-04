/**
 * Hooks for agent provider configuration.
 *
 * These hooks manage the agent execution provider settings (cloud vs local models).
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchJson } from "@/lib/api";
import { API_ENDPOINTS } from "@/lib/constants";

// =============================================================================
// Type Definitions
// =============================================================================

/** Provider configuration (nested object in API) */
export interface AgentProvider {
    type: string;
    base_url: string | null;
    model: string | null;
    api_format?: string;
    recommended_models?: string[];
}

/** Response from GET /api/agents/settings */
export interface AgentSettingsResponse {
    enabled: boolean;
    max_turns: number;
    timeout_seconds: number;
    provider: AgentProvider;
}

/** Request body for PUT /api/agents/settings */
export interface AgentSettingsUpdateRequest {
    enabled?: boolean;
    max_turns?: number;
    timeout_seconds?: number;
    provider?: {
        type: string;
        base_url?: string | null;
        model?: string | null;
    };
}

export interface TestProviderRequest {
    provider: string;
    base_url: string;
    model?: string;
}

export interface TestProviderResponse {
    success: boolean;
    message?: string;
    error?: string;
    suggestion?: string;
    models_available?: number;
}

export interface ProviderModelsResponse {
    success: boolean;
    models?: Array<{
        name: string;
        size?: number;
        modified_at?: string;
    }>;
    error?: string;
}

// =============================================================================
// Hooks
// =============================================================================

/**
 * Fetch current agent settings.
 */
export function useAgentSettings() {
    return useQuery<AgentSettingsResponse>({
        queryKey: ["agent-settings"],
        queryFn: ({ signal }) => fetchJson(API_ENDPOINTS.AGENT_SETTINGS, { signal }),
    });
}

/**
 * Update agent settings.
 */
export function useUpdateAgentSettings() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (settings: AgentSettingsUpdateRequest) =>
            fetchJson(API_ENDPOINTS.AGENT_SETTINGS, {
                method: "PUT",
                body: JSON.stringify(settings),
            }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["agent-settings"] });
        },
    });
}

// =============================================================================
// API Helpers
// =============================================================================

/**
 * List available models from a provider.
 */
export async function listAgentProviderModels(
    provider: string,
    baseUrl: string
): Promise<ProviderModelsResponse> {
    const params = new URLSearchParams({ provider, base_url: baseUrl });
    return fetchJson(`${API_ENDPOINTS.AGENT_PROVIDER_MODELS}?${params.toString()}`);
}

/**
 * Test provider connection.
 */
export async function testAgentProvider(
    request: TestProviderRequest
): Promise<TestProviderResponse> {
    return fetchJson(API_ENDPOINTS.AGENT_TEST_PROVIDER, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
    });
}
