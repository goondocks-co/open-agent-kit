import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { fetchJson } from "@/lib/api";
import { getPlanRefreshEndpoint } from "@/lib/constants";

/** Minimal plan shape needed for auto-refresh */
interface RefreshablePlan {
    id: number;
    file_path?: string | null;
}

interface RefreshPlanResponse {
    success: boolean;
    batch_id: number;
    plan_file_path: string | null;
    content_length: number;
    message: string;
}

/**
 * Module-level set of plan IDs that have already been attempted.
 * Persists across component mounts/unmounts within the same browser session,
 * so each plan is refreshed at most once per tab lifetime.
 */
const attemptedPlanIds = new Set<number>();

/**
 * Automatically refresh plan content from disk when plans are first viewed.
 *
 * Each plan is refreshed at most once per browser session (tab lifetime).
 * Fires graceful POST requests for plans that have a file_path and haven't
 * been attempted yet. Fails silently — the plan may not exist on this machine.
 * When any plan is successfully refreshed, invalidates relevant query caches
 * so the UI picks up updated content.
 *
 * @param plans - Array of plans to refresh (only those with file_path are attempted)
 */
export function useAutoRefreshPlans(plans: RefreshablePlan[]) {
    const queryClient = useQueryClient();

    useEffect(() => {
        if (plans.length === 0) return;

        // Only attempt plans with a file_path that we haven't tried yet
        const pending = plans.filter(
            (p) => p.file_path && !attemptedPlanIds.has(p.id),
        );
        if (pending.length === 0) return;

        // Mark as attempted immediately so concurrent renders don't duplicate
        for (const p of pending) {
            attemptedPlanIds.add(p.id);
        }

        let cancelled = false;

        const run = async () => {
            const results = await Promise.allSettled(
                pending.map((plan) =>
                    fetchJson<RefreshPlanResponse>(
                        getPlanRefreshEndpoint(plan.id, true),
                        { method: "POST" },
                    ),
                ),
            );

            if (cancelled) return;

            const anyUpdated = results.some(
                (r) => r.status === "fulfilled" && r.value.success,
            );

            if (anyUpdated) {
                // Invalidate plan-related queries so the UI shows fresh content
                queryClient.invalidateQueries({ queryKey: ["plans"] });
                queryClient.invalidateQueries({ queryKey: ["session"] });
            }
        };

        run();

        return () => {
            cancelled = true;
        };
    }, [plans, queryClient]);
}
