/**
 * Cloud Relay agents page — agent token display and registration instructions.
 */

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Bot, ExternalLink } from "lucide-react";
import { CopyButton, CommandBlock } from "@/components/ui/command-block";
import { useCloudRelayStatus } from "@/hooks/use-cloud-relay";

// =============================================================================
// Cloud Agents Page
// =============================================================================

export default function CloudAgents() {
    const { data: status } = useCloudRelayStatus();
    const workerUrl = status?.worker_url;
    const connected = status?.connected ?? false;

    if (!connected) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Bot className="w-5 h-5" />
                        Cloud Agents
                    </CardTitle>
                    <CardDescription>
                        Connect to a cloud relay first to register agents.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="rounded-lg border border-yellow-200 dark:border-yellow-800 bg-yellow-50 dark:bg-yellow-950/30 p-4">
                        <p className="text-sm text-yellow-800 dark:text-yellow-200">
                            You need an active cloud relay connection before you can register agents.
                            Go to the <strong>Status</strong> tab to connect, or follow the <strong>Setup</strong> guide
                            if you haven't deployed a relay yet.
                        </p>
                    </div>
                </CardContent>
            </Card>
        );
    }

    const mcpEndpoint = workerUrl ? `${workerUrl}/mcp` : "<worker-url>/mcp";

    return (
        <div className="space-y-6">
            {/* Agent Token */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Bot className="w-5 h-5" />
                        Agent Token
                    </CardTitle>
                    <CardDescription>
                        Cloud agents use this token to authenticate with your relay.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="rounded-lg border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-950/30 p-4 space-y-2">
                        <p className="text-sm text-blue-800 dark:text-blue-200">
                            Your agent token is configured in the relay Worker's environment variables.
                            Use the same token value you set during <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded">oak ci cloud-init</code>.
                        </p>
                        <CommandBlock command="wrangler secret list --name oak-cloud-relay" label="View configured secrets" />
                    </div>
                </CardContent>
            </Card>

            {/* Claude.ai Registration */}
            <Card>
                <CardHeader>
                    <CardTitle>Claude.ai</CardTitle>
                    <CardDescription>
                        Add Oak CI as an MCP server in Claude.ai.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <ol className="list-decimal list-inside text-sm text-muted-foreground space-y-2">
                        <li>Open Claude.ai settings and navigate to the <strong>MCP Servers</strong> section</li>
                        <li>Click <strong>Add MCP Server</strong></li>
                        <li>Enter the following URL as the server endpoint:</li>
                    </ol>
                    <div className="space-y-1">
                        <div className="text-xs text-muted-foreground">MCP Server URL</div>
                        <div className="flex items-center gap-2 bg-muted rounded-md px-4 py-3 font-mono text-sm">
                            <code className="flex-1 truncate">{mcpEndpoint}</code>
                            <CopyButton text={mcpEndpoint} />
                            {workerUrl && (
                                <a
                                    href={mcpEndpoint}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-muted-foreground hover:text-foreground transition-colors"
                                >
                                    <ExternalLink className="w-4 h-4" />
                                </a>
                            )}
                        </div>
                    </div>
                    <p className="text-sm text-muted-foreground">
                        Enter your agent token when prompted for authentication.
                    </p>
                </CardContent>
            </Card>

            {/* ChatGPT Registration */}
            <Card>
                <CardHeader>
                    <CardTitle>ChatGPT</CardTitle>
                    <CardDescription>
                        Connect Oak CI as a tool in ChatGPT.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <ol className="list-decimal list-inside text-sm text-muted-foreground space-y-2">
                        <li>Open ChatGPT and go to <strong>Settings</strong> &gt; <strong>Connected Tools</strong></li>
                        <li>Click <strong>Add Tool</strong> and select MCP</li>
                        <li>Enter the MCP server URL:</li>
                    </ol>
                    <div className="space-y-1">
                        <div className="text-xs text-muted-foreground">MCP Server URL</div>
                        <div className="flex items-center gap-2 bg-muted rounded-md px-4 py-3 font-mono text-sm">
                            <code className="flex-1 truncate">{mcpEndpoint}</code>
                            <CopyButton text={mcpEndpoint} />
                        </div>
                    </div>
                    <p className="text-sm text-muted-foreground">
                        Authenticate using your agent token when prompted.
                    </p>
                </CardContent>
            </Card>

            {/* Generic / Testing */}
            <Card>
                <CardHeader>
                    <CardTitle>Testing with curl</CardTitle>
                    <CardDescription>
                        Verify your relay is working with a simple API call.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <CommandBlock
                        command={`curl -X POST ${mcpEndpoint} -H "Content-Type: application/json" -H "Authorization: Bearer <your-agent-token>" -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'`}
                        label="List available tools"
                    />
                    <p className="text-sm text-muted-foreground">
                        Replace <code className="bg-muted px-1 rounded">&lt;your-agent-token&gt;</code> with your actual agent token.
                        A successful response will return a JSON-RPC result with the available Oak CI tools.
                    </p>
                </CardContent>
            </Card>
        </div>
    );
}
