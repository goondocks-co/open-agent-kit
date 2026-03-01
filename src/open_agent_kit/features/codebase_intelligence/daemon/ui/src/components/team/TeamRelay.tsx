/**
 * Team Relay page — consolidated relay management.
 *
 * Sections when connected:
 *   1. Connection status + primary action
 *   2. Observability — relay health, nodes, sync stats, relay buffer
 *   3. [collapsed] Configuration — credentials, MCP, sync settings, deployment
 *   4. Leave Team
 *
 * Sections when not connected:
 *   1. Connection status + primary action
 *   2. Join a Team (consumer input) OR Team Credentials (deployer display)
 *   3. MCP Access, Sync Settings, Deployment
 *   4. Leave Team
 */

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { CopyButton, CommandBlock } from "@/components/ui/command-block";
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
    RefreshCw,
    Settings,
    Globe,
    Link2,
    LogOut,
    Save,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
    useCloudRelayStatus,
    useCloudRelayStart,
    useCloudRelayConnect,
    useCloudRelayStop,
    useCloudRelayPreflight,
    useCloudRelayUpdateSettings,
} from "@/hooks/use-cloud-relay";
import type { CloudRelayStartResponse } from "@/hooks/use-cloud-relay";
import {
    useTeamConfig,
    useTeamStatus,
    useUpdateTeamConfig,
    useTeamLeave,
} from "@/hooks/use-team";
import { RelayDetails, ConnectedNodes, RelayBuffer, SyncStats } from "./TeamStatus";

// =============================================================================
// Helpers
// =============================================================================

const SYNC_INTERVAL_MIN = 1;
const SYNC_INTERVAL_MAX = 60;

// =============================================================================
// Error Card
// =============================================================================

