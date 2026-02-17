/**
 * React hooks for agent data fetching and mutations.
 *
 * Agent Architecture:
 * - Templates: Define capabilities (tools, permissions, system prompt)
 * - Tasks: Define what to do (default_task, maintained_files, ci_queries)
 * - Only tasks can be run directly - templates create tasks
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchJson, postJson, deleteJson } from "@/lib/api";
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

/** Agent task - runnable with pre-configured task */
export interface AgentTask {
    name: string;
    display_name: string;
    agent_type: string;  // Template reference
    description: string;
    default_task: string;
    max_turns: number;
    timeout_seconds: number;
    /** True if task has custom execution config (overrides template defaults) */
    has_execution_override: boolean;
    /** True if this is a built-in task shipped with OAK */
    is_builtin: boolean;
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
    tasks: AgentTask[];
    /** Directory where task YAML files are stored */
    tasks_dir: string;
    // Legacy fields
    agents: AgentItem[];
    total: number;
}

/** Request to create a new task */
export interface CreateTaskRequest {
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
        /** Project-specific config from oak/agents/{name}.yaml */
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
    warnings: string[];
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
        queryFn: ({ signal }) => fetchJson<AgentListResponse>(API_ENDPOINTS.AGENTS, { signal }),
        staleTime: 60000, // Consider data fresh for 60 seconds (agents rarely change)
        gcTime: 300000, // Keep in cache for 5 minutes
    });
}

/** Fetch agent detail by name */
export function useAgentDetail(agentName: string | null) {
    return useQuery({
        queryKey: ["agents", agentName],
        queryFn: ({ signal }) => fetchJson<AgentDetail>(`${API_ENDPOINTS.AGENTS}/${agentName}`, { signal }),
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
        queryFn: ({ signal }) => fetchJson<AgentRunListResponse>(`${API_ENDPOINTS.AGENT_RUNS}?${params}`, { signal }),
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
        queryFn: ({ signal }) => fetchJson<{ run: AgentRun }>(`${API_ENDPOINTS.AGENT_RUNS}/${runId}`, { signal }),
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

/** Trigger an agent run (legacy - prefer useRunTask) */
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

/** Run a task with optional runtime direction (additional_prompt) */
export function useRunTask() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ taskName, additionalPrompt }: { taskName: string; additionalPrompt?: string }) => {
            const body: { additional_prompt?: string } = {};
            if (additionalPrompt?.trim()) {
                body.additional_prompt = additionalPrompt.trim();
            }
            return postJson<AgentRunResponse>(`${API_ENDPOINTS.AGENTS}/tasks/${taskName}/run`, body);
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["agents"] });
            queryClient.invalidateQueries({ queryKey: ["agent-runs"] });
        },
    });
}

/** Create a new task from a template */
export function useCreateTask() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ templateName, ...data }: CreateTaskRequest & { templateName: string }) =>
            postJson<{ success: boolean; message: string; task: { name: string; display_name: string; agent_type: string; task_path: string } }>(
                `${API_ENDPOINTS.AGENTS}/templates/${templateName}/create-task`,
                data
            ),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["agents"] });
        },
    });
}

/** Copy a task (typically a built-in) for customization */
export function useCopyTask() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: ({ taskName, newName }: { taskName: string; newName?: string }) => {
            const params = newName ? `?new_name=${encodeURIComponent(newName)}` : "";
            return postJson<{ success: boolean; message: string; task: { name: string; display_name: string; agent_type: string; task_path: string; is_builtin: boolean } }>(
                `${API_ENDPOINTS.AGENTS}/tasks/${taskName}/copy${params}`,
                {}
            );
        },
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

/** Delete an agent run */
export function useDeleteAgentRun() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (runId: string) =>
            deleteJson<{ success: boolean; message: string; deleted: string }>(
                `${API_ENDPOINTS.AGENT_RUNS}/${runId}`
            ),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["agent-runs"] });
        },
    });
}

/** Bulk delete agent runs with optional filters */
export function useBulkDeleteAgentRuns() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (params: {
            agentName?: string;
            status?: string;
            before?: string;  // ISO date string
            keepRecent?: number;
        }) => {
            const searchParams = new URLSearchParams();
            if (params.agentName) searchParams.set("agent_name", params.agentName);
            if (params.status) searchParams.set("status", params.status);
            if (params.before) searchParams.set("before", params.before);
            if (params.keepRecent !== undefined) searchParams.set("keep_recent", String(params.keepRecent));

            const query = searchParams.toString();
            return deleteJson<{ success: boolean; message: string; deleted_count: number }>(
                `${API_ENDPOINTS.AGENT_RUNS}${query ? `?${query}` : ""}`
            );
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["agent-runs"] });
        },
    });
}
