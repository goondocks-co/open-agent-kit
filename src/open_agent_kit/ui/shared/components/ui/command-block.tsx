/**
 * Shared CopyButton and CommandBlock components.
 *
 * Extracted from Help.tsx so they can be reused across Cloud pages.
 */

import { useState } from "react";
import { Button } from "./button";
import { Copy, Check, Terminal } from "lucide-react";
import { cn } from "../../lib/utils";

// =============================================================================
// Copy Button
// =============================================================================

export interface CopyButtonProps {
    text: string;
    className?: string;
}

export function CopyButton({ text, className }: CopyButtonProps) {
    const [copied, setCopied] = useState(false);

    const handleCopy = async () => {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <Button
            variant="ghost"
            size="sm"
            onClick={handleCopy}
            className={cn("h-8 w-8 p-0", className)}
        >
            {copied ? (
                <Check className="h-4 w-4 text-green-500" />
            ) : (
                <Copy className="h-4 w-4" />
            )}
        </Button>
    );
}

// =============================================================================
// Command Block
// =============================================================================

export interface CommandBlockProps {
    command: string;
    label?: string;
}

export function CommandBlock({ command, label }: CommandBlockProps) {
    const isMultiline = command.includes("\n");
    return (
        <div className="relative group">
            {label && (
                <div className="text-xs text-muted-foreground mb-1">{label}</div>
            )}
            <div className={cn(
                "flex gap-2 bg-muted rounded-md px-4 py-3 font-mono text-sm",
                isMultiline ? "items-start" : "items-center",
            )}>
                <Terminal className="h-4 w-4 text-muted-foreground flex-shrink-0 mt-0.5" />
                <pre className="flex-1 whitespace-pre-wrap overflow-x-auto">{command}</pre>
                <CopyButton text={command} className="opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
            </div>
        </div>
    );
}
