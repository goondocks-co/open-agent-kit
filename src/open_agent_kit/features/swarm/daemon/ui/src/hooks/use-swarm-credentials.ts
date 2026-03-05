import { useQuery } from "@tanstack/react-query";
import { fetchJson } from "@/lib/api";
import { API_ENDPOINTS } from "@/lib/constants";

interface SwarmCredentials {
    swarm_url: string;
    swarm_token?: string;
}

/** Fetch swarm credentials once (not polled). */
export function useSwarmCredentials() {
    return useQuery<SwarmCredentials>({
        queryKey: ["swarm", "credentials"],
        queryFn: ({ signal }) => fetchJson(API_ENDPOINTS.SWARM_CREDENTIALS, { signal }),
        staleTime: Infinity,
    });
}
