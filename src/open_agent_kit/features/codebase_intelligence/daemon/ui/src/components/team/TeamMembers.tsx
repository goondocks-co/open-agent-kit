/**
 * Team Members page — online node directory (relay model).
 *
 * Displays a list of nodes connected to the relay with their
 * machine ID and online/offline status.
 */

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@oak/ui/components/ui/card";
import { useTeamMembers } from "@/hooks/use-team";
import { Users, AlertCircle, Package } from "lucide-react";
import { cn } from "@/lib/utils";

// =============================================================================
// Components
// =============================================================================

function OnlineIndicator({ online }: { online: boolean }) {
    return (
        <span className="flex items-center gap-1.5" title={online ? "Online" : "Offline"}>
            <span className={cn(
                "w-2 h-2 rounded-full flex-shrink-0",
                online ? "bg-green-500" : "bg-gray-400",
            )} />
            <span className="text-xs text-muted-foreground">
                {online ? "Online" : "Offline"}
            </span>
        </span>
    );
}

// =============================================================================
// Main Component
// =============================================================================

export default function TeamMembers() {
    const { data: membersData, isLoading, isError, error } = useTeamMembers();

    const nodes = membersData?.online_nodes ?? [];
    const fetchError = membersData?.error;

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

            {/* Node count */}
            <div className="flex items-center gap-3">
                <span className="text-sm text-muted-foreground">
                    {nodes.length} {nodes.length === 1 ? "node" : "nodes"}
                </span>
            </div>

            {/* Nodes list */}
            {nodes.length === 0 ? (
                <Card>
                    <CardContent className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                        <Users className="w-12 h-12 mb-4 opacity-30" />
                        <p className="text-sm">No connected nodes.</p>
                        <p className="text-xs mt-1">
                            Nodes appear here once they connect via the relay.
                        </p>
                    </CardContent>
                </Card>
            ) : (
                <Card>
                    <CardHeader className="pb-3">
                        <CardTitle className="flex items-center gap-2 text-base">
                            <Users className="h-4 w-4" />
                            Connected Nodes
                        </CardTitle>
                        <CardDescription>
                            Peer machines connected through the relay.
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="p-0">
                        <div className="border-t divide-y">
                            {/* Table header */}
                            <div className="grid grid-cols-3 gap-4 px-6 py-3 text-xs font-medium text-muted-foreground bg-muted/30">
                                <div>Machine ID</div>
                                <div>Version</div>
                                <div>Status</div>
                            </div>

                            {/* Table rows */}
                            {nodes.map((node, idx) => (
                                <div
                                    key={node.machine_id || idx}
                                    className="grid grid-cols-3 gap-4 px-6 py-3 items-center hover:bg-accent/5"
                                >
                                    <div className="flex items-center gap-3 min-w-0">
                                        <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                                            <Users className="h-4 w-4 text-primary" />
                                        </div>
                                        <code className="text-sm bg-muted px-1.5 py-0.5 rounded truncate">
                                            {node.machine_id}
                                        </code>
                                    </div>
                                    <div>
                                        {node.oak_version ? (
                                            <span className="flex items-center gap-1 text-xs text-muted-foreground">
                                                <Package className="w-3 h-3" />
                                                v{node.oak_version}
                                            </span>
                                        ) : (
                                            <span className="text-xs text-muted-foreground">—</span>
                                        )}
                                    </div>
                                    <div>
                                        <OnlineIndicator online={node.online} />
                                    </div>
                                </div>
                            ))}
                        </div>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
