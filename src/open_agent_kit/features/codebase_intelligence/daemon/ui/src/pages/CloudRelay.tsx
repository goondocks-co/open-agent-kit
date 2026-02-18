/**
 * Cloud Relay page — single-page turnkey UX for deploying and managing
 * a Cloudflare Worker relay. Mirrors the TeamSharing.tsx pattern.
 */

import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
    Cloud,
    Loader2,
    AlertCircle,
    CheckCircle2,
    ExternalLink,
    Check,
    X,
    Eye,
    EyeOff,
    ChevronDown,
    ChevronRight,
    Bot,
    FileJson,
    FlaskConical,
    Settings,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { CopyButton, CommandBlock } from "@/components/ui/command-block";
import {
    useCloudRelayStatus,
    useCloudRelayStart,
    useCloudRelayStop,
    useCloudRelayPreflight,
    useCloudRelayUpdateSettings,
} from "@/hooks/use-cloud-relay";
import type { CloudRelayStartResponse } from "@/hooks/use-cloud-relay";

// =============================================================================
// Prerequisites Card
// =============================================================================

interface PrerequisiteItemProps {
    label: string;
    satisfied: boolean;
}

function PrerequisiteItem({ label, satisfied }: PrerequisiteItemProps) {
    return (
        <div className="flex items-center gap-2 text-sm">
            {satisfied ? (
                <Check className="h-4 w-4 text-green-500 flex-shrink-0" />
            ) : (
                <X className="h-4 w-4 text-muted-foreground flex-shrink-0" />
            )}
            <span className={cn(satisfied ? "text-foreground" : "text-muted-foreground")}>
                {label}
            </span>
        </div>
    );
}

function PrerequisitesCard() {
    const { data: preflight, isLoading } = useCloudRelayPreflight();

    if (isLoading) {
        return (
            <Card className="border-dashed">
                <CardContent className="flex items-center justify-center py-8">
                    <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                </CardContent>
            </Card>
        );
    }

    if (!preflight) return null;

    return (
        <Card className="border-dashed">
            <CardHeader className="pb-3">
                <CardTitle className="text-base">Prerequisites</CardTitle>
                <CardDescription>
                    These are checked before starting the relay.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
                <PrerequisiteItem label="Node.js / npm available" satisfied={preflight.npm_available} />
                <PrerequisiteItem label="Wrangler CLI available" satisfied={preflight.wrangler_available} />
                <PrerequisiteItem label="Wrangler authenticated" satisfied={preflight.wrangler_authenticated} />
                {preflight.cf_account_name && (
                    <div className="text-xs text-muted-foreground pl-6">
                        Account: {preflight.cf_account_name}
                    </div>
                )}
                {!preflight.wrangler_available && (
                    <div className="pt-2">
                        <CommandBlock command="npm install -g wrangler && wrangler login" label="Install and authenticate" />
                    </div>
                )}
                {preflight.wrangler_available && !preflight.wrangler_authenticated && (
                    <div className="pt-2">
                        <CommandBlock command="wrangler login" label="Authenticate with Cloudflare" />
                    </div>
                )}
                <p className="text-xs text-muted-foreground pt-2">
                    <Link to="/help" state={{ tab: "cloud-relay" }} className="text-primary hover:underline">
                        Cloud relay setup guide
                    </Link>
                </p>
            </CardContent>
        </Card>
    );
}

// =============================================================================
// Error Card
// =============================================================================

interface ErrorCardProps {
    response: CloudRelayStartResponse;
}

