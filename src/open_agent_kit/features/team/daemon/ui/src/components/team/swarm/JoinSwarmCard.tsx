/**
 * Join Swarm card — allows a team to connect to a swarm via URL + token.
 * When connected, shows swarm info and a button to launch the local swarm daemon.
 */

import { useState } from "react";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@oak/ui/components/ui/card";
import { Button } from "@oak/ui/components/ui/button";
import { Alert, AlertDescription } from "@oak/ui/components/ui/alert";
import {
    Hexagon,
    Loader2,
    AlertCircle,
    CheckCircle2,
    Unlink,
    ExternalLink,
    Rocket,
} from "lucide-react";

/** Derive a human-readable swarm name from the worker URL. */
function deriveSwarmName(url: string): string | null {
  try {
    const hostname = new URL(url).hostname;
    const prefix = "oak-swarm-";
    if (!hostname.startsWith(prefix)) return null;
    const rest = hostname.slice(prefix.length);
    const dotIndex = rest.indexOf(".");
    return dotIndex > 0 ? rest.slice(0, dotIndex) : rest;
  } catch {
    return null;
  }
}

interface JoinSwarmCardProps {
    onJoin: (url: string, token: string) => void;
    onLeave: () => void;
    isJoining: boolean;
    isLeaving: boolean;
    joinError: string | null;
    joinSuccess: boolean;
    swarmStatus: {
        joined: boolean;
        swarm_url: string | null;
        cli_command: string | null;
    } | null;
    daemonStatus: {
        configured: boolean;
        running: boolean;
        name?: string;
        url?: string;
    } | null;
    onLaunchDaemon: () => void;
    isLaunchingDaemon: boolean;
    launchError: string | null;
    daemonUrl: string | null;
}

export function JoinSwarmCard({
    onJoin,
    onLeave,
    isJoining,
    isLeaving,
    joinError,
    joinSuccess,
    swarmStatus,
    daemonStatus,
    onLaunchDaemon,
    isLaunchingDaemon,
    launchError,
    daemonUrl,
}: JoinSwarmCardProps) {
    const [url, setUrl] = useState("");
    const [token, setToken] = useState("");

    const isBusy = isJoining || isLeaving;
    const isJoined = swarmStatus?.joined ?? false;

    // Connected state
    if (isJoined) {
        const swarmName = swarmStatus?.swarm_url ? deriveSwarmName(swarmStatus.swarm_url) : null;
        const isDaemonRunning = daemonStatus?.running ?? false;
        const activeDaemonUrl = daemonUrl ?? daemonStatus?.url;

        return (
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Hexagon className="h-5 w-5" />
                        Swarm{swarmName ? `: ${swarmName}` : ""}
                    </CardTitle>
                    <CardDescription>Connected to a swarm for cross-project collaboration.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                    <div className="flex items-center gap-2 text-sm text-green-600 dark:text-green-400">
                        <CheckCircle2 className="h-4 w-4" />
                        Connected to swarm
                    </div>
                    {swarmStatus?.swarm_url && (
                        <p className="text-xs text-muted-foreground font-mono truncate">
                            {swarmStatus.swarm_url}
                        </p>
                    )}

                    {/* Swarm daemon management */}
                    <div className="pt-2 border-t space-y-2">
                        {isDaemonRunning && activeDaemonUrl ? (
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2 text-sm text-green-600 dark:text-green-400">
                                    <CheckCircle2 className="h-3.5 w-3.5" />
                                    Swarm daemon running
                                </div>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => window.open(activeDaemonUrl, "_blank")}
                                >
                                    <ExternalLink className="h-3.5 w-3.5 mr-1.5" />
                                    Open
                                </Button>
                            </div>
                        ) : (
                            <div className="flex items-center justify-between">
                                <p className="text-sm text-muted-foreground">
                                    Local swarm daemon not running
                                </p>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={onLaunchDaemon}
                                    disabled={isLaunchingDaemon}
                                >
                                    {isLaunchingDaemon ? (
                                        <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                                    ) : (
                                        <Rocket className="h-3.5 w-3.5 mr-1.5" />
                                    )}
                                    {isLaunchingDaemon ? "Launching..." : "Launch Daemon"}
                                </Button>
                            </div>
                        )}
                        {launchError && (
                            <Alert variant="destructive">
                                <AlertCircle className="h-4 w-4" />
                                <AlertDescription>{launchError}</AlertDescription>
                            </Alert>
                        )}
                    </div>
                </CardContent>
                <CardFooter>
                    <Button
                        variant="destructive"
                        size="sm"
                        onClick={onLeave}
                        disabled={isBusy}
                    >
                        {isLeaving ? (
                            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        ) : (
                            <Unlink className="h-4 w-4 mr-2" />
                        )}
                        {isLeaving ? "Disconnecting..." : "Disconnect"}
                    </Button>
                </CardFooter>
            </Card>
        );
    }

    // Join form
    return (
        <Card>
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    <Hexagon className="h-5 w-5" />
                    Join Swarm
                </CardTitle>
                <CardDescription>
                    Enter the swarm URL and token shared by the swarm operator to enable cross-project search and collaboration.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                <div className="space-y-1.5">
                    <label className="text-sm font-medium">Swarm URL</label>
                    <input
                        type="url"
                        value={url}
                        onChange={(e) => setUrl(e.target.value)}
                        placeholder="https://oak-swarm-yourteam.workers.dev"
                        className="w-full rounded-md border bg-background px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring"
                        disabled={isBusy}
                    />
                </div>
                <div className="space-y-1.5">
                    <label className="text-sm font-medium">Swarm Token</label>
                    <input
                        type="password"
                        value={token}
                        onChange={(e) => setToken(e.target.value)}
                        placeholder="Swarm authentication token"
                        className="w-full rounded-md border bg-background px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring"
                        disabled={isBusy}
                    />
                </div>

                {joinError && (
                    <Alert variant="destructive">
                        <AlertCircle className="h-4 w-4" />
                        <AlertDescription>{joinError}</AlertDescription>
                    </Alert>
                )}

                {joinSuccess && (
                    <div className="flex items-center gap-2 text-sm text-green-600 dark:text-green-400">
                        <CheckCircle2 className="h-4 w-4" />
                        Successfully joined the swarm.
                    </div>
                )}
            </CardContent>
            <CardFooter>
                <Button
                    onClick={() => onJoin(url.trim(), token.trim())}
                    disabled={!url.trim() || !token.trim() || isBusy}
                    size="sm"
                >
                    {isJoining ? (
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                        <Hexagon className="h-4 w-4 mr-2" />
                    )}
                    {isJoining ? "Joining..." : "Join Swarm"}
                </Button>
            </CardFooter>
        </Card>
    );
}
