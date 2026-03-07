import { useChannel as useChannelShared } from "@oak/ui/hooks/use-channel";
import { fetchJson } from "@/lib/api";
import { API_ENDPOINTS } from "@/lib/constants";

export type { ChannelInfo } from "@oak/ui/hooks/use-channel";

export function useChannel() {
    return useChannelShared(
        API_ENDPOINTS.CHANNEL,
        fetchJson as (url: string, init?: RequestInit) => Promise<unknown>,
    );
}
