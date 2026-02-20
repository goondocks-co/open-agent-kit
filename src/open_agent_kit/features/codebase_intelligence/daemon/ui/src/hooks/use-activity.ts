import { useQuery } from "@tanstack/react-query";
import { fetchJson } from "@/lib/api";
import {
    API_ENDPOINTS,
    getSessionDetailEndpoint,
    PAGINATION,
    DEFAULT_SESSION_SORT,
} from "@/lib/constants";
import type { SessionSortOption } from "@/lib/constants";
import { usePowerQuery } from "./use-power-query";

export interface ActivityItem {
    id: string;
    session_id: string;
    prompt_batch_id: string | null;
    tool_name: string;
    tool_input: Record<string, unknown> | null;
    tool_output_summary: string | null;
    file_path: string | null;
    success: boolean;
    error_message: string | null;
    created_at: string;
}

export interface SessionItem {
    id: string;
    agent: string;
    project_root: string | null;
    started_at: string;
    ended_at: string | null;
    status: string;
    summary: string | null;
    title: string | null;
    title_manually_edited?: boolean;
    first_prompt_preview: string | null;
    prompt_batch_count: number;
    activity_count: number;
    // Session linking fields
    parent_session_id: string | null;
    parent_session_reason: string | null;
    child_session_count: number;
    // Resume command (from agent manifest)
    resume_command: string | null;
    // Summary embedding status
    summary_embedded: boolean;
}

export interface PromptBatchItem {
    id: string;
    session_id: string;
    prompt_number: number;
    user_prompt: string | null;
    classification: string | null;
    source_type: string;  // user, agent_notification, plan, system
    plan_file_path: string | null;  // Path to plan file (for source_type='plan')
    plan_content: string | null;  // Full plan content (stored for self-contained CI)
    started_at: string;
    ended_at: string | null;
    activity_count: number;
    response_summary: string | null;  // Agent's final response (v21)
}

export interface SessionStats {
    total_activities: number;
    total_prompt_batches: number;
    tools_used: Record<string, number>;
    files_touched: string[];
}

export interface SessionDetailResponse {
    session: SessionItem;
    stats: SessionStats;
    recent_activities: ActivityItem[];
    prompt_batches: PromptBatchItem[];
}

export interface SessionListResponse {
    sessions: SessionItem[];
    total: number;
    limit: number;
    offset: number;
}

export interface SessionAgentsResponse {
    agents: string[];
}

/** Refetch interval for session lists (30 seconds) */
const SESSION_REFETCH_INTERVAL_MS = 30000;

/** Refetch interval for activity stats (60 seconds) */
const STATS_REFETCH_INTERVAL_MS = 60000;

export function useSessions(
    limit: number = PAGINATION.DEFAULT_LIMIT,
    offset: number = PAGINATION.DEFAULT_OFFSET,
    sort: SessionSortOption = DEFAULT_SESSION_SORT,
    agent?: string
) {
    const params = new URLSearchParams();
    params.set("limit", String(limit));
    params.set("offset", String(offset));
    params.set("sort", sort);
    if (agent) {
        params.set("agent", agent);
    }

    return usePowerQuery<SessionListResponse>({
        queryKey: ["sessions", limit, offset, sort, agent],
        queryFn: ({ signal }) => fetchJson(`${API_ENDPOINTS.ACTIVITY_SESSIONS}?${params.toString()}`, { signal }),
        refetchInterval: SESSION_REFETCH_INTERVAL_MS,
        pollCategory: "standard",
    });
}

export function useSession(sessionId: string | undefined) {
    return usePowerQuery<SessionDetailResponse>({
        queryKey: ["session", sessionId],
        queryFn: ({ signal }) => fetchJson(getSessionDetailEndpoint(sessionId!), { signal }),
        enabled: !!sessionId,
        refetchInterval: SESSION_REFETCH_INTERVAL_MS,
        pollCategory: "standard",
    });
}

export function useSessionAgents() {
    return useQuery<SessionAgentsResponse>({
        queryKey: ["session-agents"],
        queryFn: ({ signal }) => fetchJson(API_ENDPOINTS.ACTIVITY_SESSION_AGENTS, { signal }),
    });
}

export interface ActivityStats {
    total_sessions: number;
    total_activities: number;
    total_prompt_batches: number;
    active_sessions: number;
}

export function useActivityStats() {
    return usePowerQuery<ActivityStats>({
        queryKey: ["activity_stats"],
        queryFn: ({ signal }) => fetchJson(API_ENDPOINTS.ACTIVITY_STATS, { signal }),
        refetchInterval: STATS_REFETCH_INTERVAL_MS,
        pollCategory: "standard",
    });
}
