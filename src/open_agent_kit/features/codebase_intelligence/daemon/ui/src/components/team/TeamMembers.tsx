/**
 * Team Members page — member directory with online indicators.
 *
 * Displays a table of team members with their display name,
 * machine ID, last seen time, and event count.
 */

import * as React from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
    useTeamMembers,
    useTeamStatus,
    useTeamConfig,
    usePendingJoins,
    useApproveJoin,
    useRejectJoin,
    useMachineResync,
    type TeamMember,
} from "@/hooks/use-team";
import { Users, AlertCircle, Check, X, Loader2, Clock, RefreshCw } from "lucide-react";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { cn } from "@/lib/utils";
import { formatRelativeTime, TIME_UNITS, MEMBER_ONLINE_THRESHOLD_MS } from "@/lib/constants";

// =============================================================================
// Online Status Constants
// =============================================================================

/** Threshold for "recently seen" presence state in milliseconds */
const RECENTLY_SEEN_THRESHOLD_MS = 5 * 60 * TIME_UNITS.MS_PER_SECOND;

const PRESENCE_STATE = {
    ONLINE: "online",
    RECENTLY_SEEN: "recently_seen",
    OFFLINE: "offline",
} as const;

type PresenceState = (typeof PRESENCE_STATE)[keyof typeof PRESENCE_STATE];

const PRESENCE_COLORS: Record<PresenceState, string> = {
    [PRESENCE_STATE.ONLINE]: "bg-green-500",
    [PRESENCE_STATE.RECENTLY_SEEN]: "bg-yellow-500",
    [PRESENCE_STATE.OFFLINE]: "bg-gray-400",
};

const PRESENCE_LABELS: Record<PresenceState, string> = {
    [PRESENCE_STATE.ONLINE]: "Online",
    [PRESENCE_STATE.RECENTLY_SEEN]: "Recently seen",
    [PRESENCE_STATE.OFFLINE]: "Offline",
};

function getPresenceState(lastSeen: string | undefined): PresenceState {
    if (!lastSeen) return PRESENCE_STATE.OFFLINE;

    const diffMs = Date.now() - new Date(lastSeen).getTime();
    if (diffMs < MEMBER_ONLINE_THRESHOLD_MS) return PRESENCE_STATE.ONLINE;
    if (diffMs < RECENTLY_SEEN_THRESHOLD_MS) return PRESENCE_STATE.RECENTLY_SEEN;
    return PRESENCE_STATE.OFFLINE;
}

// =============================================================================
// Components
// =============================================================================

function PresenceIndicator({ state }: { state: PresenceState }) {
    return (
        <span
            className="flex items-center gap-1.5"
            title={PRESENCE_LABELS[state]}
        >
            <span className={cn("w-2 h-2 rounded-full flex-shrink-0", PRESENCE_COLORS[state])} />
            <span className="text-xs text-muted-foreground">{PRESENCE_LABELS[state]}</span>
        </span>
    );
}

// =============================================================================
// Pending Join Requests (server mode)
// =============================================================================

