import { Link } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatCard, StatusDot, StatusBadge } from "@/components/ui/config-components";
import { useStatus } from "@/hooks/use-status";
import { useSessions, type SessionItem } from "@/hooks/use-activity";
import { usePlans } from "@/hooks/use-plans";
import { Check, FileCode, Brain, Clock, Activity, Terminal, ArrowRight, ClipboardList, Layers, HardDrive, Save, Share2 } from "lucide-react";
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
        <Link
            to={`/activity/sessions/${session.id}`}
            className="flex items-center gap-3 py-2 border-b border-border/50 last:border-0 hover:bg-accent/5 rounded-md px-2 -mx-2 transition-colors group"
        >
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
                {session.title ? (
                    <p className="text-xs text-muted-foreground truncate">{session.title}</p>
                ) : session.first_prompt_preview ? (
                    <p className="text-xs text-muted-foreground truncate">{session.first_prompt_preview}</p>
                ) : session.summary ? (
                    <p className="text-xs text-muted-foreground truncate">{session.summary}</p>
                ) : (
                    <p className="text-xs text-muted-foreground">
                        {session.activity_count} {session.activity_count === 1 ? "activity" : "activities"}
                        {session.prompt_batch_count > 0 && ` · ${session.prompt_batch_count} prompts`}
                    </p>
                )}
            </div>
            <StatusBadge status={statusType} label={statusLabel} />
            <ArrowRight className="w-4 h-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
        </Link>
    );
}

function formatBackupAge(ageHours: number | null): string {
    if (ageHours === null) return "Never";
    if (ageHours < 1) return "< 1h ago";
    if (ageHours < 24) return `${Math.round(ageHours)}h ago`;
    const days = Math.floor(ageHours / 24);
    if (days === 1) return "1 day ago";
    if (days < 7) return `${days} days ago`;
    return `${Math.floor(days / 7)}w ago`;
}

