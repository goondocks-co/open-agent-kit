import { useState } from "react";
import { useSearch } from "@/hooks/use-search";
import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Search as SearchIcon, FileText, Loader2, AlertCircle } from "lucide-react";

// Inline Input component for speed if not exists
const InputField = ({ className, ...props }: any) => (
    <input
        className={`flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 ${className}`}
        {...props}
    />
);

export default function Search() {
    const [query, setQuery] = useState("");
    const [debouncedQuery, setDebouncedQuery] = useState("");

    const { data: results, isLoading, error } = useSearch(debouncedQuery);

    const handleSearch = (e: React.FormEvent) => {
        e.preventDefault();
        setDebouncedQuery(query);
    };

    if (error) {
        return (
            <div className="space-y-6 max-w-4xl mx-auto">
                <div className="flex flex-col gap-2">
                    <h1 className="text-3xl font-bold tracking-tight">Semantic Search</h1>
                    <p className="text-muted-foreground">Search across your codebase and memories using natural language.</p>
                </div>
                <div className="p-4 border border-red-200 bg-red-50 rounded-md text-red-800 flex items-center gap-2">
                    <AlertCircle className="w-5 h-5" />
                    <div>
                        <p className="font-medium">Search unavailable</p>
                        <p className="text-sm">{(error as any).message || "Detailed search backend error."} Check your <Link to="/config" className="underline font-semibold">configuration</Link>.</p>
                    </div>
                </div>
            </div>
        )
    }

    return (
        <div className="space-y-6 max-w-4xl mx-auto">
            <div className="flex flex-col gap-2">
                <h1 className="text-3xl font-bold tracking-tight">Semantic Search</h1>
                <p className="text-muted-foreground">Search across your codebase and memories using natural language.</p>
            </div>

            <form onSubmit={handleSearch} className="flex gap-2">
                <InputField
                    placeholder="e.g. 'How is authentication handled?'"
                    value={query}
                    onChange={(e: any) => setQuery(e.target.value)}
                    className="flex-1"
                />
                <Button type="submit" disabled={!query || isLoading}>
                    {isLoading ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <SearchIcon className="w-4 h-4 mr-2" />}
                    Search
                </Button>
            </form>

            <div className="space-y-4">
                {results?.code && results.code.length > 0 && (
                    <div>
                        <h2 className="text-lg font-semibold mb-2 flex items-center gap-2">
                            <FileText className="w-5 h-5" /> Code Matches
                        </h2>
                        <div className="space-y-3">
                            {results.code.map((match: any, i: number) => (
                                <Card key={`code-${i}`} className="overflow-hidden">
                                    <CardHeader className="py-3 bg-muted/30">
                                        <CardTitle className="text-sm font-mono flex items-center gap-2">
                                            <span className="text-primary">{match.filepath}</span>
                                            {match.name && <span className="text-muted-foreground">({match.name})</span>}
                                            <span className="ml-auto text-xs text-muted-foreground">Score: {match.relevance?.toFixed(4)}</span>
                                        </CardTitle>
                                    </CardHeader>
                                    <CardContent className="p-4">
                                        <pre className="text-xs overflow-x-auto p-2 bg-muted/50 rounded-md">
                                            {match.preview || "No preview available"}
                                        </pre>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    </div>
                )}

                {results?.memory && results.memory.length > 0 && (
                    <div className="mt-8">
                        <h2 className="text-lg font-semibold mb-2 flex items-center gap-2">
                            <SearchIcon className="w-5 h-5" /> Memory Matches
                        </h2>
                        <div className="space-y-3">
                            {results.memory.map((match: any, i: number) => (
                                <Card key={`mem-${i}`} className="overflow-hidden">
                                    <CardHeader className="py-3 bg-muted/30">
                                        <CardTitle className="text-sm font-medium flex items-center gap-2">
                                            <span className="capitalize badge">{match.memory_type}</span>
                                            <span className="ml-auto text-xs text-muted-foreground">Score: {match.relevance?.toFixed(4)}</span>
                                        </CardTitle>
                                    </CardHeader>
                                    <CardContent className="p-4 text-sm">
                                        {match.summary}
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    </div>
                )}

                {debouncedQuery && !isLoading && (!results?.code?.length && !results?.memory?.length) ? (
                    <div className="text-center py-12 text-muted-foreground">No results found for "{debouncedQuery}"</div>
                ) : null}
            </div>
        </div>
    )
}
