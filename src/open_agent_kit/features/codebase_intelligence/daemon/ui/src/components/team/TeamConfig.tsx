/**
 * Team Configuration page — relay connection settings.
 *
 * Provides fields for:
 * - relay_worker_url (text input)
 * - api_key (password input, relay token)
 * - auto_sync toggle
 * - sync_interval_seconds slider
 */

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
    useTeamConfig,
    useUpdateTeamConfig,
} from "@/hooks/use-team";
import {
    Settings,
    Save,
    Loader2,
    AlertCircle,
    RefreshCw,
    Eye,
    EyeOff,
    Copy,
    Check,
    Share2,
} from "lucide-react";
import { cn } from "@/lib/utils";

// =============================================================================
// Constants
// =============================================================================

const SYNC_INTERVAL_MIN = 1;
const SYNC_INTERVAL_MAX = 60;

// =============================================================================
// Main Component
// =============================================================================

export default function TeamConfig() {
    const { data: config, isLoading: isConfigLoading } = useTeamConfig();
    const updateConfig = useUpdateTeamConfig();

    // Form state
    const [relayWorkerUrl, setRelayWorkerUrl] = useState("");
    const [apiKey, setApiKey] = useState("");
    const [showApiKey, setShowApiKey] = useState(false);
    const [autoSync, setAutoSync] = useState(false);
    const [syncInterval, setSyncInterval] = useState(3);
    const [isDirty, setIsDirty] = useState(false);
    const [configMessage, setConfigMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
    const [copiedUrl, setCopiedUrl] = useState(false);
    const [copiedKey, setCopiedKey] = useState(false);

    const copyToClipboard = (text: string, setCopied: (v: boolean) => void) => {
        navigator.clipboard.writeText(text).then(() => {
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        });
    };

    // Sync form with config on load
    useEffect(() => {
        if (config && !isDirty) {
            setRelayWorkerUrl(config.relay_worker_url ?? "");
            setApiKey(config.api_key ?? "");
            setAutoSync(config.auto_sync);
            setSyncInterval(config.sync_interval_seconds);
        }
    }, [config, isDirty]);

    const handleSaveConfig = async () => {
        setConfigMessage(null);
        try {
            await updateConfig.mutateAsync({
                relay_worker_url: relayWorkerUrl.trim() || null,
                api_key: apiKey.trim() || null,
                auto_sync: autoSync,
                sync_interval_seconds: syncInterval,
            });
            setConfigMessage({ type: "success", text: "Team configuration saved." });
            setIsDirty(false);
        } catch (err) {
            const message = err instanceof Error ? err.message : "Failed to save configuration.";
            setConfigMessage({ type: "error", text: message });
        }
    };

    if (isConfigLoading) {
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
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Settings className="h-5 w-5" />
                        Relay Configuration
                    </CardTitle>
                    <CardDescription>
                        Configure the relay connection for team synchronization.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    {configMessage && (
                        <div className={cn(
                            "p-3 rounded-md text-sm flex items-center gap-2",
                            configMessage.type === "success" ? "bg-green-500/10 text-green-600" : "bg-red-500/10 text-red-600"
                        )}>
                            {configMessage.type === "error" && <AlertCircle className="h-4 w-4" />}
                            {configMessage.text}
                        </div>
                    )}

                    {/* Relay Worker URL */}
                    <div className="space-y-2">
                        <label className="text-sm font-medium">Relay Worker URL</label>
                        <input
                            type="url"
                            value={relayWorkerUrl}
                            onChange={(e) => {
                                setRelayWorkerUrl(e.target.value);
                                setIsDirty(true);
                                setConfigMessage(null);
                            }}
                            placeholder="https://your-relay.workers.dev"
                            className="w-full h-10 rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                        />
                        <p className="text-xs text-muted-foreground">
                            The Cloudflare Worker URL used for relay communication.
                        </p>
                    </div>

                    {/* API Key */}
                    <div className="space-y-2">
                        <label className="text-sm font-medium">API Key</label>
                        <div className="flex items-center gap-2">
                            <input
                                type={showApiKey ? "text" : "password"}
                                value={apiKey}
                                onChange={(e) => {
                                    setApiKey(e.target.value);
                                    setIsDirty(true);
                                    setConfigMessage(null);
                                }}
                                placeholder="Relay authentication token"
                                className="flex-1 h-10 rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                            />
                            <Button
                                variant="ghost"
                                size="sm"
                                className="h-10 w-10 p-0"
                                onClick={() => setShowApiKey(!showApiKey)}
                                type="button"
                            >
                                {showApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                            </Button>
                        </div>
                        <p className="text-xs text-muted-foreground">
                            Authentication token for the relay worker.
                        </p>
                    </div>

                    {/* Auto-sync toggle */}
                    <div className="flex items-center gap-3">
                        <input
                            type="checkbox"
                            id="team_auto_sync"
                            checked={autoSync}
                            onChange={(e) => {
                                setAutoSync(e.target.checked);
                                setIsDirty(true);
                                setConfigMessage(null);
                            }}
                            className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
                        />
                        <label htmlFor="team_auto_sync" className="text-sm font-medium">
                            Automatic sync
                        </label>
                    </div>

                    {/* Sync interval */}
                    <div className="space-y-2">
                        <div className="flex items-center justify-between">
                            <label className="text-sm font-medium flex items-center gap-2">
                                <RefreshCw className="w-3 h-3" />
                                Sync interval
                            </label>
                            <span className="text-sm text-muted-foreground">
                                {syncInterval}s
                            </span>
                        </div>
                        <input
                            type="range"
                            min={SYNC_INTERVAL_MIN}
                            max={SYNC_INTERVAL_MAX}
                            value={syncInterval}
                            onChange={(e) => {
                                setSyncInterval(Number(e.target.value));
                                setIsDirty(true);
                                setConfigMessage(null);
                            }}
                            className="w-full"
                        />
                        <div className="flex justify-between text-xs text-muted-foreground">
                            <span>{SYNC_INTERVAL_MIN}s</span>
                            <span>{SYNC_INTERVAL_MAX}s</span>
                        </div>
                    </div>
                </CardContent>
                <CardFooter className="bg-muted/30 py-3 border-t flex items-center justify-between">
                    <p className="text-xs text-muted-foreground">
                        Changes take effect after save.
                    </p>
                    <Button
                        onClick={handleSaveConfig}
                        disabled={!isDirty || updateConfig.isPending}
                        size="sm"
                    >
                        {updateConfig.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        <Save className="mr-2 h-4 w-4" /> Save
                    </Button>
                </CardFooter>
            </Card>

            {/* Share with teammates — shown when relay is configured */}
            {relayWorkerUrl && apiKey && !isDirty && (
                <Card className="border-dashed">
                    <CardHeader className="pb-3">
                        <CardTitle className="flex items-center gap-2 text-base">
                            <Share2 className="h-4 w-4" />
                            Share with teammates
                        </CardTitle>
                        <CardDescription>
                            Give your teammates these two values so they can join the same relay.
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        <div className="space-y-1">
                            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Relay Worker URL</p>
                            <div className="flex items-center gap-2 rounded-md border bg-muted/30 px-3 py-2">
                                <code className="flex-1 text-sm truncate">{relayWorkerUrl}</code>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-7 w-7 p-0 shrink-0"
                                    onClick={() => copyToClipboard(relayWorkerUrl, setCopiedUrl)}
                                    type="button"
                                >
                                    {copiedUrl ? <Check className="h-3.5 w-3.5 text-green-500" /> : <Copy className="h-3.5 w-3.5" />}
                                </Button>
                            </div>
                        </div>
                        <div className="space-y-1">
                            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">API Key (Relay Token)</p>
                            <div className="flex items-center gap-2 rounded-md border bg-muted/30 px-3 py-2">
                                <code className="flex-1 text-sm truncate">{showApiKey ? apiKey : "•".repeat(Math.min(apiKey.length, 32))}</code>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-7 w-7 p-0 shrink-0"
                                    onClick={() => setShowApiKey(!showApiKey)}
                                    type="button"
                                >
                                    {showApiKey ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                                </Button>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-7 w-7 p-0 shrink-0"
                                    onClick={() => copyToClipboard(apiKey, setCopiedKey)}
                                    type="button"
                                >
                                    {copiedKey ? <Check className="h-3.5 w-3.5 text-green-500" /> : <Copy className="h-3.5 w-3.5" />}
                                </Button>
                            </div>
                        </div>
                        <p className="text-xs text-muted-foreground">
                            Teammates run: <code className="bg-muted px-1 rounded">oak ci config set team.relay_worker_url &lt;url&gt;</code> and <code className="bg-muted px-1 rounded">oak ci config set team.api_key &lt;token&gt;</code>
                        </p>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
