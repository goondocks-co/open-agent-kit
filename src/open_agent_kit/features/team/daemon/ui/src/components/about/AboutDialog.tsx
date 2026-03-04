import * as React from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { ExternalLink, Loader2 } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import { Button } from "@oak/ui/components/ui/button";
import { ConfirmDialog } from "@oak/ui/components/ui/confirm-dialog";
import { fetchJson } from "@/lib/api";
import { API_ENDPOINTS, RESTART_POLL_INTERVAL_MS, RESTART_TIMEOUT_MS } from "@/lib/constants";
import { useChannel } from "@/hooks/use-channel";
import type { ChannelInfo } from "@/hooks/use-channel";
import { cn } from "@/lib/utils";

interface AboutDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
}

function ChannelSection({ data }: { data: ChannelInfo }) {
    const [confirmOpen, setConfirmOpen] = React.useState(false);
    const [isSwitching, setIsSwitching] = React.useState(false);
    const [switchError, setSwitchError] = React.useState<string | null>(null);

    const targetChannel = data.current_channel === "stable" ? "beta" : "stable";
    const switchVersion =
        targetChannel === "beta" ? data.available_beta_version : data.available_stable_version;

    const switchMutation = useMutation({
        mutationFn: (target: string) =>
            fetchJson(API_ENDPOINTS.CHANNEL_SWITCH, {
                method: "POST",
                body: JSON.stringify({ target_channel: target }),
            }),
    });

    const handleConfirmedSwitch = async () => {
        setConfirmOpen(false);
        setIsSwitching(true);
        setSwitchError(null);

        try {
            await switchMutation.mutateAsync(targetChannel);

            // Poll health until the new daemon is up
            const deadline = Date.now() + RESTART_TIMEOUT_MS;
            await new Promise<void>((resolve, reject) => {
                const check = async () => {
                    if (Date.now() > deadline) {
                        reject(new Error("timeout"));
                        return;
                    }
                    try {
                        await fetchJson(API_ENDPOINTS.HEALTH);
                        resolve();
                    } catch {
                        setTimeout(check, RESTART_POLL_INTERVAL_MS);
                    }
                };
                setTimeout(check, RESTART_POLL_INTERVAL_MS);
            });

            window.location.reload();
        } catch (err) {
            const message = err instanceof Error ? err.message : "Unknown error";
            setSwitchError(
                message === "timeout"
                    ? "Switch timed out. The daemon may still be installing — check the terminal for progress."
                    : message,
            );
            setIsSwitching(false);
        }
    };

    const channelLabel = data.current_channel === "stable" ? "Stable" : "Beta";
    const channelDot = data.current_channel === "beta" ? "bg-amber-500" : "bg-green-500";

    // Build confirm dialog description
    const confirmDescription = switchVersion
        ? `This will install oak-ci${targetChannel === "beta" ? "-beta" : ""} v${switchVersion} and restart the daemon. You can switch back at any time.`
        : `This will switch to the ${targetChannel} channel and restart the daemon. You can switch back at any time.`;

    // Determine whether to show a switch button
    const canSwitch =
        data.switch_supported &&
        (targetChannel === "stable" || data.available_beta_version !== null);

    const noBetaAvailable =
        targetChannel === "beta" &&
        data.current_channel === "stable" &&
        data.available_beta_version === null;

    return (
        <div className="space-y-3">
            <div className="flex items-center gap-2">
                <span className={cn("w-2 h-2 rounded-full flex-shrink-0", channelDot)} />
                <span className="text-sm font-medium">
                    Release Channel: {channelLabel}
                    {data.current_channel === "beta" && data.current_version && (
                        <span className="ml-1 text-muted-foreground">v{data.current_version}</span>
                    )}
                </span>
            </div>

            {/* Available version info */}
            {targetChannel === "beta" && data.available_beta_version && (
                <p className="text-sm text-muted-foreground pl-4">
                    Beta channel: v{data.available_beta_version} available
                </p>
            )}
            {targetChannel === "stable" && data.available_stable_version && (
                <p className="text-sm text-muted-foreground pl-4">
                    Stable channel: v{data.available_stable_version} available
                </p>
            )}
            {noBetaAvailable && (
                <p className="text-sm text-muted-foreground pl-4">
                    Beta channel: no pre-release available
                </p>
            )}

            {/* Switch button or manual instructions */}
            {canSwitch && !isSwitching && (
                <div className="pl-4">
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setConfirmOpen(true)}
                    >
                        Switch to {targetChannel === "beta" ? "Beta" : "Stable"}
                    </Button>
                </div>
            )}

            {!data.switch_supported && (
                <div className="pl-4 space-y-1 text-sm text-muted-foreground">
                    <p>To switch channels, reinstall with your package manager:</p>
                    <code className="block px-2 py-1 rounded bg-muted font-mono text-xs">
                        {targetChannel === "beta"
                            ? "brew install goondocks-co/oak/oak-ci-beta"
                            : "brew install goondocks-co/oak/oak-ci"}
                    </code>
                    <code className="block px-2 py-1 rounded bg-muted font-mono text-xs">
                        {targetChannel === "beta" ? "oak-beta" : "oak"} team start
                    </code>
                </div>
            )}

            {isSwitching && (
                <div className="flex items-center gap-2 pl-4 text-sm text-muted-foreground">
                    <Loader2 className="h-3 w-3 animate-spin" />
                    <span>Switching channel&hellip; this may take a few minutes.</span>
                </div>
            )}

            {switchError && (
                <p className="pl-4 text-sm text-destructive">{switchError}</p>
            )}

            <ConfirmDialog
                open={confirmOpen}
                onOpenChange={setConfirmOpen}
                title={`Switch to ${targetChannel === "beta" ? "Beta" : "Stable"} Channel`}
                description={confirmDescription}
                confirmLabel="Switch"
                loadingLabel="Switching..."
                requireConfirmText="SWITCH"
                variant="destructive"
                onConfirm={handleConfirmedSwitch}
            />
        </div>
    );
}