function PendingJoinRequests() {
    const { data: pending, isLoading } = usePendingJoins();
    const approveJoin = useApproveJoin();
    const rejectJoin = useRejectJoin();

    if (isLoading) {
        return (
            <Card>
                <CardContent className="flex items-center justify-center py-6">
                    <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                </CardContent>
            </Card>
        );
    }

    if (!pending || pending.length === 0) return null;

    return (
        <Card className="border-amber-500/30">
            <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                    <Clock className="h-4 w-4 text-amber-600" />
                    Pending Join Requests
                </CardTitle>
                <CardDescription>
                    These nodes have requested to join your team. Approve to grant access.
                </CardDescription>
            </CardHeader>
            <CardContent className="p-0">
                <div className="border-t divide-y">
                    {/* Table header */}
                    <div className="grid grid-cols-4 gap-4 px-6 py-3 text-xs font-medium text-muted-foreground bg-amber-500/5">
                        <div>Node</div>
                        <div>Machine ID</div>
                        <div>Requested</div>
                        <div className="text-right">Actions</div>
                    </div>

                    {/* Table rows */}
                    {pending.map((entry) => (
                        <div
                            key={entry.key_id}
                            className="grid grid-cols-4 gap-4 px-6 py-3 items-center hover:bg-accent/5"
                        >
                            <div className="flex items-center gap-3 min-w-0">
                                <div className="w-8 h-8 rounded-full bg-amber-500/10 flex items-center justify-center flex-shrink-0">
                                    <Users className="h-4 w-4 text-amber-600" />
                                </div>
                                <div className="text-sm font-medium truncate">
                                    {entry.display_name || entry.machine_id || "Unknown"}
                                </div>
                            </div>
                            <div>
                                <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                                    {entry.machine_id || "n/a"}
                                </code>
                            </div>
                            <div className="text-sm text-muted-foreground">
                                {entry.created_at
                                    ? formatRelativeTime(entry.created_at)
                                    : "Unknown"}
                            </div>
                            <div className="flex items-center justify-end gap-2">
                                <Button
                                    size="sm"
                                    variant="outline"
                                    className="text-green-600 border-green-500/30 hover:bg-green-500/10"
                                    onClick={() => approveJoin.mutate(entry.key_id)}
                                    disabled={approveJoin.isPending || rejectJoin.isPending}
                                >
                                    {approveJoin.isPending ? (
                                        <Loader2 className="h-3 w-3 animate-spin" />
                                    ) : (
                                        <Check className="h-3 w-3 mr-1" />
                                    )}
                                    Approve
                                </Button>
                                <Button
                                    size="sm"
                                    variant="outline"
                                    className="text-red-600 border-red-500/30 hover:bg-red-500/10"
                                    onClick={() => rejectJoin.mutate(entry.key_id)}
                                    disabled={approveJoin.isPending || rejectJoin.isPending}
                                >
                                    {rejectJoin.isPending ? (
                                        <Loader2 className="h-3 w-3 animate-spin" />
                                    ) : (
                                        <X className="h-3 w-3 mr-1" />
                                    )}
                                    Reject
                                </Button>
                            </div>
                        </div>
                    ))}
                </div>
            </CardContent>
        </Card>
    );
}

// =============================================================================
// Main Component
// =============================================================================

