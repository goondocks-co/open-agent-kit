import { useQuery } from "@tanstack/react-query";
import { fetchJson } from "@/lib/api";
import { API_ENDPOINTS, DEFAULT_PLAN_SORT } from "@/lib/constants";
import type { PlanSortOption } from "@/lib/constants";

/** Refetch interval for plans list (30 seconds) */
const PLANS_REFETCH_INTERVAL_MS = 30000;

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
    sort?: PlanSortOption;
}

export function usePlans(options: UsePlansOptions = {}) {
    const { limit = 20, offset = 0, sessionId, sort = DEFAULT_PLAN_SORT } = options;

    return useQuery<PlansListResponse>({
        queryKey: ["plans", limit, offset, sessionId, sort],
        queryFn: ({ signal }) => {
            const params = new URLSearchParams({
                limit: String(limit),
                offset: String(offset),
                sort,
            });
            if (sessionId) {
                params.set("session_id", sessionId);
            }
            return fetchJson(`${API_ENDPOINTS.ACTIVITY_PLANS}?${params.toString()}`, { signal });
        },
        refetchInterval: PLANS_REFETCH_INTERVAL_MS,
    });
}
