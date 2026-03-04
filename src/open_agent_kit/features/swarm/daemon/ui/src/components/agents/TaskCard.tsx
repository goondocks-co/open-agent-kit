import { Card, CardContent, CardHeader, CardTitle } from "@oak/ui/components/ui/card";
import { Button } from "@oak/ui/components/ui/button";
import { Play, Clock, RotateCw } from "lucide-react";

interface TaskCardProps {
    name: string;
    displayName: string;
    description: string;
    agentType: string;
    maxTurns: number;
    timeoutSeconds: number;
    isRunning?: boolean;
    onRun: (taskName: string) => void;
}

export function TaskCard({
    name,
    displayName,
    description,
    agentType,
    maxTurns,
    timeoutSeconds,
    isRunning,
    onRun,
}: TaskCardProps) {
    return (
        <Card>
            <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                    <CardTitle className="text-base">{displayName}</CardTitle>
                    <Button
                        size="sm"
                        variant="outline"
                        onClick={() => onRun(name)}
                        disabled={isRunning}
                    >
                        {isRunning ? (
                            <RotateCw className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                        ) : (
                            <Play className="h-3.5 w-3.5 mr-1.5" />
                        )}
                        {isRunning ? "Running" : "Run"}
                    </Button>
                </div>
            </CardHeader>
            <CardContent>
                <p className="text-sm text-muted-foreground mb-3">{description}</p>
                <div className="flex gap-4 text-xs text-muted-foreground">
                    <span className="flex items-center gap-1">
                        <RotateCw className="h-3 w-3" />
                        {maxTurns} turns
                    </span>
                    <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {timeoutSeconds}s timeout
                    </span>
                    <span className="font-mono text-xs">{agentType}</span>
                </div>
            </CardContent>
        </Card>
    );
}
