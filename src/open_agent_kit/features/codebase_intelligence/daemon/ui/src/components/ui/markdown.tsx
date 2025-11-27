import ReactMarkdown from "react-markdown";
import { cn } from "@/lib/utils";

interface MarkdownProps {
    content: string;
    className?: string;
}

/**
 * Renders markdown content with consistent styling.
 * Uses react-markdown for parsing and rendering.
 */
export function Markdown({ content, className }: MarkdownProps) {
    return (
        <div
            className={cn(
                "prose prose-sm dark:prose-invert max-w-none",
                // Headings
                "prose-headings:font-semibold prose-headings:text-foreground",
                // Paragraphs
                "prose-p:text-muted-foreground prose-p:leading-relaxed",
                // Lists
                "prose-ul:text-muted-foreground prose-ol:text-muted-foreground",
                "prose-li:marker:text-muted-foreground",
                // Links
                "prose-a:text-blue-500 prose-a:no-underline hover:prose-a:underline",
                // Code
                "prose-code:text-foreground prose-code:bg-muted prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-xs",
                "prose-pre:bg-muted prose-pre:text-foreground",
                // Strong/bold
                "prose-strong:text-foreground prose-strong:font-semibold",
                className
            )}
        >
            <ReactMarkdown>{content}</ReactMarkdown>
        </div>
    );
}
