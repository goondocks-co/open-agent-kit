import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { AlertCircle, CheckCircle2, Download, Upload, Users, HardDrive, GitBranch, Cloud, Terminal, FolderCog, Info, Settings, Save, Loader2, Clock } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { MESSAGE_TYPES } from "@/lib/constants";
import { useBackupStatus, useCreateBackup, useRestoreBackup, useRestoreAllBackups, type RestoreResponse } from "@/hooks/use-backup";
import { useConfig, useUpdateConfig } from "@/hooks/use-config";
import type { BackupConfig } from "@/lib/api";
import { cn } from "@/lib/utils";

const BACKUP_FORM_DEFAULTS: BackupConfig = {
    auto_enabled: false,
    include_activities: false,
    on_upgrade: true,
};

/** Format a timestamp as a relative "time ago" string. */
function formatTimeAgo(isoString: string): string {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMinutes = Math.floor(diffMs / 60000);

    if (diffMinutes < 1) return "just now";
    if (diffMinutes < 60) return `${diffMinutes} minute${diffMinutes === 1 ? "" : "s"} ago`;
    const diffHours = Math.floor(diffMinutes / 60);
    if (diffHours < 24) return `${diffHours} hour${diffHours === 1 ? "" : "s"} ago`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays} day${diffDays === 1 ? "" : "s"} ago`;
}

export default function TeamBackups() {
    const queryClient = useQueryClient();
    const [message, setMessage] = useState<{ type: typeof MESSAGE_TYPES.SUCCESS | typeof MESSAGE_TYPES.ERROR, text: string } | null>(null);
    const [includeActivities, setIncludeActivities] = useState(false);
    const [restoreResult, setRestoreResult] = useState<RestoreResponse | null>(null);

    // Backup hooks
    const { data: backupStatus, refetch: refetchBackupStatus } = useBackupStatus();
    const createBackupFn = useCreateBackup();
    const restoreBackupFn = useRestoreBackup();
    const restoreAllBackupsFn = useRestoreAllBackups();

    // Config hooks for backup settings
    const { data: config, isLoading: isConfigLoading } = useConfig();
    const updateConfig = useUpdateConfig();
    const [backupForm, setBackupForm] = useState<BackupConfig>(BACKUP_FORM_DEFAULTS);
    const [isDirty, setIsDirty] = useState(false);
    const [configMessage, setConfigMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

    // Sync backup form with config on load
    useEffect(() => {
        if (config && "backup" in config && !isDirty) {
            const bkp = (config as Record<string, unknown>).backup as Partial<BackupConfig> | undefined;
            if (bkp) {
                setBackupForm({
                    auto_enabled: bkp.auto_enabled ?? BACKUP_FORM_DEFAULTS.auto_enabled,
                    include_activities: bkp.include_activities ?? BACKUP_FORM_DEFAULTS.include_activities,
                    on_upgrade: bkp.on_upgrade ?? BACKUP_FORM_DEFAULTS.on_upgrade,
                });
            }
        }
    }, [config, isDirty]);

    // Default the manual backup "include activities" checkbox to match config value
    useEffect(() => {
        if (config && "backup" in config) {
            const bkp = (config as Record<string, unknown>).backup as Partial<BackupConfig> | undefined;
            if (bkp?.include_activities !== undefined) {
                setIncludeActivities(bkp.include_activities);
            }
        }
    }, [config]);

    const handleSaveBackupConfig = async () => {
        try {
            const result = await updateConfig.mutateAsync({
                backup: {
                    auto_enabled: backupForm.auto_enabled,
                    include_activities: backupForm.include_activities,
                    on_upgrade: backupForm.on_upgrade,
                },
            } as Record<string, unknown>) as { message?: string };
            setConfigMessage({ type: "success", text: result.message || "Backup settings saved." });
            setIsDirty(false);
            refetchBackupStatus();
        } catch (err: unknown) {
            const errMessage = err instanceof Error ? err.message : "Failed to save backup settings.";
            setConfigMessage({ type: "error", text: errMessage });
        }
    };

    const handleCreateBackup = () => {
        setRestoreResult(null);
        createBackupFn.mutate(
            { include_activities: includeActivities },
            {
                onSuccess: (data) => {
                    setMessage({ type: MESSAGE_TYPES.SUCCESS, text: data.message });
                    refetchBackupStatus();
                },
                onError: (err) => {
                    setMessage({ type: MESSAGE_TYPES.ERROR, text: err.message });
                },
            }
        );
    };

    const handleRestoreMine = () => {
        setRestoreResult(null);
        restoreBackupFn.mutate(
            {},
            {
                onSuccess: (data) => {
                    setMessage({ type: MESSAGE_TYPES.SUCCESS, text: data.message });
                    setRestoreResult(data);
                    queryClient.invalidateQueries({ queryKey: ["memory-stats"] });
                    queryClient.invalidateQueries({ queryKey: ["status"] });
                },
                onError: (err) => {
                    setMessage({ type: MESSAGE_TYPES.ERROR, text: err.message });
                },
            }
        );
    };

    const handleRestoreAll = () => {
        setRestoreResult(null);
        restoreAllBackupsFn.mutate(
            {},
            {
                onSuccess: (data) => {
                    setMessage({ type: MESSAGE_TYPES.SUCCESS, text: data.message });
                    const allErrorMessages = Object.values(data.per_file)
                        .flatMap(r => r.error_messages || []);
                    const combined: RestoreResponse = {
                        status: data.status,
                        message: data.message,
                        sessions_imported: Object.values(data.per_file).reduce((sum, r) => sum + r.sessions_imported, 0),
                        sessions_skipped: Object.values(data.per_file).reduce((sum, r) => sum + r.sessions_skipped, 0),
                        batches_imported: Object.values(data.per_file).reduce((sum, r) => sum + r.batches_imported, 0),
                        batches_skipped: Object.values(data.per_file).reduce((sum, r) => sum + r.batches_skipped, 0),
                        observations_imported: Object.values(data.per_file).reduce((sum, r) => sum + r.observations_imported, 0),
                        observations_skipped: Object.values(data.per_file).reduce((sum, r) => sum + r.observations_skipped, 0),
                        activities_imported: Object.values(data.per_file).reduce((sum, r) => sum + r.activities_imported, 0),
                        activities_skipped: Object.values(data.per_file).reduce((sum, r) => sum + r.activities_skipped, 0),
                        errors: data.total_errors,
                        error_messages: allErrorMessages,
                    };
                    setRestoreResult(combined);
                    queryClient.invalidateQueries({ queryKey: ["memory-stats"] });
                    queryClient.invalidateQueries({ queryKey: ["status"] });
                },
                onError: (err) => {
                    setMessage({ type: MESSAGE_TYPES.ERROR, text: err.message });
                },
            }
        );
    };

    return (
        <div className="space-y-6">
            {/* CLI Sync Callout */}
            <Card className="border-blue-200 dark:border-blue-800 bg-blue-50/50 dark:bg-blue-950/20">
                <CardContent className="pt-6">
                    <div className="flex items-start gap-4">
                        <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-blue-100 dark:bg-blue-900 flex items-center justify-center">
                            <Terminal className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                        </div>
                        <div className="flex-1">
                            <h3 className="font-semibold text-blue-900 dark:text-blue-100">
                                Recommended: Use CLI for Team Sync
                            </h3>
                            <p className="text-sm text-blue-800 dark:text-blue-200 mt-1">
                                For the best experience, use <code className="bg-blue-100 dark:bg-blue-900 px-1.5 py-0.5 rounded text-xs font-mono">oak ci sync --team</code> from the command line.
                                It handles version detection, schema migrations, and backup ordering automatically.
                            </p>
                            <Link
                                to="/help"
                                state={{ tab: "team-sync" }}
                                className="inline-flex items-center gap-1 text-sm text-blue-600 dark:text-blue-400 hover:underline mt-2"
                            >
                                Learn more about Team Sync
                                <span aria-hidden="true">&rarr;</span>
                            </Link>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {message && (
                <Alert variant={message.type === MESSAGE_TYPES.ERROR ? "destructive" : "default"} className={message.type === MESSAGE_TYPES.SUCCESS ? "border-green-500 text-green-600 bg-green-50 dark:bg-green-950/20 dark:border-green-800 dark:text-green-400" : ""}>
                    {message.type === MESSAGE_TYPES.SUCCESS ? <CheckCircle2 className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
                    <div>
                        <AlertTitle>{message.type === MESSAGE_TYPES.SUCCESS ? "Success" : "Error"}</AlertTitle>
                        <AlertDescription>{message.text}</AlertDescription>
                    </div>
                </Alert>
            )}

            {/* Backup Settings Card */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Settings className="h-5 w-5" />
                        Backup Settings
                    </CardTitle>
                    <CardDescription>
                        Configure automatic backups, scheduling, and retention policies.
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

                    {/* Toggle switches */}
                    <div className="space-y-3">
                        <div className="flex items-center gap-3">
                            <input
                                type="checkbox"
                                id="backup_auto_enabled"
                                checked={backupForm.auto_enabled}
                                onChange={(e) => {
                                    setBackupForm((prev) => ({ ...prev, auto_enabled: e.target.checked }));
                                    setIsDirty(true);
                                    setConfigMessage(null);
                                }}
                                className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
                            />
                            <label htmlFor="backup_auto_enabled" className="text-sm font-medium">
                                Automatic backups
                            </label>
                        </div>

                        <div className="flex items-center gap-3">
                            <input
                                type="checkbox"
                                id="backup_include_activities"
                                checked={backupForm.include_activities}
                                onChange={(e) => {
                                    setBackupForm((prev) => ({ ...prev, include_activities: e.target.checked }));
                                    setIsDirty(true);
                                    setConfigMessage(null);
                                }}
                                className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
                            />
                            <label htmlFor="backup_include_activities" className="text-sm font-medium">
                                Include activities in backups
                            </label>
                        </div>

                        <div className="flex items-center gap-3">
                            <input
                                type="checkbox"
                                id="backup_on_upgrade"
                                checked={backupForm.on_upgrade}
                                onChange={(e) => {
                                    setBackupForm((prev) => ({ ...prev, on_upgrade: e.target.checked }));
                                    setIsDirty(true);
                                    setConfigMessage(null);
                                }}
                                className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
                            />
                            <label htmlFor="backup_on_upgrade" className="text-sm font-medium">
                                Backup before upgrade
                            </label>
                        </div>
                    </div>

                    {/* Transition-triggered backup explanation */}
                    {backupForm.auto_enabled && (
                        <div className="p-3 rounded-lg bg-muted/50 space-y-1">
                            <div className="flex items-center gap-2 text-sm">
                                <Clock className="h-4 w-4 text-muted-foreground" />
                                <span className="font-medium">Transition-triggered backups</span>
                            </div>
                            <p className="text-xs text-muted-foreground pl-6">
                                A backup is created automatically when the daemon enters sleep (30 min idle) or deep sleep (90 min idle).
                            </p>
                            {backupStatus?.last_auto_backup && (
                                <p className="text-xs text-muted-foreground pl-6">
                                    Last auto-backup: {formatTimeAgo(backupStatus.last_auto_backup)}
                                </p>
                            )}
                        </div>
                    )}
                </CardContent>
                <CardFooter className="bg-muted/30 py-3 border-t flex items-center justify-between">
                    <p className="text-xs text-muted-foreground">
                        Backup settings take effect on next cycle.
                    </p>
                    <Button
                        onClick={handleSaveBackupConfig}
                        disabled={!isDirty || updateConfig.isPending || isConfigLoading}
                        size="sm"
                    >
                        {updateConfig.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        <Save className="mr-2 h-4 w-4" /> Save
                    </Button>
                </CardFooter>
            </Card>

            {/* Team Backup Overview Card */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Users className="h-5 w-5" />
                        Team Backups
                    </CardTitle>
                    <CardDescription>
                        Each team member creates their own backup file. Restoring imports all team knowledge using content-based deduplication.
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    {/* Your machine info */}
                    {backupStatus && (
                        <div className="mb-4 p-3 rounded-lg bg-muted/50">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <HardDrive className="h-4 w-4 text-muted-foreground" />
                                    <span className="text-sm font-medium">Your Machine</span>
                                    <code className="text-xs bg-background px-1.5 py-0.5 rounded border">{backupStatus.machine_id}</code>
                                </div>
                                {backupStatus.backup_exists ? (
                                    <div className="flex items-center gap-2 text-green-600 dark:text-green-400">
                                        <CheckCircle2 className="h-4 w-4" />
                                        <span className="text-sm">Backup exists</span>
                                    </div>
                                ) : (
                                    <div className="flex items-center gap-2 text-yellow-600 dark:text-yellow-400">
                                        <AlertCircle className="h-4 w-4" />
                                        <span className="text-sm">No backup yet</span>
                                    </div>
                                )}
                            </div>
                            {backupStatus.backup_exists && backupStatus.backup_size_bytes && (
                                <div className="mt-2 text-xs text-muted-foreground pl-6">
                                    {(backupStatus.backup_size_bytes / 1024).toFixed(1)} KB
                                    {backupStatus.last_modified && (
                                        <span className="ml-2">
                                            Last updated: {new Date(backupStatus.last_modified).toLocaleString()}
                                        </span>
                                    )}
                                </div>
                            )}
                            {backupStatus.backup_dir_source !== "default" && (
                                <div className="mt-2 text-xs text-blue-600 dark:text-blue-400 pl-6 flex items-center gap-1">
                                    <FolderCog className="h-3 w-3" />
                                    <span>Custom backup dir: </span>
                                    <code className="bg-blue-100 dark:bg-blue-900/50 px-1 rounded">
                                        {backupStatus.backup_dir}
                                    </code>
                                    <span className="text-muted-foreground">
                                        (via {backupStatus.backup_dir_source === "environment variable" ? "OAK_CI_BACKUP_DIR env var" : ".env file"})
                                    </span>
                                </div>
                            )}
                        </div>
                    )}

                    {/* Team backup list */}
                    {backupStatus?.all_backups && backupStatus.all_backups.length > 0 && (
                        <div className="space-y-3">
                            <h4 className="text-sm font-medium flex items-center gap-2">
                                <GitBranch className="h-4 w-4" />
                                Available Backups ({backupStatus.all_backups.length})
                            </h4>
                            <div className="border rounded-lg divide-y">
                                {backupStatus.all_backups.map((backup) => (
                                    <div key={backup.filename} className="px-4 py-3 flex justify-between items-center">
                                        <div className="flex items-center gap-3">
                                            <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                                                <Users className="h-4 w-4 text-primary" />
                                            </div>
                                            <div>
                                                <div className="font-medium text-sm">{backup.machine_id}</div>
                                                <div className="text-xs text-muted-foreground">
                                                    {backup.machine_id === backupStatus.machine_id ? "(you)" : backup.filename}
                                                </div>
                                            </div>
                                        </div>
                                        <div className="text-right">
                                            <div className="text-sm">{(backup.size_bytes / 1024).toFixed(1)} KB</div>
                                            <div className="text-xs text-muted-foreground">
                                                {new Date(backup.last_modified).toLocaleDateString()}
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {(!backupStatus?.all_backups || backupStatus.all_backups.length === 0) && (
                        <div className="text-center py-8 text-muted-foreground">
                            <Cloud className="h-12 w-12 mx-auto mb-3 opacity-50" />
                            <p className="text-sm">No team backups found.</p>
                            <p className="text-xs mt-1">Create a backup to start sharing knowledge.</p>
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Backup Actions Card */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <HardDrive className="h-5 w-5" />
                        Backup & Restore
                    </CardTitle>
                    <CardDescription>
                        Create and restore backups. Files are saved to{" "}
                        <code className="bg-muted px-1 rounded text-xs">
                            {backupStatus?.backup_dir || "oak/history/"}
                        </code>
                        {backupStatus?.backup_dir_source && backupStatus.backup_dir_source !== "default" && (
                            <span className="text-xs text-muted-foreground ml-1">
                                (via {backupStatus.backup_dir_source === "environment variable" ? "OAK_CI_BACKUP_DIR" : ".env"})
                            </span>
                        )}
                        {" "}and can be committed to git.
                        {(!backupStatus?.backup_dir_source || backupStatus.backup_dir_source === "default") && (
                            <a href="#custom-backup-dir" className="ml-1 text-xs text-blue-500 hover:underline">
                                Use a custom location?
                            </a>
                        )}
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    {/* Options */}
                    <div className="flex items-center gap-2">
                        <Checkbox
                            id="include-activities"
                            checked={includeActivities}
                            onCheckedChange={(checked) => setIncludeActivities(!!checked)}
                        />
                        <Label htmlFor="include-activities" className="text-sm">
                            Include activities table (larger file, useful for debugging)
                        </Label>
                    </div>

                    {/* Action buttons */}
                    <div className="flex flex-wrap gap-3">
                        <Button
                            onClick={handleCreateBackup}
                            disabled={createBackupFn.isPending}
                        >
                            <Download className="h-4 w-4 mr-2" />
                            {createBackupFn.isPending ? "Creating..." : "Create Backup"}
                        </Button>

                        <Button
                            variant="outline"
                            onClick={handleRestoreMine}
                            disabled={restoreBackupFn.isPending || !backupStatus?.backup_exists}
                        >
                            <Upload className="h-4 w-4 mr-2" />
                            {restoreBackupFn.isPending ? "Restoring..." : "Restore My Backup"}
                        </Button>

                        <Button
                            variant="outline"
                            onClick={handleRestoreAll}
                            disabled={restoreAllBackupsFn.isPending || !backupStatus?.all_backups?.length}
                        >
                            <Users className="h-4 w-4 mr-2" />
                            {restoreAllBackupsFn.isPending ? "Restoring..." : "Restore All Team Backups"}
                        </Button>
                    </div>

                    {/* Restore statistics */}
                    {restoreResult && (
                        <Alert className="border-green-500 text-green-600 bg-green-50 dark:bg-green-950/20 dark:border-green-800 dark:text-green-400">
                            <CheckCircle2 className="h-4 w-4" />
                            <div>
                                <AlertTitle>Restore Complete</AlertTitle>
                                <AlertDescription>
                                <div className="grid grid-cols-2 gap-x-4 gap-y-1 mt-2 text-xs">
                                    <div>Memories imported: <strong>{restoreResult.observations_imported}</strong></div>
                                    <div>Memories skipped: {restoreResult.observations_skipped}</div>
                                    <div>Sessions imported: <strong>{restoreResult.sessions_imported}</strong></div>
                                    <div>Sessions skipped: {restoreResult.sessions_skipped}</div>
                                    <div>Batches imported: <strong>{restoreResult.batches_imported}</strong></div>
                                    <div>Batches skipped: {restoreResult.batches_skipped}</div>
                                    {(restoreResult.activities_imported > 0 || restoreResult.activities_skipped > 0) && (
                                        <>
                                            <div>Activities imported: <strong>{restoreResult.activities_imported}</strong></div>
                                            <div>Activities skipped: {restoreResult.activities_skipped}</div>
                                        </>
                                    )}
                                    {restoreResult.errors > 0 && (
                                        <div className="col-span-2 text-yellow-600 dark:text-yellow-400">
                                            <div>Errors: {restoreResult.errors}</div>
                                            {restoreResult.error_messages && restoreResult.error_messages.length > 0 && (
                                                <details className="mt-1">
                                                    <summary className="cursor-pointer text-xs">Show details</summary>
                                                    <ul className="mt-1 text-xs list-disc list-inside max-h-24 overflow-y-auto">
                                                        {restoreResult.error_messages.map((msg, i) => (
                                                            <li key={i} className="truncate" title={msg}>{msg}</li>
                                                        ))}
                                                    </ul>
                                                </details>
                                            )}
                                        </div>
                                    )}
                                </div>
                                <p className="mt-3 text-xs opacity-80">
                                    After restore, ChromaDB will rebuild automatically in the background.
                                </p>
                                </AlertDescription>
                            </div>
                        </Alert>
                    )}

                    <p className="text-xs text-muted-foreground">
                        Duplicates are automatically skipped using content-based hashing.
                        Team members can safely restore their backups without creating duplicate records.
                    </p>
                </CardContent>
            </Card>

            {/* Custom Backup Directory Help */}
            <Card id="custom-backup-dir" className="border-dashed scroll-mt-6">
                <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2 text-base">
                        <FolderCog className="h-4 w-4" />
                        Custom Backup Directory
                    </CardTitle>
                    <CardDescription>
                        Store backups in a shared location (network drive, separate repo) instead of the default <code className="bg-muted px-1 rounded text-xs">oak/history/</code>.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                    <div className="rounded-lg bg-muted/50 p-4 space-y-3">
                        <div className="flex items-start gap-2">
                            <Info className="h-4 w-4 mt-0.5 text-muted-foreground flex-shrink-0" />
                            <div className="text-sm">
                                <p className="font-medium">Add to your project's <code className="bg-background px-1 rounded text-xs border">.env</code> file:</p>
                                <pre className="mt-2 bg-background border rounded-md p-3 text-xs font-mono overflow-x-auto">
                                    <code>OAK_CI_BACKUP_DIR=/path/to/shared/backups</code>
                                </pre>
                                <p className="text-muted-foreground mt-2 text-xs">
                                    OAK automatically reads this from <code className="bg-background px-0.5 rounded border">.env</code> in your project root.
                                    Both absolute and relative paths work (relative paths resolve against project root).
                                </p>
                            </div>
                        </div>
                        <div className="text-xs text-muted-foreground border-t pt-3 space-y-1">
                            <p><strong>Priority:</strong> <code className="bg-background px-0.5 rounded border">OAK_CI_BACKUP_DIR</code> shell env var &gt; <code className="bg-background px-0.5 rounded border">.env</code> file &gt; default</p>
                            <p><strong>Verify:</strong> <code className="bg-background px-0.5 rounded border">oak ci backup --info</code></p>
                        </div>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
