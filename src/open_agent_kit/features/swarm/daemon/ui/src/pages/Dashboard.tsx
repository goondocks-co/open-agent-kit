import { Network, Search, Bot, Wifi, WifiOff, Play } from "lucide-react";
import { Button } from "@oak/ui/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@oak/ui/components/ui/card";
import { StatCard } from "@oak/ui/components/ui/config/stat-card";
import { useSwarmStatus } from "@/hooks/use-swarm-status";
import { useSwarmNodes } from "@/hooks/use-swarm-nodes";
import { useAgents, useAgentRuns, useRunTask } from "@/hooks/use-agents";
import { RunHistoryCard } from "@/components/agents";

export default function Dashboard() {
    const { data: status } = useSwarmStatus();
    const { data: nodes } = useSwarmNodes();
    const { data: agentsData } = useAgents();
    const { data: runsData } = useAgentRuns();
    const runTask = useRunTask();

    const connected = status?.connected ?? false;
    const nodeCount = nodes?.teams?.length ?? 0;
    const taskCount = agentsData?.tasks?.length ?? 0;
    const recentRuns = (runsData?.runs ?? []).slice(0, 5);

    const handleQuickRun = (taskName: string) => {
        runTask.mutate({ taskName });
    };

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold">Dashboard</h1>
                <p className="text-muted-foreground text-sm mt-1">
                    Swarm overview and status
                </p>
            </div>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                <StatCard
                    title="Connection"
                    value={connected ? "Connected" : "Disconnected"}
                    icon={connected ? Wifi : WifiOff}
                    subtext={status?.swarm_url || "No swarm URL"}
                />
                <StatCard
                    title="Nodes"
                    value={nodeCount}
                    icon={Network}
                    subtext="Connected teams"
                />
                <StatCard
                    title="Tasks"
                    value={taskCount}
                    icon={Bot}
                    subtext="Available agent tasks"
                    href="#/agents"
                />
                <StatCard
                    title="Swarm ID"
                    value={status?.swarm_id || "-"}
                    icon={Search}
                    subtext="Identifier"
                />
            </div>

            {/* Quick Actions */}
            {taskCount > 0 && (
                <Card>
                    <CardHeader className="pb-3">
                        <CardTitle className="text-base">Quick Actions</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="flex flex-wrap gap-2">
                            {(agentsData?.tasks ?? []).slice(0, 4).map((task) => (
                                <Button
                                    key={task.name}
                                    variant="outline"
                                    size="sm"
                                    onClick={() => handleQuickRun(task.name)}
                                    disabled={runTask.isPending}
                                >
                                    <Play className="h-3.5 w-3.5 mr-1.5" />
                                    {task.display_name}
                                </Button>
                            ))}
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Recent Runs */}
            {recentRuns.length > 0 && (
                <div>
                    <h2 className="text-lg font-semibold mb-3">Recent Runs</h2>
                    <div className="grid gap-3">
                        {recentRuns.map((run) => (
                            <RunHistoryCard
                                key={run.id}
                                runId={run.id}
                                agentName={run.agent_name}
                                taskName={run.task_name}
                                status={run.status}
                                createdAt={run.created_at}
                                completedAt={run.completed_at}
                                turnsUsed={run.turns_used}
                                error={run.error}
                            />
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
