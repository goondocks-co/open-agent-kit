import { Card, CardContent, CardHeader, CardTitle } from "@oak/ui/components/ui/card";
import { Badge } from "@oak/ui/components/ui/badge";
import { Clock, CheckCircle, XCircle, Loader2 } from "lucide-react";

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

const STATUS_CONFIG: Record<string, { icon: React.ComponentType<{ className?: string }>; variant: "default" | "secondary" | "destructive" | "outline" }> = {
    running: { icon: Loader2, variant: "default" },
    completed: { icon: CheckCircle, variant: "secondary" },
    failed: { icon: XCircle, variant: "destructive" },
    cancelled: { icon: XCircle, variant: "outline" },
    timeout: { icon: Clock, variant: "destructive" },
    pending: { icon: Clock, variant: "outline" },
};

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
    const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.pending;
    const StatusIcon = config.icon;

    const formatTime = (iso: string) => {
        try {
            return new Date(iso).toLocaleString();
        } catch {
            return iso;
        }
    };

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
                    <Badge variant={config.variant} className="flex items-center gap-1">
                        <StatusIcon className={`h-3 w-3 ${status === "running" ? "animate-spin" : ""}`} />
                        {status}
                    </Badge>
                </div>
            </CardHeader>
            <CardContent>
                <div className="flex gap-4 text-xs text-muted-foreground">
                    <span>Started: {formatTime(createdAt)}</span>
                    {completedAt && <span>Finished: {formatTime(completedAt)}</span>}
                    {turnsUsed != null && <span>{turnsUsed} turns</span>}
                </div>
                {error && (
                    <p className="text-xs text-destructive mt-2 truncate">{error}</p>
                )}
            </CardContent>
        </Card>
    );
}
