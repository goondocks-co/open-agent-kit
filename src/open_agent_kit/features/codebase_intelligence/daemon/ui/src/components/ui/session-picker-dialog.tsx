import * as React from "react";
import { useState } from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { Link2, Loader2, Search, X, Calendar, Activity } from "lucide-react";
import { Button } from "./button";
import { useSessions, type SessionItem } from "@/hooks/use-activity";
import { formatDate, getSessionTitle } from "@/lib/utils";
import { cn } from "@/lib/utils";
import {
    PAGINATION,
    SESSION_LINK_REASON_OPTIONS,
    type SessionLinkReason,
} from "@/lib/constants";

interface SessionPickerDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    title: string;
    description: string;
    excludeSessionId?: string;
    onSelect: (sessionId: string, reason?: SessionLinkReason) => void | Promise<void>;
    isLoading?: boolean;
    /** Whether to show the link reason selector. Defaults to true. */
    showReasonSelector?: boolean;
}

/**
 * Dialog to select a session from the list.
 * Used for linking sessions to parents.
 */
export function SessionPickerDialog({
    open,
    onOpenChange,
    title,
    description,
    excludeSessionId,
    onSelect,
    isLoading = false,
    showReasonSelector = true,
}: SessionPickerDialogProps) {
    const [searchQuery, setSearchQuery] = useState("");
    const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
    const [selectedReason, setSelectedReason] = useState<SessionLinkReason>("manual");
    const [isProcessing, setIsProcessing] = useState(false);

    const { data, isLoading: isLoadingSessions } = useSessions(PAGINATION.MAX_LIMIT_MEDIUM, 0);

    // Filter sessions by search query and exclude current session
    const sessions = data?.sessions ?? [];
    const filteredSessions = sessions.filter((session) => {
        // Exclude the current session
        if (excludeSessionId && session.id === excludeSessionId) return false;

        // Filter by search query
        if (searchQuery) {
            const query = searchQuery.toLowerCase();
            const title = (session.title || session.first_prompt_preview || session.id).toLowerCase();
            return title.includes(query) || session.id.toLowerCase().includes(query);
        }

        return true;
    });

    const handleSelect = async () => {
        if (!selectedSessionId || isProcessing) return;
        setIsProcessing(true);
        try {
            await onSelect(selectedSessionId, showReasonSelector ? selectedReason : undefined);
            // Reset state on success
            setSelectedSessionId(null);
            setSearchQuery("");
        } finally {
            setIsProcessing(false);
        }
    };

    // Prevent closing while loading/processing
    const handleOpenChange = (nextOpen: boolean) => {
        if (isLoading || isProcessing) return;
        if (!nextOpen) {
            setSelectedSessionId(null);
            setSearchQuery("");
        }
        onOpenChange(nextOpen);
    };

    return (
        <DialogPrimitive.Root open={open} onOpenChange={handleOpenChange}>
            <DialogPrimitive.Portal>
                <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=closed]:animate-out data-[state=closed]:fade-out-0" />
                <DialogPrimitive.Content className="fixed left-[50%] top-[50%] z-50 translate-x-[-50%] translate-y-[-50%] w-full max-w-lg rounded-lg border bg-background shadow-lg data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 max-h-[80vh] flex flex-col">
                    {/* Header */}
                    <div className="flex items-center justify-between p-4 border-b">
                        <div className="flex items-center gap-3">
                            <div className="rounded-full p-2 bg-blue-500/10">
                                <Link2 className="h-5 w-5 text-blue-500" />
                            </div>
                            <div>
                                <DialogPrimitive.Title className="text-lg font-semibold">{title}</DialogPrimitive.Title>
                                <DialogPrimitive.Description className="text-sm text-muted-foreground">{description}</DialogPrimitive.Description>
                            </div>
                        </div>
                        <DialogPrimitive.Close asChild>
                            <button
                                className="p-1 rounded hover:bg-muted"
                                disabled={isLoading}
                                aria-label="Close"
                            >
                                <X className="h-5 w-5 text-muted-foreground" />
                            </button>
                        </DialogPrimitive.Close>
                    </div>

                    {/* Search */}
                    <div className="p-4 border-b">
                        <div className="relative">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                            <input
                                type="text"
                                placeholder="Search sessions..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                className="w-full pl-9 pr-4 py-2 text-sm border rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring"
                                aria-label="Search sessions"
                            />
                        </div>
                    </div>

                    {/* Session list */}
                    <div className="flex-1 overflow-y-auto p-2 min-h-[200px] max-h-[300px]">
                        {isLoadingSessions ? (
                            <div className="flex items-center justify-center py-8">
                                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                            </div>
                        ) : filteredSessions.length === 0 ? (
                            <div className="text-center py-8 text-muted-foreground">
                                {searchQuery ? "No sessions match your search" : "No other sessions available"}
                            </div>
                        ) : (
                            <div className="space-y-1">
                                {filteredSessions.map((session) => (
                                    <SessionPickerItem
                                        key={session.id}
                                        session={session}
                                        isSelected={selectedSessionId === session.id}
                                        onClick={() => setSelectedSessionId(session.id)}
                                    />
                                ))}
                            </div>
                        )}
                    </div>

                    {/* Reason selector */}
                    {showReasonSelector && selectedSessionId && (
                        <div className="p-4 border-t bg-muted/30">
                            <label className="text-sm font-medium mb-2 block">Link reason</label>
                            <div className="flex gap-2">
                                {SESSION_LINK_REASON_OPTIONS.map((option) => (
                                    <button
                                        key={option.value}
                                        onClick={() => setSelectedReason(option.value as SessionLinkReason)}
                                        className={cn(
                                            "px-3 py-1.5 text-sm rounded-md border transition-colors",
                                            selectedReason === option.value
                                                ? "bg-primary text-primary-foreground border-primary"
                                                : "bg-background hover:bg-muted"
                                        )}
                                    >
                                        {option.label}
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Actions */}
                    <div className="flex justify-end gap-3 p-4 border-t">
                        <DialogPrimitive.Close asChild>
                            <Button
                                variant="outline"
                                disabled={isLoading}
                            >
                                Cancel
                            </Button>
                        </DialogPrimitive.Close>
                        <Button
                            onClick={handleSelect}
                            disabled={isLoading || isProcessing || !selectedSessionId}
                        >
                            {isLoading || isProcessing ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Linking...
                                </>
                            ) : (
                                <>
                                    <Link2 className="mr-2 h-4 w-4" />
                                    Link Session
                                </>
                            )}
                        </Button>
                    </div>
                </DialogPrimitive.Content>
            </DialogPrimitive.Portal>
        </DialogPrimitive.Root>
    );
}

interface SessionPickerItemProps {
    session: SessionItem;
    isSelected: boolean;
    onClick: () => void;
}

function SessionPickerItem({ session, isSelected, onClick }: SessionPickerItemProps) {
    const sessionTitle = getSessionTitle(session);

    return (
        <button
            onClick={onClick}
            className={cn(
                "w-full text-left p-3 rounded-md border transition-colors",
                isSelected
                    ? "border-primary bg-primary/5"
                    : "border-transparent hover:bg-muted"
            )}
        >
            <div className="flex items-center justify-between">
                <div className="flex-1 min-w-0">
                    <p className="font-medium text-sm truncate">{sessionTitle}</p>
                    <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1">
                            <Calendar className="w-3 h-3" />
                            {formatDate(session.started_at)}
                        </span>
                        <span className="flex items-center gap-1">
                            <Activity className="w-3 h-3" />
                            {session.activity_count} activities
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
                {isSelected && (
                    <div className="ml-2 w-4 h-4 rounded-full bg-primary flex items-center justify-center">
                        <div className="w-2 h-2 rounded-full bg-primary-foreground" />
                    </div>
                )}
            </div>
        </button>
    );
}

/**
 * Hook to manage session picker dialog state.
 */
// eslint-disable-next-line react-refresh/only-export-components
export function useSessionPickerDialog() {
    const [isOpen, setIsOpen] = React.useState(false);

    const openDialog = () => setIsOpen(true);
    const closeDialog = () => setIsOpen(false);

    return {
        isOpen,
        setIsOpen,
        openDialog,
        closeDialog,
    };
}
