import { useState, useEffect, useRef } from "react";
import { useLogs, DEFAULT_LOG_LINES, DEFAULT_LOG_FILE } from "@/hooks/use-logs";
import { useConfig, toggleDebugLogging, restartDaemon } from "@/hooks/use-config";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { RefreshCw, Pause, Play, Bug, Loader2, Copy, Check } from "lucide-react";
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
    HooksLogTagType,
    HooksLogTagCategory,
    DaemonLogTagType,
    DaemonLogTagCategory,
} from "@/lib/constants";

/** Union type for all possible log filter tags */
type LogFilterTag = HooksLogTagType | DaemonLogTagType;

/** Delay before refetching logs after restart (ms) */
const RESTART_REFETCH_DELAY_MS = 1000;

/** Log line options for the dropdown */
const LOG_LINE_OPTIONS = [100, 500, 1000, 2000, 5000] as const;

export default function Logs() {
    const [lines, setLines] = useState(DEFAULT_LOG_LINES);
    const [logFile, setLogFile] = useState<LogFileType>(DEFAULT_LOG_FILE);
    const [autoScroll, setAutoScroll] = useState(true);
    const [isTogglingDebug, setIsTogglingDebug] = useState(false);
    const [selectedTags, setSelectedTags] = useState<Set<LogFilterTag>>(new Set());
    const [copied, setCopied] = useState(false);
    const logsEndRef = useRef<HTMLDivElement>(null);
    const queryClient = useQueryClient();

    // When paused (autoScroll=false), disable polling so content stays frozen for copy/paste
    const { data, isLoading, isError, refetch, isFetching } = useLogs(lines, logFile, autoScroll);
    const { data: config } = useConfig();

    const isDebugEnabled = config?.log_level === LOG_LEVELS.DEBUG;

    /** Filter log content by selected tags (OR logic - matches any selected tag) */
    const filterLogsByTags = (content: string): string => {
        if (selectedTags.size === 0) return content;

        return content
            .split("\n")
            .filter((line) => {
                // Keep lines that match any selected tag
                return Array.from(selectedTags).some((tag) => line.includes(tag));
            })
            .join("\n");
    };

    /** Toggle a tag in the selection */
    const handleTagToggle = (tag: LogFilterTag) => {
        const newTags = new Set(selectedTags);
        if (newTags.has(tag)) {
            newTags.delete(tag);
        } else {
            newTags.add(tag);
        }
        setSelectedTags(newTags);
    };

    const handleCopyPath = async () => {
        if (!data?.log_file) return;
        try {
            await navigator.clipboard.writeText(data.log_file);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch (e) {
            console.error("Failed to copy path:", e);
        }
    };

    const handleToggleDebug = async () => {
        if (!config) return;
        setIsTogglingDebug(true);
        try {
            await toggleDebugLogging(config.log_level);
            await restartDaemon();
            queryClient.invalidateQueries({ queryKey: ["config"] });
            // Refetch logs after restart
            setTimeout(() => refetch(), RESTART_REFETCH_DELAY_MS);
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
                    <div className="flex items-center gap-2 mt-1">
                        <p className="text-muted-foreground text-sm font-mono">
                            {data?.log_file || "Loading..."}
                        </p>
                        {data?.log_file && (
                            <button
                                onClick={handleCopyPath}
                                className="p-1 rounded hover:bg-muted transition-colors"
                                title={copied ? "Copied!" : "Copy path to clipboard"}
                            >
                                {copied ? (
                                    <Check className="w-3.5 h-3.5 text-green-500" />
                                ) : (
                                    <Copy className="w-3.5 h-3.5 text-muted-foreground" />
                                )}
                            </button>
                        )}
                    </div>
                </div>

                <div className="flex items-center gap-2">
                    {/* Log File Selector */}
                    <select
                        className="bg-background border border-input rounded-md px-3 py-1 text-sm font-medium"
                        value={logFile}
                        onChange={(e) => {
                            setLogFile(e.target.value as LogFileType);
                            // Clear tag filters when switching log files (tags are hooks-log specific)
                            setSelectedTags(new Set());
                        }}
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
                        title="Number of log lines to display"
                    >
                        {LOG_LINE_OPTIONS.map((option) => (
                            <option key={option} value={option}>{option} lines</option>
                        ))}
                    </select>
                </div>
            </div>

            {/* Tag Filter Chips - different filters for each log type */}
            <div className="flex items-center gap-1 flex-wrap">
                <span className="text-xs text-muted-foreground mr-1">Filter:</span>
                {logFile === LOG_FILES.HOOKS ? (
                    /* Hooks log filters - structured event tags */
                    (Object.entries(HOOKS_LOG_TAG_CATEGORIES) as [HooksLogTagCategory, typeof HOOKS_LOG_TAG_CATEGORIES[HooksLogTagCategory]][]).map(
                        ([category, { tags }], categoryIndex) => (
                            <div key={category} className="flex items-center gap-1">
                                {tags.map((tag) => (
                                    <button
                                        key={tag}
                                        onClick={() => handleTagToggle(tag)}
                                        className={`px-2 py-0.5 text-xs rounded-full border transition-colors ${
                                            selectedTags.has(tag)
                                                ? "bg-primary text-primary-foreground border-primary"
                                                : "bg-background border-input hover:bg-accent"
                                        }`}
                                        title={`Filter to show only ${HOOKS_LOG_TAG_DISPLAY_NAMES[tag]} entries`}
                                    >
                                        {HOOKS_LOG_TAG_DISPLAY_NAMES[tag]}
                                    </button>
                                ))}
                                {categoryIndex < Object.keys(HOOKS_LOG_TAG_CATEGORIES).length - 1 && (
                                    <div className="w-px h-4 bg-border mx-1" />
                                )}
                            </div>
                        )
                    )
                ) : (
                    /* Daemon log filters - log level tags + debug topics */
                    (Object.entries(DAEMON_LOG_TAG_CATEGORIES) as [DaemonLogTagCategory, typeof DAEMON_LOG_TAG_CATEGORIES[DaemonLogTagCategory]][]).map(
                        ([category, { tags }], categoryIndex) => (
                            <div key={category} className="flex items-center gap-1">
                                {tags.map((tag) => (
                                    <button
                                        key={tag}
                                        onClick={() => handleTagToggle(tag)}
                                        className={`px-2 py-0.5 text-xs rounded-full border transition-colors ${
                                            selectedTags.has(tag)
                                                ? "bg-primary text-primary-foreground border-primary"
                                                : "bg-background border-input hover:bg-accent"
                                        }`}
                                        title={`Filter to show only ${DAEMON_LOG_TAG_DISPLAY_NAMES[tag]} entries`}
                                    >
                                        {DAEMON_LOG_TAG_DISPLAY_NAMES[tag]}
                                    </button>
                                ))}
                                {categoryIndex < Object.keys(DAEMON_LOG_TAG_CATEGORIES).length - 1 && (
                                    <div className="w-px h-4 bg-border mx-1" />
                                )}
                            </div>
                        )
                    )
                )}
                {selectedTags.size > 0 && (
                    <button
                        onClick={() => setSelectedTags(new Set())}
                        className="px-2 py-0.5 text-xs text-muted-foreground hover:text-foreground ml-2"
                    >
                        Clear
                    </button>
                )}
            </div>

            <Card className="flex-1 overflow-hidden flex flex-col">
                <CardContent className="flex-1 p-0 overflow-hidden bg-black text-green-400 font-mono text-xs rounded-b-lg">
                    {isLoading ? (
                        <div className="p-4">Loading logs...</div>
                    ) : isError ? (
                        <div className="p-4 text-red-400">Failed to load logs.</div>
                    ) : (
                        <div className="overflow-auto h-full p-4 whitespace-pre-wrap">
                            {filterLogsByTags(data?.content || "") || "No matching logs."}
                            <div ref={logsEndRef} />
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    )
}
