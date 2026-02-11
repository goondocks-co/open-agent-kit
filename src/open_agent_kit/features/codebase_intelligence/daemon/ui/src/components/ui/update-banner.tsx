import { useState } from "react";
import { AlertTriangle, X, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import { useRestart } from "@/hooks/use-restart";
import { VERSION_BANNER } from "@/lib/constants";
import type { VersionInfo } from "@/hooks/use-status";

interface UpdateBannerProps {
    version: VersionInfo;
}

export function UpdateBanner({ version }: UpdateBannerProps) {
    const { restart, isRestarting, error } = useRestart();
    const [dismissed, setDismissed] = useState(() => {
        const key = `${VERSION_BANNER.SESSION_STORAGE_KEY}-${version.installed}`;
        return sessionStorage.getItem(key) === "true";
    });

    if (dismissed || !version.update_available) return null;

    const handleDismiss = () => {
        const key = `${VERSION_BANNER.SESSION_STORAGE_KEY}-${version.installed}`;
        sessionStorage.setItem(key, "true");
        setDismissed(true);
    };

    const versionText = version.installed
        ? `(v${version.running} → v${version.installed})`
        : "";

    return (
        <div className={cn(
            "flex items-center gap-3 px-4 py-3 rounded-lg mb-4 text-sm",
            "bg-amber-500/10 border border-amber-500/20 text-amber-700 dark:text-amber-400"
        )}>
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            <span className="flex-1">
                {VERSION_BANNER.UPDATE_MESSAGE} {versionText}
            </span>
            {error && (
                <span className="text-red-600 dark:text-red-400 text-xs">{error}</span>
            )}
            <button
                onClick={restart}
                disabled={isRestarting}
                className={cn(
                    "flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium transition-colors",
                    "bg-amber-600 text-white hover:bg-amber-700",
                    "disabled:opacity-50 disabled:cursor-not-allowed"
                )}
            >
                <RefreshCw className={cn("w-3 h-3", isRestarting && "animate-spin")} />
                {isRestarting ? VERSION_BANNER.RESTARTING : VERSION_BANNER.RESTART_BUTTON}
            </button>
            {!isRestarting && (
                <button
                    onClick={handleDismiss}
                    title={VERSION_BANNER.DISMISS_LABEL}
                    aria-label={VERSION_BANNER.DISMISS_LABEL}
                    className="p-1 rounded-sm hover:bg-amber-500/20 transition-colors"
                >
                    <X className="w-3.5 h-3.5" />
                </button>
            )}
        </div>
    );
}
