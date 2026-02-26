/**
 * Team Configuration page — server mode, connection, and sync settings.
 *
 * Provides:
 * - Server Mode card: toggle this node as the team server
 * - Join/Leave card: connect to a remote team server
 * - Sync Settings card: configure sync intervals
 *
 * Dual-mode awareness:
 * - Server mode ON  → hide Join section, show server URL + keys link
 * - Connected remote → hide Server Mode option
 * - Neither          → show both Server Mode and Join options
 */

import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
    useTeamConfig,
    useTeamStatus,
    useUpdateTeamConfig,
    useJoinTeam,
    useLeaveTeam,
    useToggleServerMode,
} from "@/hooks/use-team";
import { useRestart } from "@/hooks/use-restart";
import {
    Server,
    Save,
    Loader2,
    AlertCircle,
    LogIn,
    LogOut,
    Eye,
    EyeOff,
    Settings,
    RefreshCw,
    Copy,
    Check,
    Power,
    PowerOff,
} from "lucide-react";
import { cn } from "@/lib/utils";

// =============================================================================
// Constants
// =============================================================================

const SYNC_INTERVAL_MIN = 1;
const SYNC_INTERVAL_MAX = 60;
const PULL_INTERVAL_MIN = 5;
const PULL_INTERVAL_MAX = 300;

// =============================================================================
// Main Component
// =============================================================================

