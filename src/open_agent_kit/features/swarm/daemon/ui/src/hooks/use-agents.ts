import { usePowerQuery } from "@oak/ui/hooks/use-power-query";
import { fetchJson } from "@/lib/api";
import { API_ENDPOINTS, AGENTS_POLL_MS } from "@/lib/constants";

interface AgentSession {
    id: string;
    [key: string]: unknown;
}

interface AgentsResponse {
    sessions: Record<string, AgentSession>;
}

export function useAgents() {
    return usePowerQuery<AgentsResponse>({
        queryKey: ["agents"],
        queryFn: ({ signal }) => fetchJson(API_ENDPOINTS.AGENTS, { signal }),
        refetchInterval: AGENTS_POLL_MS,
        pollCategory: "standard",
    });
}
