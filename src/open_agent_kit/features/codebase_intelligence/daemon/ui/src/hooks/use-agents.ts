/**
 * React hooks for agent data fetching and mutations.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchJson, postJson } from "@/lib/api";
import { API_ENDPOINTS } from "@/lib/constants";

// =============================================================================
// Types
// =============================================================================

/** Agent list item from the API */
export interface AgentItem {
    name: string;
    display_name: string;
    description: string;
    max_turns: number;
    timeout_seconds: number;
}

/** Agent list response */
export interface AgentListResponse {
    agents: AgentItem[];
    total: number;
}

/** Agent detail with full definition */
export interface AgentDetail {
    agent: {
        name: string;
        display_name: string;
        description: string;
        system_prompt?: string;
        allowed_tools: string[];
        disallowed_tools: string[];
        allowed_paths: string[];
        disallowed_paths: string[];
        execution: {
            max_turns: number;
            timeout_seconds: number;
            permission_mode: string;
        };
        ci_access: {
            code_search: boolean;
            memory_search: boolean;
            session_history: boolean;
            project_stats: boolean;
        };
    };
    recent_runs: AgentRun[];
}

/** Agent run status */
export type AgentRunStatus = "pending" | "running" | "completed" | "failed" | "cancelled" | "timeout";

/** Agent run record */
export interface AgentRun {
    id: string;
    agent_name: string;
    task: string;
    status: AgentRunStatus;
    result?: string;
    error?: string;
    turns_used: number;
    cost_usd?: number;
    files_created: string[];
    files_modified: string[];
    files_deleted: string[];
    created_at: string;
    started_at?: string;
    completed_at?: string;
    duration_seconds?: number;
}

/** Agent run list response */
export interface AgentRunListResponse {
    runs: AgentRun[];
    total: number;
    limit: number;
    offset: number;
}

/** Agent run request */
export interface AgentRunRequest {
    task: string;
    context?: Record<string, unknown>;
}

/** Agent run response */
export interface AgentRunResponse {
    run_id: string;
    status: AgentRunStatus;
    message: string;
}

// =============================================================================
// Hooks
// =============================================================================

/** Fetch list of available agents */
export function useAgents() {
    return useQuery({
        queryKey: ["agents"],
        queryFn: () => fetchJson<AgentListResponse>(API_ENDPOINTS.AGENTS),
        refetchInterval: 10000, // Refresh every 10 seconds
    });
}

/** Fetch agent detail by name */
export function useAgentDetail(agentName: string | null) {
    return useQuery({
        queryKey: ["agents", agentName],
        queryFn: () => fetchJson<AgentDetail>(`${API_ENDPOINTS.AGENTS}/${agentName}`),
        enabled: !!agentName,
        refetchInterval: 5000, // Refresh every 5 seconds to get run updates
    });
}

/** Fetch list of agent runs */
export function useAgentRuns(limit = 20, offset = 0, agentName?: string, status?: AgentRunStatus) {
    const params = new URLSearchParams();
    params.set("limit", String(limit));
    params.set("offset", String(offset));
    if (agentName) params.set("agent_name", agentName);
    if (status) params.set("status", status);

    return useQuery({
        queryKey: ["agent-runs", limit, offset, agentName, status],
        queryFn: () => fetchJson<AgentRunListResponse>(`${API_ENDPOINTS.AGENT_RUNS}?${params}`),
        refetchInterval: 3000, // Refresh every 3 seconds for active monitoring
    });
}

/** Fetch single agent run by ID */
export function useAgentRun(runId: string | null) {
    return useQuery({
        queryKey: ["agent-runs", runId],
        queryFn: () => fetchJson<{ run: AgentRun }>(`${API_ENDPOINTS.AGENT_RUNS}/${runId}`),
        enabled: !!runId,
        refetchInterval: 2000, // Faster refresh for active run monitoring
    });
}

/** Trigger an agent run */
export function useRunAgent() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ agentName, task }: { agentName: string; task: string }) =>
            postJson<AgentRunResponse>(`${API_ENDPOINTS.AGENTS}/${agentName}/run`, { task }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["agents"] });
            queryClient.invalidateQueries({ queryKey: ["agent-runs"] });
        },
    });
}

/** Cancel a running agent */
export function useCancelAgentRun() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (runId: string) =>
            postJson<{ success: boolean; message: string }>(`${API_ENDPOINTS.AGENT_RUNS}/${runId}/cancel`, {}),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["agent-runs"] });
        },
    });
}

/** Reload agent definitions */
export function useReloadAgents() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: () => postJson<{ success: boolean; message: string; agents: string[] }>(
            `${API_ENDPOINTS.AGENTS}/reload`,
            {}
        ),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["agents"] });
        },
    });
}
