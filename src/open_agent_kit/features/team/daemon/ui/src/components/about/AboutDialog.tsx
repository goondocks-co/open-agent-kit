import { AboutDialog as SharedAboutDialog } from "@oak/ui/components/ui/about-dialog";
import type { AboutDialogConfig } from "@oak/ui/components/ui/about-dialog";
import { useChannel } from "@/hooks/use-channel";
import { fetchJson } from "@/lib/api";
import { API_ENDPOINTS, RESTART_POLL_INTERVAL_MS, RESTART_TIMEOUT_MS } from "@/lib/constants";

const ABOUT_CONFIG: AboutDialogConfig = {
    title: "Oak CI",
    logoSrc: "/logo.png",
    channelEndpoint: API_ENDPOINTS.CHANNEL,
    channelSwitchEndpoint: API_ENDPOINTS.CHANNEL_SWITCH,
    healthEndpoint: API_ENDPOINTS.HEALTH,
    startCommand: "team start",
    restartPollIntervalMs: RESTART_POLL_INTERVAL_MS,
    restartTimeoutMs: RESTART_TIMEOUT_MS,
};

interface AboutDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
}

export function AboutDialog({ open, onOpenChange }: AboutDialogProps) {
    const { data: channelData } = useChannel();

    return (
        <SharedAboutDialog
            open={open}
            onOpenChange={onOpenChange}
            config={ABOUT_CONFIG}
            channelData={channelData}
            fetchJson={fetchJson as (url: string, init?: RequestInit) => Promise<unknown>}
        />
    );
}
