import { useState } from "react";
import { usePlans } from "@/hooks/use-plans";
import { useDeleteMemory } from "@/hooks/use-delete";
import { Link } from "react-router-dom";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { ConfirmDialog, useConfirmDialog } from "@/components/ui/confirm-dialog";
import { ContentDialog, useContentDialog } from "@/components/ui/content-dialog";
import { formatDate } from "@/lib/utils";
import { FileText, Trash2, Maximize2, CheckCircle2, Circle, FolderGit2 } from "lucide-react";
import { fetchJson } from "@/lib/api";

import type { PlanListItem } from "@/hooks/use-plans";

const PLANS_PAGE_SIZE = 20;

/** Confirmation dialog content for plan deletion */
const DELETE_PLAN_CONFIRMATION = {
    title: "Delete Plan",
    description: "This will remove this plan from the search index. The original plan file (if any) will not be deleted. This action cannot be undone.",
};

export default function PlansList() {
    const [loadedPlans, setLoadedPlans] = useState<PlanListItem[]>([]);
    const [offset, setOffset] = useState(0);

    const { data, isLoading, isFetching, refetch } = usePlans({
        limit: PLANS_PAGE_SIZE,
        offset,
    });
    const deleteMemory = useDeleteMemory();
    const { isOpen, setIsOpen, itemToDelete, openDialog, closeDialog } = useConfirmDialog();
    const { isOpen: isContentOpen, setIsOpen: setContentOpen, dialogContent, openDialog: openContentDialog } = useContentDialog();

    const handleLoadMore = () => {
        setLoadedPlans(prev => [...prev, ...(data?.plans || [])]);
        setOffset(prev => prev + PLANS_PAGE_SIZE);
    };

    const handleDelete = async () => {
        if (!itemToDelete) return;
        try {
            // Delete from ChromaDB using the plan-{id} format
            await deleteMemory.mutateAsync(`plan-${itemToDelete}`);
            closeDialog();
            // Reset pagination after deletion
            setOffset(0);
            setLoadedPlans([]);
            refetch();
        } catch (error) {
            console.error("Failed to delete plan:", error);
        }
    };

    const handleDeleteClick = (e: React.MouseEvent, planId: number) => {
        e.preventDefault();
        e.stopPropagation();
        openDialog(planId);
    };

    const handleViewFullPlan = async (plan: PlanListItem) => {
        // Fetch full plan content from the session detail endpoint
        try {
            const sessionResponse = await fetchJson<{ prompt_batches: Array<{ id: string; plan_content: string }> }>(
                `/api/activity/sessions/${plan.session_id}`
            );
            const planBatch = sessionResponse.prompt_batches?.find(b => String(b.id) === String(plan.id));
            const fullContent = planBatch?.plan_content || plan.preview;

            openContentDialog(
                plan.title,
                fullContent,
                plan.file_path || undefined
            );
        } catch {
            // Fallback to preview if full content fetch fails
            openContentDialog(
                plan.title,
                plan.preview,
                plan.file_path || undefined
            );
        }
    };

    if (isLoading && offset === 0) return <div>Loading plans...</div>;

    // Combine loaded plans with current page
    const allPlans = offset === 0 ? (data?.plans || []) : [...loadedPlans, ...(data?.plans || [])];
    const hasMore = data?.plans && data.plans.length === PLANS_PAGE_SIZE;

    if (allPlans.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center p-8 text-center border-2 border-dashed rounded-lg border-muted-foreground/25 bg-muted/5">
                <FileText className="w-10 h-10 text-muted-foreground mb-4 opacity-50" />
                <h3 className="text-lg font-medium">No plans found</h3>
                <p className="text-sm text-muted-foreground max-w-sm mt-2 mb-4">
                    Plans are created when using plan mode in Claude Code. They capture the design and implementation approach before coding begins.
                </p>
                <Link to="/data/sessions" className="text-sm font-medium text-primary hover:underline underline-offset-4">
                    View Sessions &rarr;
                </Link>
            </div>
        );
    }

    return (
        <div className="space-y-4">
            {/* Header with count */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <FileText className="w-4 h-4" />
                    <span>Design documents from plan mode sessions</span>
                </div>
                <span className="text-xs text-muted-foreground">
                    {data?.total || allPlans.length} plans
                </span>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
                {allPlans.map((plan) => (
                    <Card key={plan.id} className="overflow-hidden group relative">
                        <CardHeader className="py-3 bg-muted/30">
                            <CardTitle className="text-sm font-medium flex items-center justify-between">
                                <span className="flex items-center gap-2">
                                    <FileText className="w-4 h-4 text-amber-500" />
                                    <span className="truncate max-w-[200px]" title={plan.title}>
                                        {plan.title}
                                    </span>
                                    {plan.plan_embedded ? (
                                        <span className="flex items-center gap-1 text-xs text-green-600" title="Indexed in search">
                                            <CheckCircle2 className="w-3 h-3" />
                                        </span>
                                    ) : (
                                        <span className="flex items-center gap-1 text-xs text-muted-foreground" title="Not indexed">
                                            <Circle className="w-3 h-3" />
                                        </span>
                                    )}
                                </span>
                                <div className="flex items-center gap-2">
                                    <span className="text-xs text-muted-foreground">{formatDate(plan.created_at)}</span>
                                    <button
                                        onClick={(e) => handleDeleteClick(e, plan.id)}
                                        className="p-1 rounded text-muted-foreground hover:text-red-500 hover:bg-red-500/10 opacity-0 group-hover:opacity-100 transition-all"
                                        title="Delete plan from index"
                                    >
                                        <Trash2 className="w-3 h-3" />
                                    </button>
                                </div>
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="p-4 text-sm space-y-3">
                            {plan.preview && (
                                <div className="whitespace-pre-wrap text-muted-foreground">
                                    {plan.preview}
                                </div>
                            )}

                            <div className="flex items-center justify-between pt-2 border-t border-border/50">
                                <div className="flex items-center gap-3">
                                    <Link
                                        to={`/data/sessions/${plan.session_id}`}
                                        className="flex items-center gap-1 text-xs text-primary hover:underline"
                                    >
                                        <FolderGit2 className="w-3 h-3" />
                                        View Session
                                    </Link>
                                    {plan.file_path && (
                                        <span className="text-xs text-muted-foreground font-mono truncate max-w-[150px]" title={plan.file_path}>
                                            {plan.file_path.split('/').pop()}
                                        </span>
                                    )}
                                </div>
                                <button
                                    onClick={() => handleViewFullPlan(plan)}
                                    className="flex items-center gap-1 text-xs text-primary hover:underline"
                                >
                                    <Maximize2 className="w-3 h-3" />
                                    View Full Plan
                                </button>
                            </div>
                        </CardContent>
                    </Card>
                ))}
            </div>

            {hasMore && (
                <button
                    onClick={handleLoadMore}
                    disabled={isFetching}
                    className="w-full py-3 text-sm text-muted-foreground hover:text-foreground border border-dashed rounded-lg hover:border-muted-foreground/50 transition-colors disabled:opacity-50"
                >
                    {isFetching ? "Loading..." : "Load more plans"}
                </button>
            )}

            <ConfirmDialog
                open={isOpen}
                onOpenChange={setIsOpen}
                title={DELETE_PLAN_CONFIRMATION.title}
                description={DELETE_PLAN_CONFIRMATION.description}
                onConfirm={handleDelete}
                isLoading={deleteMemory.isPending}
            />

            {dialogContent && (
                <ContentDialog
                    open={isContentOpen}
                    onOpenChange={setContentOpen}
                    title={dialogContent.title}
                    subtitle={dialogContent.subtitle}
                    content={dialogContent.content}
                    icon={<FileText className="h-5 w-5 text-amber-500" />}
                />
            )}
        </div>
    );
}
