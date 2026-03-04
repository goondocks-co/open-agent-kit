import * as React from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X, Copy, Check, FileText } from "lucide-react";
import { Button } from "./button";
import { Markdown } from "./markdown";

interface ContentDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    title: string;
    subtitle?: string;
    content: string;
    icon?: React.ReactNode;
    /** When true, renders content as markdown. Default: false (plain text) */
    renderMarkdown?: boolean;
}

export function ContentDialog({
    open,
    onOpenChange,
    title,
    subtitle,
    content,
    icon,
    renderMarkdown = false,
}: ContentDialogProps) {
    const [copied, setCopied] = React.useState(false);
    const copyTimerRef = React.useRef<ReturnType<typeof setTimeout>>(undefined);

    React.useEffect(() => () => clearTimeout(copyTimerRef.current), []);

    const handleCopy = async () => {
        await navigator.clipboard.writeText(content);
        setCopied(true);
        clearTimeout(copyTimerRef.current);
        copyTimerRef.current = setTimeout(() => setCopied(false), 2000);
    };

    return (
        <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
            <DialogPrimitive.Portal>
                <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=closed]:animate-out data-[state=closed]:fade-out-0" />
                <DialogPrimitive.Content className="fixed left-[50%] top-[50%] z-50 translate-x-[-50%] translate-y-[-50%] w-full max-w-4xl max-h-[85vh] rounded-lg border bg-background shadow-lg data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 flex flex-col mx-4">
                    {/* Header */}
                    <div className="flex items-center justify-between p-4 border-b">
                        <div className="flex items-center gap-3">
                            {icon || <FileText className="h-5 w-5 text-amber-500" />}
                            <div>
                                <DialogPrimitive.Title className="text-lg font-semibold">{title}</DialogPrimitive.Title>
                                {subtitle && (
                                    <DialogPrimitive.Description className="text-sm text-muted-foreground">{subtitle}</DialogPrimitive.Description>
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
                            <DialogPrimitive.Close asChild>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-8 w-8 p-0"
                                    aria-label="Close"
                                >
                                    <X className="h-4 w-4" />
                                </Button>
                            </DialogPrimitive.Close>
                        </div>
                    </div>

                    {/* Hidden description for accessibility when no subtitle */}
                    {!subtitle && (
                        <DialogPrimitive.Description className="sr-only">
                            View content for {title}
                        </DialogPrimitive.Description>
                    )}

                    {/* Content */}
                    <div className="flex-1 overflow-auto p-4">
                        {renderMarkdown ? (
                            <div className="bg-muted/30 p-4 rounded-lg">
                                <Markdown content={content || "No content available"} />
                            </div>
                        ) : (
                            <pre className="whitespace-pre-wrap font-mono text-sm bg-muted/30 p-4 rounded-lg">
                                {content || "No content available"}
                            </pre>
                        )}
                    </div>
                </DialogPrimitive.Content>
            </DialogPrimitive.Portal>
        </DialogPrimitive.Root>
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
        renderMarkdown?: boolean;
    } | null>(null);

    const openDialog = (title: string, content: string, subtitle?: string, renderMarkdown?: boolean) => {
        setDialogContent({ title, content, subtitle, renderMarkdown });
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
