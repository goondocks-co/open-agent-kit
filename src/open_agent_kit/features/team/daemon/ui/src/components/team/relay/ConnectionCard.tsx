/**
 * Connection status card with primary deploy/connect/disconnect action.
 */

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@oak/ui/components/ui/card";
import { Button } from "@oak/ui/components/ui/button";
import { Alert, AlertDescription } from "@oak/ui/components/ui/alert";
import { Cloud, Loader2, AlertCircle, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import type { CloudRelayStartResponse } from "@/hooks/use-cloud-relay";
import { ErrorCard } from "./ErrorCard";

export interface ConnectionCardProps {
    isConnected: boolean;
    isDeployed: boolean;
    isStarting: boolean;
    isConnecting: boolean;
    isStopping: boolean;
    cfAccountName: string | null;
    updateAvailable: boolean;
    startError: CloudRelayStartResponse | null;
    connectError: string | null;
    stopError: string | null;
    onDeploy: () => void;
    onConnect: () => void;
    onDisconnect: () => void;
    onRedeploy: () => void;
}

export function ConnectionCard({
    isConnected, isDeployed,
    isStarting, isConnecting, isStopping,
    cfAccountName, updateAvailable,
    startError, connectError, stopError,
    onDeploy, onConnect, onDisconnect, onRedeploy,
}: ConnectionCardProps) {
    const isToggling = isStarting || isConnecting || isStopping;

    const statusLabel = isConnected
        ? "Connected"
        : isDeployed
            ? "Deployed, not connected"
            : "Not deployed";

    const statusColor = isConnected
        ? "bg-green-500"
        : isDeployed
            ? "bg-amber-500"
            : "bg-gray-400";

    const primaryLabel = () => {
        if (isStarting) return "Deploying...";
        if (isConnecting) return "Connecting...";
        if (isStopping) return "Disconnecting...";
        if (isConnected) return "Disconnect";
        if (isDeployed) return "Connect";
        return "Deploy Relay";
    };

    const handlePrimary = () => {
        if (isConnected) onDisconnect();
        else if (isDeployed) onConnect();
        else onDeploy();
    };

    return (
        <Card>
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    <Cloud className="h-5 w-5" />
                    Cloud Relay
                </CardTitle>
                <CardDescription>
                    {isConnected
                        ? "Your daemon is connected. Observations sync with teammates automatically."
                        : isDeployed
                            ? "Your relay is deployed but your daemon is not connected."
                            : "Deploy a Cloudflare Worker to enable team sync and remote AI agent access."
                    }
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                <div className="flex items-center justify-between p-4 rounded-lg bg-muted/50">
                    <div className="flex items-center gap-3">
                        <div className={cn("w-3 h-3 rounded-full", statusColor)} />
                        <div>
                            <div className="font-medium text-sm">{statusLabel}</div>
                            {isConnected && cfAccountName && (
                                <div className="text-xs text-muted-foreground">
                                    Cloudflare: {cfAccountName}
                                </div>
                            )}
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        {isDeployed && (
                            <Button
                                onClick={onRedeploy}
                                disabled={isToggling}
                                variant="outline"
                                size="sm"
                            >
                                {isStarting ? (
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                    <>
                                        <RefreshCw className="h-4 w-4 mr-1.5" />
                                        Re-deploy
                                    </>
                                )}
                            </Button>
                        )}
                        <Button
                            onClick={handlePrimary}
                            disabled={isToggling}
                            variant={isConnected ? "outline" : "default"}
                            size="sm"
                        >
                            {(isStarting || isConnecting || isStopping) && (
                                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                            )}
                            {!isConnected && !isStarting && !isConnecting && (
                                <Cloud className="h-4 w-4 mr-2" />
                            )}
                            {primaryLabel()}
                        </Button>
                    </div>
                </div>

                {isConnected && (
                    <p className="text-xs text-muted-foreground px-1">
                        Disconnecting pauses observation sync with your team. Your local data stays intact.
                        Reconnect any time — you&apos;re not leaving the team.
                    </p>
                )}

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
                            disabled={isToggling}
                            className="shrink-0 border-amber-500/40 text-amber-700 dark:text-amber-400 hover:bg-amber-500/10"
                        >
                            {isStarting ? <Loader2 className="h-4 w-4 animate-spin" /> : "Re-deploy"}
                        </Button>
                    </div>
                )}

                {/* Errors */}
                {startError && <ErrorCard response={startError} />}
                {connectError && (
                    <Alert variant="destructive">
                        <AlertCircle className="h-4 w-4" />
                        <AlertDescription>{connectError}</AlertDescription>
                    </Alert>
                )}
                {stopError && (
                    <Alert variant="destructive">
                        <AlertCircle className="h-4 w-4" />
                        <AlertDescription>{stopError}</AlertDescription>
                    </Alert>
                )}
            </CardContent>
        </Card>
    );
}
