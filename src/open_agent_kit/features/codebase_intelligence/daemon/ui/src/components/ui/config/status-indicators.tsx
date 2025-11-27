/**
 * Status display components: dots, badges, ready indicators, and test results.
 */

import { CheckCircle2, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { TEST_RESULT_CLASSES } from "@/lib/constants";

// =============================================================================
// Test Result Display
// =============================================================================

interface TestResultProps {
    /** Test result object from API */
    result: {
        success: boolean;
        pending_load?: boolean;
        message?: string;
        error?: string;
        suggestion?: string;
    } | null;
    /** Optional className */
    className?: string;
}

/**
 * Displays test result with appropriate styling and messaging.
 * Handles success, pending load, and error states.
 */
export const TestResult = ({ result, className }: TestResultProps) => {
    if (!result) return null;

    const getResultType = () => {
        if (result.success && result.pending_load) return "pending_load";
        if (result.success) return "success";
        return "error";
    };

    const resultType = getResultType();
    const colorClass = TEST_RESULT_CLASSES[resultType];

    const getTitle = () => {
        switch (resultType) {
            case "pending_load":
                return "Configuration Valid";
            case "success":
                return "Connection Successful";
            default:
                return "Test Failed";
        }
    };

    return (
        <div className={cn("col-span-2 text-sm p-3 rounded flex items-start gap-2", colorClass, className)}>
            {result.success ? (
                <CheckCircle2 className="w-4 h-4 mt-0.5" />
            ) : (
                <AlertCircle className="w-4 h-4 mt-0.5" />
            )}
            <div>
                <p className="font-medium">{getTitle()}</p>
                <p>{result.success ? result.message : result.error}</p>
                {result.suggestion && <p className="mt-1 font-semibold">{result.suggestion}</p>}
            </div>
        </div>
    );
};

// =============================================================================
// Ready Badge
// =============================================================================

interface ReadyBadgeProps {
    /** Whether to show the badge */
    show: boolean;
}

/**
 * "Ready" indicator shown when configuration is valid.
 */
export const ReadyBadge = ({ show }: ReadyBadgeProps) => {
    if (!show) return null;

    return (
        <div className="flex items-center gap-2 text-green-600">
            <CheckCircle2 className="h-5 w-5" />
            <span className="text-sm font-medium">Ready</span>
        </div>
    );
};

// =============================================================================
// Status Dot
// =============================================================================

interface StatusDotProps {
    /** Status type for styling */
    status: "active" | "completed" | "error" | "ready" | "indexing";
    /** Optional additional className */
    className?: string;
}

/**
 * Small status indicator dot with color based on status.
 */
export const StatusDot = ({ status, className }: StatusDotProps) => {
    const colorClasses: Record<string, string> = {
        active: "bg-yellow-500 animate-pulse",
        completed: "bg-green-500",
        error: "bg-red-500",
        ready: "bg-green-500",
        indexing: "bg-yellow-500 animate-pulse",
    };

    return (
        <div
            className={cn(
                "w-2 h-2 rounded-full flex-shrink-0",
                colorClasses[status] || colorClasses.ready,
                className
            )}
        />
    );
};

// =============================================================================
// Status Badge
// =============================================================================

interface StatusBadgeProps {
    /** Status type for styling */
    status: "active" | "completed" | "error" | "ready" | "indexing";
    /** Text to display */
    label: string;
    /** Optional additional className */
    className?: string;
}

/**
 * Status badge with colored background.
 */
export const StatusBadge = ({ status, label, className }: StatusBadgeProps) => {
    const colorClasses: Record<string, string> = {
        active: "bg-yellow-500/10 text-yellow-600",
        completed: "bg-green-500/10 text-green-600",
        error: "bg-red-500/10 text-red-600",
        ready: "bg-green-500/10 text-green-600",
        indexing: "bg-yellow-500/10 text-yellow-600",
    };

    return (
        <span
            className={cn(
                "text-xs px-2 py-0.5 rounded-full flex-shrink-0",
                colorClasses[status] || colorClasses.ready,
                className
            )}
        >
            {label}
        </span>
    );
};
