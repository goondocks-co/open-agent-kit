/**
 * Join Swarm card — allows a team to connect to a swarm via URL + token.
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
} from "lucide-react";

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
    } | null;
}

export function JoinSwarmCard({
    onJoin,
    onLeave,
    isJoining,
    isLeaving,
    joinError,
    joinSuccess,
    swarmStatus,
}: JoinSwarmCardProps) {
    const [url, setUrl] = useState("");
    const [token, setToken] = useState("");

    const isBusy = isJoining || isLeaving;
    const isJoined = swarmStatus?.joined ?? false;

    // Connected state
    if (isJoined) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Hexagon className="h-5 w-5" />
                        Swarm
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
