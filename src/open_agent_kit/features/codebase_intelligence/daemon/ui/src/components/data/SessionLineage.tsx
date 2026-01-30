import { Link } from "react-router-dom";
import {
    useSessionLineage,
    useSuggestedParent,
    useDismissSuggestion,
    useAcceptSuggestion,
    type SessionLineageItem,
} from "@/hooks/use-session-link";
import { formatDate } from "@/lib/utils";
import { cn } from "@/lib/utils";
import {
    ArrowUp,
    ArrowDown,
    GitBranch,
    Calendar,
    Activity,
    Loader2,
    ChevronRight,
    Lightbulb,
    Check,
    X,
    ListPlus,
} from "lucide-react";
import {
    SESSION_LINK_REASON_LABELS,
    SESSION_LINK_REASON_BADGE_CLASSES,
    SESSION_TITLE_MAX_LENGTH,
    SUGGESTION_CONFIDENCE_LABELS,
    SUGGESTION_CONFIDENCE_BADGE_CLASSES,
    type SessionLinkReason,
    type SuggestionConfidence,
} from "@/lib/constants";
import { Button } from "@/components/ui/button";

interface SessionLineageProps {
    sessionId: string;
    className?: string;
}

/**
 * Displays the lineage (ancestors and children) of a session.
 * Shows a visual chain of related sessions.
 */
