/**
 * Search filters — type pills, limit dropdown, query input, and search button.
 */

import { Button } from "@oak/ui/components/ui/button";
import { Search as SearchIcon } from "lucide-react";
import {
    SEARCH_TYPES,
    RESULT_LIMIT_OPTIONS,
    type SearchType,
} from "@/lib/constants";

interface SearchFiltersProps {
    query: string;
    onQueryChange: (query: string) => void;
    searchType: SearchType;
    onSearchTypeChange: (type: SearchType) => void;
    limit: number;
    onLimitChange: (limit: number) => void;
    onSearch: () => void;
    isSearching: boolean;
}

export function SearchFilters({
    query,
    onQueryChange,
    searchType,
    onSearchTypeChange,
    limit,
    onLimitChange,
    onSearch,
    isSearching,
}: SearchFiltersProps) {
    return (
        <div className="space-y-3">
            {/* Search input row */}
            <div className="flex gap-3">
                <input
                    type="text"
                    value={query}
                    onChange={(e) => onQueryChange(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && onSearch()}
                    placeholder="Search across connected teams..."
                    className="flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                />
                <Button
                    onClick={onSearch}
                    disabled={isSearching || !query.trim()}
                >
                    <SearchIcon className="h-4 w-4 mr-2" />
                    Search
                </Button>
            </div>

            {/* Filter row */}
            <div className="flex items-center gap-3">
                {/* Type pills */}
                <div className="flex rounded-md border border-input overflow-hidden">
                    {SEARCH_TYPES.map((type) => (
                        <button
                            key={type}
                            onClick={() => onSearchTypeChange(type)}
                            className={`px-3 py-1.5 text-xs font-medium capitalize transition-colors ${
                                searchType === type
                                    ? "bg-primary text-primary-foreground"
                                    : "bg-background text-muted-foreground hover:bg-muted"
                            }`}
                        >
                            {type}
                        </button>
                    ))}
                </div>

                {/* Limit dropdown */}
                <select
                    value={limit}
                    onChange={(e) => onLimitChange(Number(e.target.value))}
                    className="rounded-md border border-input bg-background px-2 py-1.5 text-xs"
                >
                    {RESULT_LIMIT_OPTIONS.map((opt) => (
                        <option key={opt} value={opt}>
                            {opt} results
                        </option>
                    ))}
                </select>
            </div>
        </div>
    );
}
