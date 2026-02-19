import { useMemo, useState } from "react";
import { useSessionAgents, useSessions } from "@/hooks/use-activity";
import { useDeleteSession } from "@/hooks/use-delete";
import { usePaginatedList } from "@/hooks/use-paginated-list";
import { Link, useNavigate } from "react-router-dom";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog, useConfirmDialog } from "@/components/ui/confirm-dialog";
import { formatDate, getSessionTitle } from "@/lib/utils";
import { Terminal, Activity, Calendar, ArrowRight, Trash2, ArrowUpDown, CornerLeftUp, GitFork } from "lucide-react";
import { cn } from "@/lib/utils";
import {
    DELETE_CONFIRMATIONS,
    PAGINATION,
    DEFAULT_AGENT_NAME,
    SESSION_SORT_DROPDOWN_OPTIONS,
    DEFAULT_SESSION_SORT,
    SESSION_AGENT_FILTER,
} from "@/lib/constants";
import type { SessionSortOption } from "@/lib/constants";

import type { SessionItem } from "@/hooks/use-activity";

export default function SessionList() {
    const navigate = useNavigate();
    const { offset, loadedItems: allSessions, handleLoadMore, reset } = usePaginatedList<SessionItem>(PAGINATION.DEFAULT_LIMIT);
    const [sortBy, setSortBy] = useState<SessionSortOption>(DEFAULT_SESSION_SORT);
    const [agentFilter, setAgentFilter] = useState<string>(SESSION_AGENT_FILTER.ALL);
    const limit = PAGINATION.DEFAULT_LIMIT;
    const { data: sessionAgentsData } = useSessionAgents();
    const selectedAgent = agentFilter === SESSION_AGENT_FILTER.ALL ? undefined : agentFilter;

    const { data, isLoading, isFetching } = useSessions(limit, offset, sortBy, selectedAgent);
    const deleteSession = useDeleteSession();
    const { isOpen, setIsOpen, itemToDelete, openDialog, closeDialog } = useConfirmDialog();

    const agentOptions = useMemo(() => {
        const uniqueNames = Array.from(new Set(sessionAgentsData?.agents ?? [])).sort();
        return [SESSION_AGENT_FILTER.ALL, ...uniqueNames];
    }, [sessionAgentsData]);

    const handleSortChange = (newSort: SessionSortOption) => {
        setSortBy(newSort);
        reset();
    };

    const handleAgentFilterChange = (newAgent: string) => {
        setAgentFilter(newAgent);
        reset();
    };

    const handleDelete = async () => {
        if (!itemToDelete) return;
        try {
            await deleteSession.mutateAsync(itemToDelete as string);
            closeDialog();
            reset();
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

    const currentPageSessions = data?.sessions || [];
    const displaySessions = offset === 0 ? currentPageSessions : [...allSessions, ...currentPageSessions];
    const hasMore = currentPageSessions.length === limit;

    return (
        <div className="space-y-4">
            {/* Sort controls */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Terminal className="w-4 h-4" />
                    <span>Coding agent sessions</span>
                </div>
                <div className="flex items-center gap-2">
                    <select
                        value={agentFilter}
                        onChange={(e) => handleAgentFilterChange(e.target.value)}
                        className="text-sm bg-background border border-input rounded-md px-2 py-1 focus:outline-none focus:ring-2 focus:ring-ring"
                        aria-label="Filter sessions by agent"
                    >
                        {agentOptions.map((option) => (
                            <option key={option} value={option}>
                                {option === SESSION_AGENT_FILTER.ALL ? "All Agents" : option}
                            </option>
                        ))}
                    </select>
                    <ArrowUpDown className="w-4 h-4 text-muted-foreground" />
                    <select
                        value={sortBy}
                        onChange={(e) => handleSortChange(e.target.value as SessionSortOption)}
                        className="text-sm bg-background border border-input rounded-md px-2 py-1 focus:outline-none focus:ring-2 focus:ring-ring"
                    >
                        {SESSION_SORT_DROPDOWN_OPTIONS.map((option) => (
                            <option key={option.value} value={option.value}>
                                {option.label}
                            </option>
                        ))}
                    </select>
                </div>
            </div>

            {displaySessions.map((session) => {
                const sessionTitle = getSessionTitle(session);

                return (
                    <Link key={session.id} to={`/activity/sessions/${session.id}`}>
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
                                                <span className="font-normal truncate max-w-[600px]">{sessionTitle}</span>
                                                <span className={cn("text-xs px-2 py-0.5 rounded-full border flex-shrink-0",
                                                    session.status === "active" ? "border-green-500/50 text-green-500" : "border-muted-foreground/30 text-muted-foreground")}>
                                                    {session.status}
                                                </span>
                                            </CardTitle>
                                            <div className="text-xs text-muted-foreground mt-1 flex items-center gap-3">
                                                <span className="flex items-center gap-1"><Calendar className="w-3 h-3" /> {formatDate(session.started_at)}</span>
                                                <span className="flex items-center gap-1"><Activity className="w-3 h-3" /> {session.activity_count} activities</span>
                                                {session.parent_session_id && (
                                                    <button
                                                        onClick={(e) => {
                                                            e.preventDefault();
                                                            e.stopPropagation();
                                                            navigate(`/activity/sessions/${session.parent_session_id}`);
                                                        }}
                                                        className="flex items-center gap-1 text-blue-500 hover:text-blue-400 hover:bg-blue-500/10 rounded px-1.5 py-0.5 -mx-1.5 -my-0.5 transition-colors"
                                                        title="Go to parent session"
                                                    >
                                                        <CornerLeftUp className="w-3 h-3" /> parent
                                                    </button>
                                                )}
                                                {session.child_session_count > 0 && (
                                                    <button
                                                        onClick={(e) => {
                                                            e.preventDefault();
                                                            e.stopPropagation();
                                                            navigate(`/activity/sessions/${session.id}`);
                                                        }}
                                                        className="flex items-center gap-1 text-violet-500 hover:text-violet-400 hover:bg-violet-500/10 rounded px-1.5 py-0.5 -mx-1.5 -my-0.5 transition-colors"
                                                        title="View child sessions"
                                                    >
                                                        <GitFork className="w-3 h-3" /> {session.child_session_count} {session.child_session_count === 1 ? "child" : "children"}
                                                    </button>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <button
                                            onClick={(e) => handleDeleteClick(e, session.id)}
                                            className="p-2 rounded-md text-muted-foreground hover:text-red-500 hover:bg-red-500/10 opacity-0 group-hover:opacity-100 transition-all"
                                            title="Delete session"
                                            aria-label="Delete session"
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
                    onClick={() => handleLoadMore(currentPageSessions)}
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
