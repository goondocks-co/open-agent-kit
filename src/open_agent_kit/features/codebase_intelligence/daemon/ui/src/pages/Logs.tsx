import { useState, useEffect, useRef } from "react";
import { useLogs } from "@/hooks/use-logs";
import { useConfig, toggleDebugLogging, restartDaemon } from "@/hooks/use-config";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { RefreshCw, Pause, Play, Bug, Loader2 } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";

export default function Logs() {
    const [lines, setLines] = useState(100);
    const [autoScroll, setAutoScroll] = useState(true);
    const [isTogglingDebug, setIsTogglingDebug] = useState(false);
    const logsEndRef = useRef<HTMLDivElement>(null);
    const queryClient = useQueryClient();

    const { data, isLoading, isError, refetch, isFetching } = useLogs(lines);
    const { data: config } = useConfig();

    const isDebugEnabled = config?.log_level === "DEBUG";

    const handleToggleDebug = async () => {
        if (!config) return;
        setIsTogglingDebug(true);
        try {
            await toggleDebugLogging(config.log_level);
            await restartDaemon();
            queryClient.invalidateQueries({ queryKey: ["config"] });
            // Refetch logs after restart
            setTimeout(() => refetch(), 1000);
        } catch (e) {
            console.error("Failed to toggle debug:", e);
        } finally {
            setIsTogglingDebug(false);
        }
    };

    // Auto-scroll to bottom when data changes
    useEffect(() => {
        if (autoScroll && logsEndRef.current) {
            logsEndRef.current.scrollIntoView({ behavior: "smooth" });
        }
    }, [data, autoScroll]);

    return (
        <div className="space-y-6 h-[calc(100vh-8rem)] flex flex-col">
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight">System Logs</h1>
                    <p className="text-muted-foreground text-sm font-mono mt-1">
                        {data?.log_file || "Loading..."}
                    </p>
                </div>

                <div className="flex items-center gap-2">
                    <Button
                        variant={isDebugEnabled ? "default" : "outline"}
                        size="sm"
                        onClick={handleToggleDebug}
                        disabled={isTogglingDebug}
                        title={isDebugEnabled ? "Debug logging enabled - click to disable" : "Enable debug logging for detailed output"}
                    >
                        {isTogglingDebug ? (
                            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        ) : (
                            <Bug className="w-4 h-4 mr-2" />
                        )}
                        {isDebugEnabled ? "Debug On" : "Debug Off"}
                    </Button>
                    <div className="w-px h-6 bg-border" />
                    <Button variant="outline" size="sm" onClick={() => setAutoScroll(!autoScroll)}>
                        {autoScroll ? <Pause className="w-4 h-4 mr-2" /> : <Play className="w-4 h-4 mr-2" />}
                        {autoScroll ? "Pause Scroll" : "Resume Scroll"}
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching}>
                        <RefreshCw className={`w-4 h-4 mr-2 ${isFetching ? "animate-spin" : ""}`} />
                        Refresh
                    </Button>
                    <select
                        className="bg-background border border-input rounded-md px-3 py-1 text-sm"
                        value={lines}
                        onChange={(e) => setLines(Number(e.target.value))}
                    >
                        <option value={50}>50 lines</option>
                        <option value={100}>100 lines</option>
                        <option value={500}>500 lines</option>
                    </select>
                </div>
            </div>

            <Card className="flex-1 overflow-hidden flex flex-col">
                <CardContent className="flex-1 p-0 overflow-hidden bg-black text-green-400 font-mono text-xs rounded-b-lg">
                    {isLoading ? (
                        <div className="p-4">Loading logs...</div>
                    ) : isError ? (
                        <div className="p-4 text-red-400">Failed to load logs.</div>
                    ) : (
                        <div className="overflow-auto h-full p-4 whitespace-pre-wrap">
                            {data?.content || "No logs available."}
                            <div ref={logsEndRef} />
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    )
}
