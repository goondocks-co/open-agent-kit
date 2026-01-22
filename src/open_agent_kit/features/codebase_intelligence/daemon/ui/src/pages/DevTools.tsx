import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchJson } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { AlertCircle, CheckCircle2, Play, RefreshCw, Trash2, Database, Activity, Brain, AlertTriangle, HardDrive, Download, Upload } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { API_ENDPOINTS, MEMORY_SYNC_STATUS, MESSAGE_TYPES } from "@/lib/constants";
import { useBackupStatus, useCreateBackup, useRestoreBackup } from "@/hooks/use-backup";

/** Refetch interval for memory stats (5 seconds) */
const MEMORY_STATS_REFETCH_INTERVAL_MS = 5000;

interface MemoryStats {
    sqlite: { total: number; embedded: number; unembedded: number };
    chromadb: { count: number };
    sync_status: string;
    needs_rebuild: boolean;
}

export default function DevTools() {
    const queryClient = useQueryClient();
    const [message, setMessage] = useState<{ type: typeof MESSAGE_TYPES.SUCCESS | typeof MESSAGE_TYPES.ERROR, text: string } | null>(null);
    const [includeActivities, setIncludeActivities] = useState(false);

    // Fetch memory stats
    const { data: memoryStats } = useQuery<MemoryStats>({
        queryKey: ["memory-stats"],
        queryFn: () => fetchJson(API_ENDPOINTS.DEVTOOLS_MEMORY_STATS),
        refetchInterval: MEMORY_STATS_REFETCH_INTERVAL_MS,
    });

    // Backup hooks
    const { data: backupStatus, refetch: refetchBackupStatus } = useBackupStatus();
    const createBackupFn = useCreateBackup();
    const restoreBackupFn = useRestoreBackup();

    const rebuildIndexFn = useMutation({
        mutationFn: () => fetchJson(API_ENDPOINTS.DEVTOOLS_REBUILD_INDEX, { method: "POST", body: JSON.stringify({ full_rebuild: true }) }),
        onSuccess: () => setMessage({ type: MESSAGE_TYPES.SUCCESS, text: "Index rebuild started in background." }),
        onError: (err: any) => setMessage({ type: MESSAGE_TYPES.ERROR, text: err.message || "Failed to start rebuild" })
    });

    const rebuildMemoriesFn = useMutation({
        mutationFn: () => fetchJson(API_ENDPOINTS.DEVTOOLS_REBUILD_MEMORIES, { method: "POST", body: JSON.stringify({ full_rebuild: true }) }),
        onSuccess: (data: any) => {
            setMessage({ type: MESSAGE_TYPES.SUCCESS, text: data.message || "Memory re-embedding started." });
            queryClient.invalidateQueries({ queryKey: ["memory-stats"] });
            queryClient.invalidateQueries({ queryKey: ["status"] });
        },
        onError: (err: any) => setMessage({ type: MESSAGE_TYPES.ERROR, text: err.message || "Failed to rebuild memories" })
    });

    const triggerProcessingFn = useMutation({
        mutationFn: () => fetchJson(API_ENDPOINTS.DEVTOOLS_TRIGGER_PROCESSING, { method: "POST" }),
        onSuccess: (data: any) => {
            setMessage({ type: MESSAGE_TYPES.SUCCESS, text: `Triggered successfully. Processed ${data.processed_batches} batches.` });
            queryClient.invalidateQueries({ queryKey: ["status"] });
        },
        onError: (err: any) => setMessage({ type: MESSAGE_TYPES.ERROR, text: err.message || "Failed to trigger processing" })
    });

    const resetProcessingFn = useMutation({
        mutationFn: () => fetchJson(API_ENDPOINTS.DEVTOOLS_RESET_PROCESSING, { method: "POST", body: JSON.stringify({ delete_memories: true }) }),
        onSuccess: () => {
            setMessage({ type: MESSAGE_TYPES.SUCCESS, text: "Processing state reset. Observations deleted. Background job will re-process." });
            queryClient.invalidateQueries({ queryKey: ["status"] });
            queryClient.invalidateQueries({ queryKey: ["memory-stats"] });
        },
        onError: (err: any) => setMessage({ type: MESSAGE_TYPES.ERROR, text: err.message || "Failed to reset processing" })
    });

    return (
        <div className="space-y-6 max-w-4xl mx-auto p-4">
            <div className="flex flex-col gap-2">
                <h1 className="text-3xl font-bold tracking-tight">Developer Tools</h1>
                <p className="text-muted-foreground">Advanced actions for debugging and maintenance.</p>
            </div>

            {message && (
                <Alert variant={message.type === MESSAGE_TYPES.ERROR ? "destructive" : "default"} className={message.type === MESSAGE_TYPES.SUCCESS ? "border-green-500 text-green-600 bg-green-50" : ""}>
                    {message.type === MESSAGE_TYPES.SUCCESS ? <CheckCircle2 className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
                    <AlertTitle>{message.type === MESSAGE_TYPES.SUCCESS ? "Success" : "Error"}</AlertTitle>
                    <AlertDescription>{message.text}</AlertDescription>
                </Alert>
            )}

            {/* Memory Stats Card */}
            {memoryStats && (
                <Card className={memoryStats.needs_rebuild ? "border-yellow-500" : ""}>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <Brain className="h-5 w-5" /> Memory Status
                            {memoryStats.needs_rebuild && <AlertTriangle className="h-4 w-4 text-yellow-500" />}
                        </CardTitle>
                        <CardDescription>
                            {memoryStats.sync_status === MEMORY_SYNC_STATUS.SYNCED && "All memories are synced."}
                            {memoryStats.sync_status === MEMORY_SYNC_STATUS.PENDING_EMBED && `${memoryStats.sqlite.unembedded} memories pending embedding.`}
                            {memoryStats.sync_status === MEMORY_SYNC_STATUS.OUT_OF_SYNC && "ChromaDB is out of sync with SQLite."}
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="grid grid-cols-3 gap-4 text-center">
                            <div>
                                <div className="text-2xl font-bold">{memoryStats.sqlite.total}</div>
                                <div className="text-xs text-muted-foreground">SQLite Total</div>
                            </div>
                            <div>
                                <div className="text-2xl font-bold">{memoryStats.chromadb.count}</div>
                                <div className="text-xs text-muted-foreground">ChromaDB</div>
                            </div>
                            <div>
                                <div className={`text-2xl font-bold ${memoryStats.sqlite.unembedded > 0 ? "text-yellow-500" : ""}`}>
                                    {memoryStats.sqlite.unembedded}
                                </div>
                                <div className="text-xs text-muted-foreground">Pending</div>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            )}

            <div className="grid gap-6 md:grid-cols-2">
                {/* Indexing Tools */}
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2"><Database className="h-5 w-5" /> Indexing</CardTitle>
                        <CardDescription>Manage the codebase vector index.</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <Button
                            variant="secondary"
                            onClick={() => rebuildIndexFn.mutate()}
                            disabled={rebuildIndexFn.isPending}
                            className="w-full justify-start"
                        >
                            <RefreshCw className={`mr-2 h-4 w-4 ${rebuildIndexFn.isPending ? "animate-spin" : ""}`} />
                            {rebuildIndexFn.isPending ? "Rebuilding..." : "Rebuild Codebase Index"}
                        </Button>
                        <p className="text-xs text-muted-foreground">
                            Forces a complete re-scan of the codebase and updates the vector store. Useful if the index is out of sync with files.
                        </p>
                    </CardContent>
                </Card>

                {/* Processing Tools */}
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2"><Activity className="h-5 w-5" /> Processing</CardTitle>
                        <CardDescription>Manage LLM background processing logic.</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <Button
                            variant="secondary"
                            onClick={() => triggerProcessingFn.mutate()}
                            disabled={triggerProcessingFn.isPending}
                            className="w-full justify-start"
                        >
                            <Play className="mr-2 h-4 w-4" />
                            {triggerProcessingFn.isPending ? "Running..." : "Trigger Background Processing"}
                        </Button>
                        <p className="text-xs text-muted-foreground">
                            Manually runs the background job to process pending prompt batches and generate observations immediately.
                        </p>

                        <div className="h-px bg-border my-4" />

                        <Button
                            variant="secondary"
                            onClick={() => rebuildMemoriesFn.mutate()}
                            disabled={rebuildMemoriesFn.isPending}
                            className="w-full justify-start"
                        >
                            <Brain className={`mr-2 h-4 w-4 ${rebuildMemoriesFn.isPending ? "animate-pulse" : ""}`} />
                            {rebuildMemoriesFn.isPending ? "Re-embedding..." : "Re-embed Memories to ChromaDB"}
                        </Button>
                        <p className="text-xs text-muted-foreground">
                            Re-embeds all memories from SQLite to ChromaDB. Use after changing embedding models or if ChromaDB was cleared.
                        </p>

                        <div className="h-px bg-border my-4" />

                        <Button
                            variant="destructive"
                            onClick={() => {
                                if (confirm("Are you sure? This will DELETE all existing memory observations and force re-processing of all history.")) {
                                    resetProcessingFn.mutate();
                                }
                            }}
                            disabled={resetProcessingFn.isPending}
                            className="w-full justify-start"
                        >
                            <Trash2 className="mr-2 h-4 w-4" />
                            {resetProcessingFn.isPending ? "Resetting..." : "Reset All Processing State"}
                        </Button>
                        <p className="text-xs text-muted-foreground">
                            Deletes generated memories and marks all past sessions as "unprocessed". The system will re-read activity logs and regenerate memories.
                        </p>
                    </CardContent>
                </Card>
            </div>

            {/* Database Backup */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <HardDrive className="h-5 w-5" />
                        Database Backup
                    </CardTitle>
                    <CardDescription>
                        Export and restore session history, prompts, and memories. Backups are preserved when the feature is removed.
                    </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    {backupStatus && (
                        <div className="text-sm text-muted-foreground">
                            {backupStatus.backup_exists ? (
                                <div className="space-y-1">
                                    <div className="flex items-center gap-2">
                                        <CheckCircle2 className="h-4 w-4 text-green-500" />
                                        <span>Backup exists</span>
                                    </div>
                                    <div className="text-xs pl-6">
                                        {backupStatus.backup_size_bytes && (
                                            <span>{(backupStatus.backup_size_bytes / 1024).toFixed(1)} KB</span>
                                        )}
                                        {backupStatus.last_modified && (
                                            <span className="ml-2">• Last modified: {new Date(backupStatus.last_modified).toLocaleString()}</span>
                                        )}
                                    </div>
                                </div>
                            ) : (
                                <div className="flex items-center gap-2">
                                    <AlertCircle className="h-4 w-4 text-yellow-500" />
                                    <span>No backup file found</span>
                                </div>
                            )}
                        </div>
                    )}

                    <div className="flex items-center gap-2">
                        <Checkbox
                            id="include-activities"
                            checked={includeActivities}
                            onCheckedChange={(checked) => setIncludeActivities(!!checked)}
                        />
                        <Label htmlFor="include-activities" className="text-sm">
                            Include activities table (larger file)
                        </Label>
                    </div>

                    <div className="flex gap-2">
                        <Button
                            variant="secondary"
                            onClick={() => {
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
                            }}
                            disabled={createBackupFn.isPending}
                        >
                            <Download className="h-4 w-4 mr-2" />
                            {createBackupFn.isPending ? "Backing up..." : "Create Backup"}
                        </Button>

                        <Button
                            variant="outline"
                            onClick={() => {
                                restoreBackupFn.mutate(
                                    {},
                                    {
                                        onSuccess: (data) => {
                                            setMessage({ type: MESSAGE_TYPES.SUCCESS, text: data.message });
                                        },
                                        onError: (err) => {
                                            setMessage({ type: MESSAGE_TYPES.ERROR, text: err.message });
                                        },
                                    }
                                );
                            }}
                            disabled={restoreBackupFn.isPending || !backupStatus?.backup_exists}
                        >
                            <Upload className="h-4 w-4 mr-2" />
                            {restoreBackupFn.isPending ? "Restoring..." : "Restore from Backup"}
                        </Button>
                    </div>

                    <p className="text-xs text-muted-foreground">
                        Backups are saved to <code className="bg-muted px-1 rounded">oak/data/ci_history.sql</code> and can be committed to git.
                    </p>
                </CardContent>
            </Card>
        </div>
    );
}
