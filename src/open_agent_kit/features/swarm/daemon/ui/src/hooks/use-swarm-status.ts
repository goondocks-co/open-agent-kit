import { usePowerQuery } from "@oak/ui/hooks/use-power-query";
import { fetchJson } from "@/lib/api";
import { API_ENDPOINTS, SWARM_STATUS_POLL_MS } from "@/lib/constants";

interface SwarmStatus {
    swarm_id: string;
    swarm_url: string;
    connected: boolean;
    status: string;
}

export function useSwarmStatus() {
    return usePowerQuery<SwarmStatus>({
        queryKey: ["swarm", "status"],
        queryFn: ({ signal }) => fetchJson(API_ENDPOINTS.SWARM_STATUS, { signal }),
        refetchInterval: SWARM_STATUS_POLL_MS,
        pollCategory: "heartbeat",
    });
}
