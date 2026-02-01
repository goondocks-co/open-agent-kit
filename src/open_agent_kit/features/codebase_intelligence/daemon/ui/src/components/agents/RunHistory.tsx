/**
 * Run history component for viewing agent execution history.
 *
 * Features:
 * - List all agent runs with pagination
 * - Filter by agent name and status
 * - View run details
 * - Cancel active runs
 */

import { useState, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
    useAgents,
    useAgentRuns,
    useCancelAgentRun,
    useRunAgent,
    type AgentRun,
    type AgentRunStatus,
} from "@/hooks/use-agents";
import {
    Clock,
    CheckCircle,
    XCircle,
    AlertCircle,
    Square,
    RefreshCw,
    Loader2,
    FileText,
    FileEdit,
    ChevronDown,
    ChevronUp,
    DollarSign,
    History,
    ChevronLeft,
    ChevronRight,
    Filter,
    X,
    RotateCcw,
    ShieldAlert,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
    formatRelativeTime,
    AGENT_RUN_STATUS,
    AGENT_RUN_STATUS_LABELS,
    AGENT_RUN_STATUS_COLORS,
    isWatchdogRecoveredRun,
} from "@/lib/constants";

// =============================================================================
// Components
// =============================================================================

function RunStatusIcon({ status }: { status: AgentRunStatus }) {
    switch (status) {
        case AGENT_RUN_STATUS.PENDING:
            return <Clock className="w-4 h-4 text-muted-foreground" />;
        case AGENT_RUN_STATUS.RUNNING:
            return <Loader2 className="w-4 h-4 text-yellow-500 animate-spin" />;
        case AGENT_RUN_STATUS.COMPLETED:
            return <CheckCircle className="w-4 h-4 text-green-500" />;
        case AGENT_RUN_STATUS.FAILED:
            return <XCircle className="w-4 h-4 text-red-500" />;
        case AGENT_RUN_STATUS.CANCELLED:
            return <Square className="w-4 h-4 text-gray-500" />;
        case AGENT_RUN_STATUS.TIMEOUT:
            return <AlertCircle className="w-4 h-4 text-orange-500" />;
        default:
            return <Clock className="w-4 h-4 text-muted-foreground" />;
    }
}

