import { AboutDialog as SharedAboutDialog } from "@oak/ui/components/ui/about-dialog";
import type { AboutDialogConfig } from "@oak/ui/components/ui/about-dialog";
import { useChannel } from "@/hooks/use-channel";
import { useUpdateStatus, useUpdateCheck, useUpdateApply, useUpdateChannel } from "@/hooks/use-update-status";
import { API_ENDPOINTS } from "@/lib/constants";

const ABOUT_CONFIG: AboutDialogConfig = {
    title: "OAK Team",
    logoSrc: "/logo.png",
    channelEndpoint: API_ENDPOINTS.CHANNEL,
    healthEndpoint: API_ENDPOINTS.HEALTH,
};

interface AboutDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
}

export function AboutDialog({ open, onOpenChange }: AboutDialogProps) {
    const { data: channelData } = useChannel();
    const { data: updateStatus } = useUpdateStatus();
    const updateCheck = useUpdateCheck();
    const updateApply = useUpdateApply();
    const updateChannel = useUpdateChannel();

    return (
        <SharedAboutDialog
            open={open}
            onOpenChange={onOpenChange}
            config={ABOUT_CONFIG}
            channelData={channelData}
            updateStatus={updateStatus}
            onCheckUpdate={() => updateCheck.mutate()}
            onApplyUpdate={() => updateApply.mutate()}
            onSwitchChannel={(channel) => updateChannel.mutate(channel)}
            isCheckingUpdate={updateCheck.isPending}
            isApplyingUpdate={updateApply.isPending}
        />
    );
}
