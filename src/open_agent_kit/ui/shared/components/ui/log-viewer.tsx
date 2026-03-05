/**
 * Shared terminal-style log viewer component.
 *
 * Used by both team and swarm daemon UIs for consistent log viewing
 * with pause/resume, tag filtering, line count selection, and auto-scroll.
 */

import { useState, useEffect, useRef, useMemo } from "react";
import { Button } from "./button";
import { Card, CardContent } from "./card";
import { CopyButton } from "./command-block";
import { RefreshCw, Pause, Play } from "lucide-react";
import type { TagCategory } from "../../lib/log-constants";
import { DEFAULT_LINE_COUNT_OPTIONS } from "../../lib/log-constants";

export interface LogViewerProps {
    lines: string[];
    path: string | null;
    totalLines?: number;
    isLoading: boolean;
    isError: boolean;
    isFetching: boolean;
    onRefresh: () => void;
    lineCount: number;
    onLineCountChange: (count: number) => void;
    lineCountOptions?: readonly number[];
    tagCategories?: TagCategory[];
    autoScroll: boolean;
    onAutoScrollChange: (autoScroll: boolean) => void;
    toolbarLeft?: React.ReactNode;
}

export function LogViewer({
    lines,
    path,
    totalLines,
    isLoading,
    isError,
    isFetching,
    onRefresh,
    lineCount,
    onLineCountChange,
    lineCountOptions = DEFAULT_LINE_COUNT_OPTIONS,
    tagCategories,
    autoScroll,
    onAutoScrollChange,
    toolbarLeft,
}: LogViewerProps) {
    const [selectedTags, setSelectedTags] = useState<Set<string>>(new Set());
    const logsEndRef = useRef<HTMLDivElement>(null);

    const filteredLines = useMemo(() => {
        if (selectedTags.size === 0) return lines;
        return lines.filter((line) =>
            Array.from(selectedTags).some((tag) => line.includes(tag))
        );
    }, [lines, selectedTags]);

    const handleTagToggle = (tag: string) => {
        setSelectedTags((prev) => {
            const next = new Set(prev);
            if (next.has(tag)) {
                next.delete(tag);
            } else {
                next.add(tag);
            }
            return next;
        });
    };

    useEffect(() => {
        if (autoScroll && logsEndRef.current) {
            logsEndRef.current.scrollIntoView({ behavior: "smooth" });
        }
    }, [lines, autoScroll]);

    return (
        <div className="space-y-4 h-[calc(100vh-8rem)] flex flex-col">
            {/* Header row */}
            <div className="flex justify-between items-center gap-4">
                <div className="min-w-0 flex-1">
                    <h1 className="text-3xl font-bold tracking-tight">System Logs</h1>
                    <div className="flex items-center gap-2 mt-1">
                        <p className="text-muted-foreground text-sm font-mono truncate">
                            {path || "Loading..."}
                        </p>
                        {path && <CopyButton text={path} />}
                        {totalLines !== undefined && (
                            <span className="text-muted-foreground text-xs whitespace-nowrap">
                                ({totalLines.toLocaleString()} total lines)
                            </span>
                        )}
                    </div>
                </div>

                <div className="flex items-center gap-2 flex-shrink-0">
                    {toolbarLeft}
                    {toolbarLeft && <div className="w-px h-6 bg-border" />}
                    <Button variant="outline" size="sm" onClick={() => onAutoScrollChange(!autoScroll)}>
                        {autoScroll ? <Pause className="w-4 h-4 mr-2" /> : <Play className="w-4 h-4 mr-2" />}
                        {autoScroll ? "Pause" : "Resume"}
                    </Button>
                    <Button variant="outline" size="sm" onClick={onRefresh} disabled={isFetching}>
                        <RefreshCw className={`w-4 h-4 mr-2 ${isFetching ? "animate-spin" : ""}`} />
                        Refresh
                    </Button>
                    <select
                        className="bg-background border border-input rounded-md px-3 py-1 text-sm"
                        value={lineCount}
                        onChange={(e) => onLineCountChange(Number(e.target.value))}
                        title="Number of log lines to display"
                    >
                        {lineCountOptions.map((option) => (
                            <option key={option} value={option}>{option} lines</option>
                        ))}
                    </select>
                </div>
            </div>

            {/* Tag filter chips */}
            {tagCategories && tagCategories.length > 0 && (
                <div className="flex items-center gap-1 flex-wrap">
                    <span className="text-xs text-muted-foreground mr-1">Filter:</span>
                    {tagCategories.map((category, categoryIndex) => (
                        <div key={category.label} className="flex items-center gap-1">
                            {category.tags.map((tag) => (
                                <button
                                    key={tag.value}
                                    onClick={() => handleTagToggle(tag.value)}
                                    className={`px-2 py-0.5 text-xs rounded-full border transition-colors ${
                                        selectedTags.has(tag.value)
                                            ? "bg-primary text-primary-foreground border-primary"
                                            : "bg-background border-input hover:bg-accent"
                                    }`}
                                    title={`Filter to show only ${tag.display} entries`}
                                >
                                    {tag.display}
                                </button>
                            ))}
                            {categoryIndex < tagCategories.length - 1 && (
                                <div className="w-px h-4 bg-border mx-1" />
                            )}
                        </div>
                    ))}
                    {selectedTags.size > 0 && (
                        <button
                            onClick={() => setSelectedTags(new Set())}
                            className="px-2 py-0.5 text-xs text-muted-foreground hover:text-foreground ml-2"
                        >
                            Clear
                        </button>
                    )}
                </div>
            )}

            {/* Terminal card */}
            <Card className="flex-1 overflow-hidden flex flex-col">
                <CardContent className="flex-1 p-0 overflow-hidden bg-black text-green-400 font-mono text-xs rounded-b-lg">
                    {isLoading ? (
                        <div className="p-4">Loading logs...</div>
                    ) : isError ? (
                        <div className="p-4 text-red-400">Failed to load logs.</div>
                    ) : (
                        <div className="overflow-auto h-full p-4 whitespace-pre-wrap">
                            {filteredLines.length > 0
                                ? filteredLines.join("\n")
                                : "No matching logs."}
                            <div ref={logsEndRef} />
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}
