import { fetchJson } from "@/lib/api";
import { API_ENDPOINTS, RESTART_POLL_INTERVAL_MS, RESTART_TIMEOUT_MS } from "@/lib/constants";
import { useRestart as useRestartShared } from "@oak/ui/hooks/use-restart";
import type { UseRestartReturn } from "@oak/ui/hooks/use-restart";

// Must match the backend constant (UpgradeStatus.UP_TO_DATE)
const UP_TO_DATE_STATUS = "up_to_date";

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
        upToDateStatus: UP_TO_DATE_STATUS,
        onSuccess: options?.onSuccess,
        fetchJson,
    });
}
