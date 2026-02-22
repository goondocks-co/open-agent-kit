import { useState, useCallback } from "react";
import { fetchJson } from "@/lib/api";
import { getSessionDetailEndpoint } from "@/lib/constants";
import type { SessionDetailResponse } from "@/hooks/use-activity";

interface PlanPreviewState {
    isOpen: boolean;
    title: string;
    subtitle?: string;
    content: string;
    isLoading: boolean;
}

const INITIAL_STATE: PlanPreviewState = {
    isOpen: false,
    title: "",
    content: "",
    isLoading: false,
};

/**
 * Shared hook for viewing plan content from a session.
 *
 * Fetches the session detail, finds plan batches, and provides
 * state for rendering in a ContentDialog.
 */
export function usePlanPreview() {
    const [state, setState] = useState<PlanPreviewState>(INITIAL_STATE);

    const viewPlan = useCallback(async (sessionId: string) => {
        setState((prev) => ({ ...prev, isLoading: true }));

        try {
            const response = await fetchJson<SessionDetailResponse>(
                getSessionDetailEndpoint(sessionId)
            );

            // Find plan batches (source_type='plan' with content)
            const planBatches = response.prompt_batches?.filter(
                (b) => b.source_type === "plan" && b.plan_content
            ) ?? [];

            if (planBatches.length === 0) {
                setState({
                    isOpen: true,
                    title: "Plan",
                    content: "No plan content available for this session.",
                    isLoading: false,
                });
                return;
            }

            // Use the most recent plan batch
            const planBatch = planBatches[planBatches.length - 1];
            const title = planBatch.plan_file_path
                ? planBatch.plan_file_path.split("/").pop() ?? "Plan"
                : "Plan";

            setState({
                isOpen: true,
                title,
                subtitle: planBatch.plan_file_path ?? undefined,
                content: planBatch.plan_content ?? "",
                isLoading: false,
            });
        } catch {
            setState({
                isOpen: true,
                title: "Plan",
                content: "Failed to load plan content.",
                isLoading: false,
            });
        }
    }, []);

    const setIsOpen = useCallback((open: boolean) => {
        setState((prev) => {
            if (!open) return INITIAL_STATE;
            return { ...prev, isOpen: open };
        });
    }, []);

    return {
        isOpen: state.isOpen,
        setIsOpen,
        title: state.title,
        subtitle: state.subtitle,
        content: state.content,
        isLoading: state.isLoading,
        viewPlan,
    };
}