function ErrorCard({ response }: { response: CloudRelayStartResponse }) {
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
// Section 1: Connection Status + Primary Action
// =============================================================================

interface ConnectionCardProps {
    isConnected: boolean;
    isDeployed: boolean;
    isStarting: boolean;
    isConnecting: boolean;
    isStopping: boolean;
    cfAccountName: string | null;
    updateAvailable: boolean;
    startError: CloudRelayStartResponse | null;
    connectError: string | null;
    stopError: string | null;
    onDeploy: () => void;
    onConnect: () => void;
    onDisconnect: () => void;
    onRedeploy: () => void;
}

function ConnectionCard({
    isConnected, isDeployed,
    isStarting, isConnecting, isStopping,
    cfAccountName, updateAvailable,
    startError, connectError, stopError,
    onDeploy, onConnect, onDisconnect, onRedeploy,
}: ConnectionCardProps) {
    const isToggling = isStarting || isConnecting || isStopping;

    const statusLabel = isConnected
        ? "Connected"
        : isDeployed
            ? "Deployed, not connected"
            : "Not deployed";

    const statusColor = isConnected
        ? "bg-green-500"
        : isDeployed
            ? "bg-amber-500"
            : "bg-gray-400";

    const primaryLabel = () => {
        if (isStarting) return "Deploying...";
        if (isConnecting) return "Connecting...";
        if (isStopping) return "Disconnecting...";
        if (isConnected) return "Disconnect";
        if (isDeployed) return "Connect";
        return "Deploy Relay";
    };

    const handlePrimary = () => {
        if (isConnected) onDisconnect();
        else if (isDeployed) onConnect();
        else onDeploy();
    };

    return (
        <Card>
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    <Cloud className="h-5 w-5" />
                    Cloud Relay
                </CardTitle>
                <CardDescription>
                    {isConnected
                        ? "Your daemon is connected. Observations sync with teammates automatically."
                        : isDeployed
                            ? "Your relay is deployed but your daemon is not connected."
                            : "Deploy a Cloudflare Worker to enable team sync and remote AI agent access."
                    }
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                <div className="flex items-center justify-between p-4 rounded-lg bg-muted/50">
                    <div className="flex items-center gap-3">
                        <div className={cn("w-3 h-3 rounded-full", statusColor)} />
                        <div>
                            <div className="font-medium text-sm">{statusLabel}</div>
                            {isConnected && cfAccountName && (
                                <div className="text-xs text-muted-foreground">
                                    Cloudflare: {cfAccountName}
                                </div>
                            )}
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        {isDeployed && !isConnected && (
                            <Button
                                onClick={onRedeploy}
                                disabled={isToggling}
                                variant="outline"
                                size="sm"
                            >
                                {isStarting ? (
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                    <>
                                        <RefreshCw className="h-4 w-4 mr-1.5" />
                                        Re-deploy
                                    </>
                                )}
                            </Button>
                        )}
                        <Button
                            onClick={handlePrimary}
                            disabled={isToggling}
                            variant={isConnected ? "outline" : "default"}
                            size="sm"
                        >
                            {(isStarting || isConnecting || isStopping) && (
                                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                            )}
                            {!isConnected && !isStarting && !isConnecting && (
                                <Cloud className="h-4 w-4 mr-2" />
                            )}
                            {primaryLabel()}
                        </Button>
                    </div>
                </div>

                {isConnected && (
                    <p className="text-xs text-muted-foreground px-1">
                        Disconnecting pauses observation sync with your team. Your local data stays intact.
                        Reconnect any time — you&apos;re not leaving the team.
                    </p>
                )}

                {/* Update available banner */}
                {updateAvailable && (
                    <div className="flex items-center justify-between gap-3 p-3 rounded-md bg-amber-500/10 border border-amber-500/20 text-amber-700 dark:text-amber-400 text-sm">
                        <div className="flex items-center gap-2">
                            <RefreshCw className="h-4 w-4 shrink-0" />
                            <span>Worker template updated. Re-deploy to apply the latest changes.</span>
                        </div>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={onRedeploy}
                            disabled={isToggling}
                            className="shrink-0 border-amber-500/40 text-amber-700 dark:text-amber-400 hover:bg-amber-500/10"
                        >
                            {isStarting ? <Loader2 className="h-4 w-4 animate-spin" /> : "Re-deploy"}
                        </Button>
                    </div>
                )}

                {/* Errors */}
                {startError && <ErrorCard response={startError} />}
                {connectError && (
                    <Alert variant="destructive">
                        <AlertCircle className="h-4 w-4" />
                        <AlertDescription>{connectError}</AlertDescription>
                    </Alert>
                )}
                {stopError && (
                    <Alert variant="destructive">
                        <AlertCircle className="h-4 w-4" />
                        <AlertDescription>{stopError}</AlertDescription>
                    </Alert>
                )}
            </CardContent>
        </Card>
    );
}

// =============================================================================
// Section 2a: Join a Team (consumer input form)
// =============================================================================

interface JoinTeamCardProps {
    onJoin: (url: string, token: string) => void;
    isSaving: boolean;
    isConnecting: boolean;
    joinError: string | null;
    joinSuccess: boolean;
}

function JoinTeamCard({ onJoin, isSaving, isConnecting, joinError, joinSuccess }: JoinTeamCardProps) {
    const [url, setUrl] = useState("");
    const [token, setToken] = useState("");

    const isBusy = isSaving || isConnecting;

    return (
        <Card>
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    <Link2 className="h-5 w-5" />
                    Join a Team
                </CardTitle>
                <CardDescription>
                    Enter the relay URL and token shared by your team member to start syncing.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                <div className="space-y-1.5">
                    <label className="text-sm font-medium">Relay URL</label>
                    <input
                        type="url"
                        value={url}
                        onChange={(e) => setUrl(e.target.value)}
                        placeholder="https://oak-relay-yourteam.workers.dev"
                        className="w-full rounded-md border bg-background px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring"
                        disabled={isBusy}
                    />
                </div>
                <div className="space-y-1.5">
                    <label className="text-sm font-medium">Relay Token</label>
                    <input
                        type="password"
                        value={token}
                        onChange={(e) => setToken(e.target.value)}
                        placeholder="Shared relay token"
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
                    <div className="flex items-center gap-2 text-sm text-green-600">
                        <CheckCircle2 className="h-4 w-4" />
                        Connected to relay. Syncing observations automatically.
                    </div>
                )}
            </CardContent>
            <CardFooter>
                <Button
                    onClick={() => onJoin(url.trim(), token.trim())}
                    disabled={!url.trim() || !token.trim() || isBusy}
                    size="sm"
                >
                    {isBusy
                        ? <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        : <Cloud className="h-4 w-4 mr-2" />
                    }
                    {isSaving ? "Saving..." : isConnecting ? "Connecting..." : "Connect"}
                </Button>
            </CardFooter>
        </Card>
    );
}

// =============================================================================
// Section 2b: Team Credentials (deployer display + share)
// =============================================================================

