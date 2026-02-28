/**
 * Team Status page — primary team dashboard.
 *
 * Displays connection state, server identity, sync health,
 * and provides manual flush/pull actions.
 */

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
    useTeamStatus,
    useFlushSync,
    usePullSync,
    useBackfillStatus,
    useTriggerBackfill,
} from "@/hooks/use-team";
import {
    Wifi,
    WifiOff,
    CircleDot,
    RefreshCw,
    Download,
    Upload,
    Loader2,
    AlertCircle,
    Server,
    Users,
    History,
    CheckCircle2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { formatRelativeTime } from "@/lib/constants";

// =============================================================================
// Connection indicator constants
// =============================================================================

const CONNECTION_STATE = {
    CONNECTED: "connected",
    DISCONNECTED: "disconnected",
    NOT_CONFIGURED: "not_configured",
    PENDING_APPROVAL: "pending_approval",
} as const;

type ConnectionState = (typeof CONNECTION_STATE)[keyof typeof CONNECTION_STATE];

function getConnectionState(
    configured: boolean,
    connected: boolean,
    pendingApproval?: boolean,
): ConnectionState {
    if (pendingApproval) return CONNECTION_STATE.PENDING_APPROVAL;
    if (!configured) return CONNECTION_STATE.NOT_CONFIGURED;
    return connected ? CONNECTION_STATE.CONNECTED : CONNECTION_STATE.DISCONNECTED;
}

const CONNECTION_COLORS: Record<ConnectionState, string> = {
    [CONNECTION_STATE.CONNECTED]: "bg-green-500",
    [CONNECTION_STATE.DISCONNECTED]: "bg-red-500",
    [CONNECTION_STATE.NOT_CONFIGURED]: "bg-gray-400",
    [CONNECTION_STATE.PENDING_APPROVAL]: "bg-amber-500",
};

const CONNECTION_LABELS: Record<ConnectionState, string> = {
    [CONNECTION_STATE.CONNECTED]: "Connected",
    [CONNECTION_STATE.DISCONNECTED]: "Disconnected",
    [CONNECTION_STATE.NOT_CONFIGURED]: "Not Configured",
    [CONNECTION_STATE.PENDING_APPROVAL]: "Waiting for Approval",
};

// =============================================================================
// Components
// =============================================================================

function ConnectionIndicator({ state }: { state: ConnectionState }) {
    return (
        <div className="flex items-center gap-3">
            <div className={cn("w-3 h-3 rounded-full", CONNECTION_COLORS[state])} />
            <span className="font-medium text-sm">{CONNECTION_LABELS[state]}</span>
        </div>
    );
}

function SyncStatCard({
    label,
    value,
    icon: Icon,
}: {
    label: string;
    value: string | number;
    icon: React.ComponentType<{ className?: string }>;
}) {
    return (
        <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/50">
            <Icon className="w-5 h-5 text-muted-foreground" />
            <div>
                <div className="text-xs text-muted-foreground">{label}</div>
                <div className="text-sm font-medium">{value}</div>
            </div>
        </div>
    );
}

// =============================================================================
// Main Component
// =============================================================================

export default function TeamStatus() {
    const { data: status, isLoading } = useTeamStatus();
    const { data: backfill } = useBackfillStatus();
    const flushSync = useFlushSync();
    const pullSync = usePullSync();
    const triggerBackfill = useTriggerBackfill();

    if (isLoading) {
        return (
            <div className="space-y-4">
                {[1, 2].map((i) => (
                    <div key={i} className="border rounded-lg p-6 animate-pulse">
                        <div className="h-5 bg-muted rounded w-1/3 mb-3" />
                        <div className="h-4 bg-muted rounded w-2/3" />
                    </div>
                ))}
            </div>
        );
    }

    const configured = status?.configured ?? false;
    const connected = status?.connected ?? false;
    const pendingApproval = status?.pending_approval ?? false;
    const connectionState = getConnectionState(configured, connected, pendingApproval);
    const sync = status?.sync ?? null;

    return (
        <div className="space-y-6">
            {/* Connection Status Card */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        {pendingApproval ? (
                            <CircleDot className="h-5 w-5 text-amber-500" />
                        ) : connected ? (
                            <Wifi className="h-5 w-5 text-green-500" />
                        ) : configured ? (
                            <WifiOff className="h-5 w-5 text-red-500" />
                        ) : (
                            <CircleDot className="h-5 w-5 text-gray-400" />
                        )}
                        Connection Status
                    </CardTitle>
                    <CardDescription>
                        Current team server connection and identity.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="flex items-center justify-between p-4 rounded-lg bg-muted/50">
                        <ConnectionIndicator state={connectionState} />
                        {configured && (
                            <span className="flex items-center gap-1 text-xs text-muted-foreground">
                                <Users className="w-3 h-3" />
                                {status?.members_online ?? 0} online
                            </span>
                        )}
                    </div>

                    {configured && (
                        <div className="grid gap-3 sm:grid-cols-2">
                            {status?.server_url && (
                                <div className="space-y-1">
                                    <div className="text-xs text-muted-foreground flex items-center gap-1">
                                        <Server className="w-3 h-3" />
                                        Server URL
                                    </div>
                                    <code className="text-sm bg-muted px-2 py-1 rounded block truncate">
                                        {status.server_url}
                                    </code>
                                </div>
                            )}
                            {status?.project_id && (
                                <div className="space-y-1">
                                    <div className="text-xs text-muted-foreground">Project Identity</div>
                                    <code className="text-sm bg-muted px-2 py-1 rounded block truncate">
                                        {status.project_id}
                                    </code>
                                </div>
                            )}
                        </div>
                    )}

                    {!configured && (
                        <div className="text-center py-4 text-muted-foreground">
                            <CircleDot className="h-10 w-10 mx-auto mb-3 opacity-30" />
                            <p className="text-sm">No team server configured.</p>
                            <p className="text-xs mt-1">
                                Go to the Config tab to connect to a team server.
                            </p>
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Historical Data Sync Card (only when configured) */}
            {configured && (
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <History className="h-5 w-5" />
                            Historical Data Sync
                        </CardTitle>
                        <CardDescription>
                            Pre-join sessions, memories, and activities backfilled to the team server.
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        {backfill ? (
                            <>
                                <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/50">
                                    {backfill.completed ? (
                                        <CheckCircle2 className="w-5 h-5 text-green-500 flex-shrink-0" />
                                    ) : (
                                        <History className="w-5 h-5 text-muted-foreground flex-shrink-0" />
                                    )}
                                    <div className="flex-1 min-w-0">
                                        <div className="text-sm font-medium">
                                            {backfill.completed ? "Backfill complete" : "Not yet run"}
                                        </div>
                                        {backfill.completed_at && (
                                            <div className="text-xs text-muted-foreground">
                                                Last synced {formatRelativeTime(backfill.completed_at)}
                                            </div>
                                        )}
                                    </div>
                                </div>

                                {backfill.counts && (
                                    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4 text-xs">
                                        {(
                                            [
                                                ["Sessions", backfill.counts.sessions],
                                                ["Batches", backfill.counts.batches],
                                                ["Memories", backfill.counts.observations],
                                                ["Activities", backfill.counts.activities],
                                            ] as [string, number][]
                                        ).map(([label, count]) => (
                                            <div
                                                key={label}
                                                className="flex items-center justify-between p-2 rounded bg-muted/40"
                                            >
                                                <span className="text-muted-foreground">{label}</span>
                                                <span className="font-medium tabular-nums">{count}</span>
                                            </div>
                                        ))}
                                    </div>
                                )}

                                {backfill.last_reconcile_at && (
                                    <div className="text-xs text-muted-foreground">
                                        Last reconciled {formatRelativeTime(backfill.last_reconcile_at)}
                                        {backfill.last_missing_count !== null &&
                                            backfill.last_missing_count > 0 && (
                                                <span className="ml-1 text-amber-600">
                                                    ({backfill.last_missing_count} gap
                                                    {backfill.last_missing_count !== 1 ? "s" : ""} found)
                                                </span>
                                            )}
                                    </div>
                                )}
                            </>
                        ) : (
                            <div className="text-center py-4 text-muted-foreground">
                                <p className="text-sm">No backfill data available.</p>
                            </div>
                        )}

                        <div className="flex items-center gap-3 pt-2 border-t">
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => triggerBackfill.mutate()}
                                disabled={triggerBackfill.isPending || !connected}
                            >
                                {triggerBackfill.isPending ? (
                                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                ) : (
                                    <History className="w-4 h-4 mr-2" />
                                )}
                                Re-sync Historical Data
                            </Button>
                            {triggerBackfill.isSuccess && (
                                <span className="text-xs text-green-600">Backfill started</span>
                            )}
                            {triggerBackfill.isError && (
                                <span className="text-xs text-red-600">
                                    {triggerBackfill.error.message}
                                </span>
                            )}
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Sync Status Card (only when configured) */}
            {configured && (
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <RefreshCw className="h-5 w-5" />
                            Sync Status
                        </CardTitle>
                        <CardDescription>
                            Outbox queue and synchronization health.
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        {sync ? (
                            <>
                                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                                    <SyncStatCard
                                        label="Queue Depth"
                                        value={sync.queue_depth ?? 0}
                                        icon={Upload}
                                    />
                                    <SyncStatCard
                                        label="Events Sent"
                                        value={sync.events_sent ?? 0}
                                        icon={RefreshCw}
                                    />
                                    <SyncStatCard
                                        label="Last Flush"
                                        value={
                                            sync.last_flush_at
                                                ? formatRelativeTime(sync.last_flush_at)
                                                : "Never"
                                        }
                                        icon={Upload}
                                    />
                                    <SyncStatCard
                                        label="Last Flush Count"
                                        value={sync.last_flush_count ?? 0}
                                        icon={Download}
                                    />
                                </div>

                                {sync.last_error && (
                                    <div className="flex items-start gap-2 p-3 rounded-md bg-red-500/10 text-red-600 text-sm">
                                        <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                                        <div>
                                            <div className="font-medium">Last Error</div>
                                            <div className="text-xs mt-0.5">{sync.last_error}</div>
                                        </div>
                                    </div>
                                )}
                            </>
                        ) : (
                            <div className="text-center py-4 text-muted-foreground">
                                <p className="text-sm">Sync worker not active.</p>
                                <p className="text-xs mt-1">
                                    Enable auto-sync in the Config tab or join a team server.
                                </p>
                            </div>
                        )}

                        {/* Action Buttons */}
                        <div className="flex items-center gap-3 pt-2 border-t">
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => flushSync.mutate()}
                                disabled={flushSync.isPending || !connected}
                            >
                                {flushSync.isPending ? (
                                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                ) : (
                                    <Upload className="w-4 h-4 mr-2" />
                                )}
                                Flush Now
                            </Button>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => pullSync.mutate()}
                                disabled={pullSync.isPending || !connected}
                            >
                                {pullSync.isPending ? (
                                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                ) : (
                                    <Download className="w-4 h-4 mr-2" />
                                )}
                                Pull Now
                            </Button>

                            {flushSync.isSuccess && (
                                <span className="text-xs text-green-600">
                                    Flushed {flushSync.data?.flushed ?? 0} events
                                </span>
                            )}
                            {pullSync.isSuccess && (
                                <span className="text-xs text-green-600">
                                    {pullSync.data?.status === "pull_worker_not_available"
                                        ? "Pull worker not yet available"
                                        : `Applied ${pullSync.data?.applied ?? 0} events`}
                                </span>
                            )}
                            {flushSync.isError && (
                                <span className="text-xs text-red-600">
                                    {flushSync.error.message}
                                </span>
                            )}
                            {pullSync.isError && (
                                <span className="text-xs text-red-600">
                                    {pullSync.error.message}
                                </span>
                            )}
                        </div>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
