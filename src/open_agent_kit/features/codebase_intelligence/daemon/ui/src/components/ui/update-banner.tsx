import { useState } from "react";
import { AlertTriangle, ArrowUpCircle, Copy, Check, X, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import { useRestart } from "@/hooks/use-restart";
import { API_ENDPOINTS, COPIED_FEEDBACK_DURATION_MS, UPDATE_BANNER } from "@/lib/constants";
import type { VersionInfo, UpgradeInfo } from "@/hooks/use-status";

interface UpdateBannerProps {
    version: VersionInfo;
    upgrade: UpgradeInfo;
}

export function UpdateBanner({ version, upgrade }: UpdateBannerProps) {
    const { restart, isRestarting, error } = useRestart({
        endpoint: API_ENDPOINTS.UPGRADE_AND_RESTART,
    });
    const [copied, setCopied] = useState(false);

    const needsAction = version.update_available || upgrade.needed;

    // Detect if a previous auto-upgrade attempt failed
    const upgradeAttempted = sessionStorage.getItem(UPDATE_BANNER.UPGRADE_ATTEMPTED_KEY) === "true";
    const showFallback = upgradeAttempted && needsAction;

    // Dismissal key encodes state so banner reappears when conditions change
    const dismissKey = `${UPDATE_BANNER.SESSION_STORAGE_KEY}-${version.installed}-${upgrade.pending_migrations}-${upgrade.config_version_outdated}`;
    const [dismissed, setDismissed] = useState(() => {
        return sessionStorage.getItem(dismissKey) === "true";
    });

    // Clear attempted marker when conditions resolve
    if (!needsAction) {
        sessionStorage.removeItem(UPDATE_BANNER.UPGRADE_ATTEMPTED_KEY);
        return null;
    }

    if (dismissed) return null;

    const handleDismiss = () => {
        sessionStorage.setItem(dismissKey, "true");
        setDismissed(true);
    };

    const handleUpgrade = async () => {
        sessionStorage.setItem(UPDATE_BANNER.UPGRADE_ATTEMPTED_KEY, "true");
        await restart();
    };

    const handleCopy = async () => {
        await navigator.clipboard.writeText(UPDATE_BANNER.COMMAND);
        setCopied(true);
        setTimeout(() => setCopied(false), COPIED_FEEDBACK_DURATION_MS);
    };

    const versionText = version.update_available && version.installed
        ? `(${UPDATE_BANNER.VERSION_PREFIX}${version.running} → ${UPDATE_BANNER.VERSION_PREFIX}${version.installed})`
        : "";

    const message = version.update_available
        ? UPDATE_BANNER.UPDATE_MESSAGE
        : UPDATE_BANNER.UPGRADE_MESSAGE;

    // Fallback: previous auto-upgrade attempt didn't resolve conditions
    if (showFallback) {
        return (
            <div className={cn(
                "flex items-center gap-3 px-4 py-3 rounded-lg mb-4 text-sm",
                "bg-amber-500/10 border border-amber-500/20 text-amber-700 dark:text-amber-400"
            )}>
                <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                <span className="flex-1">
                    {UPDATE_BANNER.FAILED_MESSAGE}{" "}
                    <code className="px-1.5 py-0.5 rounded bg-amber-500/10 font-mono text-xs">
                        {UPDATE_BANNER.COMMAND}
                    </code>
                </span>
                <button
                    onClick={handleCopy}
                    className={cn(
                        "flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium transition-colors",
                        "bg-amber-600 text-white hover:bg-amber-700"
                    )}
                >
                    {copied ? (
                        <>
                            <Check className="w-3 h-3" />
                            {UPDATE_BANNER.COPIED_LABEL}
                        </>
                    ) : (
                        <>
                            <Copy className="w-3 h-3" />
                            {UPDATE_BANNER.COPY_LABEL}
                        </>
                    )}
                </button>
                <button
                    onClick={handleDismiss}
                    title={UPDATE_BANNER.DISMISS_LABEL}
                    aria-label={UPDATE_BANNER.DISMISS_LABEL}
                    className="p-1 rounded-sm hover:bg-amber-500/20 transition-colors"
                >
                    <X className="w-3.5 h-3.5" />
                </button>
            </div>
        );
    }

    // Normal: show upgrade & restart button
    return (
        <div className={cn(
            "flex items-center gap-3 px-4 py-3 rounded-lg mb-4 text-sm",
            "bg-amber-500/10 border border-amber-500/20 text-amber-700 dark:text-amber-400"
        )}>
            <ArrowUpCircle className="w-4 h-4 flex-shrink-0" />
            <span className="flex-1">
                {message} {versionText}
            </span>
            {error && (
                <span className="text-red-600 dark:text-red-400 text-xs">{error}</span>
            )}
            <button
                onClick={handleUpgrade}
                disabled={isRestarting}
                className={cn(
                    "flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium transition-colors",
                    "bg-amber-600 text-white hover:bg-amber-700",
                    "disabled:opacity-50 disabled:cursor-not-allowed"
                )}
            >
                <RefreshCw className={cn("w-3 h-3", isRestarting && "animate-spin")} />
                {isRestarting ? UPDATE_BANNER.UPGRADING : UPDATE_BANNER.UPGRADE_BUTTON}
            </button>
            {!isRestarting && (
                <button
                    onClick={handleDismiss}
                    title={UPDATE_BANNER.DISMISS_LABEL}
                    aria-label={UPDATE_BANNER.DISMISS_LABEL}
                    className="p-1 rounded-sm hover:bg-amber-500/20 transition-colors"
                >
                    <X className="w-3.5 h-3.5" />
                </button>
            )}
        </div>
    );
}