function RunRow({
    run,
    onCancel,
    onRerun,
    isCancelling,
    isRerunning,
}: {
    run: AgentRun;
    onCancel: (runId: string) => void;
    onRerun: (agentName: string, task: string) => void;
    isCancelling: boolean;
    isRerunning: boolean;
}) {
    const [expanded, setExpanded] = useState(false);
    const isActive = run.status === AGENT_RUN_STATUS.PENDING || run.status === AGENT_RUN_STATUS.RUNNING;
    const statusLabel = AGENT_RUN_STATUS_LABELS[run.status] || run.status;
    const statusColors = AGENT_RUN_STATUS_COLORS[run.status] || AGENT_RUN_STATUS_COLORS.pending;
    const wasRecoveredByWatchdog = isWatchdogRecoveredRun(run.error);

    return (
        <div className="border rounded-md overflow-hidden">
            <div
                className="flex items-center gap-3 p-3 hover:bg-accent/5 cursor-pointer"
                onClick={() => setExpanded(!expanded)}
            >
                <RunStatusIcon status={run.status} />
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                        <span className="font-medium text-sm">{run.agent_name}</span>
                        <span className={cn("px-2 py-0.5 text-xs rounded-full", statusColors.badge)}>
                            {statusLabel}
                        </span>
                        {wasRecoveredByWatchdog && (
                            <span className="flex items-center gap-1 px-2 py-0.5 text-xs rounded-full bg-amber-500/10 text-amber-600" title="This run was recovered by the watchdog after being stuck">
                                <ShieldAlert className="w-3 h-3" />
                                Recovered
                            </span>
                        )}
                        <span className="text-xs text-muted-foreground">
                            {formatRelativeTime(run.created_at)}
                        </span>
                    </div>
                    <p className="text-xs text-muted-foreground truncate mt-0.5">{run.task}</p>
                </div>
                <div className="flex items-center gap-2">
                    {run.turns_used > 0 && (
                        <span className="text-xs text-muted-foreground">{run.turns_used} turns</span>
                    )}
                    {run.cost_usd !== undefined && run.cost_usd > 0 && (
                        <span className="text-xs text-muted-foreground flex items-center gap-0.5">
                            <DollarSign className="w-3 h-3" />
                            {run.cost_usd.toFixed(4)}
                        </span>
                    )}
                    {isActive ? (
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={(e) => {
                                e.stopPropagation();
                                onCancel(run.id);
                            }}
                            disabled={isCancelling}
                            className="h-7 px-2"
                        >
                            {isCancelling ? (
                                <Loader2 className="w-3 h-3 animate-spin" />
                            ) : (
                                <Square className="w-3 h-3" />
                            )}
                            <span className="ml-1 text-xs">Cancel</span>
                        </Button>
                    ) : (
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={(e) => {
                                e.stopPropagation();
                                onRerun(run.agent_name, run.task);
                            }}
                            disabled={isRerunning}
                            className="h-7 px-2"
                        >
                            {isRerunning ? (
                                <Loader2 className="w-3 h-3 animate-spin" />
                            ) : (
                                <RotateCcw className="w-3 h-3" />
                            )}
                            <span className="ml-1 text-xs">Re-run</span>
                        </Button>
                    )}
                    {expanded ? (
                        <ChevronUp className="w-4 h-4 text-muted-foreground" />
                    ) : (
                        <ChevronDown className="w-4 h-4 text-muted-foreground" />
                    )}
                </div>
            </div>

            {expanded && (
                <div className="border-t bg-muted/30 p-3 space-y-3">
                    {/* Task */}
                    <div className="space-y-1">
                        <span className="text-xs font-medium text-muted-foreground">Task:</span>
                        <p className="text-sm">{run.task}</p>
                    </div>

                    {run.error && (
                        <div className={cn(
                            "p-2 rounded text-xs",
                            wasRecoveredByWatchdog
                                ? "bg-amber-500/10 text-amber-700"
                                : "bg-red-500/10 text-red-600"
                        )}>
                            {wasRecoveredByWatchdog ? (
                                <>
                                    <strong className="flex items-center gap-1">
                                        <ShieldAlert className="w-3 h-3" />
                                        Watchdog Recovery:
                                    </strong>
                                    <span className="ml-4">
                                        This run was stuck and recovered by the background watchdog process.
                                        The agent may have hung or the daemon was restarted during execution.
                                    </span>
                                </>
                            ) : (
                                <>
                                    <strong>Error:</strong> {run.error}
                                </>
                            )}
                        </div>
                    )}

                    {run.result && (
                        <div className="space-y-1">
                            <span className="text-xs font-medium text-muted-foreground">Result:</span>
                            <pre className="p-2 rounded bg-background text-xs whitespace-pre-wrap max-h-48 overflow-y-auto">
                                {run.result}
                            </pre>
                        </div>
                    )}

                    {(run.files_created.length > 0 || run.files_modified.length > 0) && (
                        <div className="space-y-2">
                            {run.files_created.length > 0 && (
                                <div>
                                    <span className="text-xs font-medium text-green-600 flex items-center gap-1 mb-1">
                                        <FileText className="w-3 h-3" />
                                        Files Created ({run.files_created.length})
                                    </span>
                                    <div className="text-xs text-muted-foreground space-y-0.5">
                                        {run.files_created.map((f, i) => (
                                            <div key={i} className="font-mono bg-muted/50 px-2 py-0.5 rounded">{f}</div>
                                        ))}
                                    </div>
                                </div>
                            )}
                            {run.files_modified.length > 0 && (
                                <div>
                                    <span className="text-xs font-medium text-blue-600 flex items-center gap-1 mb-1">
                                        <FileEdit className="w-3 h-3" />
                                        Files Modified ({run.files_modified.length})
                                    </span>
                                    <div className="text-xs text-muted-foreground space-y-0.5">
                                        {run.files_modified.map((f, i) => (
                                            <div key={i} className="font-mono bg-muted/50 px-2 py-0.5 rounded">{f}</div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    <div className="flex gap-4 text-xs text-muted-foreground pt-2 border-t">
                        {run.duration_seconds !== undefined && (
                            <span>Duration: {run.duration_seconds.toFixed(1)}s</span>
                        )}
                        <span>Run ID: <code className="bg-muted px-1 rounded">{run.id}</code></span>
                    </div>
                </div>
            )}
        </div>
    );
}

// =============================================================================
// Filter Bar Component
// =============================================================================

interface FilterBarProps {
    agentNames: string[];
    selectedAgent: string | undefined;
    selectedStatus: AgentRunStatus | undefined;
    onAgentChange: (agent: string | undefined) => void;
    onStatusChange: (status: AgentRunStatus | undefined) => void;
    onClear: () => void;
    hasFilters: boolean;
}

function FilterBar({
    agentNames,
    selectedAgent,
    selectedStatus,
    onAgentChange,
    onStatusChange,
    onClear,
    hasFilters,
}: FilterBarProps) {
    const statusOptions = Object.entries(AGENT_RUN_STATUS_LABELS) as [AgentRunStatus, string][];

    return (
        <div className="flex items-center gap-3 p-3 bg-muted/30 rounded-lg border">
            <Filter className="w-4 h-4 text-muted-foreground flex-shrink-0" />

            {/* Agent filter */}
            <div className="flex items-center gap-2">
                <label className="text-xs text-muted-foreground">Agent:</label>
                <select
                    value={selectedAgent || ""}
                    onChange={(e) => onAgentChange(e.target.value || undefined)}
                    className="text-sm px-2 py-1 rounded border bg-background min-w-[120px]"
                >
                    <option value="">All agents</option>
                    {agentNames.map((name) => (
                        <option key={name} value={name}>
                            {name}
                        </option>
                    ))}
                </select>
            </div>

            {/* Status filter */}
            <div className="flex items-center gap-2">
                <label className="text-xs text-muted-foreground">Status:</label>
                <select
                    value={selectedStatus || ""}
                    onChange={(e) => onStatusChange((e.target.value || undefined) as AgentRunStatus | undefined)}
                    className="text-sm px-2 py-1 rounded border bg-background min-w-[120px]"
                >
                    <option value="">All statuses</option>
                    {statusOptions.map(([value, label]) => (
                        <option key={value} value={value}>
                            {label}
                        </option>
                    ))}
                </select>
            </div>

            {/* Clear filters */}
            {hasFilters && (
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={onClear}
                    className="h-7 px-2 text-xs"
                >
                    <X className="w-3 h-3 mr-1" />
                    Clear
                </Button>
            )}
        </div>
    );
}

// =============================================================================
// Main Component
// =============================================================================

const PAGE_SIZE = 20;

export default function RunHistory() {
    const queryClient = useQueryClient();
    const [offset, setOffset] = useState(0);
    const [agentFilter, setAgentFilter] = useState<string | undefined>();
    const [statusFilter, setStatusFilter] = useState<AgentRunStatus | undefined>();

    // Fetch agents for filter dropdown
    const { data: agentsData } = useAgents();
    const agentNames = agentsData?.agents?.map((a) => a.name) || [];

    // Fetch runs with filters
    const { data: runsData, isLoading, isFetching } = useAgentRuns(
        PAGE_SIZE,
        offset,
        agentFilter,
        statusFilter
    );
    const cancelRun = useCancelAgentRun();
    const runAgent = useRunAgent();

    const runs = runsData?.runs || [];
    const total = runsData?.total || 0;

    // Check if there are active runs for showing auto-refresh indicator
    const hasActiveRuns = runs.some(
        (run) => run.status === "pending" || run.status === "running"
    );

    const hasFilters = !!(agentFilter || statusFilter);

    // Manual refresh
    const handleRefresh = useCallback(() => {
        queryClient.invalidateQueries({ queryKey: ["agent-runs"] });
    }, [queryClient]);

    const handleCancelRun = async (runId: string) => {
        try {
            await cancelRun.mutateAsync(runId);
        } catch {
            // Error handling is in the mutation
        }
    };

    const handleRerun = async (agentName: string, task: string) => {
        try {
            await runAgent.mutateAsync({ agentName, task });
        } catch {
            // Error handling is in the mutation
        }
    };

    // Filter handlers - reset pagination when filters change
    const handleAgentChange = (agent: string | undefined) => {
        setAgentFilter(agent);
        setOffset(0);
    };

    const handleStatusChange = (status: AgentRunStatus | undefined) => {
        setStatusFilter(status);
        setOffset(0);
    };

    const handleClearFilters = () => {
        setAgentFilter(undefined);
        setStatusFilter(undefined);
        setOffset(0);
    };

    // Pagination
    const totalPages = Math.ceil(total / PAGE_SIZE);
    const currentPage = Math.floor(offset / PAGE_SIZE) + 1;

    const handlePrevPage = () => {
        if (offset > 0) {
            setOffset(Math.max(0, offset - PAGE_SIZE));
        }
    };

    const handleNextPage = () => {
        if (offset + PAGE_SIZE < total) {
            setOffset(offset + PAGE_SIZE);
        }
    };

    return (
        <div className="space-y-4">
            {/* Filter bar - always visible */}
            <FilterBar
                agentNames={agentNames}
                selectedAgent={agentFilter}
                selectedStatus={statusFilter}
                onAgentChange={handleAgentChange}
                onStatusChange={handleStatusChange}
                onClear={handleClearFilters}
                hasFilters={hasFilters}
            />

            {/* Header with refresh and count */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    {hasActiveRuns && (
                        <span className="flex items-center gap-1 text-xs text-yellow-600 bg-yellow-500/10 px-2 py-0.5 rounded-full">
                            <Loader2 className="w-3 h-3 animate-spin" />
                            Auto-refreshing
                        </span>
                    )}
                    {!isLoading && (
                        <span className="text-sm text-muted-foreground">
                            {total} {total === 1 ? "run" : "runs"}
                            {hasFilters && " (filtered)"}
                        </span>
                    )}
                </div>
                <Button
                    variant="outline"
                    size="sm"
                    onClick={handleRefresh}
                    disabled={isFetching}
                >
                    <RefreshCw className={cn("w-4 h-4 mr-1", isFetching && "animate-spin")} />
                    Refresh
                </Button>
            </div>

            {/* Runs list */}
            {isLoading ? (
                <div className="space-y-2">
                    {/* Loading skeleton */}
                    {[1, 2, 3].map((i) => (
                        <div key={i} className="border rounded-md p-3 animate-pulse">
                            <div className="flex items-center gap-3">
                                <div className="w-4 h-4 bg-muted rounded-full" />
                                <div className="flex-1">
                                    <div className="h-4 bg-muted rounded w-1/4 mb-2" />
                                    <div className="h-3 bg-muted rounded w-3/4" />
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            ) : runs.length === 0 ? (
                <Card>
                    <CardContent className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                        <History className="w-12 h-12 mb-4 opacity-30" />
                        <p className="text-sm">
                            {hasFilters ? "No runs match your filters" : "No runs yet"}
                        </p>
                        <p className="text-xs mt-1">
                            {hasFilters
                                ? "Try adjusting your filters or clear them"
                                : "Start an agent from the Agents tab to see run history here"}
                        </p>
                        {hasFilters && (
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={handleClearFilters}
                                className="mt-4"
                            >
                                Clear Filters
                            </Button>
                        )}
                    </CardContent>
                </Card>
            ) : (
                <>
                    <div className="space-y-2">
                        {runs.map((run) => (
                            <RunRow
                                key={run.id}
                                run={run}
                                onCancel={handleCancelRun}
                                onRerun={handleRerun}
                                isCancelling={cancelRun.isPending}
                                isRerunning={runAgent.isPending}
                            />
                        ))}
                    </div>

                    {/* Pagination */}
                    {totalPages > 1 && (
                        <div className="flex items-center justify-center gap-2 pt-4">
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={handlePrevPage}
                                disabled={offset === 0}
                            >
                                <ChevronLeft className="w-4 h-4" />
                            </Button>
                            <span className="text-sm text-muted-foreground px-4">
                                Page {currentPage} of {totalPages}
                            </span>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={handleNextPage}
                                disabled={offset + PAGE_SIZE >= total}
                            >
                                <ChevronRight className="w-4 h-4" />
                            </Button>
                        </div>
                    )}
                </>
            )}
        </div>
    );
}
