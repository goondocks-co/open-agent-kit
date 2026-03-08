import { fetchJson, postJson } from "@/lib/api";
import { API_ENDPOINTS, RESTART_POLL_INTERVAL_MS, RESTART_TIMEOUT_MS } from "@/lib/constants";
import { useRestart as useRestartShared } from "@oak/ui/hooks/use-restart";
import type { UseRestartReturn } from "@oak/ui/hooks/use-restart";

export function useRestart(): UseRestartReturn {
    return useRestartShared({
        endpoint: API_ENDPOINTS.RESTART,
        healthEndpoint: API_ENDPOINTS.HEALTH,
        pollIntervalMs: RESTART_POLL_INTERVAL_MS,
        timeoutMs: RESTART_TIMEOUT_MS,
        timeoutHint: "oak swarm restart --name <id>",
        fetchJson,
        postRestart: (endpoint) => postJson(endpoint, {}),
    });
}
