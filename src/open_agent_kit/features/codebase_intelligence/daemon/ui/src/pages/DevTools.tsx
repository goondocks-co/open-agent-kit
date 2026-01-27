import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchJson } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { AlertCircle, CheckCircle2, Play, RefreshCw, Trash2, Database, Activity, Brain, AlertTriangle, FileText } from "lucide-react";
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

export default function DevTools() {
    const queryClient = useQueryClient();
    const [message, setMessage] = useState<{ type: typeof MESSAGE_TYPES.SUCCESS | typeof MESSAGE_TYPES.ERROR, text: string } | null>(null);
    const [clearChromaFirst, setClearChromaFirst] = useState(false);

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
            </div>
        </div>
    );
}
