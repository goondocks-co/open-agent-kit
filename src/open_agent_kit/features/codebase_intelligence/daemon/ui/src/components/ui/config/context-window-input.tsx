/**
 * Context window input with preset chips for common values.
 */

import { cn } from "@/lib/utils";
import { Input } from "./form-elements";

/** Common context window sizes for embedding models */
export const EMBEDDING_CONTEXT_PRESETS = [512, 8192, 32768, 131072] as const;

/** Common context window sizes for LLM/summarization models */
export const LLM_CONTEXT_PRESETS = [8192, 32768, 131072, 1048576] as const;

interface ContextWindowInputProps {
    /** Current value */
    value: number | string;
    /** Called when value changes */
    onChange: (value: number) => void;
    /** Placeholder text */
    placeholder?: string;
    /** Which preset sizes to show */
    presets?: readonly number[];
    /** Optional className for container */
    className?: string;
}

/**
 * Context window input with preset chips for common values.
 * Allows both manual entry and quick selection of standard sizes.
 */
export const ContextWindowInput = ({
    value,
    onChange,
    placeholder = "e.g. 8192",
    presets = EMBEDDING_CONTEXT_PRESETS,
    className,
}: ContextWindowInputProps) => {
    const formatPreset = (size: number) => {
        if (size >= 1000000) {
            return `${Math.round(size / 1048576)}M`;
        }
        if (size >= 10000) {
            return `${Math.round(size / 1024)}K`;
        }
        return size.toLocaleString();
    };

    return (
        <div className={cn("space-y-2", className)}>
            <Input
                type="number"
                value={value || ''}
                onChange={(e) => {
                    const val = e.target.value;
                    // Handle empty input - pass 0 to clear, otherwise parse the number
                    onChange(val === '' ? 0 : parseInt(val, 10) || 0);
                }}
                placeholder={placeholder}
            />
            <div className="flex flex-wrap gap-1.5">
                {presets.map((size) => (
                    <button
                        key={size}
                        type="button"
                        onClick={() => onChange(size)}
                        aria-label={`Set context window to ${size.toLocaleString()} tokens`}
                        className={cn(
                            "px-2 py-0.5 text-xs rounded-md border transition-colors",
                            Number(value) === size
                                ? "bg-primary text-primary-foreground border-primary"
                                : "bg-muted/50 hover:bg-muted border-transparent hover:border-border"
                        )}
                    >
                        {formatPreset(size)}
                    </button>
                ))}
            </div>
        </div>
    );
};
