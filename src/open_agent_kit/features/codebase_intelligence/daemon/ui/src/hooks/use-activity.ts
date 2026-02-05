import { useQuery } from "@tanstack/react-query";
import { fetchJson } from "@/lib/api";
import {
    API_ENDPOINTS,
    getSessionDetailEndpoint,
    PAGINATION,
    DEFAULT_SESSION_SORT,
} from "@/lib/constants";
import type { SessionSortOption } from "@/lib/constants";

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
    first_prompt_preview: string | null;
    prompt_batch_count: number;
    activity_count: number;
    // Session linking fields
    parent_session_id: string | null;
    parent_session_reason: string | null;
    child_session_count: number;
    // Resume command (from agent manifest)
    resume_command: string | null;
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

/** Refetch interval for session lists (5 seconds) */
const SESSION_REFETCH_INTERVAL_MS = 5000;

/** Refetch interval for activity stats (10 seconds) */
const STATS_REFETCH_INTERVAL_MS = 10000;

export function useSessions(
    limit: number = PAGINATION.DEFAULT_LIMIT,
    offset: number = PAGINATION.DEFAULT_OFFSET,
    sort: SessionSortOption = DEFAULT_SESSION_SORT
) {
    return useQuery<SessionListResponse>({
        queryKey: ["sessions", limit, offset, sort],
        queryFn: () => fetchJson(`${API_ENDPOINTS.ACTIVITY_SESSIONS}?limit=${limit}&offset=${offset}&sort=${sort}`),
        refetchInterval: SESSION_REFETCH_INTERVAL_MS,
    });
}

export function useSession(sessionId: string | undefined) {
    return useQuery<SessionDetailResponse>({
        queryKey: ["session", sessionId],
        queryFn: () => fetchJson(getSessionDetailEndpoint(sessionId!)),
        enabled: !!sessionId,
        refetchInterval: SESSION_REFETCH_INTERVAL_MS,
    });
}

export interface ActivityStats {
    total_sessions: number;
    total_activities: number;
    total_prompt_batches: number;
    active_sessions: number;
}

export function useActivityStats() {
    return useQuery<ActivityStats>({
        queryKey: ["activity_stats"],
        queryFn: () => fetchJson(API_ENDPOINTS.ACTIVITY_STATS),
        refetchInterval: STATS_REFETCH_INTERVAL_MS,
    });
}
