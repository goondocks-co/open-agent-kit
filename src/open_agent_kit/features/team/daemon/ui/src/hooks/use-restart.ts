import { fetchJson } from "@/lib/api";
import { API_ENDPOINTS, RESTART_POLL_INTERVAL_MS, RESTART_TIMEOUT_MS, UPDATE_BANNER } from "@/lib/constants";
import { useRestart as useRestartShared } from "@oak/ui/hooks/use-restart";
import type { UseRestartReturn } from "@oak/ui/hooks/use-restart";

interface UseRestartOptions {
    endpoint?: string;
    onSuccess?: () => void;
    cliCommand?: string;
}

export function useRestart(options?: UseRestartOptions): UseRestartReturn {
    return useRestartShared({
        endpoint: options?.endpoint ?? API_ENDPOINTS.SELF_RESTART,
        healthEndpoint: API_ENDPOINTS.HEALTH,
        pollIntervalMs: RESTART_POLL_INTERVAL_MS,
        timeoutMs: RESTART_TIMEOUT_MS,
        timeoutHint: `${options?.cliCommand || "oak"} team restart`,
        upToDateStatus: UPDATE_BANNER.STATUS_UP_TO_DATE,
        onSuccess: options?.onSuccess,
        fetchJson,
    });
}
