import * as React from "react";
import { AlertTriangle, Loader2 } from "lucide-react";
import { Button } from "./button";
import { cn } from "@/lib/utils";

interface ConfirmDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    title: string;
    description: string;
    confirmLabel?: string;
    cancelLabel?: string;
    onConfirm: () => void | Promise<void>;
    isLoading?: boolean;
    variant?: "destructive" | "default";
    /** If set, user must type this exact text (case-sensitive) to enable the confirm button */
    requireConfirmText?: string;
    /** Custom loading label (default: "Deleting...") */
    loadingLabel?: string;
}

export function ConfirmDialog({
    open,
    onOpenChange,
    title,
    description,
    confirmLabel = "Delete",
    cancelLabel = "Cancel",
    onConfirm,
    isLoading = false,
    variant = "destructive",
    requireConfirmText,
    loadingLabel = "Deleting...",
}: ConfirmDialogProps) {
    const [confirmInput, setConfirmInput] = React.useState("");

    // Reset input when dialog opens/closes
    React.useEffect(() => {
        if (!open) {
            setConfirmInput("");
        }
    }, [open]);

    const handleConfirm = async () => {
        await onConfirm();
    };

    const isConfirmDisabled = isLoading || (requireConfirmText !== undefined && confirmInput !== requireConfirmText);

    if (!open) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
            {/* Backdrop */}
            <div
                className="fixed inset-0 bg-black/50 backdrop-blur-sm"
                onClick={() => !isLoading && onOpenChange(false)}
            />

            {/* Dialog */}
            <div className="relative z-50 w-full max-w-md rounded-lg border bg-background p-6 shadow-lg animate-in fade-in-0 zoom-in-95">
                <div className="flex flex-col gap-4">
                    {/* Header with warning icon */}
                    <div className="flex items-start gap-4">
                        <div className={cn(
                            "rounded-full p-2",
                            variant === "destructive" ? "bg-red-500/10" : "bg-yellow-500/10"
                        )}>
                            <AlertTriangle className={cn(
                                "h-5 w-5",
                                variant === "destructive" ? "text-red-500" : "text-yellow-500"
                            )} />
                        </div>
                        <div className="flex-1">
                            <h2 className="text-lg font-semibold">{title}</h2>
                            <p className="mt-1 text-sm text-muted-foreground">
                                {description}
                            </p>
                        </div>
                    </div>

                    {/* Confirmation text input (optional) */}
                    {requireConfirmText && (
                        <div className="space-y-2">
                            <label className="text-sm text-muted-foreground">
                                Type <code className="px-1.5 py-0.5 rounded bg-muted font-mono text-foreground">{requireConfirmText}</code> to confirm:
                            </label>
                            <input
                                type="text"
                                value={confirmInput}
                                onChange={(e) => setConfirmInput(e.target.value)}
                                placeholder={requireConfirmText}
                                className={cn(
                                    "w-full px-3 py-2 rounded-md border bg-background text-sm",
                                    "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
                                    confirmInput === requireConfirmText
                                        ? "border-green-500 focus:ring-green-500"
                                        : "border-input"
                                )}
                                autoFocus
                                disabled={isLoading}
                            />
                        </div>
                    )}

                    {/* Actions */}
                    <div className="flex justify-end gap-3">
                        <Button
                            variant="outline"
                            onClick={() => onOpenChange(false)}
                            disabled={isLoading}
                        >
                            {cancelLabel}
                        </Button>
                        <Button
                            variant={variant}
                            onClick={handleConfirm}
                            disabled={isConfirmDisabled}
                        >
                            {isLoading ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    {loadingLabel}
                                </>
                            ) : (
                                confirmLabel
                            )}
                        </Button>
                    </div>
                </div>
            </div>
        </div>
    );
}

/**
 * Hook to manage confirm dialog state.
 */
// eslint-disable-next-line react-refresh/only-export-components
export function useConfirmDialog() {
    const [isOpen, setIsOpen] = React.useState(false);
    const [itemToDelete, setItemToDelete] = React.useState<string | number | null>(null);

    const openDialog = (itemId: string | number) => {
        setItemToDelete(itemId);
        setIsOpen(true);
    };

    const closeDialog = () => {
        setIsOpen(false);
        setItemToDelete(null);
    };

    return {
        isOpen,
        setIsOpen,
        itemToDelete,
        openDialog,
        closeDialog,
    };
}