function ErrorCard({ response }: ErrorCardProps) {
    const [showDetail, setShowDetail] = useState(false);

    return (
        <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription className="space-y-2">
                <p>{response.error}</p>
                {response.suggestion && (
                    <p className="text-sm opacity-80">{response.suggestion}</p>
                )}
                {response.detail && (
                    <div>
                        <button
                            onClick={() => setShowDetail(!showDetail)}
                            className="flex items-center gap-1 text-xs underline opacity-70 hover:opacity-100"
                        >
                            {showDetail ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                            {showDetail ? "Hide details" : "Show details"}
                        </button>
                        {showDetail && (
                            <pre className="mt-2 rounded-md bg-background/50 p-3 text-xs font-mono overflow-x-auto whitespace-pre-wrap border">
                                {response.detail}
                            </pre>
                        )}
                    </div>
                )}
            </AlertDescription>
        </Alert>
    );
}

// =============================================================================
// Agent Registration Section
// =============================================================================

function McpJsonBlock({ mcpEndpoint, agentToken }: { mcpEndpoint: string; agentToken: string | null }) {
    const tokenPlaceholder = agentToken || "<your-agent-token>";
    const jsonConfig = JSON.stringify(
        {
            mcpServers: {
                "oak-ci": {
                    url: mcpEndpoint,
                    headers: {
                        Authorization: `Bearer ${tokenPlaceholder}`,
                    },
                },
            },
        },
        null,
        2,
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

function AgentRegistration({ mcpEndpoint, agentToken }: { mcpEndpoint: string; agentToken: string | null }) {
    const [showToken, setShowToken] = useState(false);
    const maskedToken = agentToken ? "*".repeat(Math.min(agentToken.length, 32)) : null;

    return (
        <div className="space-y-6">
            {/* Agent Token */}
            {agentToken && (
                <Card>
                    <CardHeader className="pb-3">
                        <CardTitle className="flex items-center gap-2 text-base">
                            <Bot className="h-4 w-4" />
                            Agent Token
                        </CardTitle>
                        <CardDescription>
                            Use this token when registering agents with your relay.
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="flex items-center gap-2 bg-muted rounded-md px-4 py-3 font-mono text-sm">
                            <code className="flex-1 truncate">
                                {showToken ? agentToken : maskedToken}
                            </code>
                            <Button
                                variant="ghost"
                                size="sm"
                                className="h-8 w-8 p-0"
                                onClick={() => setShowToken(!showToken)}
                            >
                                {showToken ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                            </Button>
                            <CopyButton text={agentToken} />
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* MCP Config (mcp.json) */}
            <Card>
                <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2 text-base">
                        <FileJson className="h-4 w-4" />
                        MCP Config (mcp.json)
                    </CardTitle>
                    <CardDescription>
                        Add Oak CI to any MCP-compatible client by adding this to your config file.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <McpJsonBlock mcpEndpoint={mcpEndpoint} agentToken={agentToken} />
                    <div className="space-y-2">
                        <div className="text-xs font-medium text-muted-foreground">Config file locations</div>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1 text-xs text-muted-foreground">
                            <div><strong>Claude Code</strong> &mdash; <code className="bg-muted px-1 rounded">.claude/mcp.json</code></div>
                            <div><strong>Cursor</strong> &mdash; <code className="bg-muted px-1 rounded">.cursor/mcp.json</code></div>
                            <div><strong>Windsurf</strong> &mdash; <code className="bg-muted px-1 rounded">.windsurf/mcp.json</code></div>
                            <div><strong>VS Code Copilot</strong> &mdash; <code className="bg-muted px-1 rounded">.vscode/mcp.json</code></div>
                        </div>
                        <p className="text-xs text-muted-foreground">
                            Place the file in your project root for per-project config, or in your home directory for global config.
                        </p>
                    </div>
                </CardContent>
            </Card>

            {/* Claude.ai */}
            <Card>
                <CardHeader className="pb-3">
                    <CardTitle className="text-base">Claude.ai</CardTitle>
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
                            <a
                                href={mcpEndpoint}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-muted-foreground hover:text-foreground transition-colors"
                            >
                                <ExternalLink className="w-4 h-4" />
                            </a>
                        </div>
                    </div>
                    <p className="text-sm text-muted-foreground">
                        Enter your agent token when prompted for authentication.
                    </p>
                </CardContent>
            </Card>

            {/* ChatGPT */}
            <Card>
                <CardHeader className="pb-3">
                    <CardTitle className="text-base">ChatGPT</CardTitle>
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

            {/* Testing */}
            <Card>
                <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2 text-base">
                        <FlaskConical className="h-4 w-4" />
                        Testing
                    </CardTitle>
                    <CardDescription>
                        Verify your relay is working.
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
                    <p className="text-sm text-muted-foreground">
                        For interactive testing, use the{" "}
                        <a
                            href="https://github.com/modelcontextprotocol/inspector"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-primary hover:underline inline-flex items-center gap-1"
                        >
                            MCP Inspector
                            <ExternalLink className="h-3 w-3" />
                        </a>
                        {" "}&mdash; a visual tool for browsing and calling MCP server tools.
                    </p>
                </CardContent>
            </Card>
        </div>
    );
}

// =============================================================================
// Custom Domain Settings
// =============================================================================

interface CustomDomainSettingsProps {
    currentDomain: string | null;
    workerName: string | null;
    isConnected: boolean;
}

function CustomDomainSettings({ currentDomain, workerName, isConnected }: CustomDomainSettingsProps) {
    const [domain, setDomain] = useState(currentDomain ?? "");
    const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
    const updateSettings = useCloudRelayUpdateSettings();

    // Sync local state when server value changes (e.g. after save or external update)
    useEffect(() => {
        setDomain(currentDomain ?? "");
    }, [currentDomain]);

    const hasChanged = domain !== (currentDomain ?? "");
    const isSaving = updateSettings.isPending;
    const trimmedDomain = domain.trim();

    // Derive the subdomain preview from workerName + entered domain
    const derivedSubdomain = trimmedDomain && workerName
        ? `${workerName}.${trimmedDomain}`
        : null;

    const handleSave = () => {
        setMessage(null);
        updateSettings.mutate(
            { custom_domain: trimmedDomain || null },
            {
                onSuccess: () => setMessage({ type: "success", text: "Custom domain saved." }),
                onError: (err) => setMessage({ type: "error", text: err.message }),
            },
        );
    };

    const handleClear = () => {
        setMessage(null);
        updateSettings.mutate(
            { custom_domain: null },
            {
                onSuccess: () => setMessage({ type: "success", text: "Custom domain cleared." }),
                onError: (err) => setMessage({ type: "error", text: err.message }),
            },
        );
    };

    return (
        <Card>
            <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                    <Settings className="h-4 w-4" />
                    Settings
                </CardTitle>
                <CardDescription>
                    Configure advanced relay options.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                <div className="space-y-2">
                    <label className="text-sm font-medium">Custom Domain</label>
                    <div className="flex items-center gap-2">
                        <input
                            type="text"
                            value={domain}
                            onChange={(e) => setDomain(e.target.value)}
                            placeholder="example.com"
                            className="flex-1 rounded-md border bg-background px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring"
                            disabled={isSaving}
                        />
                        <Button
                            onClick={handleSave}
                            disabled={!hasChanged || isSaving}
                            size="sm"
                        >
                            {isSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : "Save"}
                        </Button>
                    </div>
                    <p className="text-xs text-muted-foreground">
                        Enter your Cloudflare domain. The MCP endpoint will
                        be <code className="bg-muted px-1 rounded">{derivedSubdomain
                            ? `${derivedSubdomain}/mcp`
                            : `{worker}.{domain}/mcp`
                        }</code>.
                        The domain must be in the same Cloudflare account.
                    </p>
                    {derivedSubdomain && (
                        <div className="flex items-center gap-2 bg-muted/50 rounded-md px-3 py-2 text-xs font-mono border border-dashed">
                            <span className="text-muted-foreground">Endpoint:</span>
                            <code>{derivedSubdomain}/mcp</code>
                        </div>
                    )}
                    {isConnected && hasChanged && trimmedDomain !== (currentDomain ?? "") && (
                        <p className="text-xs text-amber-600 dark:text-amber-400">
                            Re-deploy needed — click Start Relay to apply.
                        </p>
                    )}
                    {currentDomain && (
                        <button
                            onClick={handleClear}
                            disabled={isSaving}
                            className="text-xs text-muted-foreground underline hover:text-foreground"
                        >
                            Clear custom domain
                        </button>
                    )}
                </div>

                {message && (
                    <div className={cn(
                        "p-3 rounded-md text-sm flex items-center gap-2",
                        message.type === "success" ? "bg-green-500/10 text-green-600" : "bg-red-500/10 text-red-600",
                    )}>
                        {message.type === "success"
                            ? <CheckCircle2 className="h-4 w-4" />
                            : <AlertCircle className="h-4 w-4" />}
                        {message.text}
                    </div>
                )}
            </CardContent>
        </Card>
    );
}

// =============================================================================
// Cloud Relay Page
// =============================================================================

export default function CloudRelay() {
    const { data: status, isLoading } = useCloudRelayStatus();
    const startRelay = useCloudRelayStart();
    const stopRelay = useCloudRelayStop();

    const isConnected = status?.connected ?? false;
    const isToggling = startRelay.isPending || stopRelay.isPending;

    const handleToggle = () => {
        if (isConnected) {
            stopRelay.mutate();
        } else {
            // Clear stale data/errors from any previous attempt so they
            // don't briefly flash while the new request is in-flight.
            startRelay.reset();
            startRelay.mutate();
        }
    };

    // Derive MCP endpoint from status or start response
    const mcpEndpoint = status?.mcp_endpoint
        ?? startRelay.data?.mcp_endpoint
        ?? (status?.worker_url ? `${status.worker_url}/mcp` : null);

    const agentToken = status?.agent_token ?? startRelay.data?.agent_token ?? null;
    const cfAccountName = status?.cf_account_name ?? startRelay.data?.cf_account_name ?? null;

    // Check if start mutation returned an error response (status !== "error" means HTTP 200 but logical error)
    const startError = startRelay.data?.error ? startRelay.data : null;

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex flex-col gap-2">
                <h1 className="text-3xl font-bold tracking-tight flex items-center gap-3">
                    <Cloud className="w-8 h-8" />
                    Cloud Relay
                </h1>
                <p className="text-muted-foreground">
                    Deploy a Cloudflare Worker so cloud AI agents can access your local Oak CI instance.
                </p>
            </div>

            {/* Main Control Card */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Cloud className="h-5 w-5" />
                        Relay Connection
                    </CardTitle>
                    <CardDescription>
                        {isConnected
                            ? "Your relay is active. Cloud agents can connect to your local instance."
                            : "Start the relay to deploy a Cloudflare Worker and connect automatically."
                        }
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    {/* Status + Toggle */}
                    <div className="flex items-center justify-between p-4 rounded-lg bg-muted/50">
                        <div className="flex items-center gap-3">
                            <div className={cn(
                                "w-3 h-3 rounded-full",
                                isConnected ? "bg-green-500" : "bg-gray-400"
                            )} />
                            <div>
                                <div className="font-medium text-sm">
                                    {isConnected ? "Relay Active" : "Relay Inactive"}
                                </div>
                                {isConnected && cfAccountName && (
                                    <div className="text-xs text-muted-foreground">
                                        Cloudflare account: {cfAccountName}
                                    </div>
                                )}
                            </div>
                        </div>
                        <Button
                            onClick={handleToggle}
                            disabled={isToggling || isLoading}
                            variant={isConnected ? "outline" : "default"}
                            size="sm"
                            aria-label={isConnected ? "Stop cloud relay" : "Start cloud relay"}
                        >
                            {isToggling ? (
                                <>
                                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                    {startRelay.isPending ? "Starting..." : "Stopping..."}
                                </>
                            ) : isConnected ? (
                                "Stop Relay"
                            ) : (
                                <>
                                    <Cloud className="h-4 w-4 mr-2" />
                                    Start Relay
                                </>
                            )}
                        </Button>
                    </div>

                    {/* MCP URL display (when connected) */}
                    {isConnected && mcpEndpoint && (
                        <div className="space-y-2">
                            <label className="text-sm font-medium">MCP Server URL</label>
                            <div className="flex items-center gap-2">
                                <code className="flex-1 bg-muted px-3 py-2 rounded-md text-sm font-mono truncate border">
                                    {mcpEndpoint}
                                </code>
                                <CopyButton text={mcpEndpoint} />
                                <Button
                                    variant="outline"
                                    size="sm"
                                    className="flex-shrink-0"
                                    asChild
                                >
                                    <a href={mcpEndpoint} target="_blank" rel="noopener noreferrer">
                                        <ExternalLink className="h-4 w-4" />
                                    </a>
                                </Button>
                            </div>
                            <p className="text-xs text-muted-foreground">
                                Give this URL to cloud AI agents (Claude.ai, ChatGPT, etc.) as the MCP server endpoint.
                            </p>
                        </div>
                    )}

                    {/* Errors — hide when relay is connected (stale from previous attempt) */}
                    {!isConnected && startError && <ErrorCard response={startError} />}

                    {!isConnected && startRelay.error && !startError && (
                        <Alert variant="destructive">
                            <AlertCircle className="h-4 w-4" />
                            <AlertDescription>{startRelay.error.message}</AlertDescription>
                        </Alert>
                    )}

                    {stopRelay.error && (
                        <Alert variant="destructive">
                            <AlertCircle className="h-4 w-4" />
                            <AlertDescription>{stopRelay.error.message}</AlertDescription>
                        </Alert>
                    )}
                </CardContent>
            </Card>

            {/* Settings */}
            <CustomDomainSettings
                currentDomain={status?.custom_domain ?? null}
                workerName={status?.worker_name ?? startRelay.data?.worker_name ?? null}
                isConnected={isConnected}
            />

            {/* Agent Registration (when connected) */}
            {isConnected && mcpEndpoint && (
                <AgentRegistration mcpEndpoint={mcpEndpoint} agentToken={agentToken} />
            )}

            {/* Prerequisites (when not connected) */}
            {!isConnected && <PrerequisitesCard />}
        </div>
    );
}
