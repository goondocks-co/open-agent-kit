/**
 * Swarm connection/deploy state machine card.
 * Mirrors the team ConnectionCard pattern but simplified:
 * Not deployed -> Deploying (steps 1-3) -> Deployed
 */

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@oak/ui/components/ui/card";
import { Button } from "@oak/ui/components/ui/button";
import { Alert, AlertDescription } from "@oak/ui/components/ui/alert";
import { Hexagon, Loader2, RefreshCw, AlertCircle } from "lucide-react";

const DEPLOY_STEPS = ["Scaffolding...", "Installing...", "Deploying..."] as const;

export interface SwarmConnectionCardProps {
    isDeployed: boolean;
    isDeploying: boolean;
    currentStep: number;
    workerUrl: string | null;
    swarmId: string | null;
    error: string | null;
    updateAvailable: boolean;
    onDeploy: () => void;
    onRedeploy: () => void;
}

export function SwarmConnectionCard({
    isDeployed,
    isDeploying,
    currentStep,
    workerUrl,
    swarmId,
    error,
    updateAvailable,
    onDeploy,
    onRedeploy,
}: SwarmConnectionCardProps) {
    const statusLabel = isDeployed
        ? "Deployed"
        : isDeploying
            ? `${DEPLOY_STEPS[currentStep - 1] ?? "Deploying..."} (${currentStep}/3)`
            : "Not deployed";

    const statusColor = isDeployed
        ? "bg-green-500"
        : isDeploying
            ? "bg-amber-500 animate-pulse"
            : "bg-gray-400";

    const description = isDeployed
        ? "Your swarm worker is live. Nodes can connect and collaborate."
        : isDeploying
            ? "Deploying your swarm worker to Cloudflare..."
            : "Deploy a Cloudflare Worker to enable cross-project collaboration.";

    return (
        <Card>
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    <Hexagon className="h-5 w-5" />
                    Swarm Worker
                </CardTitle>
                <CardDescription>{description}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                <div className="flex items-center justify-between p-4 rounded-lg bg-muted/50">
                    <div className="flex items-center gap-3">
                        <div className={`w-3 h-3 rounded-full ${statusColor}`} />
                        <div>
                            <div className="font-medium text-sm">{statusLabel}</div>
                            {isDeployed && workerUrl && (
                                <div className="text-xs text-muted-foreground truncate max-w-[280px]">
                                    {workerUrl}
                                </div>
                            )}
                            {isDeployed && swarmId && (
                                <div className="text-xs text-muted-foreground">
                                    Swarm: {swarmId}
                                </div>
                            )}
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        {isDeployed && (
                            <Button
                                onClick={onRedeploy}
                                disabled={isDeploying}
                                variant="outline"
                                size="sm"
                            >
                                {isDeploying ? (
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                    <>
                                        <RefreshCw className="h-4 w-4 mr-1.5" />
                                        Re-deploy
                                    </>
                                )}
                            </Button>
                        )}
                        {!isDeployed && (
                            <Button
                                onClick={onDeploy}
                                disabled={isDeploying}
                                size="sm"
                            >
                                {isDeploying ? (
                                    <>
                                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                        {DEPLOY_STEPS[currentStep - 1] ?? "Deploying..."}
                                    </>
                                ) : (
                                    <>
                                        <Hexagon className="h-4 w-4 mr-2" />
                                        Deploy Swarm
                                    </>
                                )}
                            </Button>
                        )}
                    </div>
                </div>

                {/* Update available banner */}
                {updateAvailable && (
                    <div className="flex items-center justify-between gap-3 p-3 rounded-md bg-amber-500/10 border border-amber-500/20 text-amber-700 dark:text-amber-400 text-sm">
                        <div className="flex items-center gap-2">
                            <RefreshCw className="h-4 w-4 shrink-0" />
                            <span>Worker template updated. Re-deploy to apply the latest changes.</span>
                        </div>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={onRedeploy}
                            disabled={isDeploying}
                            className="shrink-0 border-amber-500/40 text-amber-700 dark:text-amber-400 hover:bg-amber-500/10"
                        >
                            {isDeploying ? <Loader2 className="h-4 w-4 animate-spin" /> : "Re-deploy"}
                        </Button>
                    </div>
                )}

                {/* Error */}
                {error && (
                    <Alert variant="destructive">
                        <AlertCircle className="h-4 w-4" />
                        <AlertDescription>{error}</AlertDescription>
                    </Alert>
                )}
            </CardContent>
        </Card>
    );
}
