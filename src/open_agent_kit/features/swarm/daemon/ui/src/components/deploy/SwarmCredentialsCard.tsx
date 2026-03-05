/**
 * Swarm Credentials card — displays swarm URL + token for sharing.
 * Mirrors TeamCredentialsCard pattern.
 */

import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@oak/ui/components/ui/card";
import { Button } from "@oak/ui/components/ui/button";
import { CopyButton } from "@oak/ui/components/ui/command-block";
import { Link2, ExternalLink, Eye, EyeOff } from "lucide-react";

export interface SwarmCredentialsCardProps {
    workerUrl: string;
    swarmToken: string | null;
}

export function SwarmCredentialsCard({ workerUrl, swarmToken }: SwarmCredentialsCardProps) {
    const [showToken, setShowToken] = useState(false);
    const maskedToken = swarmToken ? "\u2022".repeat(Math.min(swarmToken.length, 32)) : null;

    return (
        <Card>
            <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                    <Link2 className="h-4 w-4" />
                    Swarm Credentials
                </CardTitle>
                <CardDescription>
                    Share these with nodes so they can join your swarm.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                {/* Swarm URL */}
                <div className="space-y-1.5">
                    <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                        Swarm URL
                    </label>
                    <div className="flex items-center gap-2 bg-muted rounded-md px-4 py-3 font-mono text-sm">
                        <code className="flex-1 truncate">{workerUrl}</code>
                        <CopyButton text={workerUrl} />
                        <a href={workerUrl} target="_blank" rel="noopener noreferrer"
                            className="text-muted-foreground hover:text-foreground transition-colors">
                            <ExternalLink className="w-4 h-4" />
                        </a>
                    </div>
                </div>

                {/* Swarm Token */}
                {swarmToken && (
                    <div className="space-y-1.5">
                        <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                            Swarm Token
                        </label>
                        <div className="flex items-center gap-2 bg-muted rounded-md px-4 py-3 font-mono text-sm">
                            <code className="flex-1 truncate">
                                {showToken ? swarmToken : maskedToken}
                            </code>
                            <Button variant="ghost" size="sm" className="h-8 w-8 p-0"
                                onClick={() => setShowToken(!showToken)}>
                                {showToken ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                            </Button>
                            <CopyButton text={swarmToken} />
                        </div>
                    </div>
                )}
            </CardContent>
        </Card>
    );
}
