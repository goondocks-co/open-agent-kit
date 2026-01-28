/**
 * Agents page for managing CI agents.
 *
 * Features:
 * - List available agents
 * - Trigger agent runs
 * - Monitor run status
 * - View run history
 */

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
    useAgents,
    useAgentRuns,
    useRunAgent,
    useCancelAgentRun,
    useReloadAgents,
    type AgentItem,
    type AgentRun,
    type AgentRunStatus,
} from "@/hooks/use-agents";
import {
    Bot,
    Play,
    Square,
    Clock,
    CheckCircle,
    XCircle,
    AlertCircle,
    RefreshCw,
    Loader2,
    FileText,
    FileEdit,
    ChevronDown,
    ChevronUp,
    DollarSign,
    Timer,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
    formatRelativeTime,
    FALLBACK_MESSAGES,
    AGENT_RUN_STATUS,
    AGENT_RUN_STATUS_LABELS,
    AGENT_RUN_STATUS_COLORS,
} from "@/lib/constants";

// =============================================================================
// Components
// =============================================================================

function AgentCard({
    agent,
    onRun,
    isRunning,
}: {
    agent: AgentItem;
    onRun: (agentName: string, task: string) => void;
    isRunning: boolean;
}) {
    const [task, setTask] = useState("");
    const [expanded, setExpanded] = useState(false);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (task.trim()) {
            onRun(agent.name, task.trim());
            setTask("");
        }
    };

    return (
        <Card>
            <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                        <div className="p-2 rounded-md bg-primary/10">
                            <Bot className="w-5 h-5 text-primary" />
                        </div>
                        <div>
                            <CardTitle className="text-lg">{agent.display_name}</CardTitle>
                            <CardDescription className="mt-1">{agent.description}</CardDescription>
                        </div>
                    </div>
                    <button
                        onClick={() => setExpanded(!expanded)}
                        className="p-1 rounded hover:bg-muted transition-colors"
                    >
                        {expanded ? (
                            <ChevronUp className="w-4 h-4 text-muted-foreground" />
                        ) : (
                            <ChevronDown className="w-4 h-4 text-muted-foreground" />
                        )}
                    </button>
                </div>
            </CardHeader>

            {expanded && (
                <CardContent className="pt-0 pb-3">
                    <div className="flex gap-4 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1">
                            <Timer className="w-3 h-3" />
                            Max {agent.max_turns} turns
                        </span>
                        <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {Math.floor(agent.timeout_seconds / 60)}m timeout
                        </span>
                    </div>
                </CardContent>
            )}

            <CardFooter className="pt-0">
                <form onSubmit={handleSubmit} className="flex gap-2 w-full">
                    <input
                        type="text"
                        value={task}
                        onChange={(e) => setTask(e.target.value)}
                        placeholder="Enter task description..."
                        className="flex-1 px-3 py-2 text-sm rounded-md border bg-background focus:outline-none focus:ring-2 focus:ring-primary/50"
                        disabled={isRunning}
                    />
                    <Button type="submit" size="sm" disabled={!task.trim() || isRunning}>
                        {isRunning ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                            <Play className="w-4 h-4" />
                        )}
                        <span className="ml-1">Run</span>
                    </Button>
                </form>
            </CardFooter>
        </Card>
    );
}

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
    isCancelling,
}: {
    run: AgentRun;
    onCancel: (runId: string) => void;
    isCancelling: boolean;
}) {
    const [expanded, setExpanded] = useState(false);
    const isActive = run.status === AGENT_RUN_STATUS.PENDING || run.status === AGENT_RUN_STATUS.RUNNING;
    const statusLabel = AGENT_RUN_STATUS_LABELS[run.status] || run.status;
    const statusColors = AGENT_RUN_STATUS_COLORS[run.status] || AGENT_RUN_STATUS_COLORS.pending;

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
                    {isActive && (
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
                    {run.error && (
                        <div className="p-2 rounded bg-red-500/10 text-red-600 text-xs">
                            <strong>Error:</strong> {run.error}
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
                        <div className="flex gap-4 text-xs">
                            {run.files_created.length > 0 && (
                                <div className="flex items-center gap-1 text-green-600">
                                    <FileText className="w-3 h-3" />
                                    {run.files_created.length} created
                                </div>
                            )}
                            {run.files_modified.length > 0 && (
                                <div className="flex items-center gap-1 text-blue-600">
                                    <FileEdit className="w-3 h-3" />
                                    {run.files_modified.length} modified
                                </div>
                            )}
                        </div>
                    )}

                    {run.duration_seconds !== undefined && (
                        <div className="text-xs text-muted-foreground">
                            Duration: {run.duration_seconds.toFixed(1)}s
                        </div>
                    )}

                    <div className="text-xs text-muted-foreground">
                        Run ID: <code className="bg-muted px-1 rounded">{run.id}</code>
                    </div>
                </div>
            )}
        </div>
    );
}

