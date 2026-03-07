import { useQuery } from "@tanstack/react-query";
import type { ChannelInfo } from "../components/ui/about-dialog";

export type { ChannelInfo };

export function useChannel(
    endpoint: string,
    fetchJson: (url: string, init?: RequestInit) => Promise<unknown>,
) {
    return useQuery({
        queryKey: ["channel", endpoint],
        queryFn: ({ signal }) => fetchJson(endpoint, { signal }) as Promise<ChannelInfo>,
        staleTime: 5 * 60 * 1000, // 5 minutes — matches backend cache TTL
    });
}
