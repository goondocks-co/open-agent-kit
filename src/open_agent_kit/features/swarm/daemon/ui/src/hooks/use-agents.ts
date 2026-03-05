import { usePowerQuery } from "@oak/ui/hooks/use-power-query";
import { fetchJson, postJson } from "@/lib/api";
import { API_ENDPOINTS, AGENTS_POLL_MS, AGENT_RUNS_POLL_MS } from "@/lib/constants";
import { useMutation, useQueryClient } from "@tanstack/react-query";

// --- Types ---

interface AgentTemplateListItem {
    name: string;
    display_name: string;
    description: string;
    max_turns: number;
    timeout_seconds: number;
}

interface AgentTaskListItem {
    name: string;
    display_name: string;
    agent_type: string;
    description: string;
    default_task: string;
    max_turns: number;
    timeout_seconds: number;
    has_execution_override: boolean;
    is_builtin: boolean;
}

interface AgentListResponse {
    templates: AgentTemplateListItem[];
    tasks: AgentTaskListItem[];
    total: number;
}

interface AgentRun {
    id: string;
    agent_name: string;
    task_name?: string;
    task: string;
    status: string;
    created_at: string;
    completed_at?: string;
    turns_used?: number;
    error?: string;
    cost_usd?: number;
}

interface AgentRunListResponse {
    runs: AgentRun[];
    total: number;
    limit: number;
    offset: number;
}

interface AgentRunResponse {
    run_id: string;
    status: string;
    message: string;
}

// --- Hooks ---

export function useAgents() {
    return usePowerQuery<AgentListResponse>({
        queryKey: ["agents"],
        queryFn: ({ signal }) => fetchJson(API_ENDPOINTS.AGENTS, { signal }),
        refetchInterval: AGENTS_POLL_MS,
        pollCategory: "standard",
    });
}

export function useAgentRuns(limit = 20) {
    return usePowerQuery<AgentRunListResponse>({
        queryKey: ["agent-runs", limit],
        queryFn: ({ signal }) =>
            fetchJson(`${API_ENDPOINTS.AGENTS_RUNS}?limit=${limit}`, { signal }),
        refetchInterval: AGENT_RUNS_POLL_MS,
        pollCategory: "standard",
    });
}

export function useRunTask() {
    const queryClient = useQueryClient();

    return useMutation<AgentRunResponse, Error, { taskName: string; additionalPrompt?: string }>({
        mutationFn: async ({ taskName, additionalPrompt }) => {
            const url = API_ENDPOINTS.AGENTS_TASK_RUN.replace(":taskName", taskName);
            const body = additionalPrompt ? { additional_prompt: additionalPrompt } : {};
            return postJson<AgentRunResponse>(url, body);
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["agent-runs"] });
        },
    });
}

export function useReloadAgents() {
    const queryClient = useQueryClient();

    return useMutation<{ success: boolean; message: string; agents: string[] }, Error, void>({
        mutationFn: () => postJson(API_ENDPOINTS.AGENTS_RELOAD, {}),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["agents"] });
        },
    });
}

export type {
    AgentTemplateListItem,
    AgentTaskListItem,
    AgentListResponse,
    AgentRun,
    AgentRunListResponse,
    AgentRunResponse,
};