// =============================================================================
// Main Page
// =============================================================================

export default function Agents() {
    const { data: agentsData, isLoading: agentsLoading, isError: agentsError } = useAgents();
    const { data: runsData, isLoading: runsLoading } = useAgentRuns(20);
    const runAgent = useRunAgent();
    const cancelRun = useCancelAgentRun();
    const reloadAgents = useReloadAgents();

    const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

    const agents = agentsData?.agents || [];
    const runs = runsData?.runs || [];

    const handleRunAgent = async (agentName: string, task: string) => {
        setMessage(null);
        try {
            const result = await runAgent.mutateAsync({ agentName, task });
            setMessage({ type: "success", text: result.message });
        } catch (error) {
            setMessage({
                type: "error",
                text: error instanceof Error ? error.message : "Failed to start agent",
            });
        }
    };

    const handleCancelRun = async (runId: string) => {
        try {
            await cancelRun.mutateAsync(runId);
        } catch (error) {
            setMessage({
                type: "error",
                text: error instanceof Error ? error.message : "Failed to cancel run",
            });
        }
    };

    const handleReload = async () => {
        try {
            const result = await reloadAgents.mutateAsync();
            setMessage({ type: "success", text: result.message });
        } catch (error) {
            setMessage({
                type: "error",
                text: error instanceof Error ? error.message : "Failed to reload agents",
            });
        }
    };

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex justify-between items-start">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight mb-2">Agents</h1>
                    <p className="text-muted-foreground">
                        Autonomous agents powered by Claude Code SDK
                    </p>
                </div>
                <Button
                    variant="outline"
                    size="sm"
                    onClick={handleReload}
                    disabled={reloadAgents.isPending}
                >
                    {reloadAgents.isPending ? (
                        <Loader2 className="w-4 h-4 animate-spin mr-1" />
                    ) : (
                        <RefreshCw className="w-4 h-4 mr-1" />
                    )}
                    Reload
                </Button>
            </div>

            {/* Messages */}
            {message && (
                <Alert variant={message.type === "error" ? "destructive" : "default"}>
                    <AlertDescription>{message.text}</AlertDescription>
                </Alert>
            )}

            {/* Error state */}
            {agentsError && (
                <div className="p-4 rounded-md bg-destructive/10 text-destructive border border-destructive/20">
                    Failed to load agents. Make sure the daemon is running and agents are enabled in config.
                </div>
            )}

            {/* Agents list */}
            <div>
                <h2 className="text-xl font-semibold mb-4">Available Agents</h2>
                {agentsLoading ? (
                    <div className="flex items-center justify-center h-32 text-muted-foreground">
                        <Loader2 className="w-5 h-5 animate-spin mr-2" />
                        {FALLBACK_MESSAGES.LOADING}
                    </div>
                ) : agents.length === 0 ? (
                    <Card>
                        <CardContent className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                            <Bot className="w-12 h-12 mb-4 opacity-30" />
                            <p className="text-sm">No agents available</p>
                            <p className="text-xs mt-1">
                                Add agent definitions to the agents/definitions directory
                            </p>
                        </CardContent>
                    </Card>
                ) : (
                    <div className="grid gap-4 md:grid-cols-2">
                        {agents.map((agent) => (
                            <AgentCard
                                key={agent.name}
                                agent={agent}
                                onRun={handleRunAgent}
                                isRunning={runAgent.isPending}
                            />
                        ))}
                    </div>
                )}
            </div>

            {/* Run history */}
            <div>
                <div className="flex items-center justify-between mb-4">
                    <h2 className="text-xl font-semibold">Run History</h2>
                    {runsData?.total !== undefined && runsData.total > 0 && (
                        <span className="text-sm text-muted-foreground">
                            {runsData.total} total runs
                        </span>
                    )}
                </div>

                {runsLoading ? (
                    <div className="flex items-center justify-center h-32 text-muted-foreground">
                        <Loader2 className="w-5 h-5 animate-spin mr-2" />
                        {FALLBACK_MESSAGES.LOADING}
                    </div>
                ) : runs.length === 0 ? (
                    <Card>
                        <CardContent className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                            <Clock className="w-12 h-12 mb-4 opacity-30" />
                            <p className="text-sm">No runs yet</p>
                            <p className="text-xs mt-1">
                                Start an agent to see run history here
                            </p>
                        </CardContent>
                    </Card>
                ) : (
                    <div className="space-y-2">
                        {runs.map((run) => (
                            <RunRow
                                key={run.id}
                                run={run}
                                onCancel={handleCancelRun}
                                isCancelling={cancelRun.isPending}
                            />
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
