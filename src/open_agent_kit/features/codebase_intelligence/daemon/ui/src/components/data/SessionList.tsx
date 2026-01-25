import { useState } from "react";
import { useSessions } from "@/hooks/use-activity";
import { useDeleteSession } from "@/hooks/use-delete";
import { Link } from "react-router-dom";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog, useConfirmDialog } from "@/components/ui/confirm-dialog";
import { formatDate } from "@/lib/utils";
import { Terminal, Activity, Calendar, ArrowRight, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { DELETE_CONFIRMATIONS, PAGINATION, DEFAULT_AGENT_NAME, SESSION_TITLE_MAX_LENGTH } from "@/lib/constants";

import type { SessionItem } from "@/hooks/use-activity";

export default function SessionList() {
    const [offset, setOffset] = useState(0);
    const [allSessions, setAllSessions] = useState<SessionItem[]>([]);
    const limit = PAGINATION.DEFAULT_LIMIT;

    const { data, isLoading, isFetching } = useSessions(limit, offset);
    const deleteSession = useDeleteSession();
    const { isOpen, setIsOpen, itemToDelete, openDialog, closeDialog } = useConfirmDialog();

    // Merge new sessions with existing ones when offset changes
    const sessions = offset === 0 ? (data?.sessions || []) : allSessions;

    const handleLoadMore = () => {
        // Save current sessions before loading more
        setAllSessions([...sessions, ...(data?.sessions || [])]);
        setOffset(prev => prev + limit);
    };

    const handleDelete = async () => {
        if (!itemToDelete) return;
        try {
            await deleteSession.mutateAsync(itemToDelete as string);
            closeDialog();
            // Reset to first page after deletion
            setOffset(0);
            setAllSessions([]);
        } catch (error) {
            console.error("Failed to delete session:", error);
        }
    };

    const handleDeleteClick = (e: React.MouseEvent, sessionId: string) => {
        e.preventDefault();
        e.stopPropagation();
        openDialog(sessionId);
    };

    if (isLoading && offset === 0) {
        return <div>Loading sessions...</div>;
    }

    const displaySessions = offset === 0 ? (data?.sessions || []) : [...allSessions.slice(0, offset), ...(data?.sessions || [])];
    const hasMore = data?.sessions.length === limit;

    return (
        <div className="space-y-4">
            {displaySessions.map((session) => {
                // Generate a session title: prefer title (LLM-generated), then first_prompt_preview, fallback to truncated ID
                const sessionTitle = session.title
                    || (session.first_prompt_preview
                        ? (session.first_prompt_preview.length > SESSION_TITLE_MAX_LENGTH
                            ? session.first_prompt_preview.slice(0, SESSION_TITLE_MAX_LENGTH) + "..."
                            : session.first_prompt_preview)
                        : `Session ${session.id.slice(0, 8)}...`);

                return (
                    <Link key={session.id} to={`/data/sessions/${session.id}`}>
                        <Card className="hover:bg-accent/5 transition-colors cursor-pointer group">
                            <CardHeader className="py-4">
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-3">
                                        <div className={cn("p-2 rounded-md", session.status === "active" ? "bg-green-500/10 text-green-500" : "bg-muted text-muted-foreground")}>
                                            <Terminal className="w-4 h-4" />
                                        </div>
                                        <div>
                                            <CardTitle className="text-base font-medium flex items-center gap-2">
                                                <span className="text-sm font-semibold text-primary/80">{session.agent || DEFAULT_AGENT_NAME}</span>
                                                <span className="text-muted-foreground font-normal">·</span>
                                                <span className="font-normal truncate max-w-[400px]">{sessionTitle}</span>
                                                <span className={cn("text-xs px-2 py-0.5 rounded-full border flex-shrink-0",
                                                    session.status === "active" ? "border-green-500/50 text-green-500" : "border-muted-foreground/30 text-muted-foreground")}>
                                                    {session.status}
                                                </span>
                                            </CardTitle>
                                            <div className="text-xs text-muted-foreground mt-1 flex items-center gap-3">
                                                <span className="flex items-center gap-1"><Calendar className="w-3 h-3" /> {formatDate(session.started_at)}</span>
                                                <span className="flex items-center gap-1"><Activity className="w-3 h-3" /> {session.activity_count} activities</span>
                                            </div>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <button
                                            onClick={(e) => handleDeleteClick(e, session.id)}
                                            className="p-2 rounded-md text-muted-foreground hover:text-red-500 hover:bg-red-500/10 opacity-0 group-hover:opacity-100 transition-all"
                                            title="Delete session"
                                        >
                                            <Trash2 className="w-4 h-4" />
                                        </button>
                                        <ArrowRight className="w-4 h-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                                    </div>
                                </div>
                            </CardHeader>
                        </Card>
                    </Link>
                );
            })}

            {displaySessions.length === 0 && (
                <div className="text-center py-12 text-muted-foreground border border-dashed rounded-lg">
                    No sessions found. Start using 'agent' to generate activity.
                </div>
            )}

            {hasMore && displaySessions.length > 0 && (
                <button
                    onClick={handleLoadMore}
                    disabled={isFetching}
                    className="w-full py-3 text-sm text-muted-foreground hover:text-foreground border border-dashed rounded-lg hover:border-muted-foreground/50 transition-colors disabled:opacity-50"
                >
                    {isFetching ? "Loading..." : "Load more sessions"}
                </button>
            )}

            <ConfirmDialog
                open={isOpen}
                onOpenChange={setIsOpen}
                title={DELETE_CONFIRMATIONS.SESSION.title}
                description={DELETE_CONFIRMATIONS.SESSION.description}
                onConfirm={handleDelete}
                isLoading={deleteSession.isPending}
            />
        </div>
    );
}
