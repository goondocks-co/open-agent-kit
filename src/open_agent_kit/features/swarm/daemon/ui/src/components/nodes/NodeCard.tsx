/**
 * Node card — displays a connected team node with status, metadata, and remove action.
 */

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@oak/ui/components/ui/card";
import { Button } from "@oak/ui/components/ui/button";
import { ConfirmDialog } from "@oak/ui/components/ui/confirm-dialog";
import { Trash2 } from "lucide-react";

/** Status badge color mappings */
const STATUS_BADGE_COLORS = {
    connected: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
    stale: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400",
    disconnected: "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400",
} as const;

const STATUS_DOT_COLORS = {
    connected: "bg-green-500",
    stale: "bg-yellow-500",
    disconnected: "bg-gray-400",
} as const;

const CAPABILITY_COLORS: Record<string, string> = {
    swarm_search_v1: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
    swarm_management_v1: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
} as const;

interface SwarmNode {
    team_id: string;
    project_slug: string;
    status: string;
    last_seen?: string;
    capabilities?: string[];
    tool_names?: string[];
    oak_version?: string;
    node_count?: number;
}

interface NodeCardProps {
    node: SwarmNode;
    onRemove: (teamId: string) => void;
    isRemoving: boolean;
}

export function NodeCard({ node, onRemove, isRemoving }: NodeCardProps) {
    const [confirmOpen, setConfirmOpen] = useState(false);

    const statusKey = node.status as keyof typeof STATUS_BADGE_COLORS;
    const badgeColor = STATUS_BADGE_COLORS[statusKey] ?? STATUS_BADGE_COLORS.disconnected;
    const dotColor = STATUS_DOT_COLORS[statusKey] ?? STATUS_DOT_COLORS.disconnected;

    return (
        <>
            <Card>
                <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                        <CardTitle className="text-base">{node.project_slug}</CardTitle>
                        <div className="flex items-center gap-2">
                            <span
                                className={`inline-flex items-center gap-1.5 text-xs font-medium px-2 py-1 rounded-full ${badgeColor}`}
                            >
                                <span className={`h-1.5 w-1.5 rounded-full ${dotColor}`} />
                                {node.status}
                            </span>
                            <Button
                                variant="ghost"
                                size="sm"
                                className="h-8 w-8 p-0 text-muted-foreground hover:text-destructive"
                                onClick={() => setConfirmOpen(true)}
                                disabled={isRemoving}
                            >
                                <Trash2 className="h-4 w-4" />
                            </Button>
                        </div>
                    </div>
                </CardHeader>
                <CardContent>
                    <div className="text-xs text-muted-foreground space-y-1">
                        {node.last_seen && (
                            <p>Last seen: {new Date(node.last_seen).toLocaleString()}</p>
                        )}
                        {node.oak_version && (
                            <p>Version: {node.oak_version}</p>
                        )}
                        {node.node_count != null && (
                            <p>Nodes: {node.node_count}</p>
                        )}
                        {node.capabilities?.length ? (
                            <div className="flex gap-1 flex-wrap mt-2">
                                {node.capabilities.map((cap) => (
                                    <span
                                        key={cap}
                                        className={`px-1.5 py-0.5 rounded text-xs ${CAPABILITY_COLORS[cap] ?? "bg-muted"}`}
                                    >
                                        {cap.replace(/_v\d+$/, "").replace(/_/g, " ")}
                                    </span>
                                ))}
                            </div>
                        ) : null}
                        {node.tool_names?.length ? (
                            <details className="mt-2">
                                <summary className="text-xs cursor-pointer hover:text-foreground">
                                    {node.tool_names.length} tool{node.tool_names.length !== 1 ? "s" : ""} available
                                </summary>
                                <div className="flex gap-1 flex-wrap mt-1">
                                    {node.tool_names.map((name) => (
                                        <span
                                            key={name}
                                            className="px-1.5 py-0.5 rounded bg-muted text-xs font-mono"
                                        >
                                            {name}
                                        </span>
                                    ))}
                                </div>
                            </details>
                        ) : null}
                    </div>
                </CardContent>
            </Card>

            <ConfirmDialog
                open={confirmOpen}
                onOpenChange={setConfirmOpen}
                title="Remove Node"
                description={`Remove "${node.project_slug}" from the swarm? The team can rejoin later using the invite credentials.`}
                confirmLabel="Remove"
                onConfirm={() => {
                    onRemove(node.team_id);
                    setConfirmOpen(false);
                }}
                isLoading={isRemoving}
                variant="destructive"
                loadingLabel="Removing..."
            />
        </>
    );
}