export default function TeamMembers() {
    const { data: status } = useTeamStatus();
    const { data: config } = useTeamConfig();
    const { data: membersData, isLoading, isError, error } = useTeamMembers();
    const isServerMode = config?.server_mode ?? false;

    const configured = status?.configured ?? false;
    const members = membersData?.members ?? [];
    const fetchError = membersData?.error;

    // Resync state
    const [resyncTarget, setResyncTarget] = React.useState<TeamMember | null>(null);
    const [resyncResult, setResyncResult] = React.useState<{ machineId: string; applied: number } | null>(null);
    const resync = useMachineResync();

    const handleResyncConfirm = async () => {
        if (!resyncTarget) return;
        const result = await resync.mutateAsync(resyncTarget.machine_id);
        setResyncResult({ machineId: result.machine_id, applied: result.applied });
        setResyncTarget(null);
        // Clear the success badge after a few seconds
        setTimeout(() => setResyncResult(null), 5000);
    };

    if (!configured) {
        return (
            <Card>
                <CardContent className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                    <Users className="w-12 h-12 mb-4 opacity-30" />
                    <p className="text-sm">No team server configured.</p>
                    <p className="text-xs mt-1">
                        Connect to a team server to see members.
                    </p>
                </CardContent>
            </Card>
        );
    }

    if (isLoading) {
        return (
            <div className="space-y-2">
                {[1, 2, 3].map((i) => (
                    <div key={i} className="border rounded-md p-4 animate-pulse">
                        <div className="flex items-center gap-3">
                            <div className="w-8 h-8 bg-muted rounded-full" />
                            <div className="flex-1">
                                <div className="h-4 bg-muted rounded w-1/4 mb-2" />
                                <div className="h-3 bg-muted rounded w-1/2" />
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        );
    }

    return (
        <div className="space-y-4">
            {/* Pending join requests (server mode only) */}
            {isServerMode && <PendingJoinRequests />}

            {/* Error banner */}
            {(isError || fetchError) && (
                <div className="flex items-center gap-2 p-3 rounded-md bg-red-500/10 text-red-600 text-sm">
                    <AlertCircle className="h-4 w-4 flex-shrink-0" />
                    <span>
                        {fetchError || (error instanceof Error ? error.message : "Failed to fetch members")}
                    </span>
                </div>
            )}

            {/* Member count */}
            <div className="flex items-center gap-3">
                <span className="text-sm text-muted-foreground">
                    {members.length} {members.length === 1 ? "member" : "members"}
                </span>
            </div>

            {/* Members table */}
            {members.length === 0 ? (
                <Card>
                    <CardContent className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                        <Users className="w-12 h-12 mb-4 opacity-30" />
                        <p className="text-sm">No team members found.</p>
                        <p className="text-xs mt-1">
                            Members appear here once they connect to the team server.
                        </p>
                    </CardContent>
                </Card>
            ) : (
                <Card>
                    <CardHeader className="pb-3">
                        <CardTitle className="flex items-center gap-2 text-base">
                            <Users className="h-4 w-4" />
                            Members
                        </CardTitle>
                        <CardDescription>
                            Team members connected to the server.
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="p-0">
                        <div className="border-t divide-y">
                            {/* Table header */}
                            <div className="grid grid-cols-5 gap-4 px-6 py-3 text-xs font-medium text-muted-foreground bg-muted/30">
                                <div>Member</div>
                                <div>Machine ID</div>
                                <div>Last Seen</div>
                                <div className="text-right">Events</div>
                                <div className="text-right">Actions</div>
                            </div>

                            {/* Table rows */}
                            {members.map((member, idx) => {
                                const presence = getPresenceState(member.last_seen);
                                const justResynced = resyncResult?.machineId === member.machine_id;
                                return (
                                    <div
                                        key={member.machine_id || idx}
                                        className="grid grid-cols-5 gap-4 px-6 py-3 items-center hover:bg-accent/5"
                                    >
                                        <div className="flex items-center gap-3 min-w-0">
                                            <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                                                <Users className="h-4 w-4 text-primary" />
                                            </div>
                                            <div className="min-w-0">
                                                <div className="flex items-center gap-1.5">
                                                    <span className="text-sm font-medium truncate">
                                                        {member.display_name || member.machine_id}
                                                    </span>
                                                    {member.is_server && (
                                                        <span className="shrink-0 text-xs bg-blue-500/10 text-blue-600 dark:text-blue-400 px-1.5 py-0.5 rounded font-medium">
                                                            Server
                                                        </span>
                                                    )}
                                                </div>
                                                <PresenceIndicator state={presence} />
                                            </div>
                                        </div>
                                        <div>
                                            <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                                                {member.machine_id}
                                            </code>
                                        </div>
                                        <div className="text-sm text-muted-foreground">
                                            {member.last_seen
                                                ? formatRelativeTime(member.last_seen)
                                                : "Never"}
                                        </div>
                                        <div className="text-sm text-right text-muted-foreground">
                                            {member.event_count ?? 0}
                                        </div>
                                        <div className="flex items-center justify-end gap-2">
                                            {justResynced && (
                                                <span className="text-xs text-green-600 bg-green-500/10 px-1.5 py-0.5 rounded">
                                                    {resyncResult.applied} applied
                                                </span>
                                            )}
                                            <button
                                                onClick={() => setResyncTarget(member)}
                                                className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                                                title="Resync this machine's data"
                                            >
                                                <RefreshCw className="h-3.5 w-3.5" />
                                            </button>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Resync confirmation dialog */}
            <ConfirmDialog
                open={resyncTarget !== null}
                onOpenChange={(open) => { if (!open) setResyncTarget(null); }}
                title="Resync machine data"
                description={
                    resyncTarget
                        ? `This will delete this node's local copy of data from machine "${resyncTarget.machine_id}" and re-apply it from the team server. Use this when this node has corrupt or stale data from that peer.`
                        : ""
                }
                confirmLabel="Resync"
                loadingLabel="Resyncing..."
                onConfirm={handleResyncConfirm}
                isLoading={resync.isPending}
                variant="destructive"
                requireConfirmText={resyncTarget?.machine_id}
            />
        </div>
    );
}
