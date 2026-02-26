/**
 * Team Members page — member directory with online indicators.
 *
 * Displays a table of team members with their display name,
 * machine ID, last seen time, and event count.
 */

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useTeamMembers, useTeamStatus } from "@/hooks/use-team";
import { Users, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatRelativeTime, TIME_UNITS } from "@/lib/constants";

// =============================================================================
// Online Status Constants
// =============================================================================

/** Thresholds for online status in milliseconds */
const ONLINE_THRESHOLD_MS = 60 * TIME_UNITS.MS_PER_SECOND;
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
    if (diffMs < ONLINE_THRESHOLD_MS) return PRESENCE_STATE.ONLINE;
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
// Main Component
// =============================================================================

export default function TeamMembers() {
    const { data: status } = useTeamStatus();
    const { data: membersData, isLoading, isError, error } = useTeamMembers();

    const configured = status?.configured ?? false;
    const members = membersData?.members ?? [];
    const fetchError = membersData?.error;

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
                            <div className="grid grid-cols-4 gap-4 px-6 py-3 text-xs font-medium text-muted-foreground bg-muted/30">
                                <div>Member</div>
                                <div>Machine ID</div>
                                <div>Last Seen</div>
                                <div className="text-right">Events</div>
                            </div>

                            {/* Table rows */}
                            {members.map((member, idx) => {
                                const presence = getPresenceState(member.last_seen);
                                return (
                                    <div
                                        key={member.machine_id || idx}
                                        className="grid grid-cols-4 gap-4 px-6 py-3 items-center hover:bg-accent/5"
                                    >
                                        <div className="flex items-center gap-3 min-w-0">
                                            <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                                                <Users className="h-4 w-4 text-primary" />
                                            </div>
                                            <div className="min-w-0">
                                                <div className="text-sm font-medium truncate">
                                                    {member.display_name || member.machine_id}
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
                                    </div>
                                );
                            })}
                        </div>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
