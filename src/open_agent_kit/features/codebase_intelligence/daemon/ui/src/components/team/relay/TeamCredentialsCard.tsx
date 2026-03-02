/**
 * Team Credentials card — displays relay URL + token for the deployer to share.
 */

import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { CopyButton, CommandBlock } from "@/components/ui/command-block";
import { Link2, ExternalLink, Eye, EyeOff } from "lucide-react";

export function TeamCredentialsCard({ workerUrl, relayToken }: { workerUrl: string; relayToken: string | null }) {
    const [showToken, setShowToken] = useState(false);
    const maskedToken = relayToken ? "\u2022".repeat(Math.min(relayToken.length, 32)) : null;

    const cliCommands = [
        `oak ci config set team.relay_worker_url ${workerUrl}`,
        relayToken ? `oak ci config set team.api_key ${relayToken}` : null,
    ].filter(Boolean).join("\n");

    return (
        <Card>
            <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                    <Link2 className="h-4 w-4" />
                    Team Credentials
                </CardTitle>
                <CardDescription>
                    Share these with teammates so they can join your relay.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                {/* Relay URL */}
                <div className="space-y-1.5">
                    <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                        Relay URL
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

                {/* Relay Token */}
                {relayToken && (
                    <div className="space-y-1.5">
                        <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                            Relay Token
                        </label>
                        <div className="flex items-center gap-2 bg-muted rounded-md px-4 py-3 font-mono text-sm">
                            <code className="flex-1 truncate">
                                {showToken ? relayToken : maskedToken}
                            </code>
                            <Button variant="ghost" size="sm" className="h-8 w-8 p-0"
                                onClick={() => setShowToken(!showToken)}>
                                {showToken ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                            </Button>
                            <CopyButton text={relayToken} />
                        </div>
                    </div>
                )}

                {/* CLI snippet */}
                <CommandBlock command={cliCommands} label="Teammate setup (run on their machine)" />
            </CardContent>
        </Card>
    );
}
