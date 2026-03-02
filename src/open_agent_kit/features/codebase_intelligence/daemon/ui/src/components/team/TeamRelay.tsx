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
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Settings, ChevronDown, ChevronRight } from "lucide-react";
import {
    useCloudRelayStatus,
    useCloudRelayStart,
    useCloudRelayConnect,
    useCloudRelayStop,
} from "@/hooks/use-cloud-relay";
import {
    useTeamConfig,
    useTeamStatus,
    useUpdateTeamConfig,
    useTeamLeave,
} from "@/hooks/use-team";
import { RelayDetails, ConnectedNodes, RelayBuffer, SyncStats } from "./TeamStatus";
import {
    ConnectionCard,
    JoinTeamCard,
    TeamCredentialsCard,
    McpAccessCard,
    SyncSettingsCard,
    DeploymentCard,
    LeaveTeamSection,
} from "./relay";

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
    const [keepRelayAlive, setKeepRelayAlive] = useState(false);
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
            setKeepRelayAlive(config.keep_relay_alive);
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

    // Deploy and re-deploy share the same logic
    const handleDeployOrRedeploy = () => { startRelay.reset(); startRelay.mutate(); };
    const handleConnect = () => { connectRelay.reset(); connectRelay.mutate(); };
    const handleDisconnect = () => stopRelay.mutate();

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
            await updateConfig.mutateAsync({
                auto_sync: autoSync,
                sync_interval_seconds: syncInterval,
                keep_relay_alive: keepRelayAlive,
            });
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
                onDeploy={handleDeployOrRedeploy}
                onConnect={handleConnect}
                onDisconnect={handleDisconnect}
                onRedeploy={handleDeployOrRedeploy}
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
                        keepRelayAlive={keepRelayAlive}
                        isSaving={updateConfig.isPending}
                        isDirty={syncDirty}
                        message={syncMessage}
                        onAutoSyncChange={(v) => { setAutoSync(v); setSyncDirty(true); setSyncMessage(null); }}
                        onIntervalChange={(v) => { setSyncInterval(v); setSyncDirty(true); setSyncMessage(null); }}
                        onKeepRelayAliveChange={(v) => { setKeepRelayAlive(v); setSyncDirty(true); setSyncMessage(null); }}
                        onSave={handleSaveSync}
                    />

                    {/* Deployment */}
                    <DeploymentCard
                        isDeployed={isDeployed}
                        isStarting={isStarting}
                        isToggling={isToggling}
                        currentDomain={customDomain}
                        workerName={workerName}
                        onRedeploy={handleDeployOrRedeploy}
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
