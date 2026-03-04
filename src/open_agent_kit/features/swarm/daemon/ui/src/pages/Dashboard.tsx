import { Card, CardContent, CardHeader, CardTitle } from "@oak/ui/components/ui/card";
import { Network, Search, Bot, Wifi, WifiOff } from "lucide-react";
import { useSwarmStatus } from "@/hooks/use-swarm-status";
import { useSwarmNodes } from "@/hooks/use-swarm-nodes";
import { useAgents } from "@/hooks/use-agents";

export default function Dashboard() {
    const { data: status } = useSwarmStatus();
    const { data: nodes } = useSwarmNodes();
    const { data: agents } = useAgents();

    const connected = status?.connected ?? false;
    const nodeCount = nodes?.teams?.length ?? 0;
    const sessionCount = agents ? Object.keys(agents.sessions).length : 0;

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold">Dashboard</h1>
                <p className="text-muted-foreground text-sm mt-1">
                    Swarm overview and status
                </p>
            </div>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Connection</CardTitle>
                        {connected ? (
                            <Wifi className="h-4 w-4 text-green-500" />
                        ) : (
                            <WifiOff className="h-4 w-4 text-muted-foreground" />
                        )}
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">
                            {connected ? "Connected" : "Disconnected"}
                        </div>
                        <p className="text-xs text-muted-foreground">
                            {status?.swarm_url || "No swarm URL"}
                        </p>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Nodes</CardTitle>
                        <Network className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{nodeCount}</div>
                        <p className="text-xs text-muted-foreground">Connected teams</p>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Agents</CardTitle>
                        <Bot className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{sessionCount}</div>
                        <p className="text-xs text-muted-foreground">Active sessions</p>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Swarm ID</CardTitle>
                        <Search className="h-4 w-4 text-muted-foreground" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold truncate">
                            {status?.swarm_id || "-"}
                        </div>
                        <p className="text-xs text-muted-foreground">Identifier</p>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
