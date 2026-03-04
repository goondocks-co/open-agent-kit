import { Card, CardContent, CardHeader, CardTitle } from "@oak/ui/components/ui/card";
import { Network } from "lucide-react";
import { useSwarmNodes } from "@/hooks/use-swarm-nodes";

export default function Nodes() {
    const { data, isLoading } = useSwarmNodes();

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold">Nodes</h1>
                <p className="text-muted-foreground text-sm mt-1">
                    Connected teams and projects
                </p>
            </div>

            {isLoading && <p className="text-sm text-muted-foreground">Loading...</p>}

            {data?.error && (
                <Card>
                    <CardContent className="pt-6">
                        <p className="text-sm text-destructive">{data.error}</p>
                    </CardContent>
                </Card>
            )}

            {data?.teams?.length === 0 && (
                <Card>
                    <CardContent className="pt-6 text-center py-12">
                        <Network className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                        <p className="text-muted-foreground">No nodes connected</p>
                        <p className="text-xs text-muted-foreground mt-1">
                            Start CI daemons with swarm configuration to connect nodes
                        </p>
                    </CardContent>
                </Card>
            )}

            <div className="grid gap-4">
                {data?.teams?.map((node) => (
                    <Card key={node.team_id || node.project_slug}>
                        <CardHeader className="pb-3">
                            <div className="flex items-center justify-between">
                                <CardTitle className="text-base">
                                    {node.project_slug}
                                </CardTitle>
                                <span
                                    className={`inline-flex items-center gap-1.5 text-xs font-medium px-2 py-1 rounded-full ${
                                        node.status === "connected"
                                            ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                                            : node.status === "stale"
                                            ? "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400"
                                            : "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400"
                                    }`}
                                >
                                    <span className={`h-1.5 w-1.5 rounded-full ${
                                        node.status === "connected" ? "bg-green-500" :
                                        node.status === "stale" ? "bg-yellow-500" : "bg-gray-400"
                                    }`} />
                                    {node.status}
                                </span>
                            </div>
                        </CardHeader>
                        <CardContent>
                            <div className="text-xs text-muted-foreground space-y-1">
                                {node.last_seen && (
                                    <p>Last seen: {new Date(node.last_seen).toLocaleString()}</p>
                                )}
                                {node.capabilities?.length ? (
                                    <div className="flex gap-1 flex-wrap mt-2">
                                        {node.capabilities.map((cap) => (
                                            <span key={cap} className="px-1.5 py-0.5 rounded bg-muted text-xs">
                                                {cap}
                                            </span>
                                        ))}
                                    </div>
                                ) : null}
                            </div>
                        </CardContent>
                    </Card>
                ))}
            </div>
        </div>
    );
}