export function AboutDialog({ open, onOpenChange }: AboutDialogProps) {
    const { data: channelData } = useChannel();

    return (
        <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
            <DialogPrimitive.Portal>
                <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=closed]:animate-out data-[state=closed]:fade-out-0" />
                <DialogPrimitive.Content className="fixed left-[50%] top-[50%] z-50 translate-x-[-50%] translate-y-[-50%] w-full max-w-md rounded-lg border bg-background p-6 shadow-lg data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95">
                    <div className="flex flex-col gap-5">
                        {/* Header */}
                        <div className="flex items-center gap-3">
                            <img src="/logo.png" alt="Oak CI" className="w-8 h-8 object-contain" />
                            <div>
                                <DialogPrimitive.Title className="text-lg font-bold tracking-tight">
                                    Oak CI
                                </DialogPrimitive.Title>
                                {channelData && (
                                    <p className="text-sm text-muted-foreground">
                                        v{channelData.current_version}
                                    </p>
                                )}
                            </div>
                        </div>

                        {/* Channel section */}
                        {channelData ? (
                            <ChannelSection data={channelData} />
                        ) : (
                            <p className="text-sm text-muted-foreground">
                                Loading channel info&hellip;
                            </p>
                        )}

                        {/* Links */}
                        <div className="flex items-center gap-3 pt-1 border-t">
                            <a
                                href="https://github.com/goondocks-co/open-agent-kit"
                                target="_blank"
                                rel="noopener noreferrer"
                                className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
                            >
                                GitHub
                                <ExternalLink className="h-3 w-3" />
                            </a>
                            <a
                                href="https://docs.goondocks.co/oak"
                                target="_blank"
                                rel="noopener noreferrer"
                                className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
                            >
                                Docs
                                <ExternalLink className="h-3 w-3" />
                            </a>
                        </div>
                    </div>
                </DialogPrimitive.Content>
            </DialogPrimitive.Portal>
        </DialogPrimitive.Root>
    );
}