function TeamCredentialsCard({ workerUrl, relayToken }: { workerUrl: string; relayToken: string | null }) {
    const [showToken, setShowToken] = useState(false);
    const maskedToken = relayToken ? "•".repeat(Math.min(relayToken.length, 32)) : null;

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

// =============================================================================
// Section 3: MCP Access
// =============================================================================

function McpJsonBlock({ mcpEndpoint, agentToken }: { mcpEndpoint: string; agentToken: string | null }) {
    const tokenPlaceholder = agentToken || "<your-agent-token>";
    const jsonConfig = JSON.stringify(
        { mcpServers: { "oak-ci": { url: mcpEndpoint, headers: { Authorization: `Bearer ${tokenPlaceholder}` } } } },
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

function McpAccessCard({ mcpEndpoint, agentToken }: { mcpEndpoint: string; agentToken: string | null }) {
    const [showToken, setShowToken] = useState(false);
    const maskedToken = agentToken ? "•".repeat(Math.min(agentToken.length, 32)) : null;

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

// =============================================================================
// Section 4: Sync Settings
// =============================================================================

interface SyncSettingsCardProps {
    autoSync: boolean;
    syncInterval: number;
    isSaving: boolean;
    isDirty: boolean;
    message: { type: "success" | "error"; text: string } | null;
    onAutoSyncChange: (v: boolean) => void;
    onIntervalChange: (v: number) => void;
    onSave: () => void;
}

function SyncSettingsCard({
    autoSync, syncInterval, isSaving, isDirty, message,
    onAutoSyncChange, onIntervalChange, onSave,
}: SyncSettingsCardProps) {
    return (
        <Card>
            <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                    <RefreshCw className="h-4 w-4" />
                    Sync Settings
                </CardTitle>
                <CardDescription>
                    Control when this daemon syncs observations with the team.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                <div className="flex items-center gap-3">
                    <input
                        type="checkbox"
                        id="relay_auto_sync"
                        checked={autoSync}
                        onChange={(e) => onAutoSyncChange(e.target.checked)}
                        className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
                    />
                    <label htmlFor="relay_auto_sync" className="text-sm font-medium">
                        Auto-sync observations
                    </label>
                </div>
                <div className="space-y-2">
                    <div className="flex items-center justify-between">
                        <label className="text-sm font-medium">Sync interval</label>
                        <span className="text-sm text-muted-foreground">{syncInterval}s</span>
                    </div>
                    <input
                        type="range"
                        min={SYNC_INTERVAL_MIN}
                        max={SYNC_INTERVAL_MAX}
                        value={syncInterval}
                        onChange={(e) => onIntervalChange(Number(e.target.value))}
                        className="w-full"
                        disabled={!autoSync}
                    />
                    <div className="flex justify-between text-xs text-muted-foreground">
                        <span>{SYNC_INTERVAL_MIN}s</span>
                        <span>{SYNC_INTERVAL_MAX}s</span>
                    </div>
                </div>
            </CardContent>
            <CardFooter className="bg-muted/30 py-3 border-t flex items-center justify-between">
                {message ? (
                    <div className={cn(
                        "flex items-center gap-2 text-sm",
                        message.type === "success" ? "text-green-600" : "text-red-600",
                    )}>
                        {message.type === "success"
                            ? <CheckCircle2 className="h-4 w-4" />
                            : <AlertCircle className="h-4 w-4" />}
                        {message.text}
                    </div>
                ) : (
                    <p className="text-xs text-muted-foreground">Changes take effect after save.</p>
                )}
                <Button onClick={onSave} disabled={!isDirty || isSaving} size="sm">
                    {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    <Save className="mr-2 h-4 w-4" /> Save
                </Button>
            </CardFooter>
        </Card>
    );
}

// =============================================================================
// Section 5: Deployment (prerequisites + custom domain + re-deploy)
// =============================================================================

interface PrerequisiteItemProps { label: string; satisfied: boolean }

function PrerequisiteItem({ label, satisfied }: PrerequisiteItemProps) {
    return (
        <div className="flex items-center gap-2 text-sm">
            {satisfied
                ? <Check className="h-4 w-4 text-green-500 flex-shrink-0" />
                : <X className="h-4 w-4 text-muted-foreground flex-shrink-0" />}
            <span className={cn(satisfied ? "text-foreground" : "text-muted-foreground")}>{label}</span>
        </div>
    );
}

interface DeploymentCardProps {
    isDeployed: boolean;
    isStarting: boolean;
    isToggling: boolean;
    currentDomain: string | null;
    workerName: string | null;
    onRedeploy: () => void;
}

function DeploymentCard({
    isDeployed, isStarting, isToggling,
    currentDomain, workerName, onRedeploy,
}: DeploymentCardProps) {
    const { data: preflight } = useCloudRelayPreflight();
    const updateSettings = useCloudRelayUpdateSettings();

    const [domain, setDomain] = useState(currentDomain ?? "");
    const [domainMessage, setDomainMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

    useEffect(() => { setDomain(currentDomain ?? ""); }, [currentDomain]);

    const hasChanged = domain !== (currentDomain ?? "");
    const trimmedDomain = domain.trim();
    const derivedSubdomain = trimmedDomain && workerName ? `${workerName}.${trimmedDomain}` : null;

    const handleSaveDomain = () => {
        setDomainMessage(null);
        updateSettings.mutate(
            { custom_domain: trimmedDomain || null },
            {
                onSuccess: () => setDomainMessage({ type: "success", text: "Custom domain saved." }),
                onError: (err) => setDomainMessage({ type: "error", text: err.message }),
            },
        );
    };

    return (
        <Card>
            <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                    <Settings className="h-4 w-4" />
                    Deployment
                </CardTitle>
                <CardDescription>
                    Manage the Cloudflare Worker deployment.
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
                {/* Prerequisites */}
                {preflight && (
                    <div className="space-y-2">
                        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Prerequisites</p>
                        <div className="space-y-1.5">
                            <PrerequisiteItem label="Node.js / npm available" satisfied={preflight.npm_available} />
                            <PrerequisiteItem label="Wrangler CLI available" satisfied={preflight.wrangler_available} />
                            <PrerequisiteItem label="Wrangler authenticated" satisfied={preflight.wrangler_authenticated} />
                            {preflight.cf_account_name && (
                                <p className="text-xs text-muted-foreground pl-6">Account: {preflight.cf_account_name}</p>
                            )}
                        </div>
                        {!preflight.wrangler_available && (
                            <CommandBlock command="npm install -g wrangler && wrangler login" label="Install and authenticate" />
                        )}
                        {preflight.wrangler_available && !preflight.wrangler_authenticated && (
                            <CommandBlock command="wrangler login" label="Authenticate with Cloudflare" />
                        )}
                    </div>
                )}

                {/* Re-deploy */}
                {isDeployed && (
                    <div className="space-y-2 pt-1 border-t">
                        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Re-deploy</p>
                        <p className="text-xs text-muted-foreground">
                            Pushes the latest Worker code to Cloudflare. Required after config changes or OAK updates.
                        </p>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={onRedeploy}
                            disabled={isToggling}
                        >
                            {isStarting
                                ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Deploying...</>
                                : <><RefreshCw className="h-4 w-4 mr-2" />Re-deploy Worker</>
                            }
                        </Button>
                    </div>
                )}

                {/* Custom domain */}
                <div className="space-y-2 pt-1 border-t">
                    <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Custom Domain</p>
                    <div className="flex items-center gap-2">
                        <input
                            type="text"
                            value={domain}
                            onChange={(e) => setDomain(e.target.value)}
                            placeholder="example.com"
                            className="flex-1 rounded-md border bg-background px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring"
                            disabled={updateSettings.isPending}
                        />
                        <Button onClick={handleSaveDomain} disabled={!hasChanged || updateSettings.isPending} size="sm">
                            {updateSettings.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Save"}
                        </Button>
                    </div>
                    {derivedSubdomain && (
                        <p className="text-xs text-muted-foreground">
                            MCP endpoint: <code className="bg-muted px-1 rounded">{derivedSubdomain}/mcp</code>
                        </p>
                    )}
                    {domainMessage && (
                        <div className={cn(
                            "flex items-center gap-2 text-sm",
                            domainMessage.type === "success" ? "text-green-600" : "text-red-600",
                        )}>
                            {domainMessage.type === "success"
                                ? <CheckCircle2 className="h-4 w-4" />
                                : <AlertCircle className="h-4 w-4" />}
                            {domainMessage.text}
                        </div>
                    )}
                    {currentDomain && (
                        <button
                            onClick={() => {
                                setDomain("");
                                updateSettings.mutate({ custom_domain: null });
                            }}
                            disabled={updateSettings.isPending}
                            className="text-xs text-muted-foreground underline hover:text-foreground"
                        >
                            Clear custom domain
                        </button>
                    )}
                </div>
            </CardContent>
        </Card>
    );
}

// =============================================================================
// Section 6: Leave Team
// =============================================================================

function LeaveTeamSection({ onLeave, isLeaving }: { onLeave: () => void; isLeaving: boolean }) {
    const [confirmOpen, setConfirmOpen] = useState(false);
    return (
        <Card className="border-destructive/30">
            <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base text-destructive">
                    <LogOut className="h-4 w-4" />
                    Leave Team
                </CardTitle>
                <CardDescription>
                    Disconnect from the relay and clear your team credentials.
                    Your local data stays intact. You can rejoin by re-entering the relay URL and token.
                </CardDescription>
            </CardHeader>
            <CardContent>
                <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => setConfirmOpen(true)}
                    disabled={isLeaving}
                >
                    {isLeaving
                        ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Leaving...</>
                        : <><LogOut className="h-4 w-4 mr-2" />Leave Team</>
                    }
                </Button>
                <ConfirmDialog
                    open={confirmOpen}
                    onOpenChange={setConfirmOpen}
                    title="Leave the team?"
                    description="This will disconnect your daemon from the relay and clear your relay credentials. Your local data (sessions, memories, observations) is not deleted. You can rejoin anytime."
                    confirmLabel="Leave Team"
                    loadingLabel="Leaving..."
                    onConfirm={onLeave}
                    isLoading={isLeaving}
                />
            </CardContent>
        </Card>
    );
}

// =============================================================================
// Main Component
// =============================================================================

export default function TeamRelay() {
    const { data: status, isLoading: statusLoading } = useCloudRelayStatus();
    const { data: config, isLoading: configLoading } = useTeamConfig();
    const { data: teamStatus } = useTeamStatus();

    const startRelay = useCloudRelayStart();
    const connectRelay = useCloudRelayConnect();
    const stopRelay = useCloudRelayStop();
    const updateConfig = useUpdateTeamConfig();
    const leaveTeam = useTeamLeave();

    // Sync settings form state
    const [autoSync, setAutoSync] = useState(false);
    const [syncInterval, setSyncInterval] = useState(3);
    const [syncDirty, setSyncDirty] = useState(false);
    const [syncMessage, setSyncMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

    // Join flow state
    const [joinError, setJoinError] = useState<string | null>(null);
    const [joinSuccess, setJoinSuccess] = useState(false);

    // Config sections are collapsed by default when connected
    const [showConfig, setShowConfig] = useState(false);

    useEffect(() => {
        if (config && !syncDirty) {
            setAutoSync(config.auto_sync);
            setSyncInterval(config.sync_interval_seconds);
        }
    }, [config, syncDirty]);

    // Collapse config when connection is established
    useEffect(() => {
        if (status?.connected) setShowConfig(false);
    }, [status?.connected]);

    // Derived state
    const isConnected = status?.connected ?? false;
    const workerUrl = status?.worker_url ?? config?.relay_worker_url ?? null;
    const isDeployed = !!workerUrl;
    const relayToken = config?.api_key ?? null;
    const mcpEndpoint = status?.mcp_endpoint ?? (workerUrl ? `${workerUrl}/mcp` : null);
    const agentToken = status?.agent_token ?? null;
    const updateAvailable = status?.update_available ?? false;
    const cfAccountName = status?.cf_account_name ?? null;
    const customDomain = status?.custom_domain ?? null;
    const workerName = status?.worker_name ?? startRelay.data?.worker_name ?? null;

    const isStarting = startRelay.isPending;
    const isConnecting = connectRelay.isPending;
    const isStopping = stopRelay.isPending;
    const isToggling = isStarting || isConnecting || isStopping;

    const startError = startRelay.data?.error ? startRelay.data : null;
    const connectError = connectRelay.error?.message ?? null;
    const stopError = stopRelay.error?.message ?? null;

    const showConfigSections = !isConnected || showConfig;

    const handleDeploy = () => { startRelay.reset(); startRelay.mutate(); };
    const handleConnect = () => { connectRelay.reset(); connectRelay.mutate(); };
    const handleDisconnect = () => stopRelay.mutate();
    const handleRedeploy = () => { startRelay.reset(); startRelay.mutate(); };

    const handleJoin = async (url: string, token: string) => {
        setJoinError(null);
        setJoinSuccess(false);
        try {
            await updateConfig.mutateAsync({
                relay_worker_url: url,
                api_key: token,
                auto_sync: true,
            });
            connectRelay.mutate(undefined, {
                onSuccess: () => setJoinSuccess(true),
                onError: (err) => setJoinError(err.message),
            });
        } catch (err) {
            setJoinError(err instanceof Error ? err.message : "Failed to save configuration.");
        }
    };

    const handleSaveSync = async () => {
        setSyncMessage(null);
        try {
            await updateConfig.mutateAsync({ auto_sync: autoSync, sync_interval_seconds: syncInterval });
            setSyncMessage({ type: "success", text: "Sync settings saved." });
            setSyncDirty(false);
        } catch (err) {
            setSyncMessage({ type: "error", text: err instanceof Error ? err.message : "Failed to save." });
        }
    };

    const handleLeave = () => { leaveTeam.mutate(); };

    if (statusLoading || configLoading) {
        return (
            <div className="space-y-4">
                {[1, 2].map((i) => (
                    <div key={i} className="border rounded-lg p-6 animate-pulse">
                        <div className="h-5 bg-muted rounded w-1/3 mb-3" />
                        <div className="h-4 bg-muted rounded w-2/3" />
                    </div>
                ))}
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* 1. Connection status + primary action */}
            <ConnectionCard
                isConnected={isConnected}
                isDeployed={isDeployed}
                isStarting={isStarting}
                isConnecting={isConnecting}
                isStopping={isStopping}
                cfAccountName={cfAccountName}
                updateAvailable={updateAvailable}
                startError={isConnected ? null : startError}
                connectError={isConnected ? null : connectError}
                stopError={stopError}
                onDeploy={handleDeploy}
                onConnect={handleConnect}
                onDisconnect={handleDisconnect}
                onRedeploy={handleRedeploy}
            />

            {/* 2. Observability — shown prominently when connected */}
            {isConnected && teamStatus && (
                <div className="space-y-4">
                    {teamStatus.relay && (
                        <Card>
                            <CardHeader className="pb-3">
                                <CardTitle className="text-base">Relay Health</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <RelayDetails
                                    relay={teamStatus.relay}
                                    onlineCount={(teamStatus.online_nodes ?? []).filter(n => n.online).length}
                                />
                            </CardContent>
                        </Card>
                    )}
                    <ConnectedNodes nodes={teamStatus.online_nodes ?? []} />
                    <RelayBuffer pending={teamStatus.relay_pending ?? {}} />
                    {teamStatus.sync?.enabled && <SyncStats sync={teamStatus.sync} />}
                </div>
            )}

            {/* Config toggle — only shown when connected */}
            {isConnected && (
                <button
                    onClick={() => setShowConfig(!showConfig)}
                    className="w-full flex items-center justify-center gap-2 py-2 text-sm text-muted-foreground hover:text-foreground transition-colors rounded-md border border-dashed hover:border-border"
                >
                    <Settings className="h-4 w-4" />
                    {showConfig ? "Hide configuration" : "Show configuration"}
                    {showConfig ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                </button>
            )}

            {/* Config sections — always visible when not connected, toggled when connected */}
            {showConfigSections && (
                <>
                    {/* Consumer join form — when no relay is configured */}
                    {!isDeployed && (
                        <JoinTeamCard
                            onJoin={handleJoin}
                            isSaving={updateConfig.isPending}
                            isConnecting={isConnecting}
                            joinError={joinError}
                            joinSuccess={joinSuccess}
                        />
                    )}

                    {/* Team credentials — when relay is deployed (deployer view) */}
                    {workerUrl && (
                        <TeamCredentialsCard workerUrl={workerUrl} relayToken={relayToken} />
                    )}

                    {/* MCP access */}
                    {mcpEndpoint && (
                        <McpAccessCard mcpEndpoint={mcpEndpoint} agentToken={agentToken} />
                    )}

                    {/* Sync settings */}
                    <SyncSettingsCard
                        autoSync={autoSync}
                        syncInterval={syncInterval}
                        isSaving={updateConfig.isPending}
                        isDirty={syncDirty}
                        message={syncMessage}
                        onAutoSyncChange={(v) => { setAutoSync(v); setSyncDirty(true); setSyncMessage(null); }}
                        onIntervalChange={(v) => { setSyncInterval(v); setSyncDirty(true); setSyncMessage(null); }}
                        onSave={handleSaveSync}
                    />

                    {/* Deployment */}
                    <DeploymentCard
                        isDeployed={isDeployed}
                        isStarting={isStarting}
                        isToggling={isToggling}
                        currentDomain={customDomain}
                        workerName={workerName}
                        onRedeploy={handleRedeploy}
                    />
                </>
            )}

            {/* Leave team — always visible when relay is configured */}
            {(isDeployed || relayToken) && (
                <LeaveTeamSection onLeave={handleLeave} isLeaving={leaveTeam.isPending} />
            )}
        </div>
    );
}
