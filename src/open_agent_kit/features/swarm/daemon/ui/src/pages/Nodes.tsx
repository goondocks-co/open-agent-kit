import { Card, CardContent } from "@oak/ui/components/ui/card";
import { Hexagon } from "lucide-react";
import { useSwarmNodes, useRemoveNode } from "@/hooks/use-swarm-nodes";
import { SwarmInviteCard, NodeCard } from "@/components/nodes";

export default function Nodes() {
    const { data, isLoading } = useSwarmNodes();
    const removeNode = useRemoveNode();

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold">Nodes</h1>
                <p className="text-muted-foreground text-sm mt-1">
                    Connected teams and projects
                </p>
            </div>

            <SwarmInviteCard />

            {isLoading && (
                <div className="space-y-4">
                    {[1, 2].map((i) => (
                        <Card key={i}>
                            <CardContent className="pt-6 animate-pulse">
                                <div className="h-5 bg-muted rounded w-1/3 mb-3" />
                                <div className="h-4 bg-muted rounded w-2/3" />
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}

            {data?.error && (
                <Card>
                    <CardContent className="pt-6">
                        <p className="text-sm text-destructive">{data.error}</p>
                    </CardContent>
                </Card>
            )}

            {data?.teams?.length === 0 && !isLoading && (
                <Card>
                    <CardContent className="pt-6 text-center py-12">
                        <Hexagon className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                        <p className="text-muted-foreground">No teams connected yet</p>
                        <p className="text-xs text-muted-foreground mt-1">
                            Share the invite credentials above to connect teams to this swarm
                        </p>
                    </CardContent>
                </Card>
            )}

            <div className="grid gap-4">
                {data?.teams?.map((node) => (
                    <NodeCard
                        key={node.team_id || node.project_slug}
                        node={node}
                        onRemove={(teamId) => removeNode.mutate({ team_id: teamId })}
                        isRemoving={removeNode.isPending}
                    />
                ))}
            </div>
        </div>
    );
}