export default function Dashboard() {
    const { data: status, isLoading, isError } = useStatus();
    const { data: sessionsData, isLoading: sessionsLoading, isError: sessionsError } = useSessions(PAGINATION.DASHBOARD_SESSION_LIMIT);
    const { data: plansData, isLoading: plansLoading } = usePlans({ limit: 1 });

    const isIndexing = status?.indexing;
    const indexStats = status?.index_stats;
    const sessions = sessionsData?.sessions || [];
    const totalSessions = sessionsData?.total || 0;
    const totalPlans = plansData?.total || 0;
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

            {/* Stats Cards */}
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
                <StatCard
                    title="Files Indexed"
                    value={indexStats?.files_indexed || 0}
                    icon={FileCode}
                    subtext={indexStats?.ast_stats?.ast_success ? `${indexStats.ast_stats.ast_success} AST parsed` : "Files in index"}
                    loading={isLoading}
                    href="/search?tab=code"
                />
                <StatCard
                    title="Memories"
                    value={indexStats?.memories_stored || 0}
                    icon={Brain}
                    subtext="Stored observations"
                    loading={isLoading}
                    href="/activity/memories"
                />
                <StatCard
                    title="Sessions"
                    value={totalSessions}
                    icon={Layers}
                    subtext="Agent sessions tracked"
                    loading={sessionsLoading}
                    href="/activity/sessions"
                />
                <StatCard
                    title="Plans"
                    value={totalPlans}
                    icon={ClipboardList}
                    subtext="Implementation plans"
                    loading={plansLoading}
                    href="/activity/plans"
                />
                <StatCard
                    title="Uptime"
                    value={status ? formatUptime(status.uptime_seconds) : "0m"}
                    icon={Clock}
                    subtext="Daemon session"
                    loading={isLoading}
                />
            </div>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
                <Card className="col-span-4">
                    <CardHeader className="flex flex-row items-center justify-between">
                        <CardTitle>Recent Sessions</CardTitle>
                        <div className="flex items-center gap-3">
                            {sessions.length > 0 && (
                                <span className="text-xs text-muted-foreground">
                                    {totalSessions} total
                                </span>
                            )}
                            <Link
                                to="/activity/sessions"
                                className="text-xs text-primary hover:underline flex items-center gap-1"
                            >
                                View all
                                <ArrowRight className="w-3 h-3" />
                            </Link>
                        </div>
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
                        <div className="space-y-3">
                            {/* Embedding Provider */}
                            <div className="flex items-center justify-between">
                                <span className="text-sm text-muted-foreground">Embedding</span>
                                <span className="font-medium text-sm truncate max-w-[180px]" title={status?.embedding_provider || undefined}>
                                    {status?.embedding_provider || "Not configured"}
                                </span>
                            </div>

                            {/* Summarization Provider */}
                            <div className="flex items-center justify-between gap-4">
                                <span className="text-sm text-muted-foreground flex-shrink-0">Summarization</span>
                                <span className={cn(
                                    "font-medium text-sm text-right",
                                    !status?.summarization?.enabled && "text-muted-foreground"
                                )}>
                                    {status?.summarization?.enabled
                                        ? `${status.summarization.provider}:${status.summarization.model}`
                                        : "Disabled"
                                    }
                                </span>
                            </div>

                            <div className="h-px bg-border my-1" />

                            {/* File Watcher */}
                            <div className="flex items-center justify-between">
                                <span className="text-sm text-muted-foreground">File Watcher</span>
                                <span className={cn("text-sm flex items-center gap-1", status?.file_watcher?.running ? "text-green-500" : "text-yellow-500")}>
                                    {status?.file_watcher?.running ? <Check className="w-3 h-3" /> : null}
                                    {status?.file_watcher?.running ? "Active" : "Inactive"}
                                </span>
                            </div>

                            {/* Pending Changes */}
                            <div className="flex items-center justify-between">
                                <span className="text-sm text-muted-foreground">Pending Changes</span>
                                <span className={cn(
                                    "font-medium text-sm",
                                    (status?.file_watcher?.pending_changes || 0) > 0 && "text-yellow-500"
                                )}>
                                    {status?.file_watcher?.pending_changes || 0}
                                </span>
                            </div>

                            <div className="h-px bg-border my-1" />

                            {/* Database Storage */}
                            <div className="flex items-center justify-between">
                                <span className="text-sm text-muted-foreground flex items-center gap-1">
                                    <HardDrive className="w-3 h-3" />
                                    Storage
                                </span>
                                <span className="font-medium text-sm">
                                    {status?.storage?.total_size_mb || "0.0"} MB
                                </span>
                            </div>

                            {/* Backup Status */}
                            <div className="flex items-center justify-between">
                                <span className="text-sm text-muted-foreground flex items-center gap-1">
                                    <Save className="w-3 h-3" />
                                    <a href="/team" className="hover:underline">Backup</a>
                                </span>
                                <span className={cn(
                                    "font-medium text-sm",
                                    !status?.backup?.exists && "text-yellow-500",
                                    status?.backup?.exists && (status.backup.age_hours || 0) > 24 && "text-yellow-500"
                                )}>
                                    {status?.backup?.exists
                                        ? `${formatBackupAge(status.backup.age_hours)} · ${((status.backup.size_bytes || 0) / (1024 * 1024)).toFixed(1)} MB`
                                        : "Not created"
                                    }
                                </span>
                            </div>

                            {/* Tunnel Sharing */}
                            <div className="flex items-center justify-between">
                                <span className="text-sm text-muted-foreground flex items-center gap-1">
                                    <Share2 className="w-3 h-3" />
                                    <Link to="/team/sharing" className="hover:underline">Sharing</Link>
                                </span>
                                <span className={cn(
                                    "font-medium text-sm",
                                    status?.tunnel?.active ? "text-green-500" : "text-muted-foreground"
                                )}>
                                    {status?.tunnel?.active
                                        ? <span className="flex items-center gap-1" title={status.tunnel.public_url || undefined}>
                                            <Check className="w-3 h-3" />
                                            Active
                                          </span>
                                        : <Link to="/team/sharing" className="hover:underline">Off</Link>
                                    }
                                </span>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    )
}
