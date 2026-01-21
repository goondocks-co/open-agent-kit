/**
 * Shared configuration UI components.
 *
 * These components provide reusable building blocks for the provider
 * configuration flow, reducing duplication between embedding and
 * summarization settings.
 */

import { Loader2, CheckCircle2, AlertCircle, RotateCw, Plug } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
    STEP_BADGE_CLASSES,
    TEST_RESULT_CLASSES,
    PROVIDER_OPTIONS,
    DEFAULT_PROVIDER_URLS,
    type ProviderType,
} from "@/lib/constants";

// =============================================================================
// Form Elements (consistent styling)
// =============================================================================

interface LabelProps {
    children: React.ReactNode;
    className?: string;
    htmlFor?: string;
}

export const Label = ({ children, className, htmlFor }: LabelProps) => (
    <label
        htmlFor={htmlFor}
        className={cn(
            "text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70",
            className
        )}
    >
        {children}
    </label>
);

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
    className?: string;
}

export const Input = ({ className, ...props }: InputProps) => (
    <input
        className={cn(
            "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm",
            "ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium",
            "placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2",
            "focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
            className
        )}
        {...props}
    />
);

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
    children: React.ReactNode;
    className?: string;
}

export const Select = ({ className, children, ...props }: SelectProps) => (
    <select
        className={cn(
            "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm",
            "ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2",
            "focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
            className
        )}
        {...props}
    >
        {children}
    </select>
);

// =============================================================================
// Step Badge Component
// =============================================================================

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

// =============================================================================
// Step Header Component
// =============================================================================

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

// =============================================================================
// Test Result Display Component
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
// Provider Select Component
// =============================================================================

interface ProviderSelectProps {
    /** Currently selected provider */
    value: string;
    /** Callback when provider changes */
    onChange: (provider: string, defaultUrl: string) => void;
    /** Whether the select is disabled */
    disabled?: boolean;
}

/**
 * Provider selection dropdown with built-in URL defaults.
 * Returns both the selected provider and its default URL.
 */
export const ProviderSelect = ({ value, onChange, disabled }: ProviderSelectProps) => (
    <Select
        value={value}
        onChange={(e) => {
            const provider = e.target.value as ProviderType;
            const defaultUrl = DEFAULT_PROVIDER_URLS[provider];
            onChange(provider, defaultUrl);
        }}
        disabled={disabled}
    >
        {PROVIDER_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
                {opt.label}
            </option>
        ))}
    </Select>
);

// =============================================================================
// URL Input with Refresh Button
// =============================================================================

interface UrlInputWithRefreshProps {
    /** Current URL value */
    value: string;
    /** Callback when URL changes */
    onChange: (url: string) => void;
    /** Callback when refresh button is clicked */
    onRefresh: () => void;
    /** Whether refresh is in progress */
    isRefreshing: boolean;
    /** Placeholder text */
    placeholder?: string;
    /** Whether the input is disabled */
    disabled?: boolean;
}

/**
 * URL input field with integrated refresh button for model discovery.
 */
export const UrlInputWithRefresh = ({
    value,
    onChange,
    onRefresh,
    isRefreshing,
    placeholder = "http://localhost:11434",
    disabled,
}: UrlInputWithRefreshProps) => (
    <div className="flex gap-2">
        <Input
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder}
            disabled={disabled}
        />
        <Button variant="outline" size="icon" onClick={onRefresh} title="Load Models" disabled={disabled}>
            {isRefreshing ? (
                <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
                <RotateCw className="h-4 w-4" />
            )}
        </Button>
    </div>
);

// =============================================================================
// Model Select Component
// =============================================================================

interface ModelOption {
    /** Model identifier (used as value) */
    name?: string;
    id?: string;
    /** Display name (shown in dropdown) */
    display_name?: string;
    /** Dimensions (for embedding models) */
    dimensions?: number;
    /** Provider name */
    provider?: string;
}

interface ModelSelectProps {
    /** Currently selected model */
    value: string;
    /** Available models from discovery */
    models: ModelOption[];
    /** Callback when model changes */
    onChange: (modelId: string, model: ModelOption | undefined) => void;
    /** Placeholder for manual input */
    placeholder: string;
    /** Whether to show dimensions in dropdown */
    showDimensions?: boolean;
    /** Help text shown below */
    helpText?: string;
}

/**
 * Model selection that switches between dropdown (when models discovered)
 * and text input (when no models available).
 */
export const ModelSelect = ({
    value,
    models,
    onChange,
    placeholder,
    showDimensions = false,
    helpText,
}: ModelSelectProps) => {
    const hasModels = models.length > 0;

    return (
        <div className="space-y-2">
            {hasModels ? (
                <Select
                    value={value}
                    onChange={(e) => {
                        const modelId = e.target.value;
                        const model = models.find((m) => (m.name || m.id) === modelId);
                        onChange(modelId, model);
                    }}
                >
                    <option value="" disabled>
                        Select a model...
                    </option>
                    {models.map((m) => {
                        const id = m.name || m.id || "";
                        return (
                            <option key={id} value={id}>
                                {showDimensions && m.dimensions
                                    ? `${id} (${m.dimensions} dims) - ${m.provider}`
                                    : m.display_name || id}
                            </option>
                        );
                    })}
                </Select>
            ) : (
                <Input
                    value={value}
                    onChange={(e) => onChange(e.target.value, undefined)}
                    placeholder={placeholder}
                />
            )}
            {helpText && <p className="text-xs text-muted-foreground">{helpText}</p>}
        </div>
    );
};

// =============================================================================
// Test Button Component
// =============================================================================

interface TestButtonProps {
    /** Callback when button is clicked */
    onClick: () => void;
    /** Whether test is in progress */
    isTesting: boolean;
    /** Whether the button is disabled */
    disabled?: boolean;
    /** Button label (default: "Test & Detect") */
    label?: string;
    /** Additional className */
    className?: string;
}

/**
 * Test & Detect button with loading state.
 */
export const TestButton = ({
    onClick,
    isTesting,
    disabled,
    label = "Test & Detect",
    className,
}: TestButtonProps) => (
    <Button
        variant="secondary"
        className={cn("w-full", className)}
        onClick={onClick}
        disabled={isTesting || disabled}
    >
        {isTesting ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        ) : (
            <Plug className="mr-2 h-4 w-4" />
        )}
        {label}
    </Button>
);

// =============================================================================
// Ready Badge Component
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
// Stat Card Component
// =============================================================================

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
}

/**
 * Statistics card for dashboard displays.
 * Shows a title, icon, main value, and optional subtext.
 */
export const StatCard = ({ title, value, icon: Icon, subtext, loading }: StatCardProps) => (
    <div className="rounded-lg border bg-card text-card-foreground shadow-sm">
        <div className="p-6 flex flex-row items-center justify-between space-y-0 pb-2">
            <h3 className="tracking-tight text-sm font-medium">{title}</h3>
            <Icon className="h-4 w-4 text-muted-foreground" />
        </div>
        <div className="p-6 pt-0">
            <div className="text-2xl font-bold">{loading ? "..." : value}</div>
            {subtext && <p className="text-xs text-muted-foreground">{subtext}</p>}
        </div>
    </div>
);

// =============================================================================
// Status Indicator Components
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
