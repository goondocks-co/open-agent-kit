import { useQuery } from "@tanstack/react-query";
import { fetchJson } from "@/lib/api";

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

export function useSessions(limit: number = 20, offset: number = 0) {
    return useQuery<SessionListResponse>({
        queryKey: ["sessions", limit, offset],
        queryFn: () => fetchJson(`/api/activity/sessions?limit=${limit}&offset=${offset}`),
        refetchInterval: 5000,
    });
}

export function useSession(sessionId: string | undefined) {
    return useQuery<SessionDetailResponse>({
        queryKey: ["session", sessionId],
        queryFn: () => fetchJson(`/api/activity/sessions/${sessionId}`),
        enabled: !!sessionId,
        refetchInterval: 5000,
    });
}

export function useActivityStats() {
    return useQuery<any>({
        queryKey: ["activity_stats"],
        queryFn: () => fetchJson(`/api/activity/stats`),
        refetchInterval: 10000,
    })
}
