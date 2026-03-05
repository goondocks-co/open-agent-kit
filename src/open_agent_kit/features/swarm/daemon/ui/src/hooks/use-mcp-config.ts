import { useQuery } from "@tanstack/react-query";
import { fetchJson } from "@/lib/api";
import { API_ENDPOINTS } from "@/lib/constants";

interface McpConfig {
    mcp_endpoint: string;
    agent_token: string;
    has_agent_token: boolean;
}

/** Fetch MCP endpoint configuration once (not polled). */
export function useMcpConfig() {
    return useQuery<McpConfig>({
        queryKey: ["mcp", "config"],
        queryFn: ({ signal }) => fetchJson(API_ENDPOINTS.CONFIG_MCP, { signal }),
        staleTime: Infinity,
    });
}
