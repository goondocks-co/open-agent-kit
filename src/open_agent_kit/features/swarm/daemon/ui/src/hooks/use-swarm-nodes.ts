import { usePowerQuery } from "@oak/ui/hooks/use-power-query";
import { fetchJson } from "@/lib/api";
import { API_ENDPOINTS, NODES_POLL_MS } from "@/lib/constants";

interface SwarmNode {
    team_id: string;
    project_slug: string;
    status: string;
    last_seen?: string;
    capabilities?: string[];
}

interface NodesResponse {
    swarm_id?: string;
    teams: SwarmNode[];
    error?: string;
}

export function useSwarmNodes() {
    return usePowerQuery<NodesResponse>({
        queryKey: ["swarm", "nodes"],
        queryFn: ({ signal }) => fetchJson(API_ENDPOINTS.SWARM_NODES, { signal }),
        refetchInterval: NODES_POLL_MS,
        pollCategory: "standard",
    });
}
