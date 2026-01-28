import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchJson } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { AlertCircle, CheckCircle2, Play, RefreshCw, Trash2, Database, Activity, Brain, AlertTriangle, FileText, RotateCcw, Eye, X, Wrench } from "lucide-react";
// Note: Backup functionality moved to Team page
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { API_ENDPOINTS, MEMORY_SYNC_STATUS, MESSAGE_TYPES } from "@/lib/constants";

/** Refetch interval for memory stats (5 seconds) */
const MEMORY_STATS_REFETCH_INTERVAL_MS = 5000;

interface MemoryStats {
    sqlite: { total: number; embedded: number; unembedded: number; plans_embedded?: number; plans_unembedded?: number };
    chromadb: { count: number };
    sync_status: string;
    needs_rebuild: boolean;
}

interface ReprocessDryRunResult {
    status: string;
    message: string;
    batches_found: number;
    batch_ids?: number[];
    machine_id: string;
}

interface ReprocessResult {
    status: string;
    message: string;
    batches_queued?: number;
    observations_deleted?: number;
    previous_observations?: number;
    machine_id?: string;
    mode?: string;
}

interface MaintenanceResult {
    status: string;
    message: string;
    operations?: string[];
    integrity_check?: string | null;
    size_before_mb?: number;
    size_mb?: number;
}

