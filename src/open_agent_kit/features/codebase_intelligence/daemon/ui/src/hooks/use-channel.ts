import { useQuery } from "@tanstack/react-query";
import { fetchJson } from "@/lib/api";
import { API_ENDPOINTS } from "@/lib/constants";

export interface ChannelInfo {
    current_channel: "stable" | "beta";
    cli_command: string;
    current_version: string;
    install_method: "homebrew" | "pipx" | "uv" | "unknown";
    switch_supported: boolean;
    available_stable_version: string | null;
    available_beta_version: string | null;
}

export function useChannel() {
    return useQuery({
        queryKey: ["channel"],
        queryFn: ({ signal }) => fetchJson<ChannelInfo>(API_ENDPOINTS.CHANNEL, { signal }),
        staleTime: 5 * 60 * 1000, // 5 minutes — matches backend cache TTL
    });
}
