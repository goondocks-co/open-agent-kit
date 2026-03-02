/**
 * Team Status page — relay-based team dashboard.
 *
 * Shows relay connection state, peer count, connection timestamps,
 * heartbeat freshness, reconnect attempts, errors, and sync stats.
 */

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
    Users,
    Clock,
    AlertCircle,
    RefreshCw,
    Send,
    Inbox,
    Package,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { OnlineNode, RelayStatus, SyncStatus } from "@/hooks/use-team";

// =============================================================================
// Helpers
// =============================================================================

export function timeAgo(iso: string | null | undefined): string {
    if (!iso) return "never";
    const diffMs = Date.now() - new Date(iso).getTime();
    const secs = Math.floor(diffMs / 1000);
    if (secs < 60) return `${secs}s ago`;
    const mins = Math.floor(secs / 60);
    if (mins < 60) return `${mins}m ago`;
    return `${Math.floor(mins / 60)}h ago`;
}

export function formatTimestamp(iso: string | null | undefined): string {
    if (!iso) return "—";
    return new Date(iso).toLocaleTimeString();
}

// =============================================================================
// Connection indicator
// =============================================================================

const CONNECTION_STATE = {
    CONNECTED: "connected",
    DISCONNECTED: "disconnected",
    NOT_CONFIGURED: "not_configured",
} as const;

type ConnectionState = (typeof CONNECTION_STATE)[keyof typeof CONNECTION_STATE];

function getConnectionState(relay: RelayStatus | null): ConnectionState {
    if (!relay?.worker_url) return CONNECTION_STATE.NOT_CONFIGURED;
    return relay.connected ? CONNECTION_STATE.CONNECTED : CONNECTION_STATE.DISCONNECTED;
}

const CONNECTION_COLORS: Record<ConnectionState, string> = {
    [CONNECTION_STATE.CONNECTED]: "bg-green-500",
    [CONNECTION_STATE.DISCONNECTED]: "bg-red-500",
    [CONNECTION_STATE.NOT_CONFIGURED]: "bg-gray-400",
};

const CONNECTION_LABELS: Record<ConnectionState, string> = {
    [CONNECTION_STATE.CONNECTED]: "Connected",
    [CONNECTION_STATE.DISCONNECTED]: "Disconnected",
    [CONNECTION_STATE.NOT_CONFIGURED]: "Not Configured",
};

function ConnectionIndicator({ state }: { state: ConnectionState }) {
    return (
        <div className="flex items-center gap-3">
            <div className={cn("w-3 h-3 rounded-full", CONNECTION_COLORS[state])} />
            <span className="font-medium text-sm">{CONNECTION_LABELS[state]}</span>
        </div>
    );
}

// =============================================================================
// Relay detail rows
// =============================================================================

export function DetailRow({ icon, label, value, className }: {
    icon: React.ReactNode;
    label: string;
    value: string;
    className?: string;
}) {
    return (
        <div className={cn("flex items-center justify-between text-sm", className)}>
            <span className="flex items-center gap-1.5 text-muted-foreground">
                {icon}
                {label}
            </span>
            <span className="font-mono text-xs">{value}</span>
        </div>
    );
}

// =============================================================================
// Sub-components
// =============================================================================

