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
    useJoinStatus,
} from "@/hooks/use-team";
import type { TeamJoinResponse } from "@/hooks/use-team";
import { useRestart } from "@/hooks/use-restart";
import {
    Server,
    Save,
    Loader2,
    AlertCircle,
    LogIn,
    LogOut,
    Settings,
    RefreshCw,
    Copy,
    Check,
    Power,
    PowerOff,
    Clock,
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
    const [joinError, setJoinError] = useState<string | null>(null);
    const [pendingKeyId, setPendingKeyId] = useState<string | null>(null);

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

    // Poll join status when waiting for approval
    const effectiveKeyId = pendingKeyId ?? status?.pending_key_id ?? null;
    const isPendingApproval = status?.pending_approval ?? !!effectiveKeyId;
    const { data: joinStatusData } = useJoinStatus(effectiveKeyId);

    // When join is approved, clear pending state and refresh
    useEffect(() => {
        if (joinStatusData?.status === "approved") {
            setPendingKeyId(null);
        }
    }, [joinStatusData?.status]);

    const configured = status?.configured ?? false;
    const isServerMode = config?.server_mode ?? false;
    // Actually connected and syncing (not just configured + pending)
    const connected = configured && !isPendingApproval;
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
        if (!joinUrl.trim()) {
            setJoinError("Server URL is required.");
            return;
        }
        setJoinError(null);
        try {
            const result: TeamJoinResponse = await joinTeam.mutateAsync({
                server_url: joinUrl.trim(),
            });
            if (result.status === "pending_approval" && result.key_id) {
                setPendingKeyId(result.key_id);
            } else {
                setJoinUrl("");
            }
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
                                        <Link to="/team/connectivity" className="text-blue-600 dark:text-blue-400 underline hover:no-underline">
                                            Cloud Relay
                                        </Link>{" "}
                                        in the Connectivity tab and share that URL instead.
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
                                : isPendingApproval
                                    ? "Your join request is awaiting approval from the server admin."
                                    : "Enter your team server URL to request access."}
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
                        ) : isPendingApproval ? (
                            <>
                                <div className="flex items-center gap-3 p-4 rounded-lg border border-amber-500/30 bg-amber-500/10">
                                    <Clock className="w-5 h-5 text-amber-600 flex-shrink-0" />
                                    <div>
                                        <div className="text-sm font-medium text-amber-700">
                                            Waiting for approval
                                        </div>
                                        <p className="text-xs text-amber-600 mt-0.5">
                                            Your join request has been sent. The server admin
                                            will approve or reject your access.
                                        </p>
                                        {config?.server_url && (
                                            <code className="text-xs text-amber-600/80 mt-1 block">
                                                {config.server_url}
                                            </code>
                                        )}
                                    </div>
                                    {effectiveKeyId && (
                                        <Loader2 className="w-4 h-4 text-amber-600 animate-spin flex-shrink-0" />
                                    )}
                                </div>

                                {joinStatusData?.status === "rejected" && (
                                    <div className="flex items-center gap-2 text-sm text-red-600 bg-red-500/10 px-3 py-2 rounded">
                                        <AlertCircle className="h-4 w-4 flex-shrink-0" />
                                        Your join request was rejected by the server admin.
                                    </div>
                                )}

                                <Button
                                    variant="outline"
                                    onClick={handleLeave}
                                    disabled={leaveTeam.isPending}
                                >
                                    {leaveTeam.isPending ? (
                                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                    ) : (
                                        <LogOut className="w-4 h-4 mr-2" />
                                    )}
                                    Cancel &amp; Leave
                                </Button>

                                {leaveTeam.isError && (
                                    <div className="text-sm text-red-600 bg-red-500/10 px-3 py-2 rounded">
                                        {leaveTeam.error.message}
                                    </div>
                                )}
                            </>
                        ) : (
                            <>
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
                                    <p className="text-xs text-muted-foreground">
                                        An API key will be generated automatically when the server admin approves your request.
                                    </p>
                                </div>

                                {joinError && (
                                    <div className="flex items-center gap-2 text-sm text-red-600 bg-red-500/10 px-3 py-2 rounded">
                                        <AlertCircle className="h-4 w-4 flex-shrink-0" />
                                        {joinError}
                                    </div>
                                )}

                                <Button
                                    onClick={handleJoin}
                                    disabled={joinTeam.isPending || !joinUrl.trim()}
                                >
                                    {joinTeam.isPending ? (
                                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                    ) : (
                                        <LogIn className="w-4 h-4 mr-2" />
                                    )}
                                    Request to Join
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
