import { Wifi, WifiOff } from "lucide-react";
import { useSwarmStatus } from "@/hooks/use-swarm-status";
import { useSwarmNodes } from "@/hooks/use-swarm-nodes";
import { useDeployStatus } from "@/hooks/use-deploy";
import { useMcpConfig } from "@/hooks/use-mcp-config";
import { SwarmTopology } from "@/components/topology";

export default function Dashboard() {
    const { data: status } = useSwarmStatus();
    const { data: nodes } = useSwarmNodes();
    const { data: deploy } = useDeployStatus();
    const { data: mcpConfig } = useMcpConfig();

    const connected = status?.connected ?? false;

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-2xl font-bold">Dashboard</h1>
                    <p className="text-muted-foreground text-sm mt-1">
                        Swarm overview and status
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    {connected
                        ? <Wifi className="w-4 h-4 text-green-500" />
                        : <WifiOff className="w-4 h-4 text-muted-foreground" />}
                    <span className="text-sm font-medium">
                        {connected ? "Connected" : "Disconnected"}
                    </span>
                </div>
            </div>

            <SwarmTopology
                swarmId={status?.swarm_id ?? ""}
                connected={connected}
                nodes={nodes?.teams ?? []}
                workerUrl={deploy?.worker_url}
                customDomain={deploy?.custom_domain}
                mcpEndpoint={mcpConfig?.mcp_endpoint}
            />
        </div>
    );
}
