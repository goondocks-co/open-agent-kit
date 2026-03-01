/**
 * Team Connectivity page — cloud relay controls, team join URL, and MCP server URL.
 *
 * Shows relay controls + URLs for remote access and agent registration.
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
    Globe,
    Link2,
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
// Team URLs Section (shown when relay is connected)
// =============================================================================

function TeamUrls({ workerUrl, mcpEndpoint }: { workerUrl: string; mcpEndpoint: string }) {
    return (
        <div className="space-y-4">
            {/* Team Join URL */}
            <Card>
                <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2 text-base">
                        <Link2 className="h-4 w-4" />
                        Team Join URL
                    </CardTitle>
                    <CardDescription>
                        Share this URL with teammates so they can request to join your team.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="flex items-center gap-2 bg-muted rounded-md px-4 py-3 font-mono text-sm">
                        <code className="flex-1 truncate">{workerUrl}</code>
                        <CopyButton text={workerUrl} />
                        <a
                            href={workerUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-muted-foreground hover:text-foreground transition-colors"
                        >
                            <ExternalLink className="w-4 h-4" />
                        </a>
                    </div>
                </CardContent>
            </Card>

            {/* MCP Server URL */}
            <Card>
                <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2 text-base">
                        <Globe className="h-4 w-4" />
                        MCP Server URL
                    </CardTitle>
                    <CardDescription>
                        Give this URL to cloud AI agents (Claude.ai, ChatGPT, etc.) as the MCP server endpoint.
                    </CardDescription>
                </CardHeader>
                <CardContent>
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
                </CardContent>
            </Card>
        </div>
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

    useEffect(() => {
        setDomain(currentDomain ?? "");
    }, [currentDomain]);

    const hasChanged = domain !== (currentDomain ?? "");
    const isSaving = updateSettings.isPending;
    const trimmedDomain = domain.trim();

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
// Main Component
// =============================================================================

export default function TeamConnectivity() {
    const { data: status, isLoading } = useCloudRelayStatus();
    const startRelay = useCloudRelayStart();
    const stopRelay = useCloudRelayStop();

    const isConnected = status?.connected ?? false;
    const isToggling = startRelay.isPending || stopRelay.isPending;

    const handleToggle = () => {
        if (isConnected) {
            stopRelay.mutate();
        } else {
            startRelay.reset();
            startRelay.mutate();
        }
    };

    // Derive URLs from status or start response
    const workerUrl = status?.worker_url ?? startRelay.data?.worker_url ?? null;
    const mcpEndpoint = status?.mcp_endpoint
        ?? startRelay.data?.mcp_endpoint
        ?? (workerUrl ? `${workerUrl}/mcp` : null);

    const agentToken = status?.agent_token ?? startRelay.data?.agent_token ?? null;
    const cfAccountName = status?.cf_account_name ?? startRelay.data?.cf_account_name ?? null;

    const startError = startRelay.data?.error ? startRelay.data : null;

    if (isLoading) {
        return (
            <div className="space-y-4">
                <div className="border rounded-lg p-6 animate-pulse">
                    <div className="h-5 bg-muted rounded w-1/3 mb-3" />
                    <div className="h-4 bg-muted rounded w-2/3" />
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Main Relay Control Card */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Cloud className="h-5 w-5" />
                        Cloud Relay
                    </CardTitle>
                    <CardDescription>
                        {isConnected
                            ? "Your relay is active. Remote teammates and cloud agents can connect."
                            : "Deploy a Cloudflare Worker to enable remote access for teammates and cloud AI agents."
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

                    {/* Errors — hide when relay is connected */}
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

            {/* Team URLs (when connected) */}
            {isConnected && workerUrl && mcpEndpoint && (
                <TeamUrls workerUrl={workerUrl} mcpEndpoint={mcpEndpoint} />
            )}

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
