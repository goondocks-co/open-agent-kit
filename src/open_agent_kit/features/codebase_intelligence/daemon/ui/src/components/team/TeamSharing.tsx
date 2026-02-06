import { useState, useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Share2, Copy, Check, Loader2, Globe, AlertCircle, ExternalLink, Save, Settings } from "lucide-react";
import { useTunnelStatus, useTunnelStart, useTunnelStop } from "@/hooks/use-tunnel";
import { useConfig, useUpdateConfig } from "@/hooks/use-config";
import { cn } from "@/lib/utils";

interface TunnelFormData {
    provider: string;
    auto_start: boolean;
    cloudflared_path: string;
    ngrok_path: string;
}

const TUNNEL_DEFAULTS: TunnelFormData = {
    provider: "cloudflared",
    auto_start: false,
    cloudflared_path: "",
    ngrok_path: "",
};

export default function TeamSharing() {
    const { data: tunnelStatus, isLoading } = useTunnelStatus();
    const startTunnel = useTunnelStart();
    const stopTunnel = useTunnelStop();
    const [copied, setCopied] = useState(false);
    const copyTimerRef = useRef<ReturnType<typeof setTimeout>>(undefined);

    useEffect(() => () => clearTimeout(copyTimerRef.current), []);

    // Config state for tunnel settings
    const { data: config, isLoading: isConfigLoading } = useConfig();
    const updateConfig = useUpdateConfig();
    const [tunnelForm, setTunnelForm] = useState<TunnelFormData>(TUNNEL_DEFAULTS);
    const [isDirty, setIsDirty] = useState(false);
    const [configMessage, setConfigMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

    // Sync tunnel form with config on load
    useEffect(() => {
        if (config?.tunnel && !isDirty) {
            setTunnelForm({
                provider: config.tunnel.provider ?? TUNNEL_DEFAULTS.provider,
                auto_start: config.tunnel.auto_start ?? TUNNEL_DEFAULTS.auto_start,
                cloudflared_path: config.tunnel.cloudflared_path ?? TUNNEL_DEFAULTS.cloudflared_path,
                ngrok_path: config.tunnel.ngrok_path ?? TUNNEL_DEFAULTS.ngrok_path,
            });
        }
    }, [config, isDirty]);

    const isActive = tunnelStatus?.active ?? false;
    const publicUrl = tunnelStatus?.public_url;
    const provider = tunnelStatus?.provider;
    const error = tunnelStatus?.error;

    const handleToggle = () => {
        if (isActive) {
            stopTunnel.mutate();
        } else {
            startTunnel.mutate();
        }
    };

    const handleCopyUrl = async () => {
        if (!publicUrl) return;
        try {
            await navigator.clipboard.writeText(publicUrl);
            setCopied(true);
            clearTimeout(copyTimerRef.current);
            copyTimerRef.current = setTimeout(() => setCopied(false), 2000);
        } catch (err) {
            console.error("Failed to copy URL:", err);
        }
    };

    const handleSaveTunnelConfig = async () => {
        try {
            const result = await updateConfig.mutateAsync({
                tunnel: {
                    provider: tunnelForm.provider,
                    auto_start: tunnelForm.auto_start,
                    cloudflared_path: tunnelForm.cloudflared_path,
                    ngrok_path: tunnelForm.ngrok_path,
                },
            }) as { message?: string };
            setConfigMessage({ type: "success", text: result.message || "Tunnel settings saved." });
            setIsDirty(false);
        } catch (err: unknown) {
            const message = err instanceof Error ? err.message : "Failed to save tunnel settings.";
            setConfigMessage({ type: "error", text: message });
        }
    };

    const isToggling = startTunnel.isPending || stopTunnel.isPending;

    return (
        <div className="space-y-6">
            {/* Tunnel Control Card */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Share2 className="h-5 w-5" />
                        Share Dashboard
                    </CardTitle>
                    <CardDescription>
                        Create a public URL to share your daemon dashboard with teammates.
                        Anyone with the link can view sessions, memories, and search your codebase.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    {/* Status + Toggle */}
                    <div className="flex items-center justify-between p-4 rounded-lg bg-muted/50">
                        <div className="flex items-center gap-3">
                            <div className={cn(
                                "w-3 h-3 rounded-full",
                                isActive ? "bg-green-500" : "bg-gray-400"
                            )} />
                            <div>
                                <div className="font-medium text-sm">
                                    {isActive ? "Tunnel Active" : "Tunnel Inactive"}
                                </div>
                                {provider && isActive && (
                                    <div className="text-xs text-muted-foreground">
                                        via {provider}
                                        {tunnelStatus?.started_at && (
                                            <span className="ml-2">
                                                started {new Date(tunnelStatus.started_at).toLocaleTimeString()}
                                            </span>
                                        )}
                                    </div>
                                )}
                            </div>
                        </div>
                        <Button
                            onClick={handleToggle}
                            disabled={isToggling || isLoading}
                            variant={isActive ? "outline" : "default"}
                            size="sm"
                        >
                            {isToggling ? (
                                <>
                                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                    {startTunnel.isPending ? "Starting..." : "Stopping..."}
                                </>
                            ) : isActive ? (
                                "Stop Sharing"
                            ) : (
                                <>
                                    <Globe className="h-4 w-4 mr-2" />
                                    Start Sharing
                                </>
                            )}
                        </Button>
                    </div>

                    {/* Public URL display */}
                    {isActive && publicUrl && (
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Public URL</label>
                            <div className="flex items-center gap-2">
                                <code className="flex-1 bg-muted px-3 py-2 rounded-md text-sm font-mono truncate border">
                                    {publicUrl}
                                </code>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={handleCopyUrl}
                                    className="flex-shrink-0"
                                >
                                    {copied ? (
                                        <Check className="h-4 w-4 text-green-500" />
                                    ) : (
                                        <Copy className="h-4 w-4" />
                                    )}
                                </Button>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    className="flex-shrink-0"
                                    asChild
                                >
                                    <a href={publicUrl} target="_blank" rel="noopener noreferrer">
                                        <ExternalLink className="h-4 w-4" />
                                    </a>
                                </Button>
                            </div>
                            <p className="text-xs text-muted-foreground">
                                Share this URL with your team. The link is active as long as the tunnel is running.
                            </p>
                        </div>
                    )}

                    {/* Error display */}
                    {error && !isActive && (
                        <Alert variant="destructive">
                            <AlertCircle className="h-4 w-4" />
                            <AlertDescription>{error}</AlertDescription>
                        </Alert>
                    )}

                    {/* Start error from mutation */}
                    {startTunnel.error && (
                        <Alert variant="destructive">
                            <AlertCircle className="h-4 w-4" />
                            <AlertDescription>{startTunnel.error.message}</AlertDescription>
                        </Alert>
                    )}
                </CardContent>
            </Card>

            {/* Tunnel Configuration Card */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-base">
                        <Settings className="h-4 w-4" />
                        Tunnel Settings
                    </CardTitle>
                    <CardDescription>
                        Configure the tunnel provider and options for sharing.
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

                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Provider</label>
                            <select
                                value={tunnelForm.provider}
                                onChange={(e) => {
                                    setTunnelForm((prev) => ({ ...prev, provider: e.target.value }));
                                    setIsDirty(true);
                                    setConfigMessage(null);
                                }}
                                className="w-full h-10 rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                            >
                                <option value="cloudflared">Cloudflared (default)</option>
                                <option value="ngrok">ngrok</option>
                            </select>
                        </div>
                        {tunnelForm.provider === "cloudflared" && (
                            <div className="space-y-2">
                                <label className="text-sm font-medium">Cloudflared Path</label>
                                <input
                                    type="text"
                                    value={tunnelForm.cloudflared_path}
                                    onChange={(e) => {
                                        setTunnelForm((prev) => ({ ...prev, cloudflared_path: e.target.value }));
                                        setIsDirty(true);
                                        setConfigMessage(null);
                                    }}
                                    placeholder="cloudflared (from PATH)"
                                    className="w-full h-10 rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                                />
                            </div>
                        )}
                        {tunnelForm.provider === "ngrok" && (
                            <div className="space-y-2">
                                <label className="text-sm font-medium">ngrok Path</label>
                                <input
                                    type="text"
                                    value={tunnelForm.ngrok_path}
                                    onChange={(e) => {
                                        setTunnelForm((prev) => ({ ...prev, ngrok_path: e.target.value }));
                                        setIsDirty(true);
                                        setConfigMessage(null);
                                    }}
                                    placeholder="ngrok (from PATH)"
                                    className="w-full h-10 rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                                />
                            </div>
                        )}
                    </div>

                    <div className="flex items-center gap-3">
                        <input
                            type="checkbox"
                            id="tunnel_auto_start"
                            checked={tunnelForm.auto_start}
                            onChange={(e) => {
                                setTunnelForm((prev) => ({ ...prev, auto_start: e.target.checked }));
                                setIsDirty(true);
                                setConfigMessage(null);
                            }}
                            className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
                        />
                        <label htmlFor="tunnel_auto_start" className="text-sm font-medium">
                            Start tunnel automatically when daemon starts
                        </label>
                    </div>
                </CardContent>
                <CardFooter className="bg-muted/30 py-3 border-t flex items-center justify-between">
                    <p className="text-xs text-muted-foreground">
                        Changes take effect on next tunnel start.
                    </p>
                    <Button
                        onClick={handleSaveTunnelConfig}
                        disabled={!isDirty || updateConfig.isPending || isConfigLoading}
                        size="sm"
                    >
                        {updateConfig.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        <Save className="mr-2 h-4 w-4" /> Save
                    </Button>
                </CardFooter>
            </Card>

            {/* Setup Info Card (when inactive) */}
            {!isActive && (
                <Card className="border-dashed">
                    <CardHeader className="pb-3">
                        <CardTitle className="flex items-center gap-2 text-base">
                            <Globe className="h-4 w-4" />
                            How Sharing Works
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <p className="text-sm text-muted-foreground">
                            Sharing creates a secure tunnel from your local daemon to a public URL using
                            cloudflared (default) or ngrok. Your teammates can open the URL in their browser
                            to see the full daemon UI.
                        </p>

                        <div className="space-y-3">
                            <div className="rounded-lg bg-muted/50 p-3">
                                <h4 className="text-sm font-medium mb-1">Cloudflared (default)</h4>
                                <p className="text-xs text-muted-foreground mb-2">
                                    Free, no account required. Generates a random trycloudflare.com URL.
                                </p>
                                <pre className="bg-background border rounded-md p-2 text-xs font-mono overflow-x-auto">
                                    <code>brew install cloudflared</code>
                                </pre>
                            </div>

                            <div className="rounded-lg bg-muted/50 p-3">
                                <h4 className="text-sm font-medium mb-1">ngrok (alternative)</h4>
                                <p className="text-xs text-muted-foreground mb-2">
                                    Requires a free account. Configure auth via <code className="text-xs">ngrok config add-authtoken</code>.
                                </p>
                                <pre className="bg-background border rounded-md p-2 text-xs font-mono overflow-x-auto">
                                    <code>brew install ngrok</code>
                                </pre>
                            </div>
                        </div>

                        <p className="text-xs text-muted-foreground">
                            You can also use the CLI: <code className="bg-muted px-1.5 py-0.5 rounded text-xs font-mono">oak ci tunnel-start</code>
                        </p>
                        <p className="text-xs text-muted-foreground">
                            <Link to="/help" state={{ tab: "sharing" }} className="text-primary hover:underline">
                                Sharing setup guide
                            </Link>
                        </p>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
