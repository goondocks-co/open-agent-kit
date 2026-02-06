/**
 * Step badge and header for the guided configuration flow.
 */

import { cn } from "@/lib/utils";
import { STEP_BADGE_CLASSES } from "@/lib/constants";

interface StepBadgeProps {
    /** Step number to display */
    step: number;
    /** Whether this step is complete */
    isComplete: boolean;
    /** Optional additional className */
    className?: string;
}

/**
 * Numbered step indicator for the guided configuration flow.
 * Shows green when complete, muted when incomplete.
 */
export const StepBadge = ({ step, isComplete, className }: StepBadgeProps) => (
    <span
        className={cn(
            "flex items-center justify-center w-5 h-5 rounded-full text-xs",
            isComplete ? STEP_BADGE_CLASSES.complete : STEP_BADGE_CLASSES.incomplete,
            className
        )}
    >
        {step}
    </span>
);

interface StepHeaderProps {
    /** Step number */
    step: number;
    /** Step title */
    title: string;
    /** Whether this step is complete */
    isComplete: boolean;
}

/**
 * Step header with badge and title.
 */
export const StepHeader = ({ step, title, isComplete }: StepHeaderProps) => (
    <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
        <StepBadge step={step} isComplete={isComplete} />
        {title}
    </div>
);
