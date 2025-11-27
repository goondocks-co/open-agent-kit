/**
 * Statistics card for dashboard displays.
 */

import { cn } from "@/lib/utils";

interface StatCardProps {
    /** Card title */
    title: string;
    /** Main value to display */
    value: string | number;
    /** Icon component to display */
    icon: React.ComponentType<{ className?: string }>;
    /** Optional subtext below the value */
    subtext?: string;
    /** Whether data is loading */
    loading?: boolean;
    /** Optional link URL - makes the card clickable */
    href?: string;
}

/**
 * Statistics card for dashboard displays.
 * Shows a title, icon, main value, and optional subtext.
 * Optionally linkable when href is provided.
 */
export const StatCard = ({ title, value, icon: Icon, subtext, loading, href }: StatCardProps) => {
    const content = (
        <>
            <div className="p-6 flex flex-row items-center justify-between space-y-0 pb-2">
                <h3 className="tracking-tight text-sm font-medium">{title}</h3>
                <Icon className="h-4 w-4 text-muted-foreground" />
            </div>
            <div className="p-6 pt-0">
                <div className="text-2xl font-bold">{loading ? "..." : value}</div>
                {subtext && <p className="text-xs text-muted-foreground">{subtext}</p>}
            </div>
        </>
    );

    const baseClasses = "rounded-lg border bg-card text-card-foreground shadow-sm";
    const interactiveClasses = href ? "cursor-pointer hover:bg-accent/50 transition-colors" : "";

    if (href) {
        return (
            <a href={href} className={cn(baseClasses, interactiveClasses, "block")}>
                {content}
            </a>
        );
    }

    return <div className={baseClasses}>{content}</div>;
};
