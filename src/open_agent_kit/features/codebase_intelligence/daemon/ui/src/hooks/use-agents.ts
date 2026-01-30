/**
 * React hooks for agent data fetching and mutations.
 *
 * Agent Architecture:
 * - Templates: Define capabilities (tools, permissions, system prompt)
 * - Instances: Define tasks (default_task, maintained_files, ci_queries)
 * - Only instances can be run directly - templates create instances
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchJson, postJson } from "@/lib/api";
import { API_ENDPOINTS } from "@/lib/constants";

// =============================================================================
// Types
// =============================================================================

/** Agent template - defines capabilities, cannot be run directly */
export interface AgentTemplate {
    name: string;
    display_name: string;
    description: string;
    max_turns: number;
    timeout_seconds: number;
}

/** Agent instance - runnable with pre-configured task */
export interface AgentInstance {
    name: string;
    display_name: string;
    agent_type: string;  // Template reference
    description: string;
    default_task: string;
    max_turns: number;
    timeout_seconds: number;
}

/** Agent list item from the API (legacy) */
export interface AgentItem {
    name: string;
    display_name: string;
    description: string;
    max_turns: number;
    timeout_seconds: number;
    /** Project-specific config from agent config directory */
    project_config?: Record<string, unknown>;
}

/** Agent list response */
export interface AgentListResponse {
    templates: AgentTemplate[];
    instances: AgentInstance[];
    /** Directory where instance YAML files are stored */
    instances_dir: string;
    // Legacy fields
    agents: AgentItem[];
    total: number;
}

/** Request to create a new instance */
export interface CreateInstanceRequest {
    name: string;
    display_name: string;
    description: string;
    default_task: string;
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
        /** Project-specific config from oak/ci/agents/{name}.yaml */
        project_config?: Record<string, unknown>;
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
        staleTime: 60000, // Consider data fresh for 60 seconds (agents rarely change)
        gcTime: 300000, // Keep in cache for 5 minutes
    });
}

/** Fetch agent detail by name */
export function useAgentDetail(agentName: string | null) {
    return useQuery({
        queryKey: ["agents", agentName],
        queryFn: () => fetchJson<AgentDetail>(`${API_ENDPOINTS.AGENTS}/${agentName}`),
        enabled: !!agentName,
        staleTime: 10000, // Consider data fresh for 10 seconds
    });
}

/** Fetch list of agent runs with smart polling */
export function useAgentRuns(limit = 20, offset = 0, agentName?: string, status?: AgentRunStatus) {
    const params = new URLSearchParams();
    params.set("limit", String(limit));
    params.set("offset", String(offset));
    if (agentName) params.set("agent_name", agentName);
    if (status) params.set("status", status);

    const query = useQuery({
        queryKey: ["agent-runs", limit, offset, agentName, status],
        queryFn: () => fetchJson<AgentRunListResponse>(`${API_ENDPOINTS.AGENT_RUNS}?${params}`),
        staleTime: 5000, // Consider data fresh for 5 seconds
        placeholderData: (previousData) => previousData, // Keep showing previous data while loading
        // Smart polling: only poll when there are active runs
        refetchInterval: (query) => {
            const data = query.state.data;
            if (!data) return false;
            const hasActiveRuns = data.runs.some(
                (run) => run.status === "pending" || run.status === "running"
            );
            return hasActiveRuns ? 3000 : false; // Poll only when active runs exist
        },
    });

    return query;
}

/** Fetch single agent run by ID with smart polling */
export function useAgentRun(runId: string | null) {
    return useQuery({
        queryKey: ["agent-runs", runId],
        queryFn: () => fetchJson<{ run: AgentRun }>(`${API_ENDPOINTS.AGENT_RUNS}/${runId}`),
        enabled: !!runId,
        staleTime: 2000,
        // Smart polling: only poll when run is active
        refetchInterval: (query) => {
            const run = query.state.data?.run;
            if (!run) return false;
            const isActive = run.status === "pending" || run.status === "running";
            return isActive ? 2000 : false;
        },
    });
}

/** Trigger an agent run (legacy - prefer useRunInstance) */
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

/** Run an instance (no task input - uses configured default_task) */
export function useRunInstance() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (instanceName: string) =>
            postJson<AgentRunResponse>(`${API_ENDPOINTS.AGENTS}/instances/${instanceName}/run`, {}),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["agents"] });
            queryClient.invalidateQueries({ queryKey: ["agent-runs"] });
        },
    });
}

/** Create a new instance from a template */
export function useCreateInstance() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ templateName, ...data }: CreateInstanceRequest & { templateName: string }) =>
            postJson<{ success: boolean; message: string; instance: { name: string; display_name: string; agent_type: string; instance_path: string } }>(
                `${API_ENDPOINTS.AGENTS}/templates/${templateName}/create-instance`,
                data
            ),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["agents"] });
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
