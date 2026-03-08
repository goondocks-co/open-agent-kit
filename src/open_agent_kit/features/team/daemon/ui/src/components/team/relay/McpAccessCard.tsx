/**
 * MCP Access section — endpoint, agent token, mcp.json config, and test command.
 */

import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@oak/ui/components/ui/card";
import { Button } from "@oak/ui/components/ui/button";
import { CopyButton, CommandBlock } from "@oak/ui/components/ui/command-block";
import { Globe, Bot, FileJson, FlaskConical, ExternalLink, Eye, EyeOff } from "lucide-react";

function McpJsonBlock({ mcpEndpoint, agentToken }: { mcpEndpoint: string; agentToken: string | null }) {
    const tokenPlaceholder = agentToken || "<your-agent-token>";
    const jsonConfig = JSON.stringify(
        { mcpServers: { "oak-team": { url: mcpEndpoint, headers: { Authorization: `Bearer ${tokenPlaceholder}` } } } },
        null, 2,
    );
    return (
        <div className="relative">
            <pre className="rounded-md bg-muted p-4 text-xs font-mono overflow-x-auto whitespace-pre border">
                {jsonConfig}
            </pre>
            <div className="absolute top-2 right-2">
                <CopyButton text={jsonConfig} />
            </div>
        </div>
    );
}

export function McpAccessCard({ mcpEndpoint, agentToken }: { mcpEndpoint: string; agentToken: string | null }) {
    const [showToken, setShowToken] = useState(false);
    const maskedToken = agentToken ? "\u2022".repeat(Math.min(agentToken.length, 32)) : null;

    return (
        <div className="space-y-4">
            <Card>
                <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2 text-base">
                        <Globe className="h-4 w-4" />
                        MCP Endpoint
                    </CardTitle>
                    <CardDescription>
                        Give this URL to cloud AI agents (Claude.ai, ChatGPT, etc.).
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="flex items-center gap-2 bg-muted rounded-md px-4 py-3 font-mono text-sm">
                        <code className="flex-1 truncate">{mcpEndpoint}</code>
                        <CopyButton text={mcpEndpoint} />
                        <a href={mcpEndpoint} target="_blank" rel="noopener noreferrer"
                            className="text-muted-foreground hover:text-foreground transition-colors">
                            <ExternalLink className="w-4 h-4" />
                        </a>
                    </div>
                </CardContent>
            </Card>

            {agentToken && (
                <Card>
                    <CardHeader className="pb-3">
                        <CardTitle className="flex items-center gap-2 text-base">
                            <Bot className="h-4 w-4" />
                            Agent Token
                        </CardTitle>
                        <CardDescription>
                            Use this token (not the relay token) to authenticate AI agents.
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
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
                    </CardContent>
                </Card>
            )}

            <Card>
                <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2 text-base">
                        <FileJson className="h-4 w-4" />
                        MCP Config (mcp.json)
                    </CardTitle>
                    <CardDescription>
                        Add Oak CI to any MCP-compatible client.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <McpJsonBlock mcpEndpoint={mcpEndpoint} agentToken={agentToken} />
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1 text-xs text-muted-foreground">
                        <div><strong>Claude Code</strong> — <code className="bg-muted px-1 rounded">.claude/mcp.json</code></div>
                        <div><strong>Cursor</strong> — <code className="bg-muted px-1 rounded">.cursor/mcp.json</code></div>
                        <div><strong>Windsurf</strong> — <code className="bg-muted px-1 rounded">.windsurf/mcp.json</code></div>
                        <div><strong>VS Code Copilot</strong> — <code className="bg-muted px-1 rounded">.vscode/mcp.json</code></div>
                    </div>
                </CardContent>
            </Card>

            <Card>
                <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2 text-base">
                        <FlaskConical className="h-4 w-4" />
                        Test the Relay
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <CommandBlock
                        command={`curl -X POST ${mcpEndpoint} -H "Content-Type: application/json" -H "Authorization: Bearer <agent-token>" -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'`}
                        label="List available MCP tools"
                    />
                </CardContent>
            </Card>
        </div>
    );
}
