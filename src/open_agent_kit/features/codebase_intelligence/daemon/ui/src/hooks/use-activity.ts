import { useQuery } from "@tanstack/react-query";
import { fetchJson } from "@/lib/api";
import {
    API_ENDPOINTS,
    getSessionDetailEndpoint,
    PAGINATION,
} from "@/lib/constants";

export interface ActivityItem {
    id: string;
    session_id: string;
    prompt_batch_id: string | null;
    tool_name: string;
    tool_input: any;
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
    prompt_batch_count: number;
    activity_count: number;
}

export interface PromptBatchItem {
    id: string;
    session_id: string;
    prompt_number: number;
    user_prompt: string | null;
    classification: string | null;
    started_at: string;
    ended_at: string | null;
    activity_count: number;
}

export interface SessionDetailResponse {
    session: SessionItem;
    stats: any;
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

export function useSessions(limit: number = PAGINATION.DEFAULT_LIMIT, offset: number = PAGINATION.DEFAULT_OFFSET) {
    return useQuery<SessionListResponse>({
        queryKey: ["sessions", limit, offset],
        queryFn: () => fetchJson(`${API_ENDPOINTS.ACTIVITY_SESSIONS}?limit=${limit}&offset=${offset}`),
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

export function useActivityStats() {
    return useQuery<any>({
        queryKey: ["activity_stats"],
        queryFn: () => fetchJson(API_ENDPOINTS.ACTIVITY_STATS),
        refetchInterval: STATS_REFETCH_INTERVAL_MS,
    });
}