export default function TeamConfig() {
    const { data: config, isLoading: isConfigLoading } = useTeamConfig();
    const { data: status } = useTeamStatus();
    const updateConfig = useUpdateTeamConfig();
    const joinTeam = useJoinTeam();
    const leaveTeam = useLeaveTeam();
    const toggleServer = useToggleServerMode();
    const { restart, isRestarting } = useRestart();

    // Join form state
    const [joinUrl, setJoinUrl] = useState("");
    const [joinToken, setJoinToken] = useState("");
    const [showToken, setShowToken] = useState(false);
    const [joinError, setJoinError] = useState<string | null>(null);

    // Config form state
    const [autoSync, setAutoSync] = useState(false);
    const [syncInterval, setSyncInterval] = useState(3);
    const [pullInterval, setPullInterval] = useState(15);
    const [isDirty, setIsDirty] = useState(false);
    const [configMessage, setConfigMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

    // Server mode state
    const [serverUrl, setServerUrl] = useState<string | null>(null);
    const [showRestartPrompt, setShowRestartPrompt] = useState(false);
    const [copied, setCopied] = useState(false);

    const connected = status?.configured ?? false;
    const isServerMode = config?.server_mode ?? false;
    // Connected to a remote server (not loopback)
    const isRemoteConnected = connected && !isServerMode;

    // Sync form with config on load
    useEffect(() => {
        if (config && !isDirty) {
            setAutoSync(config.auto_sync);
            setSyncInterval(config.sync_interval_seconds);
            setPullInterval(config.pull_interval_seconds);
        }
    }, [config, isDirty]);

    const handleEnableServer = async () => {
        try {
            const result = await toggleServer.mutateAsync(true);
            setServerUrl(result.server_url ?? null);
            if (result.restart_required) {
                setShowRestartPrompt(true);
            }
        } catch {
            // Error handled by mutation state
        }
    };

    const handleDisableServer = async () => {
        try {
            const result = await toggleServer.mutateAsync(false);
            setServerUrl(null);
            if (result.restart_required) {
                setShowRestartPrompt(true);
            }
        } catch {
            // Error handled by mutation state
        }
    };

    const handleCopyUrl = async (url: string) => {
        await navigator.clipboard.writeText(url);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    const handleJoin = async () => {
        if (!joinUrl.trim() || !joinToken.trim()) {
            setJoinError("Both server URL and API key are required.");
            return;
        }
        setJoinError(null);
        try {
            await joinTeam.mutateAsync({
                server_url: joinUrl.trim(),
                api_key: joinToken.trim(),
            });
            setJoinUrl("");
            setJoinToken("");
        } catch (err) {
            setJoinError(err instanceof Error ? err.message : "Failed to join team");
        }
    };

    const handleLeave = async () => {
        try {
            await leaveTeam.mutateAsync();
        } catch {
            // Error handled by mutation
        }
    };

    const handleSaveConfig = async () => {
        setConfigMessage(null);
        try {
            await updateConfig.mutateAsync({
                auto_sync: autoSync,
                sync_interval_seconds: syncInterval,
                pull_interval_seconds: pullInterval,
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

    const displayServerUrl = serverUrl ?? config?.server_url;

    return (
        <div className="space-y-6">
            {/* Restart prompt banner */}
            {showRestartPrompt && (
                <div className="flex items-center justify-between p-4 rounded-lg border border-amber-500/30 bg-amber-500/10">
                    <div className="text-sm text-amber-700">
                        {isRestarting
                            ? "Restarting daemon... The page will reload automatically."
                            : "Server mode changed. A restart is required for changes to take effect."}
                    </div>
                    <Button
                        size="sm"
                        onClick={() => restart()}
                        disabled={isRestarting}
                    >
                        {isRestarting ? (
                            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        ) : (
                            <RefreshCw className="w-4 h-4 mr-2" />
                        )}
                        {isRestarting ? "Restarting..." : "Restart Now"}
                    </Button>
                </div>
            )}

            {/* Server Mode Card — hidden when connected to a remote server */}
            {!isRemoteConnected && (
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <Server className="h-5 w-5" />
                            {isServerMode ? "Server Mode (Active)" : "Server Mode"}
                        </CardTitle>
                        <CardDescription>
                            {isServerMode
                                ? "This node is running as the team server."
                                : "Make this node the team server. Your local database becomes the shared team DB."}
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        {isServerMode ? (
                            <>
                                <div className="flex items-center gap-2 p-3 rounded-md bg-green-500/10 text-green-700 text-sm">
                                    <Power className="h-4 w-4 flex-shrink-0" />
                                    Running as team server
                                </div>

                                {displayServerUrl && (
                                    <div className="flex items-center justify-between p-3 rounded-md bg-muted/50">
                                        <div>
                                            <div className="text-xs text-muted-foreground">Server URL</div>
                                            <code className="text-sm">{displayServerUrl}</code>
                                        </div>
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            onClick={() => handleCopyUrl(displayServerUrl)}
                                        >
                                            {copied ? (
                                                <Check className="h-4 w-4 text-green-600" />
                                            ) : (
                                                <Copy className="h-4 w-4" />
                                            )}
                                        </Button>
                                    </div>
                                )}

                                <p className="text-xs text-muted-foreground">
                                    Create API keys in the Keys tab for teammates to connect.
                                </p>

                                <div className="rounded-md border border-blue-500/20 bg-blue-500/5 p-3 space-y-1">
                                    <p className="text-sm font-medium text-blue-700 dark:text-blue-400">
                                        Remote access
                                    </p>
                                    <p className="text-xs text-muted-foreground">
                                        The server URL above is local. To let remote teammates connect,
                                        set up a{" "}
                                        <Link to="/cloud" className="text-blue-600 dark:text-blue-400 underline hover:no-underline">
                                            Cloud Relay
                                        </Link>{" "}
                                        and share that URL instead.
                                    </p>
                                </div>

                                <Button
                                    variant="outline"
                                    onClick={handleDisableServer}
                                    disabled={toggleServer.isPending}
                                >
                                    {toggleServer.isPending ? (
                                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                    ) : (
                                        <PowerOff className="w-4 h-4 mr-2" />
                                    )}
                                    Disable Server Mode
                                </Button>
                            </>
                        ) : (
                            <>
                                <Button
                                    onClick={handleEnableServer}
                                    disabled={toggleServer.isPending}
                                >
                                    {toggleServer.isPending ? (
                                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                    ) : (
                                        <Power className="w-4 h-4 mr-2" />
                                    )}
                                    Enable Server Mode
                                </Button>
                            </>
                        )}

                        {toggleServer.isError && (
                            <div className="flex items-center gap-2 text-sm text-red-600 bg-red-500/10 px-3 py-2 rounded">
                                <AlertCircle className="h-4 w-4 flex-shrink-0" />
                                {toggleServer.error.message}
                            </div>
                        )}
                    </CardContent>
                </Card>
            )}

            {/* Join / Leave Card — hidden when server mode is ON */}
            {!isServerMode && (
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <Server className="h-5 w-5" />
                            {connected ? "Team Connection" : "Join a Team"}
                        </CardTitle>
                        <CardDescription>
                            {connected
                                ? "You are connected to a team server. You can disconnect below."
                                : "Enter your team server URL and API key to connect."}
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        {connected ? (
                            <>
                                <div className="flex items-center justify-between p-4 rounded-lg bg-muted/50">
                                    <div>
                                        <div className="text-sm font-medium">Connected to:</div>
                                        <code className="text-xs text-muted-foreground">
                                            {config?.server_url ?? "Unknown"}
                                        </code>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <span className="w-2 h-2 rounded-full bg-green-500" />
                                        <span className="text-xs text-green-600">Active</span>
                                    </div>
                                </div>

                                <Button
                                    variant="destructive"
                                    onClick={handleLeave}
                                    disabled={leaveTeam.isPending}
                                >
                                    {leaveTeam.isPending ? (
                                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                    ) : (
                                        <LogOut className="w-4 h-4 mr-2" />
                                    )}
                                    Leave Team
                                </Button>

                                {leaveTeam.isError && (
                                    <div className="text-sm text-red-600 bg-red-500/10 px-3 py-2 rounded">
                                        {leaveTeam.error.message}
                                    </div>
                                )}
                            </>
                        ) : (
                            <>
                                <div className="space-y-4">
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium">Server URL</label>
                                        <input
                                            type="url"
                                            value={joinUrl}
                                            onChange={(e) => {
                                                setJoinUrl(e.target.value);
                                                setJoinError(null);
                                            }}
                                            placeholder="https://team-server.example.com"
                                            className="w-full h-10 rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                                            disabled={joinTeam.isPending}
                                        />
                                    </div>

                                    <div className="space-y-2">
                                        <label className="text-sm font-medium">API Key</label>
                                        <div className="relative">
                                            <input
                                                type={showToken ? "text" : "password"}
                                                value={joinToken}
                                                onChange={(e) => {
                                                    setJoinToken(e.target.value);
                                                    setJoinError(null);
                                                }}
                                                placeholder="Your team authentication API key"
                                                className="w-full h-10 rounded-md border border-input bg-background px-3 py-2 pr-10 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                                                disabled={joinTeam.isPending}
                                            />
                                            <button
                                                type="button"
                                                onClick={() => setShowToken(!showToken)}
                                                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                                                tabIndex={-1}
                                                aria-label={showToken ? "Hide token" : "Show token"}
                                            >
                                                {showToken ? (
                                                    <EyeOff className="w-4 h-4" />
                                                ) : (
                                                    <Eye className="w-4 h-4" />
                                                )}
                                            </button>
                                        </div>
                                    </div>
                                </div>

                                {joinError && (
                                    <div className="flex items-center gap-2 text-sm text-red-600 bg-red-500/10 px-3 py-2 rounded">
                                        <AlertCircle className="h-4 w-4 flex-shrink-0" />
                                        {joinError}
                                    </div>
                                )}

                                <Button
                                    onClick={handleJoin}
                                    disabled={joinTeam.isPending || !joinUrl.trim() || !joinToken.trim()}
                                >
                                    {joinTeam.isPending ? (
                                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                    ) : (
                                        <LogIn className="w-4 h-4 mr-2" />
                                    )}
                                    Join Team
                                </Button>
                            </>
                        )}
                    </CardContent>
                </Card>
            )}

            {/* Sync Settings Card (only when configured) */}
            {connected && (
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2 text-base">
                            <Settings className="h-4 w-4" />
                            Sync Settings
                        </CardTitle>
                        <CardDescription>
                            Configure automatic synchronization intervals.
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

                        {/* Pull interval */}
                        <div className="space-y-2">
                            <div className="flex items-center justify-between">
                                <label className="text-sm font-medium flex items-center gap-2">
                                    <RefreshCw className="w-3 h-3" />
                                    Pull interval
                                </label>
                                <span className="text-sm text-muted-foreground">
                                    {pullInterval}s
                                </span>
                            </div>
                            <input
                                type="range"
                                min={PULL_INTERVAL_MIN}
                                max={PULL_INTERVAL_MAX}
                                step={5}
                                value={pullInterval}
                                onChange={(e) => {
                                    setPullInterval(Number(e.target.value));
                                    setIsDirty(true);
                                    setConfigMessage(null);
                                }}
                                className="w-full"
                            />
                            <div className="flex justify-between text-xs text-muted-foreground">
                                <span>{PULL_INTERVAL_MIN}s</span>
                                <span>{PULL_INTERVAL_MAX}s</span>
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
            )}
        </div>
    );
}