export function SessionLineage({ sessionId, className }: SessionLineageProps) {
    const { data, isLoading, error } = useSessionLineage(sessionId);

    if (isLoading) {
        return (
            <div className={cn("flex items-center justify-center py-4", className)}>
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
        );
    }

    if (error) {
        return (
            <div className={cn("text-sm text-muted-foreground py-4", className)}>
                Failed to load lineage
            </div>
        );
    }

    if (!data) return null;

    const hasAncestors = data.ancestors.length > 0;
    const hasChildren = data.children.length > 0;
    const hasLineage = hasAncestors || hasChildren;

    if (!hasLineage) {
        return (
            <div className={cn("text-sm text-muted-foreground py-4 text-center", className)}>
                <GitBranch className="h-5 w-5 mx-auto mb-2 opacity-50" />
                No linked sessions
            </div>
        );
    }

    return (
        <div className={cn("space-y-4", className)}>
            {/* Ancestors (parent chain) */}
            {hasAncestors && (
                <div className="space-y-2">
                    <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground uppercase tracking-wide">
                        <ArrowUp className="h-3 w-3" />
                        Parent Sessions ({data.ancestors.length})
                    </div>
                    <div className="space-y-1">
                        {data.ancestors.map((ancestor, index) => (
                            <LineageItem
                                key={ancestor.id}
                                session={ancestor}
                                direction="ancestor"
                                depth={index}
                            />
                        ))}
                    </div>
                </div>
            )}

            {/* Divider if both exist */}
            {hasAncestors && hasChildren && (
                <div className="border-t my-3" />
            )}

            {/* Children */}
            {hasChildren && (
                <div className="space-y-2">
                    <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground uppercase tracking-wide">
                        <ArrowDown className="h-3 w-3" />
                        Child Sessions ({data.children.length})
                    </div>
                    <div className="space-y-1">
                        {data.children.map((child) => (
                            <LineageItem
                                key={child.id}
                                session={child}
                                direction="child"
                            />
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}

interface LineageItemProps {
    session: SessionLineageItem;
    direction: "ancestor" | "child";
    depth?: number;
}

function LineageItem({ session, direction, depth = 0 }: LineageItemProps) {
    const sessionTitle = session.title
        || (session.first_prompt_preview
            ? (session.first_prompt_preview.length > SESSION_TITLE_MAX_LENGTH
                ? session.first_prompt_preview.slice(0, SESSION_TITLE_MAX_LENGTH) + "..."
                : session.first_prompt_preview)
            : `Session ${session.id.slice(0, 8)}...`);

    const reason = session.parent_session_reason as SessionLinkReason | null;
    const reasonLabel = reason ? SESSION_LINK_REASON_LABELS[reason] : null;
    const reasonClass = reason ? SESSION_LINK_REASON_BADGE_CLASSES[reason] : null;

    return (
        <Link
            to={`/activity/sessions/${session.id}`}
            className={cn(
                "block p-3 rounded-md border bg-card hover:bg-accent/5 transition-colors group",
                direction === "ancestor" && depth > 0 && "ml-4 border-l-2 border-l-blue-500/30"
            )}
        >
            <div className="flex items-center justify-between">
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                        <p className="font-medium text-sm truncate">{sessionTitle}</p>
                        {reason && reasonLabel && reasonClass && (
                            <span className={cn("px-2 py-0.5 text-xs rounded-full", reasonClass)}>
                                {reasonLabel}
                            </span>
                        )}
                    </div>
                    <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1">
                            <Calendar className="w-3 h-3" />
                            {formatDate(session.started_at)}
                        </span>
                        <span className="flex items-center gap-1">
                            <Activity className="w-3 h-3" />
                            {session.prompt_batch_count} prompts
                        </span>
                        <span className={cn(
                            "px-1.5 py-0.5 rounded text-xs",
                            session.status === "active"
                                ? "bg-green-500/10 text-green-600"
                                : "bg-muted text-muted-foreground"
                        )}>
                            {session.status}
                        </span>
                    </div>
                </div>
                <ChevronRight className="h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
            </div>
        </Link>
    );
}

/**
 * Compact version of lineage display for inline use.
 * Shows just parent info if present.
 */
interface SessionLineageBadgeProps {
    parentSessionId: string | null;
    parentSessionReason: string | null;
    childCount: number;
}

export function SessionLineageBadge({
    parentSessionId,
    parentSessionReason,
    childCount,
}: SessionLineageBadgeProps) {
    if (!parentSessionId && childCount === 0) return null;

    const reason = parentSessionReason as SessionLinkReason | null;
    const reasonLabel = reason ? SESSION_LINK_REASON_LABELS[reason] : "Linked";

    return (
        <div className="flex items-center gap-2 text-xs">
            {parentSessionId && (
                <Link
                    to={`/activity/sessions/${parentSessionId}`}
                    className="flex items-center gap-1 px-2 py-1 rounded bg-blue-500/10 text-blue-600 hover:bg-blue-500/20 transition-colors"
                    title={`Parent: ${parentSessionId}`}
                >
                    <ArrowUp className="w-3 h-3" />
                    {reasonLabel}
                </Link>
            )}
            {childCount > 0 && (
                <span className="flex items-center gap-1 px-2 py-1 rounded bg-purple-500/10 text-purple-600">
                    <ArrowDown className="w-3 h-3" />
                    {childCount} child{childCount !== 1 ? "ren" : ""}
                </span>
            )}
        </div>
    );
}

// =============================================================================
// Suggested Parent Banner
// =============================================================================

interface SuggestedParentBannerProps {
    sessionId: string;
    hasParent: boolean;
    onPickDifferent?: () => void;
    className?: string;
}

/**
 * Banner showing a suggested parent session for unlinked sessions.
 * Allows users to accept, dismiss, or pick a different parent.
 */
export function SuggestedParentBanner({
    sessionId,
    hasParent,
    onPickDifferent,
    className,
}: SuggestedParentBannerProps) {
    const { data, isLoading, error } = useSuggestedParent(hasParent ? undefined : sessionId);
    const dismissMutation = useDismissSuggestion();
    const acceptMutation = useAcceptSuggestion();

    // Don't show if session already has a parent
    if (hasParent) return null;

    // Loading state
    if (isLoading) {
        return (
            <div className={cn("p-3 rounded-md border bg-muted/30", className)}>
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Checking for related sessions...
                </div>
            </div>
        );
    }

    // Error or no data
    if (error || !data) return null;

    // No suggestion available or dismissed
    if (!data.has_suggestion || data.dismissed) return null;

    const suggestion = data.suggested_parent;
    if (!suggestion) return null;

    const confidence = data.confidence as SuggestionConfidence | null;
    const confidenceLabel = confidence ? SUGGESTION_CONFIDENCE_LABELS[confidence] : null;
    const confidenceClass = confidence ? SUGGESTION_CONFIDENCE_BADGE_CLASSES[confidence] : null;

    const sessionTitle = suggestion.title
        || (suggestion.first_prompt_preview
            ? (suggestion.first_prompt_preview.length > SESSION_TITLE_MAX_LENGTH
                ? suggestion.first_prompt_preview.slice(0, SESSION_TITLE_MAX_LENGTH) + "..."
                : suggestion.first_prompt_preview)
            : `Session ${suggestion.id.slice(0, 8)}...`);

    const handleAccept = () => {
        acceptMutation.mutate({
            sessionId,
            parentSessionId: suggestion.id,
            confidenceScore: data.confidence_score ?? undefined,
        });
    };

    const handleDismiss = () => {
        dismissMutation.mutate(sessionId);
    };

    const isActing = acceptMutation.isPending || dismissMutation.isPending;

    return (
        <div className={cn(
            "p-4 rounded-md border bg-amber-500/5 border-amber-500/20",
            className
        )}>
            <div className="flex items-start gap-3">
                <Lightbulb className="h-5 w-5 text-amber-500 mt-0.5 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                        <span className="text-sm font-medium">Suggested Parent Session</span>
                        {confidence && confidenceLabel && confidenceClass && (
                            <span className={cn("px-2 py-0.5 text-xs rounded-full", confidenceClass)}>
                                {confidenceLabel}
                            </span>
                        )}
                    </div>
                    <Link
                        to={`/activity/sessions/${suggestion.id}`}
                        className="text-sm text-foreground hover:underline block truncate"
                    >
                        {sessionTitle}
                    </Link>
                    {data.reason && (
                        <p className="text-xs text-muted-foreground mt-1">
                            {data.reason}
                        </p>
                    )}
                    <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1">
                            <Calendar className="w-3 h-3" />
                            {formatDate(suggestion.started_at)}
                        </span>
                        <span className="flex items-center gap-1">
                            <Activity className="w-3 h-3" />
                            {suggestion.prompt_batch_count} prompts
                        </span>
                    </div>
                </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-2 mt-3 ml-8">
                <Button
                    size="sm"
                    variant="default"
                    onClick={handleAccept}
                    disabled={isActing}
                    className="h-7 text-xs"
                >
                    {acceptMutation.isPending ? (
                        <Loader2 className="h-3 w-3 animate-spin mr-1" />
                    ) : (
                        <Check className="h-3 w-3 mr-1" />
                    )}
                    Accept
                </Button>
                <Button
                    size="sm"
                    variant="outline"
                    onClick={handleDismiss}
                    disabled={isActing}
                    className="h-7 text-xs"
                >
                    {dismissMutation.isPending ? (
                        <Loader2 className="h-3 w-3 animate-spin mr-1" />
                    ) : (
                        <X className="h-3 w-3 mr-1" />
                    )}
                    Dismiss
                </Button>
                {onPickDifferent && (
                    <Button
                        size="sm"
                        variant="ghost"
                        onClick={onPickDifferent}
                        disabled={isActing}
                        className="h-7 text-xs"
                    >
                        <ListPlus className="h-3 w-3 mr-1" />
                        Pick Different
                    </Button>
                )}
            </div>
        </div>
    );
}
