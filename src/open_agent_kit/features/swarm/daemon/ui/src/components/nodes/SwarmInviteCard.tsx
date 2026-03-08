/**
 * Swarm invite card — displays swarm URL, token, and CLI command for teams to join.
 */

import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@oak/ui/components/ui/card";
import { Button } from "@oak/ui/components/ui/button";
import { CopyButton, CommandBlock } from "@oak/ui/components/ui/command-block";
import { Link2, Eye, EyeOff } from "lucide-react";
import { useSwarmStatus } from "@/hooks/use-swarm-status";
import { useSwarmCredentials } from "@/hooks/use-swarm-credentials";

export function SwarmInviteCard() {
    const { data: status } = useSwarmStatus();
    const { data: credentials } = useSwarmCredentials();
    const [showToken, setShowToken] = useState(false);

    const swarmUrl = status?.swarm_url ?? "";
    const swarmToken = credentials?.swarm_token ?? "";

    if (!swarmUrl) return null;

    const cliCommand = `oak team join-swarm --url ${swarmUrl} --token ${showToken && swarmToken ? swarmToken : "<token>"}`;

    return (
        <Card>
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    <Link2 className="h-5 w-5" />
                    Invite Teams
                </CardTitle>
                <CardDescription>
                    Share the swarm URL and token with teams so they can connect to this swarm.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                {/* Swarm URL */}
                <div className="space-y-1.5">
                    <label className="text-sm font-medium">Swarm URL</label>
                    <div className="flex items-center gap-2">
                        <code className="flex-1 rounded-md border bg-muted px-3 py-2 text-sm font-mono truncate">
                            {swarmUrl}
                        </code>
                        <CopyButton text={swarmUrl} />
                    </div>
                </div>

                {/* Swarm Token */}
                {swarmToken && (
                    <div className="space-y-1.5">
                        <label className="text-sm font-medium">Swarm Token</label>
                        <div className="flex items-center gap-2">
                            <code className="flex-1 rounded-md border bg-muted px-3 py-2 text-sm font-mono truncate">
                                {showToken ? swarmToken : "\u2022".repeat(24)}
                            </code>
                            <Button
                                variant="ghost"
                                size="sm"
                                className="h-8 w-8 p-0"
                                onClick={() => setShowToken(!showToken)}
                            >
                                {showToken ? (
                                    <EyeOff className="h-4 w-4" />
                                ) : (
                                    <Eye className="h-4 w-4" />
                                )}
                            </Button>
                            <CopyButton text={swarmToken} />
                        </div>
                    </div>
                )}

                {/* CLI command */}
                <div className="space-y-1.5">
                    <label className="text-sm font-medium">CLI Command</label>
                    <CommandBlock command={cliCommand} />
                </div>

                <p className="text-xs text-muted-foreground">
                    Teams can run the CLI command above or enter the URL and token in their
                    Team dashboard to join this swarm.
                </p>
            </CardContent>
        </Card>
    );
}
