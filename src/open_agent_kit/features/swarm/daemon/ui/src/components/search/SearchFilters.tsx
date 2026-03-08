/**
 * Swarm search filters — wraps the shared SearchBar with swarm-specific type pills and limit dropdown.
 */

import { SearchBar, TypePills } from "@oak/ui/components/ui/search-bar";
import {
    SEARCH_TYPES,
    RESULT_LIMIT_OPTIONS,
    type SearchType,
} from "@/lib/constants";

const TYPE_OPTIONS = SEARCH_TYPES.map((t) => ({ value: t, label: t }));

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
        <SearchBar
            query={query}
            onQueryChange={onQueryChange}
            onSearch={onSearch}
            isSearching={isSearching}
            placeholder="Search across connected teams..."
            filters={
                <>
                    <TypePills
                        options={TYPE_OPTIONS}
                        value={searchType}
                        onChange={(v) => onSearchTypeChange(v as SearchType)}
                    />
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
                </>
            }
        />
    );
}
