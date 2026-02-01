import { useState } from "react";
import { Link } from "react-router-dom";
import {
    useSessionLineage,
    useSuggestedParent,
    useDismissSuggestion,
    useAcceptSuggestion,
    useSessionRelated,
    useSuggestedRelated,
    useAddRelated,
    useRemoveRelated,
    type SessionLineageItem,
    type RelatedSessionItem,
    type SuggestedRelatedItem,
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
    ChevronDown,
    Lightbulb,
    Check,
    X,
    ListPlus,
    Link2,
    Trash2,
} from "lucide-react";
import {
    SESSION_LINK_REASON_LABELS,
    SESSION_LINK_REASON_BADGE_CLASSES,
    SESSION_TITLE_MAX_LENGTH,
    SUGGESTION_CONFIDENCE_LABELS,
    SUGGESTION_CONFIDENCE_BADGE_CLASSES,
    RELATIONSHIP_CREATED_BY_LABELS,
    RELATIONSHIP_CREATED_BY_BADGE_CLASSES,
    type SessionLinkReason,
    type SuggestionConfidence,
    type RelationshipCreatedBy,
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
    const { data: relatedData } = useSessionRelated(sessionId);

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
    const hasRelated = relatedData && relatedData.related.length > 0;
    const hasLineage = hasAncestors || hasChildren;

    if (!hasLineage && !hasRelated) {
        return (
            <div className={cn("space-y-4", className)}>
                {/* Show suggestion banner for sessions without parents */}
                <SuggestedParentBanner
                    sessionId={sessionId}
                    hasParent={false}
                />
                {/* Show related sessions section with suggestions */}
                <RelatedSessionsSection sessionId={sessionId} />
                <div className="text-sm text-muted-foreground py-4 text-center">
                    <GitBranch className="h-5 w-5 mx-auto mb-2 opacity-50" />
                    No linked sessions
                </div>
            </div>
        );
    }

    return (
        <div className={cn("space-y-4", className)}>
            {/* Show suggestion banner if no parent (but might have children) */}
            {!hasAncestors && (
                <SuggestedParentBanner
                    sessionId={sessionId}
                    hasParent={false}
                />
            )}

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

            {/* Divider if ancestors exist */}
            {hasAncestors && (hasChildren || hasRelated) && (
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

            {/* Divider before related */}
            {(hasAncestors || hasChildren) && (
                <div className="border-t my-3" />
            )}

            {/* Related Sessions (many-to-many) */}
            <RelatedSessionsSection sessionId={sessionId} />
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
    const [isExpanded, setIsExpanded] = useState(false);
    const { data, isLoading, error } = useSuggestedParent(hasParent ? undefined : sessionId);
    const dismissMutation = useDismissSuggestion();
    const acceptMutation = useAcceptSuggestion();

    // Don't show if session already has a parent
    if (hasParent) return null;

    // Don't show loading state - just return null
    if (isLoading) return null;

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

    // Collapsed view - just show header with expand button
    if (!isExpanded) {
        return (
            <div className={cn("space-y-2", className)}>
                <button
                    onClick={() => setIsExpanded(true)}
                    className="flex items-center gap-2 text-xs font-medium text-muted-foreground uppercase tracking-wide hover:text-foreground transition-colors w-full text-left"
                >
                    <ChevronRight className="h-3 w-3" />
                    <Lightbulb className="h-3 w-3 text-amber-500" />
                    Suggested Parent Session
                    {confidence && confidenceLabel && confidenceClass && (
                        <span className={cn("px-2 py-0.5 text-xs rounded-full normal-case", confidenceClass)}>
                            {confidenceLabel}
                        </span>
                    )}
                </button>
            </div>
        );
    }

    // Expanded view - full details
    return (
        <div className={cn("space-y-2", className)}>
            <button
                onClick={() => setIsExpanded(false)}
                className="flex items-center gap-2 text-xs font-medium text-muted-foreground uppercase tracking-wide hover:text-foreground transition-colors w-full text-left"
            >
                <ChevronDown className="h-3 w-3" />
                <Lightbulb className="h-3 w-3 text-amber-500" />
                Suggested Parent Session
            </button>
            <div className="p-4 rounded-md border bg-amber-500/5 border-amber-500/20">
                <div className="flex items-start gap-3">
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                            <Link
                                to={`/activity/sessions/${suggestion.id}`}
                                className="text-sm font-medium text-foreground hover:underline truncate"
                            >
                                {sessionTitle}
                            </Link>
                            {confidence && confidenceLabel && confidenceClass && (
                                <span className={cn("px-2 py-0.5 text-xs rounded-full", confidenceClass)}>
                                    {confidenceLabel}
                                </span>
                            )}
                        </div>
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
                <div className="flex items-center gap-2 mt-3">
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
        </div>
    );
}


// =============================================================================
// Related Sessions Section (many-to-many semantic links)
// =============================================================================

interface RelatedSessionsSectionProps {
    sessionId: string;
    className?: string;
}

/**
 * Section showing related sessions and suggested related sessions.
 * Related sessions are many-to-many semantic links that can span any time gap.
 */
function RelatedSessionsSection({ sessionId, className }: RelatedSessionsSectionProps) {
    const { data: relatedData, isLoading: relatedLoading } = useSessionRelated(sessionId);
    const { data: suggestedData, isLoading: suggestedLoading } = useSuggestedRelated(sessionId);

    const hasRelated = relatedData && relatedData.related.length > 0;
    const hasSuggestions = suggestedData && suggestedData.suggestions.length > 0;

    if (relatedLoading) {
        return (
            <div className={cn("py-2", className)}>
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Loader2 className="h-3 w-3 animate-spin" />
                    Loading related sessions...
                </div>
            </div>
        );
    }

    return (
        <div className={cn("space-y-3", className)}>
            {/* Related Sessions */}
            <div className="space-y-2">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground uppercase tracking-wide">
                        <Link2 className="h-3 w-3" />
                        Related Sessions {hasRelated && `(${relatedData.related.length})`}
                    </div>
                </div>

                {hasRelated ? (
                    <div className="space-y-1">
                        {relatedData.related.map((related) => (
                            <RelatedSessionItem
                                key={related.relationship_id}
                                sessionId={sessionId}
                                related={related}
                            />
                        ))}
                    </div>
                ) : (
                    <div className="text-xs text-muted-foreground py-2">
                        No related sessions yet
                    </div>
                )}
            </div>

            {/* Suggested Related */}
            {(suggestedLoading || hasSuggestions) && (
                <SuggestedRelatedSection
                    sessionId={sessionId}
                    suggestions={suggestedData?.suggestions || []}
                    isLoading={suggestedLoading}
                />
            )}
        </div>
    );
}


interface RelatedSessionItemProps {
    sessionId: string;
    related: RelatedSessionItem;
}

/**
 * A single related session item with remove button.
 */
function RelatedSessionItem({ sessionId, related }: RelatedSessionItemProps) {
    const removeMutation = useRemoveRelated();

    const sessionTitle = related.title
        || (related.first_prompt_preview
            ? (related.first_prompt_preview.length > SESSION_TITLE_MAX_LENGTH
                ? related.first_prompt_preview.slice(0, SESSION_TITLE_MAX_LENGTH) + "..."
                : related.first_prompt_preview)
            : `Session ${related.id.slice(0, 8)}...`);

    const createdBy = related.created_by as RelationshipCreatedBy;
    const createdByLabel = RELATIONSHIP_CREATED_BY_LABELS[createdBy];
    const createdByClass = RELATIONSHIP_CREATED_BY_BADGE_CLASSES[createdBy];

    const handleRemove = () => {
        removeMutation.mutate({
            sessionId,
            relatedSessionId: related.id,
        });
    };

    return (
        <div className="flex items-center gap-2 p-3 rounded-md border bg-card group">
            <Link
                to={`/activity/sessions/${related.id}`}
                className="flex-1 min-w-0 hover:underline"
            >
                <div className="flex items-center gap-2">
                    <p className="font-medium text-sm truncate">{sessionTitle}</p>
                    {createdByLabel && createdByClass && (
                        <span className={cn("px-2 py-0.5 text-xs rounded-full whitespace-nowrap", createdByClass)}>
                            {createdByLabel}
                        </span>
                    )}
                    {related.similarity_score !== null && (
                        <span className="text-xs text-muted-foreground">
                            {Math.round(related.similarity_score * 100)}% similar
                        </span>
                    )}
                </div>
                <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                    <span className="flex items-center gap-1">
                        <Calendar className="w-3 h-3" />
                        {formatDate(related.started_at)}
                    </span>
                    <span className="flex items-center gap-1">
                        <Activity className="w-3 h-3" />
                        {related.prompt_batch_count} prompts
                    </span>
                </div>
            </Link>
            <Button
                size="sm"
                variant="ghost"
                onClick={handleRemove}
                disabled={removeMutation.isPending}
                className="h-7 w-7 p-0 opacity-0 group-hover:opacity-100 transition-opacity"
                title="Remove relationship"
            >
                {removeMutation.isPending ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                    <Trash2 className="h-3 w-3 text-muted-foreground hover:text-destructive" />
                )}
            </Button>
        </div>
    );
}


interface SuggestedRelatedSectionProps {
    sessionId: string;
    suggestions: SuggestedRelatedItem[];
    isLoading: boolean;
}

/**
 * Shows suggested related sessions based on semantic similarity.
 */
function SuggestedRelatedSection({
    sessionId,
    suggestions,
    isLoading,
}: SuggestedRelatedSectionProps) {
    const [isExpanded, setIsExpanded] = useState(false);
    const addMutation = useAddRelated();

    if (isLoading) {
        return null; // Don't show loading state for suggestions
    }

    if (suggestions.length === 0) {
        return null;
    }

    return (
        <div className="space-y-2">
            <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="flex items-center gap-2 text-xs font-medium text-muted-foreground uppercase tracking-wide hover:text-foreground transition-colors w-full text-left"
            >
                {isExpanded ? (
                    <ChevronDown className="h-3 w-3" />
                ) : (
                    <ChevronRight className="h-3 w-3" />
                )}
                <Lightbulb className="h-3 w-3 text-amber-500" />
                Suggested Related ({suggestions.length})
            </button>
            {isExpanded && (
                <div className="space-y-1">
                    {suggestions.map((suggestion) => (
                        <SuggestedRelatedItem
                            key={suggestion.id}
                            sessionId={sessionId}
                            suggestion={suggestion}
                            onAdd={() => {
                                addMutation.mutate({
                                    sessionId,
                                    relatedSessionId: suggestion.id,
                                    similarityScore: suggestion.confidence_score,
                                });
                            }}
                            isAdding={addMutation.isPending}
                        />
                    ))}
                </div>
            )}
        </div>
    );
}


interface SuggestedRelatedItemProps {
    sessionId: string;
    suggestion: SuggestedRelatedItem;
    onAdd: () => void;
    isAdding: boolean;
}

/**
 * A single suggested related session with accept button.
 */
function SuggestedRelatedItem({
    suggestion,
    onAdd,
    isAdding,
}: SuggestedRelatedItemProps) {
    const sessionTitle = suggestion.title
        || (suggestion.first_prompt_preview
            ? (suggestion.first_prompt_preview.length > SESSION_TITLE_MAX_LENGTH
                ? suggestion.first_prompt_preview.slice(0, SESSION_TITLE_MAX_LENGTH) + "..."
                : suggestion.first_prompt_preview)
            : `Session ${suggestion.id.slice(0, 8)}...`);

    const confidence = suggestion.confidence as SuggestionConfidence;
    const confidenceLabel = SUGGESTION_CONFIDENCE_LABELS[confidence];
    const confidenceClass = SUGGESTION_CONFIDENCE_BADGE_CLASSES[confidence];

    return (
        <div className="flex items-center gap-2 p-3 rounded-md border bg-amber-500/5 border-amber-500/20">
            <Link
                to={`/activity/sessions/${suggestion.id}`}
                className="flex-1 min-w-0 hover:underline"
            >
                <div className="flex items-center gap-2">
                    <p className="font-medium text-sm truncate">{sessionTitle}</p>
                    {confidenceLabel && confidenceClass && (
                        <span className={cn("px-2 py-0.5 text-xs rounded-full whitespace-nowrap", confidenceClass)}>
                            {confidenceLabel}
                        </span>
                    )}
                </div>
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
                {suggestion.reason && (
                    <p className="text-xs text-muted-foreground mt-1">{suggestion.reason}</p>
                )}
            </Link>
            <Button
                size="sm"
                variant="outline"
                onClick={onAdd}
                disabled={isAdding}
                className="h-7 text-xs"
            >
                {isAdding ? (
                    <Loader2 className="h-3 w-3 animate-spin mr-1" />
                ) : (
                    <Check className="h-3 w-3 mr-1" />
                )}
                Link
            </Button>
        </div>
    );
}
