import { useMutation, useQueryClient } from "@tanstack/react-query";
import { usePowerQuery } from "@oak/ui/hooks/use-power-query";
import { fetchJson, postJson } from "@/lib/api";
import { API_ENDPOINTS, NODES_POLL_MS } from "@/lib/constants";

interface SwarmNode {
    team_id: string;
    project_slug: string;
    status: string;
    last_seen?: string;
    capabilities?: string[];
    tool_names?: string[];
    oak_version?: string;
    node_count?: number;
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

export function useRemoveNode() {
    const queryClient = useQueryClient();
    return useMutation<{ success: boolean }, Error, { team_id: string }>({
        mutationFn: (params) => postJson(API_ENDPOINTS.SWARM_NODE_REMOVE, params),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ["swarm", "nodes"] }),
    });
}