export function RelayDetails({ relay, onlineCount }: { relay: RelayStatus; onlineCount: number }) {
    const connectionState = getConnectionState(relay);

    return (
        <div className="space-y-4">
            {/* Status row */}
            <div className="flex items-center justify-between p-4 rounded-lg bg-muted/50">
                <ConnectionIndicator state={connectionState} />
                {relay.connected && (
                    <span className="flex items-center gap-1 text-xs text-muted-foreground">
                        <Users className="w-3 h-3" />
                        {onlineCount} online
                    </span>
                )}
            </div>

            {/* Worker URL */}
            {relay.worker_url && (
                <div className="space-y-1">
                    <div className="text-xs text-muted-foreground">Relay Worker URL</div>
                    <code className="text-sm bg-muted px-2 py-1 rounded block truncate">
                        {relay.worker_url}
                    </code>
                </div>
            )}

            {/* Timestamps + reconnect (only when we have any info) */}
            {(relay.connected_at || relay.last_heartbeat || relay.reconnect_attempts > 0) && (
                <div className="space-y-2 pt-1 border-t">
                    {relay.connected_at && (
                        <DetailRow
                            icon={<Clock className="w-3 h-3" />}
                            label="Connected at"
                            value={formatTimestamp(relay.connected_at)}
                        />
                    )}
                    {relay.last_heartbeat && (
                        <DetailRow
                            icon={<RefreshCw className="w-3 h-3" />}
                            label="Last heartbeat"
                            value={timeAgo(relay.last_heartbeat)}
                        />
                    )}
                    {relay.reconnect_attempts > 0 && (
                        <DetailRow
                            icon={<RefreshCw className="w-3 h-3" />}
                            label="Reconnect attempts"
                            value={String(relay.reconnect_attempts)}
                            className="text-amber-600"
                        />
                    )}
                </div>
            )}

            {/* Error */}
            {relay.error && (
                <div className="flex items-start gap-2 p-3 rounded-md bg-red-500/10 text-red-600 text-sm">
                    <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                    <span>{relay.error}</span>
                </div>
            )}
        </div>
    );
}

export function ConnectedNodes({ nodes }: { nodes: OnlineNode[] }) {
    return (
        <Card>
            <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                    <Users className="h-4 w-4" />
                    Connected Nodes
                </CardTitle>
                <CardDescription>Machines currently connected to the cloud relay.</CardDescription>
            </CardHeader>
            <CardContent>
                {nodes.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No nodes connected.</p>
                ) : (
                    <div className="space-y-3">
                        {nodes.map((node) => (
                            <div key={node.machine_id} className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <div className="w-2 h-2 rounded-full bg-green-500" />
                                    <span className="text-sm font-mono">{node.machine_id}</span>
                                </div>
                                <div className="flex items-center gap-1.5">
                                    {node.capabilities?.map((cap) => (
                                        <span
                                            key={cap}
                                            className="inline-flex items-center rounded-full bg-blue-500/10 px-2 py-0.5 text-xs font-medium text-blue-700 dark:text-blue-400"
                                        >
                                            {cap.replace(/_v\d+$/, '').replace(/_/g, ' ')}
                                        </span>
                                    ))}
                                    {node.oak_version && (
                                        <span className="flex items-center gap-1 text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                                            <Package className="w-3 h-3" />
                                            v{node.oak_version}
                                        </span>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </CardContent>
        </Card>
    );
}

export function RelayBuffer({ pending }: { pending: Record<string, number> }) {
    const entries = Object.entries(pending);
    if (!entries.length) return null;
    return (
        <Card>
            <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                    <Inbox className="h-4 w-4" />
                    Relay Buffer
                </CardTitle>
                <CardDescription>
                    Observations queued in the relay for offline peers.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
                {entries.map(([machineId, count]) => (
                    <DetailRow
                        key={machineId}
                        icon={<Package className="w-3 h-3" />}
                        label={machineId}
                        value={`${count} pending`}
                        className="text-amber-600"
                    />
                ))}
            </CardContent>
        </Card>
    );
}

export function SyncStats({ sync }: { sync: SyncStatus }) {
    return (
        <Card>
            <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                    <Send className="h-4 w-4" />
                    Sync Stats
                </CardTitle>
                <CardDescription>
                    Observation outbox activity for this session.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
                <DetailRow
                    icon={<Inbox className="w-3 h-3" />}
                    label="Queue depth"
                    value={String(sync.queue_depth)}
                />
                <DetailRow
                    icon={<Send className="w-3 h-3" />}
                    label="Total sent"
                    value={String(sync.events_sent_total)}
                />
                {sync.last_sync && (
                    <DetailRow
                        icon={<Clock className="w-3 h-3" />}
                        label="Last sync"
                        value={timeAgo(sync.last_sync)}
                    />
                )}
                {sync.last_error && (
                    <div className="flex items-start gap-2 p-3 rounded-md bg-red-500/10 text-red-600 text-sm mt-2">
                        <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                        <span>{sync.last_error}</span>
                    </div>
                )}
            </CardContent>
        </Card>
    );
}

