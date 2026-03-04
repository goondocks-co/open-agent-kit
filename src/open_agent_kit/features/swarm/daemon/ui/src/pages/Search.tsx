import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@oak/ui/components/ui/card";
import { Button } from "@oak/ui/components/ui/button";
import { Alert, AlertDescription } from "@oak/ui/components/ui/alert";
import { Search as SearchIcon } from "lucide-react";
import { useSwarmSearch } from "@/hooks/use-swarm-search";

export default function SearchPage() {
    const [query, setQuery] = useState("");
    const [searchType, setSearchType] = useState("all");
    const searchMutation = useSwarmSearch();

    const handleSearch = () => {
        if (!query.trim()) return;
        searchMutation.mutate({ query, search_type: searchType });
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
                    <div className="flex gap-3">
                        <input
                            type="text"
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                            placeholder="Search query..."
                            className="flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        />
                        <select
                            value={searchType}
                            onChange={(e) => setSearchType(e.target.value)}
                            className="rounded-md border border-input bg-background px-3 py-2 text-sm"
                        >
                            <option value="all">All</option>
                            <option value="code">Code</option>
                            <option value="memory">Memory</option>
                        </select>
                        <Button onClick={handleSearch} disabled={searchMutation.isPending || !query.trim()}>
                            <SearchIcon className="h-4 w-4 mr-2" />
                            Search
                        </Button>
                    </div>
                </CardContent>
            </Card>

            {searchMutation.data?.error && (
                <Alert variant="destructive">
                    <AlertDescription>{searchMutation.data.error}</AlertDescription>
                </Alert>
            )}

            {searchMutation.data?.results?.map((projectResult, i) => (
                <Card key={i}>
                    <CardHeader>
                        <CardTitle className="text-base">{projectResult.project_slug}</CardTitle>
                    </CardHeader>
                    <CardContent>
                        {projectResult.matches?.length ? (
                            <div className="space-y-3">
                                {projectResult.matches.map((match, j) => (
                                    <div key={j} className="border rounded-md p-3 text-sm">
                                        <div className="flex items-center gap-2 mb-1">
                                            <span className="text-xs font-medium px-2 py-0.5 rounded bg-muted">
                                                {match.type}
                                            </span>
                                            {match.score !== undefined && (
                                                <span className="text-xs text-muted-foreground">
                                                    Score: {match.score.toFixed(2)}
                                                </span>
                                            )}
                                        </div>
                                        <pre className="whitespace-pre-wrap text-xs mt-1 text-muted-foreground">
                                            {match.content}
                                        </pre>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <p className="text-sm text-muted-foreground">No results</p>
                        )}
                    </CardContent>
                </Card>
            ))}

            {searchMutation.isSuccess && !searchMutation.data?.results?.length && !searchMutation.data?.error && (
                <p className="text-sm text-muted-foreground text-center py-8">No results found</p>
            )}
        </div>
    );
}
