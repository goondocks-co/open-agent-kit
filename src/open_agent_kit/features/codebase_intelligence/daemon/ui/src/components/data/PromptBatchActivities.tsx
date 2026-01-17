import { useQuery } from "@tanstack/react-query";
import { fetchJson } from "@/lib/api";
import type { ActivityItem } from "@/hooks/use-activity";
import { Loader2, AlertCircle, Wrench, FileCode, CheckCircle2, XCircle } from "lucide-react";
import { cn, formatDate } from "@/lib/utils";

interface PromptBatchActivitiesProps {
    batchId: string;
}

export function PromptBatchActivities({ batchId }: PromptBatchActivitiesProps) {
    const { data: response, isLoading, error } = useQuery<any>({
        queryKey: ["batch_activities", batchId],
        queryFn: () => fetchJson(`/api/activity/prompt-batches/${batchId}/activities?limit=50`),
    });

    if (isLoading) return <div className="flex items-center gap-2 text-sm text-muted-foreground py-2"><Loader2 className="animate-spin w-3 h-3" /> Loading activities...</div>;
    if (error) return <div className="flex items-center gap-2 text-sm text-destructive py-2"><AlertCircle className="w-3 h-3" /> Failed to load activities</div>;

    const activities: ActivityItem[] = response?.activities || [];

    if (activities.length === 0) return <div className="text-sm text-muted-foreground italic py-2">No activities recorded in this batch.</div>;

    return (
        <div className="space-y-2 mt-4 border-l-2 pl-4 border-muted">
            {activities.map((act) => (
                <div key={act.id} className="text-sm grid grid-cols-[auto_1fr] gap-3 py-2 border-b last:border-0 border-dashed border-muted-foreground/30">
                    <div className={cn("mt-0.5", act.success ? "text-green-500" : "text-red-500")}>
                        {act.success ? <CheckCircle2 className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
                    </div>
                    <div className="space-y-1">
                        <div className="font-mono font-medium flex items-center gap-2">
                            <Wrench className="w-3 h-3 text-muted-foreground" />
                            {act.tool_name}
                            {act.file_path && (
                                <span className="text-xs text-muted-foreground flex items-center gap-1 bg-muted px-1.5 rounded">
                                    <FileCode className="w-3 h-3" />
                                    {act.file_path.split('/').pop()}
                                </span>
                            )}
                            <span className="ml-auto text-xs text-muted-foreground">{formatDate(act.created_at).split(', ')[1]}</span>
                        </div>
                        <div className="bg-muted/50 rounded p-2 font-mono text-xs overflow-x-auto text-muted-foreground/80">
                            {/* Simple rendering of input/output summary */}
                            {act.tool_input && (
                                <div className="mb-1">
                                    <span className="font-semibold text-foreground/80">Input:</span> {JSON.stringify(act.tool_input).slice(0, 100)}{JSON.stringify(act.tool_input).length > 100 ? '...' : ''}
                                </div>
                            )}
                            {act.tool_output_summary && (
                                <div>
                                    <span className="font-semibold text-foreground/80">Output:</span> {act.tool_output_summary}
                                </div>
                            )}
                            {act.error_message && (
                                <div className="text-red-500 mt-1">
                                    Error: {act.error_message}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            ))}
        </div>
    )
}
