import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@oak/ui/components/ui/card";
import { Button } from "@oak/ui/components/ui/button";
import { Label } from "@oak/ui/components/ui/label";
import { AlertCircle, Loader2, Save, Shield } from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useConfig, updateConfig, type LogRotationConfig } from "@/hooks/use-config";
import { fetchJson } from "@/lib/api";
import { API_ENDPOINTS } from "@/lib/constants";

/** Log rotation defaults (must match Python constants) */
const LOG_ROTATION_DEFAULTS = {
    ENABLED: true,
    MAX_SIZE_MB: 10,
    BACKUP_COUNT: 3,
} as const;

/** Log rotation validation limits (must match Python constants) */
const LOG_ROTATION_LIMITS = {
    MIN_SIZE_MB: 1,
    MAX_SIZE_MB: 100,
    MAX_BACKUP_COUNT: 10,
} as const;

function calculateMaxLogDiskUsage(maxSizeMb: number, backupCount: number): number {
    return maxSizeMb * (1 + backupCount);
}

export default function Config() {
    const { data: config, isLoading } = useConfig();
    const queryClient = useQueryClient();

    const [rotation, setRotation] = useState<LogRotationConfig>({
        enabled: LOG_ROTATION_DEFAULTS.ENABLED,
        max_size_mb: LOG_ROTATION_DEFAULTS.MAX_SIZE_MB,
        backup_count: LOG_ROTATION_DEFAULTS.BACKUP_COUNT,
    });
    const [isDirty, setIsDirty] = useState(false);
    const [isSaving, setIsSaving] = useState(false);

    // min_oak_version state (stored in swarm DO, not local config)
    const { data: versionConfig } = useQuery<{ min_oak_version: string }>({
        queryKey: ["min-oak-version"],
        queryFn: ({ signal }) => fetchJson(API_ENDPOINTS.CONFIG_MIN_OAK_VERSION, { signal }),
    });
    const [minVersion, setMinVersion] = useState("");
    const [versionDirty, setVersionDirty] = useState(false);
    const [versionSaving, setVersionSaving] = useState(false);
    const [versionError, setVersionError] = useState<string | null>(null);

    useEffect(() => {
        if (versionConfig?.min_oak_version != null) {
            setMinVersion(versionConfig.min_oak_version);
            setVersionDirty(false);
        }
    }, [versionConfig]);

    const handleVersionSave = async () => {
        setVersionSaving(true);
        setVersionError(null);
        try {
            const resp = await fetchJson(API_ENDPOINTS.CONFIG_MIN_OAK_VERSION, {
                method: "PUT",
                body: JSON.stringify({ min_oak_version: minVersion.trim() }),
            }) as { error?: string; min_oak_version?: string };
            if (resp.error) {
                setVersionError(resp.error);
            } else {
                queryClient.invalidateQueries({ queryKey: ["min-oak-version"] });
                setVersionDirty(false);
            }
        } catch (e) {
            setVersionError(e instanceof Error ? e.message : "Failed to save");
        } finally {
            setVersionSaving(false);
        }
    };

    // Sync form state when config loads
    useEffect(() => {
        if (config?.log_rotation) {
            setRotation(config.log_rotation);
            setIsDirty(false);
        }
    }, [config]);

    const handleSave = async () => {
        setIsSaving(true);
        try {
            await updateConfig({ log_rotation: rotation });
            queryClient.invalidateQueries({ queryKey: ["config"] });
            setIsDirty(false);
        } catch (e) {
            console.error("Failed to save config:", e);
        } finally {
            setIsSaving(false);
        }
    };

    if (isLoading) {
        return (
            <div className="flex items-center justify-center h-64">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
        );
    }

    return (
        <div className="space-y-6 max-w-2xl">
            <div>
                <h1 className="text-2xl font-bold">Settings</h1>
                <p className="text-muted-foreground text-sm mt-1">
                    Configure swarm daemon behavior. Changes require a daemon restart.
                </p>
            </div>

            {/* Version Policy Section */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Shield className="h-5 w-5" />
                        Version Policy
                    </CardTitle>
                    <CardDescription>
                        Set a minimum OAK version for connected teams. Teams running older versions will receive upgrade advisories via heartbeat.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="space-y-2">
                        <Label>Minimum OAK Version</Label>
                        <input
                            type="text"
                            placeholder="e.g. 1.4.0 (leave empty to disable)"
                            value={minVersion}
                            onChange={(e) => {
                                setMinVersion(e.target.value);
                                setVersionDirty(true);
                                setVersionError(null);
                            }}
                            className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                        />
                        <p className="text-xs text-muted-foreground">
                            Format: major.minor.patch — teams below this version will see a warning advisory.
                        </p>
                    </div>
                    {versionError && (
                        <div className="flex items-center gap-2 text-sm text-destructive bg-destructive/10 p-3 rounded-md">
                            <AlertCircle className="h-4 w-4" />
                            <span>{versionError}</span>
                        </div>
                    )}
                </CardContent>
                <CardFooter className="bg-muted/30 py-3 border-t flex items-center justify-between">
                    <p className="text-xs text-muted-foreground">
                        Takes effect on the next team heartbeat (within 60s).
                    </p>
                    <Button onClick={handleVersionSave} disabled={!versionDirty || versionSaving} size="sm">
                        {versionSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        <Save className="mr-2 h-4 w-4" /> Save
                    </Button>
                </CardFooter>
            </Card>

            {/* Logging Section */}
            <Card>
                <CardHeader>
                    <CardTitle>Logging</CardTitle>
                    <CardDescription>Configure log file rotation to prevent unbounded disk usage.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="flex items-center gap-3">
                        <input
                            type="checkbox"
                            id="log_rotation_enabled"
                            checked={rotation.enabled}
                            onChange={(e) => {
                                setRotation((prev) => ({ ...prev, enabled: e.target.checked }));
                                setIsDirty(true);
                            }}
                            className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
                        />
                        <Label htmlFor="log_rotation_enabled">Enable log rotation</Label>
                    </div>

                    <div className={`grid grid-cols-2 gap-4 ${!rotation.enabled ? "opacity-50 pointer-events-none" : ""}`}>
                        <div className="space-y-2">
                            <Label>Max File Size (MB)</Label>
                            <input
                                type="number"
                                min={LOG_ROTATION_LIMITS.MIN_SIZE_MB}
                                max={LOG_ROTATION_LIMITS.MAX_SIZE_MB}
                                value={rotation.max_size_mb}
                                onChange={(e) => {
                                    const value = parseInt(e.target.value, 10) || LOG_ROTATION_DEFAULTS.MAX_SIZE_MB;
                                    setRotation((prev) => ({
                                        ...prev,
                                        max_size_mb: Math.min(Math.max(value, LOG_ROTATION_LIMITS.MIN_SIZE_MB), LOG_ROTATION_LIMITS.MAX_SIZE_MB),
                                    }));
                                    setIsDirty(true);
                                }}
                                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                            />
                            <p className="text-xs text-muted-foreground">
                                Rotate when file exceeds this size ({LOG_ROTATION_LIMITS.MIN_SIZE_MB}-{LOG_ROTATION_LIMITS.MAX_SIZE_MB} MB)
                            </p>
                        </div>
                        <div className="space-y-2">
                            <Label>Backup Count</Label>
                            <input
                                type="number"
                                min={0}
                                max={LOG_ROTATION_LIMITS.MAX_BACKUP_COUNT}
                                value={rotation.backup_count}
                                onChange={(e) => {
                                    const value = parseInt(e.target.value, 10) || 0;
                                    setRotation((prev) => ({
                                        ...prev,
                                        backup_count: Math.min(Math.max(value, 0), LOG_ROTATION_LIMITS.MAX_BACKUP_COUNT),
                                    }));
                                    setIsDirty(true);
                                }}
                                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                            />
                            <p className="text-xs text-muted-foreground">
                                Keep up to {LOG_ROTATION_LIMITS.MAX_BACKUP_COUNT} backup files (daemon.log.1, .2, etc.)
                            </p>
                        </div>
                    </div>

                    {rotation.enabled && (
                        <div className="flex items-center gap-2 text-sm text-muted-foreground bg-muted/30 p-3 rounded-md">
                            <AlertCircle className="h-4 w-4" />
                            <span>
                                Max disk usage: {calculateMaxLogDiskUsage(rotation.max_size_mb, rotation.backup_count)} MB
                                ({rotation.max_size_mb} MB × {1 + rotation.backup_count} files)
                            </span>
                        </div>
                    )}
                </CardContent>
                <CardFooter className="bg-muted/30 py-3 border-t flex items-center justify-between">
                    <p className="text-xs text-muted-foreground">
                        Requires daemon restart to take effect.
                    </p>
                    <Button onClick={handleSave} disabled={!isDirty || isSaving} size="sm">
                        {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        <Save className="mr-2 h-4 w-4" /> Save
                    </Button>
                </CardFooter>
            </Card>
        </div>
    );
}
