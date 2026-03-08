/**
 * Shared SearchBar component — full-width search input with type pill filters.
 *
 * Used by both the team and swarm daemon search pages. Renders a search input
 * row with a submit button, and an optional filter row with type pills and
 * extra controls (checkboxes, dropdowns) passed via the `filters` slot.
 */

import { Button } from "./button";
import { Search as SearchIcon, Loader2 } from "lucide-react";
import { cn } from "../../lib/utils";

// =============================================================================
// Type Pills
// =============================================================================

export interface TypePillOption {
    value: string;
    label: string;
}

interface TypePillsProps {
    options: readonly TypePillOption[];
    value: string;
    onChange: (value: string) => void;
}

export function TypePills({ options, value, onChange }: TypePillsProps) {
    return (
        <div className="flex rounded-md border border-input overflow-hidden">
            {options.map((opt) => (
                <button
                    key={opt.value}
                    type="button"
                    onClick={() => onChange(opt.value)}
                    className={cn(
                        "px-3 py-1.5 text-xs font-medium capitalize transition-colors",
                        value === opt.value
                            ? "bg-primary text-primary-foreground"
                            : "bg-background text-muted-foreground hover:bg-muted",
                    )}
                >
                    {opt.label}
                </button>
            ))}
        </div>
    );
}

// =============================================================================
// Search Bar
// =============================================================================

export interface SearchBarProps {
    query: string;
    onQueryChange: (query: string) => void;
    onSearch: () => void;
    isSearching: boolean;
    placeholder?: string;
    /** Additional filter controls rendered in the filter row */
    filters?: React.ReactNode;
}

export function SearchBar({
    query,
    onQueryChange,
    onSearch,
    isSearching,
    placeholder = "Search...",
    filters,
}: SearchBarProps) {
    return (
        <div className="space-y-3">
            {/* Search input row */}
            <div className="flex gap-3">
                <input
                    type="text"
                    value={query}
                    onChange={(e) => onQueryChange(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && onSearch()}
                    placeholder={placeholder}
                    className="flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                />
                <Button
                    type="button"
                    onClick={onSearch}
                    disabled={isSearching || !query.trim()}
                >
                    {isSearching
                        ? <Loader2 className="h-4 w-4 animate-spin mr-2" />
                        : <SearchIcon className="h-4 w-4 mr-2" />}
                    Search
                </Button>
            </div>

            {/* Filter row */}
            {filters && (
                <div className="flex items-center gap-3 flex-wrap">
                    {filters}
                </div>
            )}
        </div>
    );
}
