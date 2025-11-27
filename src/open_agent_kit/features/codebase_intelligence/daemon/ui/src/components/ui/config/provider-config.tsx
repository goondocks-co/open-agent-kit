/**
 * Provider configuration components: provider select, URL input, model select, test button.
 */

import { Loader2, RotateCw, Plug } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { PROVIDER_OPTIONS, DEFAULT_PROVIDER_URLS, type ProviderType } from "@/lib/constants";
import { Input, Select } from "./form-elements";

// =============================================================================
// Provider Select
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
// Model Select
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
// Test Button
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
