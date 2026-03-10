import * as DialogPrimitive from "@radix-ui/react-dialog";
import { ExternalLink, Loader2, CheckCircle2, ArrowUpCircle, RefreshCw } from "lucide-react";
import { Button } from "./button";
import { cn } from "../../lib/utils";

export interface ChannelInfo {
    current_channel: "stable" | "beta";
    current_version: string;
    available_stable_version: string | null;
    available_beta_version: string | null;
}

export interface AboutDialogConfig {
    title: string;
    logoSrc: string;
    channelEndpoint: string;
    healthEndpoint: string;
}

/** Staged update waiting to be applied */
export interface StagedUpdate {
    version: string;
    wheel_path: string;
    downloaded_at: string;
}

/** Last update check result */
export interface LastCheck {
    timestamp: number;
    version: string;
    update_available: boolean;
}

/** Update status from the self-update API */
export interface UpdateStatus {
    exempt: boolean;
    reason?: string;
    message?: string;
    running_version?: string;
    channel?: string;
    auto_download?: boolean;
    staged_update?: StagedUpdate | null;
    last_check?: LastCheck | null;
    error?: string | null;
}


interface AboutDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    config: AboutDialogConfig;
    channelData: ChannelInfo | undefined;
    /** Update status from the self-update API (optional — omit for swarm or exempt installs) */
    updateStatus?: UpdateStatus;
    /** Called when user clicks "Check Now" */
    onCheckUpdate?: () => void;
    /** Called when user clicks "Apply Update" */
    onApplyUpdate?: () => void;
    /** Called when user toggles the update channel */
    onSwitchChannel?: (channel: string) => void;
    /** Whether a check/apply mutation is currently pending */
    isCheckingUpdate?: boolean;
    isApplyingUpdate?: boolean;
}

function formatLastChecked(timestamp: number): string {
    const diffMs = Date.now() - timestamp * 1000;
    const diffMins = Math.floor(diffMs / 60_000);
    if (diffMins < 1) return "just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${Math.floor(diffHours / 24)}d ago`;
}

function UpdateSection({
    updateStatus,
    onCheckUpdate,
    onApplyUpdate,
    onSwitchChannel,
    isCheckingUpdate,
    isApplyingUpdate,
}: {
    updateStatus: UpdateStatus;
    onCheckUpdate?: () => void;
    onApplyUpdate?: () => void;
    onSwitchChannel?: (channel: string) => void;
    isCheckingUpdate?: boolean;
    isApplyingUpdate?: boolean;
}) {
    if (updateStatus.exempt) {
        return (
            <div className="text-sm text-muted-foreground">
                {updateStatus.message ?? "Self-update not available for this install."}
            </div>
        );
    }

    const hasUpdate = !!updateStatus.staged_update;
    const channel = updateStatus.channel ?? "stable";
    const lastCheck = updateStatus.last_check;

    return (
        <div className="space-y-3">
            {/* Version + status row */}
            <div className="flex items-center gap-2">
                {hasUpdate ? (
                    <ArrowUpCircle className="w-4 h-4 text-emerald-500 flex-shrink-0" />
                ) : (
                    <CheckCircle2 className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                )}
                <span className="text-sm font-medium">
                    {hasUpdate
                        ? `Update ready: v${updateStatus.staged_update!.version}`
                        : "Up to date"}
                </span>
                {updateStatus.running_version && (
                    <span className="text-xs text-muted-foreground">
                        (running v{updateStatus.running_version})
                    </span>
                )}
            </div>

            {/* Action buttons */}
            <div className="flex items-center gap-2 pl-6">
                {hasUpdate && onApplyUpdate && (
                    <Button
                        size="sm"
                        onClick={onApplyUpdate}
                        disabled={isApplyingUpdate}
                        className="bg-emerald-600 hover:bg-emerald-700 text-white"
                    >
                        {isApplyingUpdate ? (
                            <>
                                <Loader2 className="w-3 h-3 mr-1.5 animate-spin" />
                                Applying&hellip;
                            </>
                        ) : (
                            "Apply Update"
                        )}
                    </Button>
                )}
                {!hasUpdate && onCheckUpdate && (
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={onCheckUpdate}
                        disabled={isCheckingUpdate}
                    >
                        {isCheckingUpdate ? (
                            <>
                                <RefreshCw className="w-3 h-3 mr-1.5 animate-spin" />
                                Checking&hellip;
                            </>
                        ) : (
                            "Check Now"
                        )}
                    </Button>
                )}
            </div>

            {/* Channel toggle */}
            {onSwitchChannel && (
                <div className="pl-6 flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">Channel:</span>
                    <div className="flex items-center rounded-md bg-muted/50 p-0.5 gap-0.5">
                        {(["stable", "beta"] as const).map((ch) => (
                            <button
                                key={ch}
                                onClick={() => ch !== channel && onSwitchChannel(ch)}
                                className={cn(
                                    "px-2 py-0.5 rounded-sm text-xs font-medium transition-all capitalize",
                                    ch === channel
                                        ? "bg-background shadow-sm text-foreground"
                                        : "text-muted-foreground hover:text-foreground"
                                )}
                            >
                                {ch === "beta" ? "Beta" : "Stable"}
                            </button>
                        ))}
                    </div>
                </div>
            )}

            {/* Last checked */}
            {lastCheck && (
                <p className="pl-6 text-xs text-muted-foreground">
                    Last checked {formatLastChecked(lastCheck.timestamp)}
                </p>
            )}

            {/* Error */}
            {updateStatus.error && (
                <p className="pl-6 text-xs text-destructive">{updateStatus.error}</p>
            )}
        </div>
    );
}

export function AboutDialog({ open, onOpenChange, config, channelData, updateStatus, onCheckUpdate, onApplyUpdate, onSwitchChannel, isCheckingUpdate, isApplyingUpdate }: AboutDialogProps) {
    return (
        <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
            <DialogPrimitive.Portal>
                <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=closed]:animate-out data-[state=closed]:fade-out-0" />
                <DialogPrimitive.Content className="fixed left-[50%] top-[50%] z-50 translate-x-[-50%] translate-y-[-50%] w-full max-w-md rounded-lg border bg-background p-6 shadow-lg data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95">
                    <div className="flex flex-col gap-5">
                        {/* Header */}
                        <div className="flex items-center gap-3">
                            <img src={config.logoSrc} alt={config.title} className="w-8 h-8 object-contain" />
                            <div>
                                <DialogPrimitive.Title className="text-lg font-bold tracking-tight">
                                    {config.title}
                                </DialogPrimitive.Title>
                                {channelData && (
                                    <p className="text-sm text-muted-foreground">
                                        v{channelData.current_version}
                                    </p>
                                )}
                            </div>
                        </div>

                        {/* Update section */}
                        {updateStatus ? (
                            <UpdateSection
                                updateStatus={updateStatus}
                                onCheckUpdate={onCheckUpdate}
                                onApplyUpdate={onApplyUpdate}
                                onSwitchChannel={onSwitchChannel}
                                isCheckingUpdate={isCheckingUpdate}
                                isApplyingUpdate={isApplyingUpdate}
                            />
                        ) : (
                            <p className="text-sm text-muted-foreground">
                                Loading update info&hellip;
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
