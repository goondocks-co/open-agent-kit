import * as React from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
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

    // Prevent closing while loading
    const handleOpenChange = (nextOpen: boolean) => {
        if (isLoading) return;
        onOpenChange(nextOpen);
    };

    return (
        <DialogPrimitive.Root open={open} onOpenChange={handleOpenChange}>
            <DialogPrimitive.Portal>
                <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=closed]:animate-out data-[state=closed]:fade-out-0" />
                <DialogPrimitive.Content className="fixed left-[50%] top-[50%] z-50 translate-x-[-50%] translate-y-[-50%] w-full max-w-md rounded-lg border bg-background p-6 shadow-lg data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95">
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
                                <DialogPrimitive.Title className="text-lg font-semibold">{title}</DialogPrimitive.Title>
                                <DialogPrimitive.Description className="mt-1 text-sm text-muted-foreground">
                                    {description}
                                </DialogPrimitive.Description>
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
                            <DialogPrimitive.Close asChild>
                                <Button
                                    variant="outline"
                                    disabled={isLoading}
                                >
                                    {cancelLabel}
                                </Button>
                            </DialogPrimitive.Close>
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
                </DialogPrimitive.Content>
            </DialogPrimitive.Portal>
        </DialogPrimitive.Root>
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
