import { useQuery } from "@tanstack/react-query";
import { fetchJson } from "@/lib/api";
import { useDeleteActivity } from "@/hooks/use-delete";
import type { ActivityItem } from "@/hooks/use-activity";
import { ConfirmDialog, useConfirmDialog } from "@/components/ui/confirm-dialog";
import { ContentDialog, useContentDialog } from "@/components/ui/content-dialog";
import { Loader2, AlertCircle, Wrench, FileCode, CheckCircle2, XCircle, Trash2, Maximize2 } from "lucide-react";
import { cn, formatDate } from "@/lib/utils";
import { DELETE_CONFIRMATIONS, ACTIVITY_TRUNCATION_LIMIT } from "@/lib/constants";

interface PromptBatchActivitiesProps {
    batchId: string;
}

export function PromptBatchActivities({ batchId }: PromptBatchActivitiesProps) {
    const { data: response, isLoading, error } = useQuery<any>({
        queryKey: ["batch_activities", batchId],
        queryFn: () => fetchJson(`/api/activity/prompt-batches/${batchId}/activities?limit=50`),
    });

    const deleteActivity = useDeleteActivity();
    const { isOpen, setIsOpen, itemToDelete, openDialog, closeDialog } = useConfirmDialog();
    const { isOpen: isContentOpen, setIsOpen: setContentOpen, dialogContent, openDialog: openContentDialog } = useContentDialog();

    /** Format full activity content for the modal */
    const formatActivityContent = (act: ActivityItem): string => {
        const parts: string[] = [];
        if (act.tool_input) {
            parts.push(`Input:\n${JSON.stringify(act.tool_input, null, 2)}`);
        }
        if (act.tool_output_summary) {
            parts.push(`Output:\n${act.tool_output_summary}`);
        }
        if (act.error_message) {
            parts.push(`Error:\n${act.error_message}`);
        }
        return parts.join("\n\n");
    };

    /** Check if activity content is truncated */
    const isContentTruncated = (act: ActivityItem): boolean => {
        const inputStr = act.tool_input ? JSON.stringify(act.tool_input) : "";
        return inputStr.length > ACTIVITY_TRUNCATION_LIMIT;
    };

    const handleDelete = async () => {
        if (!itemToDelete) return;
        try {
            await deleteActivity.mutateAsync({
                activityId: itemToDelete as number,
                batchId: batchId,
            });
            closeDialog();
        } catch (error) {
            console.error("Failed to delete activity:", error);
        }
    };

    if (isLoading) return <div className="flex items-center gap-2 text-sm text-muted-foreground py-2"><Loader2 className="animate-spin w-3 h-3" /> Loading activities...</div>;
    if (error) return <div className="flex items-center gap-2 text-sm text-destructive py-2"><AlertCircle className="w-3 h-3" /> Failed to load activities</div>;

    const activities: ActivityItem[] = response?.activities || [];

    if (activities.length === 0) return <div className="text-sm text-muted-foreground italic py-2">No activities recorded in this batch.</div>;

    return (
        <div className="space-y-2 mt-4 border-l-2 pl-4 border-muted">
            {activities.map((act) => (
                <div key={act.id} className="text-sm grid grid-cols-[auto_1fr] gap-3 py-2 border-b last:border-0 border-dashed border-muted-foreground/30 group">
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
                            <span className="ml-auto flex items-center gap-2">
                                <span className="text-xs text-muted-foreground">{formatDate(act.created_at).split(', ')[1]}</span>
                                <button
                                    onClick={() => openDialog(parseInt(act.id))}
                                    className="p-1 rounded text-muted-foreground hover:text-red-500 hover:bg-red-500/10 opacity-0 group-hover:opacity-100 transition-all"
                                    title="Delete activity"
                                >
                                    <Trash2 className="w-3 h-3" />
                                </button>
                            </span>
                        </div>
                        <div className="bg-muted/50 rounded p-2 font-mono text-xs overflow-x-auto text-muted-foreground/80">
                            {/* Simple rendering of input/output summary */}
                            {act.tool_input && (
                                <div className="mb-1">
                                    <span className="font-semibold text-foreground/80">Input:</span> {JSON.stringify(act.tool_input).slice(0, ACTIVITY_TRUNCATION_LIMIT)}{JSON.stringify(act.tool_input).length > ACTIVITY_TRUNCATION_LIMIT ? '...' : ''}
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
                            {isContentTruncated(act) && (
                                <button
                                    onClick={() => openContentDialog(
                                        `${act.tool_name} Activity`,
                                        formatActivityContent(act),
                                        act.file_path || undefined
                                    )}
                                    className="mt-2 flex items-center gap-1 text-primary hover:underline"
                                >
                                    <Maximize2 className="w-3 h-3" />
                                    View Full Activity
                                </button>
                            )}
                        </div>
                    </div>
                </div>
            ))}

            <ConfirmDialog
                open={isOpen}
                onOpenChange={setIsOpen}
                title={DELETE_CONFIRMATIONS.ACTIVITY.title}
                description={DELETE_CONFIRMATIONS.ACTIVITY.description}
                onConfirm={handleDelete}
                isLoading={deleteActivity.isPending}
            />

            {dialogContent && (
                <ContentDialog
                    open={isContentOpen}
                    onOpenChange={setContentOpen}
                    title={dialogContent.title}
                    subtitle={dialogContent.subtitle}
                    content={dialogContent.content}
                    icon={<Wrench className="h-5 w-5 text-blue-500" />}
                />
            )}
        </div>
    )
}
