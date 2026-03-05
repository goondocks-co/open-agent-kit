/**
 * MCP Endpoint card — displays the cloud agent MCP endpoint URL + agent token.
 * Shown on the Deploy page below swarm credentials.
 */

import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@oak/ui/components/ui/card";
import { Button } from "@oak/ui/components/ui/button";
import { CopyButton } from "@oak/ui/components/ui/command-block";
import { Globe, Eye, EyeOff } from "lucide-react";

export interface McpEndpointCardProps {
    mcpEndpoint: string;
    agentToken: string | null;
}

export function McpEndpointCard({ mcpEndpoint, agentToken }: McpEndpointCardProps) {
    const [showToken, setShowToken] = useState(false);
    const maskedToken = agentToken ? "\u2022".repeat(Math.min(agentToken.length, 32)) : null;

    return (
        <Card>
            <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                    <Globe className="h-4 w-4" />
                    MCP Endpoint
                </CardTitle>
                <CardDescription>
                    Connect cloud agents to the swarm using this endpoint and token.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                {/* Endpoint URL */}
                <div className="space-y-1.5">
                    <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                        Endpoint URL
                    </label>
                    <div className="flex items-center gap-2 bg-muted rounded-md px-4 py-3 font-mono text-sm">
                        <code className="flex-1 truncate">{mcpEndpoint}</code>
                        <CopyButton text={mcpEndpoint} />
                    </div>
                </div>

                {/* Agent Token */}
                {agentToken && (
                    <div className="space-y-1.5">
                        <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                            Agent Token
                        </label>
                        <div className="flex items-center gap-2 bg-muted rounded-md px-4 py-3 font-mono text-sm">
                            <code className="flex-1 truncate">
                                {showToken ? agentToken : maskedToken}
                            </code>
                            <Button variant="ghost" size="sm" className="h-8 w-8 p-0"
                                onClick={() => setShowToken(!showToken)}>
                                {showToken ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                            </Button>
                            <CopyButton text={agentToken} />
                        </div>
                        <p className="text-xs text-muted-foreground">
                            Include in the <code className="bg-muted px-1 rounded">Authorization: Bearer</code> header when connecting.
                        </p>
                    </div>
                )}
            </CardContent>
        </Card>
    );
}
