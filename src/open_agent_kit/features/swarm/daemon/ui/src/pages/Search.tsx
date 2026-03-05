import { useState } from "react";
import { Card, CardContent } from "@oak/ui/components/ui/card";
import { Alert, AlertDescription } from "@oak/ui/components/ui/alert";
import { Search as SearchIcon } from "lucide-react";
import { useSwarmSearch } from "@/hooks/use-swarm-search";
import { SearchFilters, ProjectResultGroup } from "@/components/search";
import type { SearchType } from "@/lib/constants";

export default function SearchPage() {
    const [query, setQuery] = useState("");
    const [searchType, setSearchType] = useState<SearchType>("all");
    const [limit, setLimit] = useState(10);
    const searchMutation = useSwarmSearch();

    const handleSearch = () => {
        if (!query.trim()) return;
        searchMutation.mutate({ query, search_type: searchType, limit });
    };

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold">Search</h1>
                <p className="text-muted-foreground text-sm mt-1">
                    Search across all connected swarm nodes
                </p>
            </div>

            <Card>
                <CardContent className="pt-6">
                    <SearchFilters
                        query={query}
                        onQueryChange={setQuery}
                        searchType={searchType}
                        onSearchTypeChange={setSearchType}
                        limit={limit}
                        onLimitChange={setLimit}
                        onSearch={handleSearch}
                        isSearching={searchMutation.isPending}
                    />
                </CardContent>
            </Card>

            {/* Loading skeleton */}
            {searchMutation.isPending && (
                <div className="space-y-4">
                    {[1, 2, 3].map((i) => (
                        <Card key={i}>
                            <CardContent className="pt-6 space-y-3 animate-pulse">
                                <div className="h-5 bg-muted rounded w-1/3" />
                                <div className="h-16 bg-muted rounded" />
                                <div className="h-16 bg-muted rounded" />
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}

            {/* Mutation error (thrown exception, e.g. auth failure) */}
            {searchMutation.isError && (
                <Alert variant="destructive">
                    <AlertDescription>
                        Search request failed: {searchMutation.error?.message ?? "Unknown error"}
                    </AlertDescription>
                </Alert>
            )}

            {/* API-level error (200 response with error field) */}
            {searchMutation.data?.error && (
                <Alert variant="destructive">
                    <AlertDescription>{searchMutation.data.error}</AlertDescription>
                </Alert>
            )}

            {/* Results */}
            {!searchMutation.isPending &&
                searchMutation.data?.results?.map((projectResult, i) => (
                    <ProjectResultGroup key={i} result={projectResult} />
                ))}

            {/* Empty state */}
            {searchMutation.isSuccess &&
                !searchMutation.data?.results?.length &&
                !searchMutation.data?.error && (
                    <Card>
                        <CardContent className="pt-6 text-center py-12">
                            <SearchIcon className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                            <p className="text-muted-foreground">No results found</p>
                            <p className="text-xs text-muted-foreground mt-2">
                                Try different keywords or broaden your search type
                            </p>
                        </CardContent>
                    </Card>
                )}

            {/* Initial empty state (before any search) */}
            {!searchMutation.data && !searchMutation.isPending && (
                <Card>
                    <CardContent className="pt-6 text-center py-12">
                        <SearchIcon className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                        <p className="text-muted-foreground">Search across your swarm</p>
                        <p className="text-xs text-muted-foreground mt-2">
                            Try &quot;authentication flow&quot; or &quot;database schema&quot;
                        </p>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
