import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatCard, StatusDot, StatusBadge } from "@/components/ui/config-components";
import { useStatus } from "@/hooks/use-status";
import { useSessions, type SessionItem } from "@/hooks/use-activity";
import { Check, FileCode, Database, Cpu, Clock, Activity, Terminal } from "lucide-react";
import { cn } from "@/lib/utils";
import {
    formatRelativeTime,
    formatUptime,
    SESSION_STATUS,
    SESSION_STATUS_LABELS,
    SYSTEM_STATUS_LABELS,
    FALLBACK_MESSAGES,
    DEFAULT_AGENT_NAME,
    PAGINATION,
} from "@/lib/constants";

function SessionRow({ session }: { session: SessionItem }) {
    const isActive = session.status === SESSION_STATUS.ACTIVE;
    const statusType = isActive ? "active" : "completed";
    const statusLabel = SESSION_STATUS_LABELS[session.status as keyof typeof SESSION_STATUS_LABELS] || "done";

    return (
        <div className="flex items-center gap-3 py-2 border-b border-border/50 last:border-0">
            <StatusDot status={statusType} />
            <Terminal className="w-4 h-4 text-muted-foreground flex-shrink-0" />
            <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                    <span className="font-medium text-sm truncate">
                        {session.agent || DEFAULT_AGENT_NAME}
                    </span>
                    <span className="text-xs text-muted-foreground">
                        {formatRelativeTime(session.started_at)}
                    </span>
                </div>
                {session.summary ? (
                    <p className="text-xs text-muted-foreground truncate">{session.summary}</p>
                ) : (
                    <p className="text-xs text-muted-foreground">
                        {session.activity_count} {session.activity_count === 1 ? "activity" : "activities"}
                        {session.prompt_batch_count > 0 && ` · ${session.prompt_batch_count} prompts`}
                    </p>
                )}
            </div>
            <StatusBadge status={statusType} label={statusLabel} />
        </div>
    );
}

export default function Dashboard() {
    const { data: status, isLoading, isError } = useStatus();
    const { data: sessionsData, isLoading: sessionsLoading, isError: sessionsError } = useSessions(PAGINATION.DASHBOARD_SESSION_LIMIT);

    const isIndexing = status?.indexing;
    const indexStats = status?.index_stats;
    const sessions = sessionsData?.sessions || [];
    const systemStatus = isIndexing ? "indexing" : "ready";
    const systemStatusLabel = isIndexing ? SYSTEM_STATUS_LABELS.indexing : SYSTEM_STATUS_LABELS.ready;

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight mb-2">Dashboard</h1>
                    <p className="text-muted-foreground">
                        {status?.project_root ? `Project: ${status.project_root.split('/').pop()}` : "Open Agent Kit"}
                    </p>
                </div>

                <div className="flex items-center gap-2">
                    <StatusDot status={systemStatus} className="w-3 h-3" />
                    <span className="text-sm font-medium">
                        {systemStatusLabel}
                    </span>
                </div>
            </div>

            {isError && (
                <div className="p-4 rounded-md bg-destructive/10 text-destructive border border-destructive/20">
                    Failed to connect to daemon. Is it running?
                </div>
            )}

            {!isError && sessionsError && (
                <div className="p-4 rounded-md bg-yellow-500/10 text-yellow-600 dark:text-yellow-400 border border-yellow-500/20">
                    Activity tracking unavailable. Configure embedding and summarization models in Configuration to enable session tracking.
                </div>
            )}

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                <StatCard
                    title="Files Indexed"
                    value={indexStats?.files_indexed || 0}
                    icon={FileCode}
                    subtext={indexStats?.ast_stats?.ast_success ? `${indexStats.ast_stats.ast_success} AST parsed` : "Files in index"}
                    loading={isLoading}
                />
                <StatCard
                    title="Code Chunks"
                    value={indexStats?.chunks_indexed?.toLocaleString() || 0}
                    icon={Database}
                    subtext="Vector embeddings"
                    loading={isLoading}
                />
                <StatCard
                    title="Memories"
                    value={indexStats?.memories_stored || 0}
                    icon={Cpu}
                    subtext="Stored observations"
                    loading={isLoading}
                />
                <StatCard
                    title="Uptime"
                    value={status ? formatUptime(status.uptime_seconds) : "0m"}
                    icon={Clock}
                    subtext="Session duration"
                    loading={isLoading}
                />
            </div>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
                <Card className="col-span-4">
                    <CardHeader className="flex flex-row items-center justify-between">
                        <CardTitle>Recent Sessions</CardTitle>
                        {sessions.length > 0 && (
                            <span className="text-xs text-muted-foreground">
                                {sessionsData?.total || sessions.length} total
                            </span>
                        )}
                    </CardHeader>
                    <CardContent>
                        {sessionsError ? (
                            <div className="flex flex-col items-center justify-center h-[200px] text-muted-foreground text-sm border-2 border-dashed rounded-md">
                                <Activity className="w-8 h-8 mb-2 opacity-50" />
                                <span>Configure models to track sessions</span>
                            </div>
                        ) : sessionsLoading ? (
                            <div className="flex items-center justify-center h-[200px] text-muted-foreground text-sm">
                                {FALLBACK_MESSAGES.LOADING}
                            </div>
                        ) : sessions.length === 0 ? (
                            <div className="flex flex-col items-center justify-center h-[200px] text-muted-foreground text-sm border-2 border-dashed rounded-md">
                                <Activity className="w-8 h-8 mb-2 opacity-50" />
                                {FALLBACK_MESSAGES.NO_SESSIONS}
                            </div>
                        ) : (
                            <div className="space-y-1">
                                {sessions.map((session) => (
                                    <SessionRow key={session.id} session={session} />
                                ))}
                            </div>
                        )}
                    </CardContent>
                </Card>

                <Card className="col-span-3">
                    <CardHeader>
                        <CardTitle>System Health</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-4">
                            <div className="flex items-center justify-between">
                                <span className="text-sm text-muted-foreground">Provider</span>
                                <span className="font-medium text-sm">{status?.embedding_provider || "Unknown"}</span>
                            </div>
                            <div className="flex items-center justify-between">
                                <span className="text-sm text-muted-foreground">File Watcher</span>
                                <span className={cn("text-sm flex items-center gap-1", status?.file_watcher?.running ? "text-green-500" : "text-yellow-500")}>
                                    {status?.file_watcher?.running ? <Check className="w-3 h-3" /> : null}
                                    {status?.file_watcher?.running ? "Active" : "Inactive"}
                                </span>
                            </div>
                            <div className="flex items-center justify-between">
                                <span className="text-sm text-muted-foreground">Pending Changes</span>
                                <span className="font-medium text-sm">{status?.file_watcher?.pending_changes || 0}</span>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    )
}
