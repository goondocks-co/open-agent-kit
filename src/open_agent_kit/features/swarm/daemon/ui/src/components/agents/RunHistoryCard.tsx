import { Card, CardContent, CardHeader, CardTitle } from "@oak/ui/components/ui/card";
import {
    AGENT_RUN_STATUS_LABELS,
    AGENT_RUN_STATUS_COLORS,
    type AgentRunStatusType,
} from "@oak/ui/lib/agent-status";
import { formatRelativeTime } from "@oak/ui/lib/time-utils";

interface RunHistoryCardProps {
    runId: string;
    agentName: string;
    taskName?: string;
    status: string;
    createdAt: string;
    completedAt?: string;
    turnsUsed?: number;
    error?: string;
}

export function RunHistoryCard({
    runId,
    agentName,
    taskName,
    status,
    createdAt,
    completedAt,
    turnsUsed,
    error,
}: RunHistoryCardProps) {
    const statusLabel = AGENT_RUN_STATUS_LABELS[status as AgentRunStatusType] ?? status;
    const colors = AGENT_RUN_STATUS_COLORS[status as AgentRunStatusType] ?? AGENT_RUN_STATUS_COLORS.pending;

    return (
        <Card>
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                    <div>
                        <CardTitle className="text-sm">
                            {taskName ?? agentName}
                        </CardTitle>
                        <p className="text-xs text-muted-foreground font-mono mt-0.5">
                            {runId.slice(0, 8)}
                        </p>
                    </div>
                    <span className={`inline-flex items-center gap-1.5 text-xs font-medium px-2 py-0.5 rounded-full ${colors.badge}`}>
                        <span className={`h-1.5 w-1.5 rounded-full ${colors.dot}`} />
                        {statusLabel}
                    </span>
                </div>
            </CardHeader>
            <CardContent>
                <div className="flex gap-4 text-xs text-muted-foreground">
                    <span>Started: {formatRelativeTime(createdAt)}</span>
                    {completedAt && <span>Finished: {formatRelativeTime(completedAt)}</span>}
                    {turnsUsed != null && <span>{turnsUsed} turns</span>}
                </div>
                {error && (
                    <p className="text-xs text-destructive mt-2 truncate">{error}</p>
                )}
            </CardContent>
        </Card>
    );
}
