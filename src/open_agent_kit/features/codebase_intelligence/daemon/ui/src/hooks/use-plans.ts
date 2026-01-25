import { useQuery } from "@tanstack/react-query";
import { fetchJson } from "@/lib/api";
import { API_ENDPOINTS } from "@/lib/constants";

export interface PlanListItem {
    id: number;
    title: string;
    session_id: string;
    created_at: string;
    file_path: string | null;
    preview: string;
    plan_embedded: boolean;
}

export interface PlansListResponse {
    plans: PlanListItem[];
    total: number;
    limit: number;
    offset: number;
}

export interface UsePlansOptions {
    limit?: number;
    offset?: number;
    sessionId?: string;
}

export function usePlans(options: UsePlansOptions = {}) {
    const { limit = 20, offset = 0, sessionId } = options;

    return useQuery<PlansListResponse>({
        queryKey: ["plans", limit, offset, sessionId],
        queryFn: () => {
            const params = new URLSearchParams({
                limit: String(limit),
                offset: String(offset),
            });
            if (sessionId) {
                params.set("session_id", sessionId);
            }
            return fetchJson(`${API_ENDPOINTS.ACTIVITY_PLANS}?${params.toString()}`);
        },
    });
}
