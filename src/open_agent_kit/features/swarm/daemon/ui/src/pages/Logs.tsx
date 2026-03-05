import { useState } from "react";
import { LogViewer } from "@oak/ui/components/ui/log-viewer";
import { DAEMON_LOG_TAG_CATEGORIES, DEFAULT_LINE_COUNT } from "@oak/ui/lib/log-constants";
import { Button } from "@oak/ui/components/ui/button";
import { Bug, Loader2 } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useLogs } from "@/hooks/use-logs";
import { useConfig, toggleDebugLogging, restartDaemon } from "@/hooks/use-config";

/** Delay before refetching logs after restart (ms) */
const RESTART_REFETCH_DELAY_MS = 1000;

export default function Logs() {
    const [lines, setLines] = useState(DEFAULT_LINE_COUNT);
    const [autoScroll, setAutoScroll] = useState(true);
    const [isTogglingDebug, setIsTogglingDebug] = useState(false);
    const queryClient = useQueryClient();

    const { data, isLoading, isError, refetch, isFetching } = useLogs(lines, autoScroll);
    const { data: config } = useConfig();

    const isDebugEnabled = config?.log_level === "DEBUG";

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

    const toolbarLeft = (
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
            tagCategories={DAEMON_LOG_TAG_CATEGORIES}
            autoScroll={autoScroll}
            onAutoScrollChange={setAutoScroll}
            toolbarLeft={toolbarLeft}
        />
    );
}
