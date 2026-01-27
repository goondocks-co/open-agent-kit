import { useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { useSession } from "@/hooks/use-activity";
import { useDeleteSession, useDeletePromptBatch, usePromoteBatch } from "@/hooks/use-delete";
import { useLinkSession, useUnlinkSession, useRegenerateSummary } from "@/hooks/use-session-link";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { PromptBatchActivities } from "@/components/data/PromptBatchActivities";
import { SessionLineage, SessionLineageBadge } from "@/components/data/SessionLineage";
import { ConfirmDialog, useConfirmDialog } from "@/components/ui/confirm-dialog";
import { ContentDialog, useContentDialog } from "@/components/ui/content-dialog";
import { SessionPickerDialog, useSessionPickerDialog } from "@/components/ui/session-picker-dialog";
import { formatDate } from "@/lib/utils";
import { ArrowLeft, Terminal, MessageSquare, Clock, ChevronDown, ChevronRight, Trash2, Bot, FileText, Settings, Eye, EyeOff, Sparkles, Loader2, Maximize2, GitBranch, Link2, Unlink, RefreshCw, FileDigit } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { DELETE_CONFIRMATIONS, type SessionLinkReason } from "@/lib/constants";

// Source type configuration for badges and icons
const SOURCE_TYPE_CONFIG: Record<string, { badge: string; label: string; icon: React.ElementType; muted?: boolean }> = {
    user: { badge: "bg-blue-500/20 text-blue-500 border-blue-500/30", label: "User", icon: MessageSquare },
    agent_notification: { badge: "bg-purple-500/20 text-purple-500 border-purple-500/30", label: "Agent", icon: Bot, muted: true },
    plan: { badge: "bg-amber-500/20 text-amber-500 border-amber-500/30", label: "Plan", icon: FileText },
    system: { badge: "bg-gray-500/20 text-gray-500 border-gray-500/30", label: "System", icon: Settings, muted: true },
};

// Maximum characters to show before truncating
const PROMPT_TRUNCATE_LENGTH = 500;

/**
 * Truncate text and indicate if it was truncated
 */
function truncateText(text: string | null | undefined, maxLength: number): { text: string; truncated: boolean } {
    if (!text) return { text: "No prompt text provided", truncated: false };
    if (text.length <= maxLength) return { text, truncated: false };
    return { text: text.slice(0, maxLength) + "...", truncated: true };
}

export default function SessionDetail() {
    const { id } = useParams();
    const navigate = useNavigate();
    const { data, isLoading } = useSession(id);
    const [expandedBatches, setExpandedBatches] = useState<Record<string, boolean>>({});
    const [showAgentBatches, setShowAgentBatches] = useState(true);

    const deleteSession = useDeleteSession();
    const deletePromptBatch = useDeletePromptBatch();
    const promoteBatch = usePromoteBatch();
    const linkSession = useLinkSession();
    const unlinkSession = useUnlinkSession();
    const regenerateSummary = useRegenerateSummary();

    // Track which batch is being promoted (for loading state)
    const [promotingBatchId, setPromotingBatchId] = useState<string | null>(null);
    // Track summary regeneration message
    const [summaryMessage, setSummaryMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
    // Track if lineage card is expanded (collapsed by default when no links)
    const [lineageExpanded, setLineageExpanded] = useState(false);

    // Session delete dialog
    const sessionDialog = useConfirmDialog();
    // Batch delete dialog
    const batchDialog = useConfirmDialog();
    // Content viewer dialog (for plans and full prompts)
    const contentDialog = useContentDialog();
    // Session picker dialog for linking
    const sessionPickerDialog = useSessionPickerDialog();
    // Unlink confirmation dialog
    const unlinkDialog = useConfirmDialog();

    const toggleBatch = (batchId: string) => {
        setExpandedBatches(prev => ({ ...prev, [batchId]: !prev[batchId] }));
    };

    const handleDeleteSession = async () => {
        if (!id) return;
        try {
            await deleteSession.mutateAsync(id);
            sessionDialog.closeDialog();
            navigate("/data/sessions");
        } catch (error) {
            console.error("Failed to delete session:", error);
        }
    };

    const handleDeleteBatch = async () => {
        if (!batchDialog.itemToDelete || !id) return;
        try {
            await deletePromptBatch.mutateAsync({
                batchId: batchDialog.itemToDelete as number,
                sessionId: id,
            });
            batchDialog.closeDialog();
        } catch (error) {
            console.error("Failed to delete batch:", error);
        }
    };

    const handlePromoteBatch = async (batchId: string) => {
        if (!id) return;
        setPromotingBatchId(batchId);
        try {
            await promoteBatch.mutateAsync({
                batchId: parseInt(batchId),
                sessionId: id,
            });
        } catch (error) {
            console.error("Failed to promote batch:", error);
        } finally {
            setPromotingBatchId(null);
        }
    };

    const handleViewPlan = (batch: { plan_content: string | null; plan_file_path: string | null; prompt_number: number }) => {
        const fileName = batch.plan_file_path?.split('/').pop() || `Plan #${batch.prompt_number}`;
        const content = batch.plan_content || "Plan content not available. The plan may have been created before content storage was enabled.";
        contentDialog.openDialog(fileName, content, batch.plan_file_path || undefined);
    };

    const handleViewFullPrompt = (batch: { user_prompt: string | null; prompt_number: number; source_type: string }) => {
        const config = SOURCE_TYPE_CONFIG[batch.source_type] || SOURCE_TYPE_CONFIG.user;
        contentDialog.openDialog(
            `Prompt #${batch.prompt_number}`,
            batch.user_prompt || "No prompt text provided",
            `${config.label} prompt`
        );
    };

    const handleLinkSession = async (parentSessionId: string, reason: SessionLinkReason) => {
        if (!id) return;
        try {
            await linkSession.mutateAsync({
                sessionId: id,
                parentSessionId,
                reason,
            });
            sessionPickerDialog.closeDialog();
        } catch (error) {
            console.error("Failed to link session:", error);
        }
    };

    const handleUnlinkSession = async () => {
        if (!id) return;
        try {
            await unlinkSession.mutateAsync(id);
            unlinkDialog.closeDialog();
        } catch (error) {
            console.error("Failed to unlink session:", error);
        }
    };

    const handleRegenerateSummary = async () => {
        if (!id) return;
        setSummaryMessage(null);
        try {
            const result = await regenerateSummary.mutateAsync(id);
            if (result.success) {
                setSummaryMessage({ type: "success", text: result.message });
            } else {
                setSummaryMessage({ type: "error", text: result.message });
            }
            // Clear message after 5 seconds
            setTimeout(() => setSummaryMessage(null), 5000);
        } catch (error) {
            setSummaryMessage({
                type: "error",
                text: error instanceof Error ? error.message : "Failed to regenerate summary",
            });
            setTimeout(() => setSummaryMessage(null), 5000);
        }
    };

    if (isLoading) return <div>Loading session details...</div>;
    if (!data) return <div>Session not found</div>;

    const { session, prompt_batches } = data;

    // Generate session title with fallback chain: title → first_prompt_preview → partial ID
    const sessionTitle = session.title
        || session.first_prompt_preview
        || `Session ${session.id.slice(0, 8)}`;

    // Filter batches based on toggle
    const filteredBatches = showAgentBatches
        ? prompt_batches
        : prompt_batches.filter(batch => {
            const sourceType = batch.source_type || "user";
            return sourceType === "user" || sourceType === "plan";
        });

    // Count agent batches for the toggle label
    const agentBatchCount = prompt_batches.filter(
        batch => batch.source_type === "agent_notification" || batch.source_type === "system"
    ).length;

    // Get plan batches for the Plans section
    const planBatches = prompt_batches.filter(batch => batch.source_type === "plan");

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <Link to="/data/sessions" className="p-2 hover:bg-accent rounded-full">
                        <ArrowLeft className="w-5 h-5" />
                    </Link>
                    <h1 className="text-2xl font-bold tracking-tight">{sessionTitle}</h1>
                </div>
                <Button
                    variant="outline"
                    size="sm"
                    className="text-red-500 hover:text-red-600 hover:bg-red-500/10 border-red-500/30"
                    onClick={() => sessionDialog.openDialog(session.id)}
                >
                    <Trash2 className="w-4 h-4 mr-2" />
                    Delete Session
                </Button>
            </div>

            <div className="grid gap-4 md:grid-cols-4">
                <Card>
                    <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Status</CardTitle></CardHeader>
                    <CardContent>
                        <div className="flex items-center gap-2">
                            <span className={cn("w-2 h-2 rounded-full", session.status === "active" ? "bg-green-500" : "bg-muted-foreground")} />
                            <span className="capitalize font-medium">{session.status}</span>
                        </div>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Started</CardTitle></CardHeader>
                    <CardContent className="text-sm">{formatDate(session.started_at)}</CardContent>
                </Card>
                <Card>
                    <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Prompts</CardTitle></CardHeader>
                    <CardContent className="text-2xl font-bold">{session.prompt_batch_count}</CardContent>
                </Card>
                <Card>
                    <CardHeader className="pb-2"><CardTitle className="text-sm font-medium">Activities</CardTitle></CardHeader>
                    <CardContent className="text-2xl font-bold">{session.activity_count}</CardContent>
                </Card>
            </div>

            {/* Session Lineage Card - collapsible when no linked sessions */}
            {(() => {
                const hasLineage = !!(session.parent_session_id || session.child_session_count > 0);
                const isExpanded = hasLineage || lineageExpanded;

                return (
                    <Card>
                        <CardHeader className={cn("pb-3", !isExpanded && "pb-3")}>
                            <div className="flex items-center justify-between">
                                <button
                                    className="flex items-center gap-2 text-lg font-semibold hover:text-foreground/80 transition-colors"
                                    onClick={() => !hasLineage && setLineageExpanded(!lineageExpanded)}
                                    disabled={hasLineage}
                                >
                                    <GitBranch className="w-5 h-5 text-blue-500" />
                                    Session Lineage
                                    {!hasLineage && (
                                        isExpanded
                                            ? <ChevronDown className="w-4 h-4 text-muted-foreground" />
                                            : <ChevronRight className="w-4 h-4 text-muted-foreground" />
                                    )}
                                    {!hasLineage && !isExpanded && (
                                        <span className="text-xs font-normal text-muted-foreground ml-2">No linked sessions</span>
                                    )}
                                </button>
                                <div className="flex items-center gap-2">
                                    {session.parent_session_id ? (
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            className="h-8 text-xs"
                                            onClick={() => unlinkDialog.openDialog(session.id)}
                                        >
                                            <Unlink className="w-3 h-3 mr-1" />
                                            Unlink
                                        </Button>
                                    ) : (
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            className="h-8 text-xs"
                                            onClick={() => sessionPickerDialog.openDialog()}
                                        >
                                            <Link2 className="w-3 h-3 mr-1" />
                                            Link to Parent
                                        </Button>
                                    )}
                                </div>
                            </div>
                            {/* Show current lineage badge inline */}
                            {hasLineage && (
                                <div className="mt-2">
                                    <SessionLineageBadge
                                        parentSessionId={session.parent_session_id}
                                        parentSessionReason={session.parent_session_reason}
                                        childCount={session.child_session_count}
                                    />
                                </div>
                            )}
                        </CardHeader>
                        {isExpanded && (
                            <CardContent>
                                <SessionLineage sessionId={session.id} />
                            </CardContent>
                        )}
                    </Card>
                );
            })()}

            {/* Session Summary Card */}
            <Card>
                <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                        <CardTitle className="flex items-center gap-2 text-lg">
                            <FileDigit className="w-5 h-5 text-green-500" />
                            Session Summary
                        </CardTitle>
                        <Button
                            variant="outline"
                            size="sm"
                            className="h-8 text-xs"
                            onClick={handleRegenerateSummary}
                            disabled={regenerateSummary.isPending}
                        >
                            {regenerateSummary.isPending ? (
                                <>
                                    <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                                    Generating...
                                </>
                            ) : (
                                <>
                                    <RefreshCw className="w-3 h-3 mr-1" />
                                    Regenerate Summary
                                </>
                            )}
                        </Button>
                    </div>
                </CardHeader>
                <CardContent>
                    {summaryMessage && (
                        <div className={cn(
                            "mb-3 p-3 rounded-md text-sm",
                            summaryMessage.type === "success"
                                ? "bg-green-500/10 text-green-600"
                                : "bg-red-500/10 text-red-600"
                        )}>
                            {summaryMessage.text}
                        </div>
                    )}
                    {session.summary ? (
                        <div className="p-4 rounded-lg bg-muted/30 text-sm whitespace-pre-wrap">
                            {session.summary}
                        </div>
                    ) : (
                        <div className="text-sm text-muted-foreground text-center py-4">
                            No summary generated yet. Click "Regenerate Summary" to create one.
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Plans Section */}
            {planBatches.length > 0 && (
                <Card>
                    <CardHeader className="pb-3">
                        <CardTitle className="flex items-center gap-2 text-lg">
                            <FileText className="w-5 h-5 text-amber-500" />
                            Plans ({planBatches.length})
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        {planBatches.map(batch => {
                            const fileName = batch.plan_file_path?.split('/').pop() || `Plan #${batch.prompt_number}`;
                            const hasContent = !!batch.plan_content;
                            return (
                                <div key={batch.id} className="flex items-center justify-between p-3 rounded-lg border bg-amber-500/5 border-amber-500/20">
                                    <div className="flex items-center gap-3">
                                        <FileText className="w-4 h-4 text-amber-500" />
                                        <div>
                                            <p className="font-medium text-sm">{fileName}</p>
                                            {batch.plan_file_path && (
                                                <p className="text-xs text-muted-foreground truncate max-w-md" title={batch.plan_file_path}>
                                                    {batch.plan_file_path}
                                                </p>
                                            )}
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <span className="text-xs text-muted-foreground">{formatDate(batch.started_at)}</span>
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            className="h-7 text-xs border-amber-500/30 text-amber-600 hover:bg-amber-500/10"
                                            onClick={() => handleViewPlan(batch)}
                                            title={hasContent ? "View plan content" : "Plan content not available"}
                                        >
                                            <FileText className="w-3 h-3 mr-1" />
                                            View Plan
                                        </Button>
                                    </div>
                                </div>
                            );
                        })}
                    </CardContent>
                </Card>
            )}

            <div className="space-y-6">
                <div className="flex items-center justify-between">
                    <h2 className="text-xl font-semibold">Timeline</h2>
                    {agentBatchCount > 0 && (
                        <Button
                            variant="outline"
                            size="sm"
                            className="h-8 gap-2 text-xs"
                            onClick={() => setShowAgentBatches(!showAgentBatches)}
                        >
                            {showAgentBatches ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
                            {showAgentBatches ? "Hide" : "Show"} agent work ({agentBatchCount})
                        </Button>
                    )}
                </div>
                <div className="relative border-l ml-4 space-y-8 pl-8 pb-8">
                    {filteredBatches.map((batch) => {
                        const sourceType = batch.source_type || "user";
                        const config = SOURCE_TYPE_CONFIG[sourceType] || SOURCE_TYPE_CONFIG.user;
                        const IconComponent = config.icon;
                        const { text: displayText, truncated } = truncateText(batch.user_prompt, PROMPT_TRUNCATE_LENGTH);

                        return (
                            <div key={batch.id} className={cn("relative", config.muted && "opacity-70")}>
                                <span className={cn("absolute -left-[41px] bg-background p-1 border rounded-full", config.badge)}>
                                    <IconComponent className="w-4 h-4" />
                                </span>
                                <div className="mb-2">
                                    <div className="flex items-center gap-2 mb-1">
                                        <p className="font-medium text-sm text-muted-foreground">Prompt #{batch.prompt_number}</p>
                                        <span className={cn("px-2 py-0.5 text-xs rounded-full border flex items-center gap-1", config.badge)}>
                                            {config.label}
                                        </span>
                                        {batch.classification && (
                                            <span className="px-2 py-0.5 text-xs rounded-full bg-muted text-muted-foreground">
                                                {batch.classification}
                                            </span>
                                        )}
                                    </div>
                                    <div className={cn(
                                        "p-4 rounded-lg border text-sm whitespace-pre-wrap",
                                        config.muted ? "bg-muted/20" : "bg-muted/30"
                                    )}>
                                        {displayText}
                                        {truncated && (
                                            <Button
                                                variant="link"
                                                size="sm"
                                                className="h-auto p-0 ml-1 text-xs text-blue-500 hover:text-blue-600"
                                                onClick={() => handleViewFullPrompt(batch)}
                                            >
                                                <Maximize2 className="w-3 h-3 mr-1" />
                                                View full prompt
                                            </Button>
                                        )}
                                    </div>
                                </div>

                                <div className="text-xs text-muted-foreground flex items-center gap-4 mt-2 flex-wrap">
                                    <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> {formatDate(batch.started_at)}</span>
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        className="h-6 gap-1 text-xs"
                                        onClick={() => toggleBatch(batch.id)}
                                    >
                                        {expandedBatches[batch.id] ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                                        <Terminal className="w-3 h-3" /> {batch.activity_count > 0 ? `${batch.activity_count} activities` : "View activities"}
                                    </Button>
                                    {/* Promote button for agent batches */}
                                    {(sourceType === "agent_notification" || sourceType === "system") && (
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            className="h-6 gap-1 text-xs text-purple-500 hover:text-purple-600 hover:bg-purple-500/10"
                                            onClick={() => handlePromoteBatch(batch.id)}
                                            disabled={promotingBatchId === batch.id}
                                            title="Extract memories from this batch using LLM"
                                        >
                                            {promotingBatchId === batch.id ? (
                                                <Loader2 className="w-3 h-3 animate-spin" />
                                            ) : (
                                                <Sparkles className="w-3 h-3" />
                                            )}
                                            {promotingBatchId === batch.id ? "Promoting..." : "Promote"}
                                        </Button>
                                    )}
                                    {/* View Plan button for plan batches */}
                                    {sourceType === "plan" && (batch.plan_content || batch.plan_file_path) && (
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            className="h-6 gap-1 text-xs text-amber-500 hover:text-amber-600 hover:bg-amber-500/10"
                                            title="View plan content"
                                            onClick={() => handleViewPlan(batch)}
                                        >
                                            <FileText className="w-3 h-3" />
                                            View Plan
                                        </Button>
                                    )}
                                    <button
                                        onClick={() => batchDialog.openDialog(parseInt(batch.id))}
                                        className="p-1 rounded text-muted-foreground hover:text-red-500 hover:bg-red-500/10 transition-colors"
                                        title="Delete batch"
                                    >
                                        <Trash2 className="w-3 h-3" />
                                    </button>
                                </div>

                                {expandedBatches[batch.id] && (
                                    <PromptBatchActivities batchId={batch.id} />
                                )}
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* Session Delete Confirmation */}
            <ConfirmDialog
                open={sessionDialog.isOpen}
                onOpenChange={sessionDialog.setIsOpen}
                title={DELETE_CONFIRMATIONS.SESSION.title}
                description={DELETE_CONFIRMATIONS.SESSION.description}
                onConfirm={handleDeleteSession}
                isLoading={deleteSession.isPending}
            />

            {/* Batch Delete Confirmation */}
            <ConfirmDialog
                open={batchDialog.isOpen}
                onOpenChange={batchDialog.setIsOpen}
                title={DELETE_CONFIRMATIONS.BATCH.title}
                description={DELETE_CONFIRMATIONS.BATCH.description}
                onConfirm={handleDeleteBatch}
                isLoading={deletePromptBatch.isPending}
            />

            {/* Content Viewer Dialog (for plans and full prompts) */}
            <ContentDialog
                open={contentDialog.isOpen}
                onOpenChange={contentDialog.setIsOpen}
                title={contentDialog.dialogContent?.title || ""}
                subtitle={contentDialog.dialogContent?.subtitle}
                content={contentDialog.dialogContent?.content || ""}
            />

            {/* Unlink Confirmation Dialog */}
            <ConfirmDialog
                open={unlinkDialog.isOpen}
                onOpenChange={unlinkDialog.setIsOpen}
                title="Unlink Session"
                description="This will remove the link to the parent session. The sessions will no longer be connected in the lineage. This action can be reversed by re-linking."
                confirmLabel="Unlink"
                onConfirm={handleUnlinkSession}
                isLoading={unlinkSession.isPending}
                variant="default"
            />

            {/* Session Picker Dialog for linking */}
            <SessionPickerDialog
                open={sessionPickerDialog.isOpen}
                onOpenChange={sessionPickerDialog.setIsOpen}
                title="Link to Parent Session"
                description="Select a session to link as the parent of this session"
                excludeSessionId={session.id}
                onSelect={handleLinkSession}
                isLoading={linkSession.isPending}
            />
        </div>
    )
}
