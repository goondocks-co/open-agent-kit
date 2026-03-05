import { Bot, RefreshCw } from "lucide-react";
import { Button } from "@oak/ui/components/ui/button";
import { Card, CardContent } from "@oak/ui/components/ui/card";
import { AGENT_RUN_STATUS } from "@oak/ui/lib/agent-status";
import { TaskCard, RunHistoryCard } from "@/components/agents";
import { useAgents, useAgentRuns, useRunTask, useReloadAgents } from "@/hooks/use-agents";

export default function Agents() {
    const { data: agentsData, isLoading: agentsLoading } = useAgents();
    const { data: runsData, isLoading: runsLoading } = useAgentRuns();
    const runTask = useRunTask();
    const reloadAgents = useReloadAgents();

    const tasks = agentsData?.tasks ?? [];
    const runs = runsData?.runs ?? [];

    const runningTaskNames = new Set(
        runs.filter((r) => r.status === AGENT_RUN_STATUS.RUNNING && r.task_name).map((r) => r.task_name!)
    );

    const handleRunTask = (taskName: string) => {
        runTask.mutate({ taskName });
    };

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold">Agents</h1>
                    <p className="text-muted-foreground text-sm mt-1">
                        Swarm analysis tasks and run history
                    </p>
                </div>
                <Button
                    variant="outline"
                    size="sm"
                    onClick={() => reloadAgents.mutate()}
                    disabled={reloadAgents.isPending}
                >
                    <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${reloadAgents.isPending ? "animate-spin" : ""}`} />
                    Reload
                </Button>
            </div>

            {/* Tasks */}
            <div>
                <h2 className="text-lg font-semibold mb-3">Tasks</h2>
                {agentsLoading && (
                    <p className="text-sm text-muted-foreground">Loading...</p>
                )}
                {tasks.length === 0 && !agentsLoading && (
                    <Card>
                        <CardContent className="pt-6 text-center py-12">
                            <Bot className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                            <p className="text-muted-foreground">No tasks available</p>
                        </CardContent>
                    </Card>
                )}
                <div className="grid gap-4 md:grid-cols-2">
                    {tasks.map((task) => (
                        <TaskCard
                            key={task.name}
                            name={task.name}
                            displayName={task.display_name}
                            description={task.description}
                            agentType={task.agent_type}
                            maxTurns={task.max_turns}
                            timeoutSeconds={task.timeout_seconds}
                            isRunning={runningTaskNames.has(task.name)}
                            onRun={handleRunTask}
                        />
                    ))}
                </div>
            </div>

            {/* Run History */}
            <div>
                <h2 className="text-lg font-semibold mb-3">Recent Runs</h2>
                {runsLoading && (
                    <p className="text-sm text-muted-foreground">Loading...</p>
                )}
                {runs.length === 0 && !runsLoading && (
                    <Card>
                        <CardContent className="pt-6 text-center py-12">
                            <p className="text-muted-foreground">No runs yet</p>
                        </CardContent>
                    </Card>
                )}
                <div className="grid gap-3">
                    {runs.map((run) => (
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
        </div>
    );
}
