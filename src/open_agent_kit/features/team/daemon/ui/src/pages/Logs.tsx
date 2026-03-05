import { useState } from "react";
import { useLogs, DEFAULT_LOG_LINES, DEFAULT_LOG_FILE } from "@/hooks/use-logs";
import { useConfig, toggleDebugLogging, restartDaemon } from "@/hooks/use-config";
import { Button } from "@oak/ui/components/ui/button";
import { LogViewer } from "@oak/ui/components/ui/log-viewer";
import { Bug, Loader2 } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import {
    LOG_LEVELS,
    LOG_FILES,
    LOG_FILE_OPTIONS,
    HOOKS_LOG_TAG_CATEGORIES,
    HOOKS_LOG_TAG_DISPLAY_NAMES,
    DAEMON_LOG_TAG_CATEGORIES,
    DAEMON_LOG_TAG_DISPLAY_NAMES,
} from "@/lib/constants";
import type {
    LogFileType,
    HooksLogTagCategory,
    DaemonLogTagCategory,
} from "@/lib/constants";
import type { TagCategory } from "@oak/ui/lib/log-constants";

/** Delay before refetching logs after restart (ms) */
const RESTART_REFETCH_DELAY_MS = 1000;

/** Convert team hooks tag categories to shared TagCategory format */
function getHooksTagCategories(): TagCategory[] {
    return (Object.entries(HOOKS_LOG_TAG_CATEGORIES) as [HooksLogTagCategory, typeof HOOKS_LOG_TAG_CATEGORIES[HooksLogTagCategory]][]).map(
        ([, { label, tags }]) => ({
            label,
            tags: tags.map((tag) => ({ value: tag, display: HOOKS_LOG_TAG_DISPLAY_NAMES[tag] })),
        })
    );
}

/** Convert team daemon tag categories to shared TagCategory format */
function getDaemonTagCategories(): TagCategory[] {
    return (Object.entries(DAEMON_LOG_TAG_CATEGORIES) as [DaemonLogTagCategory, typeof DAEMON_LOG_TAG_CATEGORIES[DaemonLogTagCategory]][]).map(
        ([, { label, tags }]) => ({
            label,
            tags: tags.map((tag) => ({ value: tag, display: DAEMON_LOG_TAG_DISPLAY_NAMES[tag] })),
        })
    );
}

export default function Logs() {
    const [lines, setLines] = useState(DEFAULT_LOG_LINES);
    const [logFile, setLogFile] = useState<LogFileType>(DEFAULT_LOG_FILE);
    const [autoScroll, setAutoScroll] = useState(true);
    const [isTogglingDebug, setIsTogglingDebug] = useState(false);
    const queryClient = useQueryClient();

    const { data, isLoading, isError, refetch, isFetching } = useLogs(lines, logFile, autoScroll);
    const { data: config } = useConfig();

    const isDebugEnabled = config?.log_level === LOG_LEVELS.DEBUG;

    const handleToggleDebug = async () => {
        if (!config) return;
        setIsTogglingDebug(true);
        try {
            await toggleDebugLogging(config.log_level);
            await restartDaemon();
            queryClient.invalidateQueries({ queryKey: ["config"] });
            setTimeout(() => refetch(), RESTART_REFETCH_DELAY_MS);
        } catch (e) {
            console.error("Failed to toggle debug:", e);
        } finally {
            setIsTogglingDebug(false);
        }
    };

    const tagCategories = logFile === LOG_FILES.HOOKS
        ? getHooksTagCategories()
        : getDaemonTagCategories();

    const toolbarLeft = (
        <>
            <select
                className="bg-background border border-input rounded-md px-3 py-1 text-sm font-medium"
                value={logFile}
                onChange={(e) => setLogFile(e.target.value as LogFileType)}
                title="Select log file to view"
            >
                {LOG_FILE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                ))}
            </select>

            <div className="w-px h-6 bg-border" />

            <Button
                variant={isDebugEnabled ? "default" : "outline"}
                size="sm"
                onClick={handleToggleDebug}
                disabled={isTogglingDebug}
                title={isDebugEnabled ? "Debug logging enabled - click to disable" : "Enable debug logging"}
            >
                {isTogglingDebug ? (
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                    <Bug className="w-4 h-4 mr-2" />
                )}
                {isDebugEnabled ? "Debug On" : "Debug Off"}
            </Button>
        </>
    );

    return (
        <LogViewer
            lines={data?.lines ?? []}
            path={data?.path ?? null}
            totalLines={data?.total_lines}
            isLoading={isLoading}
            isError={isError}
            isFetching={isFetching}
            onRefresh={() => refetch()}
            lineCount={lines}
            onLineCountChange={setLines}
            tagCategories={tagCategories}
            autoScroll={autoScroll}
            onAutoScrollChange={setAutoScroll}
            toolbarLeft={toolbarLeft}
        />
    );
}
