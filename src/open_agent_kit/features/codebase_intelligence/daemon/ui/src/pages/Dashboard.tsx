import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useStatus } from "@/hooks/use-status";
import { useSessions, type SessionItem } from "@/hooks/use-activity";
import { Check, FileCode, Database, Cpu, Clock, Activity, Terminal } from "lucide-react";
import { cn } from "@/lib/utils";

function formatRelativeTime(dateString: string): string {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffSeconds = Math.floor(diffMs / 1000);
    const diffMinutes = Math.floor(diffSeconds / 60);
    const diffHours = Math.floor(diffMinutes / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffSeconds < 60) return "just now";
    if (diffMinutes < 60) return `${diffMinutes}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays === 1) return "yesterday";
    return `${diffDays}d ago`;
}

function SessionRow({ session }: { session: SessionItem }) {
    const isActive = session.status === "active";
    return (
        <div className="flex items-center gap-3 py-2 border-b border-border/50 last:border-0">
            <div className={cn(
                "w-2 h-2 rounded-full flex-shrink-0",
                isActive ? "bg-yellow-500 animate-pulse" : "bg-green-500"
            )} />
            <Terminal className="w-4 h-4 text-muted-foreground flex-shrink-0" />
            <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                    <span className="font-medium text-sm truncate">
                        {session.agent || "claude-code"}
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
            <span className={cn(
                "text-xs px-2 py-0.5 rounded-full flex-shrink-0",
                isActive ? "bg-yellow-500/10 text-yellow-600" : "bg-green-500/10 text-green-600"
            )}>
                {isActive ? "active" : "done"}
            </span>
        </div>
    );
}

const StatCard = ({ title, value, icon: Icon, subtext, loading }: any) => (
    <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{title}</CardTitle>
            <Icon className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
            <div className="text-2xl font-bold">{loading ? "..." : value}</div>
            {subtext && <p className="text-xs text-muted-foreground">{subtext}</p>}
        </CardContent>
    </Card>
);

export default function Dashboard() {
    const { data: status, isLoading, isError } = useStatus();
    const { data: sessionsData, isLoading: sessionsLoading } = useSessions(5);

    const isIndexing = status?.indexing;
    const indexStats = status?.index_stats;
    const sessions = sessionsData?.sessions || [];

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
                    <div className={cn("w-3 h-3 rounded-full transition-colors",
                        isIndexing ? "bg-yellow-500 animate-pulse" : "bg-green-500"
                    )} />
                    <span className="text-sm font-medium">
                        {isIndexing ? "Indexing..." : "System Ready"}
                    </span>
                </div>
            </div>

            {isError && (
                <div className="p-4 rounded-md bg-destructive/10 text-destructive border border-destructive/20">
                    Failed to connect to daemon. Is it running?
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
                    value={status ? `${Math.floor(status.uptime_seconds / 60)}m` : "0m"}
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
                        {sessionsLoading ? (
                            <div className="flex items-center justify-center h-[200px] text-muted-foreground text-sm">
                                Loading sessions...
                            </div>
                        ) : sessions.length === 0 ? (
                            <div className="flex flex-col items-center justify-center h-[200px] text-muted-foreground text-sm border-2 border-dashed rounded-md">
                                <Activity className="w-8 h-8 mb-2 opacity-50" />
                                No sessions recorded yet
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
