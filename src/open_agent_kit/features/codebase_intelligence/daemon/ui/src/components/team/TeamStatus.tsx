/**
 * Team Status page — relay-based team dashboard.
 *
 * Displays relay connection state and online node count.
 */

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useTeamStatus } from "@/hooks/use-team";
import {
    Wifi,
    WifiOff,
    CircleDot,
    Users,
} from "lucide-react";
import { cn } from "@/lib/utils";

// =============================================================================
// Connection indicator constants
// =============================================================================

const CONNECTION_STATE = {
    CONNECTED: "connected",
    DISCONNECTED: "disconnected",
    NOT_CONFIGURED: "not_configured",
} as const;

type ConnectionState = (typeof CONNECTION_STATE)[keyof typeof CONNECTION_STATE];

function getConnectionState(
    relayConnected: boolean,
    hasWorkerUrl: boolean,
): ConnectionState {
    if (!hasWorkerUrl) return CONNECTION_STATE.NOT_CONFIGURED;
    return relayConnected ? CONNECTION_STATE.CONNECTED : CONNECTION_STATE.DISCONNECTED;
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

// =============================================================================
// Main Component
// =============================================================================

export default function TeamStatus() {
    const { data: status, isLoading } = useTeamStatus();

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

    const relay = status?.relay ?? null;
    const relayConnected = relay?.connected ?? false;
    const hasWorkerUrl = !!relay?.worker_url;
    const connectionState = getConnectionState(relayConnected, hasWorkerUrl);
    const onlineNodes = status?.online_nodes ?? [];
    const onlineCount = onlineNodes.filter((n) => n.online).length;

    return (
        <div className="space-y-6">
            {/* Connection Status Card */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        {relayConnected ? (
                            <Wifi className="h-5 w-5 text-green-500" />
                        ) : hasWorkerUrl ? (
                            <WifiOff className="h-5 w-5 text-red-500" />
                        ) : (
                            <CircleDot className="h-5 w-5 text-gray-400" />
                        )}
                        Relay Status
                    </CardTitle>
                    <CardDescription>
                        Current relay connection and online peers.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="flex items-center justify-between p-4 rounded-lg bg-muted/50">
                        <ConnectionIndicator state={connectionState} />
                        {relayConnected && (
                            <span className="flex items-center gap-1 text-xs text-muted-foreground">
                                <Users className="w-3 h-3" />
                                {onlineCount} online
                            </span>
                        )}
                    </div>

                    {relay?.worker_url && (
                        <div className="space-y-1">
                            <div className="text-xs text-muted-foreground">Relay Worker URL</div>
                            <code className="text-sm bg-muted px-2 py-1 rounded block truncate">
                                {relay.worker_url}
                            </code>
                        </div>
                    )}

                    {!hasWorkerUrl && (
                        <div className="text-center py-4 text-muted-foreground">
                            <CircleDot className="h-10 w-10 mx-auto mb-3 opacity-30" />
                            <p className="text-sm">No relay configured.</p>
                            <p className="text-xs mt-1">
                                Go to the Config tab to set up a relay connection.
                            </p>
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}