export default function DevTools() {
    const queryClient = useQueryClient();
    const [message, setMessage] = useState<{ type: typeof MESSAGE_TYPES.SUCCESS | typeof MESSAGE_TYPES.ERROR, text: string } | null>(null);
    const [clearChromaFirst, setClearChromaFirst] = useState(false);
    const [dryRunResult, setDryRunResult] = useState<ReprocessDryRunResult | null>(null);
    const [showDryRunDialog, setShowDryRunDialog] = useState(false);
    const [maintenanceOpts, setMaintenanceOpts] = useState({
        vacuum: true,
        analyze: true,
        fts_optimize: true,
        integrity_check: false,
    });

    // Fetch memory stats
    const { data: memoryStats } = useQuery<MemoryStats>({
        queryKey: ["memory-stats"],
        queryFn: () => fetchJson(API_ENDPOINTS.DEVTOOLS_MEMORY_STATS),
        refetchInterval: MEMORY_STATS_REFETCH_INTERVAL_MS,
    });

    const rebuildIndexFn = useMutation({
        mutationFn: () => fetchJson(API_ENDPOINTS.DEVTOOLS_REBUILD_INDEX, { method: "POST", body: JSON.stringify({ full_rebuild: true }) }),
        onSuccess: () => setMessage({ type: MESSAGE_TYPES.SUCCESS, text: "Index rebuild started in background." }),
        onError: (err: Error) => setMessage({ type: MESSAGE_TYPES.ERROR, text: err.message || "Failed to start rebuild" })
    });

    const rebuildMemoriesFn = useMutation({
        mutationFn: (clearFirst: boolean) => fetchJson<{ message?: string }>(API_ENDPOINTS.DEVTOOLS_REBUILD_MEMORIES, { method: "POST", body: JSON.stringify({ full_rebuild: true, clear_chromadb_first: clearFirst }) }),
        onSuccess: (data) => {
            setMessage({ type: MESSAGE_TYPES.SUCCESS, text: data.message || "Memory re-embedding started." });
            queryClient.invalidateQueries({ queryKey: ["memory-stats"] });
            queryClient.invalidateQueries({ queryKey: ["status"] });
            setClearChromaFirst(false);
        },
        onError: (err: Error) => setMessage({ type: MESSAGE_TYPES.ERROR, text: err.message || "Failed to rebuild memories" })
    });

    const triggerProcessingFn = useMutation({
        mutationFn: () => fetchJson<{ processed_batches?: number }>(API_ENDPOINTS.DEVTOOLS_TRIGGER_PROCESSING, { method: "POST" }),
        onSuccess: (data) => {
            setMessage({ type: MESSAGE_TYPES.SUCCESS, text: `Triggered successfully. Processed ${data.processed_batches} batches.` });
            queryClient.invalidateQueries({ queryKey: ["status"] });
        },
        onError: (err: Error) => setMessage({ type: MESSAGE_TYPES.ERROR, text: err.message || "Failed to trigger processing" })
    });

    const regenerateSummariesFn = useMutation({
        mutationFn: () => fetchJson<{ status: string; sessions_queued: number; message?: string }>(API_ENDPOINTS.DEVTOOLS_REGENERATE_SUMMARIES, { method: "POST" }),
        onSuccess: (data) => {
            const msg = data.status === "skipped"
                ? data.message || "No sessions need summaries"
                : `Started regenerating summaries for ${data.sessions_queued} sessions`;
            setMessage({ type: MESSAGE_TYPES.SUCCESS, text: msg });
            queryClient.invalidateQueries({ queryKey: ["memory-stats"] });
        },
        onError: (err: Error) => setMessage({ type: MESSAGE_TYPES.ERROR, text: err.message || "Failed to regenerate summaries" })
    });

    const resetProcessingFn = useMutation({
        mutationFn: () => fetchJson(API_ENDPOINTS.DEVTOOLS_RESET_PROCESSING, { method: "POST", body: JSON.stringify({ delete_memories: true }) }),
        onSuccess: () => {
            setMessage({ type: MESSAGE_TYPES.SUCCESS, text: "Processing state reset. Observations deleted. Background job will re-process." });
            queryClient.invalidateQueries({ queryKey: ["status"] });
            queryClient.invalidateQueries({ queryKey: ["memory-stats"] });
        },
        onError: (err: Error) => setMessage({ type: MESSAGE_TYPES.ERROR, text: err.message || "Failed to reset processing" })
    });

    const reprocessDryRunFn = useMutation({
        mutationFn: () => fetchJson<ReprocessDryRunResult>(API_ENDPOINTS.DEVTOOLS_REPROCESS_OBSERVATIONS, {
            method: "POST",
            body: JSON.stringify({ mode: "all", dry_run: true })
        }),
        onSuccess: (data) => {
            setDryRunResult(data);
            setShowDryRunDialog(true);
        },
        onError: (err: Error) => setMessage({ type: MESSAGE_TYPES.ERROR, text: err.message || "Failed to preview reprocessing" })
    });

    const reprocessObservationsFn = useMutation({
        mutationFn: () => fetchJson<ReprocessResult>(API_ENDPOINTS.DEVTOOLS_REPROCESS_OBSERVATIONS, {
            method: "POST",
            body: JSON.stringify({ mode: "all", delete_existing: true, dry_run: false })
        }),
        onSuccess: (data) => {
            setShowDryRunDialog(false);
            setDryRunResult(null);
            const msg = data.status === "skipped"
                ? data.message
                : `Reprocessing ${data.batches_queued} batches. Deleted ${data.observations_deleted} old observations.`;
            setMessage({ type: MESSAGE_TYPES.SUCCESS, text: msg });
            queryClient.invalidateQueries({ queryKey: ["memory-stats"] });
            queryClient.invalidateQueries({ queryKey: ["status"] });
        },
        onError: (err: Error) => setMessage({ type: MESSAGE_TYPES.ERROR, text: err.message || "Failed to reprocess observations" })
    });

    const maintenanceFn = useMutation({
        mutationFn: () => fetchJson<MaintenanceResult>(API_ENDPOINTS.DEVTOOLS_DATABASE_MAINTENANCE, {
            method: "POST",
            body: JSON.stringify(maintenanceOpts)
        }),
        onSuccess: (data) => {
            let msg = data.message;
            if (data.integrity_check) {
                msg += ` Integrity: ${data.integrity_check}`;
            }
            if (data.size_before_mb) {
                msg += ` (DB size: ${data.size_before_mb}MB)`;
            }
            setMessage({ type: MESSAGE_TYPES.SUCCESS, text: msg });
        },
        onError: (err: Error) => setMessage({ type: MESSAGE_TYPES.ERROR, text: err.message || "Failed to run maintenance" })
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
                            {memoryStats.sync_status === MEMORY_SYNC_STATUS.PENDING_EMBED && `${memoryStats.sqlite.unembedded + (memoryStats.sqlite.plans_unembedded || 0)} items pending embedding.`}
                            {memoryStats.sync_status === MEMORY_SYNC_STATUS.OUT_OF_SYNC && "ChromaDB has orphaned entries. Use 'Clear orphaned entries' below to fix."}
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="grid grid-cols-3 gap-4 text-center">
                            <div>
                                <div className="text-2xl font-bold">{memoryStats.sqlite.embedded + (memoryStats.sqlite.plans_embedded || 0)}</div>
                                <div className="text-xs text-muted-foreground">SQLite Total</div>
                                <div className="text-xs text-muted-foreground/60">({memoryStats.sqlite.embedded} memories + {memoryStats.sqlite.plans_embedded || 0} plans)</div>
                            </div>
                            <div>
                                <div className="text-2xl font-bold">{memoryStats.chromadb.count}</div>
                                <div className="text-xs text-muted-foreground">ChromaDB</div>
                            </div>
                            <div>
                                <div className={`text-2xl font-bold ${(memoryStats.sqlite.unembedded + (memoryStats.sqlite.plans_unembedded || 0)) > 0 ? "text-yellow-500" : ""}`}>
                                    {memoryStats.sqlite.unembedded + (memoryStats.sqlite.plans_unembedded || 0)}
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

                        <Button
                            variant="secondary"
                            onClick={() => regenerateSummariesFn.mutate()}
                            disabled={regenerateSummariesFn.isPending}
                            className="w-full justify-start"
                        >
                            <FileText className={`mr-2 h-4 w-4 ${regenerateSummariesFn.isPending ? "animate-pulse" : ""}`} />
                            {regenerateSummariesFn.isPending ? "Regenerating..." : "Regenerate Session Summaries"}
                        </Button>
                        <p className="text-xs text-muted-foreground">
                            Backfills missing session summaries for completed sessions. Use after fixing summary generation issues.
                        </p>

                        <div className="h-px bg-border my-4" />

                        <Button
                            variant="secondary"
                            onClick={() => reprocessDryRunFn.mutate()}
                            disabled={reprocessDryRunFn.isPending || reprocessObservationsFn.isPending}
                            className="w-full justify-start"
                        >
                            <Eye className={`mr-2 h-4 w-4 ${reprocessDryRunFn.isPending ? "animate-pulse" : ""}`} />
                            {reprocessDryRunFn.isPending ? "Checking..." : "Preview Reprocess Observations"}
                        </Button>
                        <p className="text-xs text-muted-foreground">
                            Re-extract observations using updated prompts (with new importance criteria). Preview first to see what will change.
                        </p>

                        <div className="h-px bg-border my-4" />

                        <div className="flex items-center gap-2 mb-2">
                            <Checkbox
                                id="clear-chroma-first"
                                checked={clearChromaFirst}
                                onCheckedChange={(checked) => setClearChromaFirst(checked === true)}
                            />
                            <Label htmlFor="clear-chroma-first" className="text-sm">
                                Clear orphaned entries first
                            </Label>
                        </div>
                        <Button
                            variant="secondary"
                            onClick={() => rebuildMemoriesFn.mutate(clearChromaFirst)}
                            disabled={rebuildMemoriesFn.isPending}
                            className="w-full justify-start"
                        >
                            <Brain className={`mr-2 h-4 w-4 ${rebuildMemoriesFn.isPending ? "animate-pulse" : ""}`} />
                            {rebuildMemoriesFn.isPending ? "Re-embedding..." : "Re-embed Memories to ChromaDB"}
                        </Button>
                        <p className="text-xs text-muted-foreground">
                            Re-embeds all memories from SQLite to ChromaDB. Check "Clear orphaned entries" to remove stale ChromaDB data after restores or deletions.
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

                {/* Database Maintenance */}
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2"><Wrench className="h-5 w-5" /> Database Maintenance</CardTitle>
                        <CardDescription>Optimize SQLite after heavy operations.</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="space-y-3">
                            <div className="flex items-center gap-2">
                                <Checkbox
                                    id="maint-vacuum"
                                    checked={maintenanceOpts.vacuum}
                                    onCheckedChange={(checked) => setMaintenanceOpts(o => ({ ...o, vacuum: checked === true }))}
                                />
                                <Label htmlFor="maint-vacuum" className="text-sm">
                                    VACUUM <span className="text-muted-foreground">(reclaim space)</span>
                                </Label>
                            </div>
                            <div className="flex items-center gap-2">
                                <Checkbox
                                    id="maint-analyze"
                                    checked={maintenanceOpts.analyze}
                                    onCheckedChange={(checked) => setMaintenanceOpts(o => ({ ...o, analyze: checked === true }))}
                                />
                                <Label htmlFor="maint-analyze" className="text-sm">
                                    ANALYZE <span className="text-muted-foreground">(update stats)</span>
                                </Label>
                            </div>
                            <div className="flex items-center gap-2">
                                <Checkbox
                                    id="maint-fts"
                                    checked={maintenanceOpts.fts_optimize}
                                    onCheckedChange={(checked) => setMaintenanceOpts(o => ({ ...o, fts_optimize: checked === true }))}
                                />
                                <Label htmlFor="maint-fts" className="text-sm">
                                    FTS optimize <span className="text-muted-foreground">(search index)</span>
                                </Label>
                            </div>
                            <div className="flex items-center gap-2">
                                <Checkbox
                                    id="maint-integrity"
                                    checked={maintenanceOpts.integrity_check}
                                    onCheckedChange={(checked) => setMaintenanceOpts(o => ({ ...o, integrity_check: checked === true }))}
                                />
                                <Label htmlFor="maint-integrity" className="text-sm">
                                    Integrity check <span className="text-muted-foreground">(slower)</span>
                                </Label>
                            </div>
                        </div>

                        <Button
                            variant="secondary"
                            onClick={() => maintenanceFn.mutate()}
                            disabled={maintenanceFn.isPending || (!maintenanceOpts.vacuum && !maintenanceOpts.analyze && !maintenanceOpts.fts_optimize && !maintenanceOpts.integrity_check)}
                            className="w-full justify-start"
                        >
                            <Wrench className={`mr-2 h-4 w-4 ${maintenanceFn.isPending ? "animate-spin" : ""}`} />
                            {maintenanceFn.isPending ? "Running..." : "Run Maintenance"}
                        </Button>
                        <p className="text-xs text-muted-foreground">
                            Run periodically (weekly/monthly) or after heavy delete/rebuild operations to maintain performance.
                        </p>
                    </CardContent>
                </Card>
            </div>

            {/* Dry Run Preview Dialog */}
            {showDryRunDialog && (
                <div className="fixed inset-0 z-50 flex items-center justify-center">
                    {/* Backdrop */}
                    <div
                        className="fixed inset-0 bg-black/50 backdrop-blur-sm"
                        onClick={() => !reprocessObservationsFn.isPending && setShowDryRunDialog(false)}
                    />

                    {/* Dialog */}
                    <div className="relative z-50 w-full max-w-lg rounded-lg border bg-background shadow-lg animate-in fade-in-0 zoom-in-95 mx-4">
                        {/* Header */}
                        <div className="flex items-center justify-between p-4 border-b">
                            <div className="flex items-center gap-3">
                                <div className="rounded-full p-2 bg-blue-500/10">
                                    <RotateCcw className="h-5 w-5 text-blue-500" />
                                </div>
                                <div>
                                    <h2 className="text-lg font-semibold">Reprocess Observations Preview</h2>
                                    <p className="text-sm text-muted-foreground">
                                        Re-extract with updated prompts
                                    </p>
                                </div>
                            </div>
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setShowDryRunDialog(false)}
                                disabled={reprocessObservationsFn.isPending}
                                className="h-8 w-8 p-0"
                            >
                                <X className="h-4 w-4" />
                            </Button>
                        </div>

                        {/* Content */}
                        <div className="p-4 space-y-4">
                            {dryRunResult && (
                                <>
                                    <div className="grid grid-cols-2 gap-4 text-sm">
                                        <div className="bg-muted p-3 rounded-md">
                                            <div className="text-2xl font-bold">{dryRunResult.batches_found}</div>
                                            <div className="text-muted-foreground">Batches to reprocess</div>
                                        </div>
                                        <div className="bg-muted p-3 rounded-md">
                                            <div className="text-xs font-mono truncate">{dryRunResult.machine_id}</div>
                                            <div className="text-muted-foreground text-xs mt-1">Machine ID (only your data)</div>
                                        </div>
                                    </div>

                                    {dryRunResult.batch_ids && dryRunResult.batch_ids.length > 0 && (
                                        <div className="text-xs text-muted-foreground">
                                            <span className="font-medium">Sample batch IDs:</span>{" "}
                                            {dryRunResult.batch_ids.slice(0, 10).join(", ")}
                                            {dryRunResult.batch_ids.length > 10 && ` ... and ${dryRunResult.batch_ids.length - 10} more`}
                                        </div>
                                    )}

                                    {dryRunResult.batches_found === 0 && (
                                        <Alert>
                                            <AlertCircle className="h-4 w-4" />
                                            <AlertDescription>
                                                No batches found to reprocess. This may mean all your data is already processed.
                                            </AlertDescription>
                                        </Alert>
                                    )}

                                    {dryRunResult.batches_found > 0 && (
                                        <Alert variant="default" className="border-yellow-500/50 bg-yellow-50">
                                            <AlertTriangle className="h-4 w-4 text-yellow-600" />
                                            <AlertDescription className="text-yellow-800">
                                                After reprocessing, run <strong>Re-embed Memories to ChromaDB</strong> to sync the search index.
                                            </AlertDescription>
                                        </Alert>
                                    )}
                                </>
                            )}
                        </div>

                        {/* Footer */}
                        <div className="flex justify-end gap-3 p-4 border-t">
                            <Button
                                variant="outline"
                                onClick={() => setShowDryRunDialog(false)}
                                disabled={reprocessObservationsFn.isPending}
                            >
                                Cancel
                            </Button>
                            <Button
                                variant="default"
                                onClick={() => reprocessObservationsFn.mutate()}
                                disabled={reprocessObservationsFn.isPending || !dryRunResult || dryRunResult.batches_found === 0}
                            >
                                <RotateCcw className={`mr-2 h-4 w-4 ${reprocessObservationsFn.isPending ? "animate-spin" : ""}`} />
                                {reprocessObservationsFn.isPending ? "Reprocessing..." : `Reprocess ${dryRunResult?.batches_found || 0} Batches`}
                            </Button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
