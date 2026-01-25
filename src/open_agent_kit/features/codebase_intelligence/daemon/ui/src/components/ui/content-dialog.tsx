import * as React from "react";
import { X, Copy, Check, FileText } from "lucide-react";
import { Button } from "./button";

interface ContentDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    title: string;
    subtitle?: string;
    content: string;
    icon?: React.ReactNode;
}

export function ContentDialog({
    open,
    onOpenChange,
    title,
    subtitle,
    content,
    icon,
}: ContentDialogProps) {
    const [copied, setCopied] = React.useState(false);

    const handleCopy = async () => {
        await navigator.clipboard.writeText(content);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    if (!open) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
            {/* Backdrop */}
            <div
                className="fixed inset-0 bg-black/50 backdrop-blur-sm"
                onClick={() => onOpenChange(false)}
            />

            {/* Dialog */}
            <div className="relative z-50 w-full max-w-4xl max-h-[85vh] rounded-lg border bg-background shadow-lg animate-in fade-in-0 zoom-in-95 flex flex-col mx-4">
                {/* Header */}
                <div className="flex items-center justify-between p-4 border-b">
                    <div className="flex items-center gap-3">
                        {icon || <FileText className="h-5 w-5 text-amber-500" />}
                        <div>
                            <h2 className="text-lg font-semibold">{title}</h2>
                            {subtitle && (
                                <p className="text-sm text-muted-foreground">{subtitle}</p>
                            )}
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={handleCopy}
                            className="h-8 gap-2"
                        >
                            {copied ? (
                                <>
                                    <Check className="h-4 w-4" />
                                    Copied
                                </>
                            ) : (
                                <>
                                    <Copy className="h-4 w-4" />
                                    Copy
                                </>
                            )}
                        </Button>
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => onOpenChange(false)}
                            className="h-8 w-8 p-0"
                        >
                            <X className="h-4 w-4" />
                        </Button>
                    </div>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-auto p-4">
                    <pre className="whitespace-pre-wrap font-mono text-sm bg-muted/30 p-4 rounded-lg">
                        {content || "No content available"}
                    </pre>
                </div>
            </div>
        </div>
    );
}

/**
 * Hook to manage content dialog state.
 */
// eslint-disable-next-line react-refresh/only-export-components
export function useContentDialog() {
    const [isOpen, setIsOpen] = React.useState(false);
    const [dialogContent, setDialogContent] = React.useState<{
        title: string;
        subtitle?: string;
        content: string;
    } | null>(null);

    const openDialog = (title: string, content: string, subtitle?: string) => {
        setDialogContent({ title, content, subtitle });
        setIsOpen(true);
    };

    const closeDialog = () => {
        setIsOpen(false);
        setDialogContent(null);
    };

    return {
        isOpen,
        setIsOpen,
        dialogContent,
        openDialog,
        closeDialog,
    };
}
