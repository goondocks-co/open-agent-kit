import { useState } from "react";
import { useSearch } from "@/hooks/use-search";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/config-components";
import { Link } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Search as SearchIcon, FileText, Loader2, AlertCircle, Brain, ClipboardList } from "lucide-react";
import {
    FALLBACK_MESSAGES,
    SCORE_DISPLAY_PRECISION,
    CONFIDENCE_FILTER_OPTIONS,
    CONFIDENCE_BADGE_CLASSES,
    DOC_TYPE_BADGE_CLASSES,
    DOC_TYPE_LABELS,
    SEARCH_TYPE_OPTIONS,
    SEARCH_TYPES,
    type ConfidenceFilter,
    type ConfidenceLevel,
    type DocType,
    type SearchType,
} from "@/lib/constants";
import type { CodeResult, MemoryResult, PlanResult } from "@/hooks/use-search";

export default function Search() {
    const [query, setQuery] = useState("");
    const [debouncedQuery, setDebouncedQuery] = useState("");
    const [confidenceFilter, setConfidenceFilter] = useState<ConfidenceFilter>("all");
    const [applyDocTypeWeights, setApplyDocTypeWeights] = useState(true);
    const [searchType, setSearchType] = useState<SearchType>(SEARCH_TYPES.ALL);

    const { data: results, isLoading, error } = useSearch(debouncedQuery, confidenceFilter, applyDocTypeWeights, searchType);

    const handleSearch = (e: React.FormEvent) => {
        e.preventDefault();
        setDebouncedQuery(query);
    };

    if (error) {
        return (
            <div className="space-y-6 max-w-4xl mx-auto">
                <div className="flex flex-col gap-2">
                    <h1 className="text-3xl font-bold tracking-tight">Semantic Search</h1>
                    <p className="text-muted-foreground">Search across your codebase, memories, and plans using natural language.</p>
                </div>
                <div className="p-4 border border-red-200 bg-red-50 rounded-md text-red-800 flex items-center gap-2">
                    <AlertCircle className="w-5 h-5" />
                    <div>
                        <p className="font-medium">Search unavailable</p>
                        <p className="text-sm">{error instanceof Error ? error.message : "Detailed search backend error."} Check your <Link to="/config" className="underline font-semibold">configuration</Link>.</p>
                    </div>
                </div>
            </div>
        )
    }

    const hasResults = results?.code?.length || results?.memory?.length || results?.plans?.length;

    return (
        <div className="space-y-6 max-w-4xl mx-auto">
            <div className="flex flex-col gap-2">
                <h1 className="text-3xl font-bold tracking-tight">Semantic Search</h1>
                <p className="text-muted-foreground">Search across your codebase, memories, and plans using natural language.</p>
            </div>

            <form onSubmit={handleSearch} className="flex gap-2 flex-wrap">
                <Input
                    placeholder="e.g. 'How is authentication handled?'"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    className="flex-1 min-w-[200px]"
                />
                <Select
                    value={searchType}
                    onChange={(e) => setSearchType(e.target.value as SearchType)}
                    className="w-40"
                >
                    {SEARCH_TYPE_OPTIONS.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                            {opt.label}
                        </option>
                    ))}
                </Select>
                <Select
                    value={confidenceFilter}
                    onChange={(e) => setConfidenceFilter(e.target.value as ConfidenceFilter)}
                    className="w-40"
                >
                    {CONFIDENCE_FILTER_OPTIONS.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                            {opt.label}
                        </option>
                    ))}
                </Select>
                <label className="flex items-center gap-2 text-sm text-muted-foreground whitespace-nowrap">
                    <input
                        type="checkbox"
                        checked={applyDocTypeWeights}
                        onChange={(e) => setApplyDocTypeWeights(e.target.checked)}
                        className="rounded border-gray-300"
                    />
                    Weight by type
                </label>
                <Button type="submit" disabled={!query || isLoading}>
                    {isLoading ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <SearchIcon className="w-4 h-4 mr-2" />}
                    Search
                </Button>
            </form>

            <div className="space-y-4">
                {results?.code && results.code.length > 0 && (
                    <div>
                        <h2 className="text-lg font-semibold mb-2 flex items-center gap-2">
                            <FileText className="w-5 h-5" /> Code Matches ({results.code.length})
                        </h2>
                        <div className="space-y-3">
                            {results.code.map((match: CodeResult, i: number) => (
                                <Card key={`code-${i}`} className="overflow-hidden">
                                    <CardHeader className="py-3 bg-muted/30">
                                        <CardTitle className="text-sm font-mono flex items-center gap-2">
                                            <span className="text-primary">{match.filepath}</span>
                                            {match.name && <span className="text-muted-foreground">({match.name})</span>}
                                            <span className="ml-auto flex items-center gap-2">
                                                <span className={`text-xs px-2 py-0.5 rounded ${DOC_TYPE_BADGE_CLASSES[match.doc_type as DocType] || ""}`}>
                                                    {DOC_TYPE_LABELS[match.doc_type as DocType] || match.doc_type}
                                                </span>
                                                <span className={`text-xs px-2 py-0.5 rounded capitalize ${CONFIDENCE_BADGE_CLASSES[match.confidence as ConfidenceLevel] || ""}`}>
                                                    {match.confidence}
                                                </span>
                                                <span className="text-xs text-muted-foreground">Score: {match.relevance?.toFixed(SCORE_DISPLAY_PRECISION)}</span>
                                            </span>
                                        </CardTitle>
                                    </CardHeader>
                                    <CardContent className="p-4">
                                        <pre className="text-xs overflow-x-auto p-2 bg-muted/50 rounded-md">
                                            {match.preview || FALLBACK_MESSAGES.NO_PREVIEW}
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
                            <Brain className="w-5 h-5" /> Memory Matches ({results.memory.length})
                        </h2>
                        <div className="space-y-3">
                            {results.memory.map((match: MemoryResult, i: number) => (
                                <Card key={`mem-${i}`} className="overflow-hidden">
                                    <CardHeader className="py-3 bg-muted/30">
                                        <CardTitle className="text-sm font-medium flex items-center gap-2">
                                            <span className="capitalize badge">{match.memory_type}</span>
                                            <span className="ml-auto flex items-center gap-2">
                                                <span className={`text-xs px-2 py-0.5 rounded capitalize ${CONFIDENCE_BADGE_CLASSES[match.confidence as ConfidenceLevel] || ""}`}>
                                                    {match.confidence}
                                                </span>
                                                <span className="text-xs text-muted-foreground">Score: {match.relevance?.toFixed(SCORE_DISPLAY_PRECISION)}</span>
                                            </span>
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

                {results?.plans && results.plans.length > 0 && (
                    <div className="mt-8">
                        <h2 className="text-lg font-semibold mb-2 flex items-center gap-2">
                            <ClipboardList className="w-5 h-5" /> Plan Matches ({results.plans.length})
                        </h2>
                        <div className="space-y-3">
                            {results.plans.map((match: PlanResult, i: number) => (
                                <Card key={`plan-${i}`} className="overflow-hidden">
                                    <CardHeader className="py-3 bg-amber-500/5 border-l-2 border-amber-500">
                                        <CardTitle className="text-sm font-medium flex items-center gap-2">
                                            <span className="text-amber-600">{match.title || "Untitled Plan"}</span>
                                            <span className="ml-auto flex items-center gap-2">
                                                <span className={`text-xs px-2 py-0.5 rounded capitalize ${CONFIDENCE_BADGE_CLASSES[match.confidence as ConfidenceLevel] || ""}`}>
                                                    {match.confidence}
                                                </span>
                                                <span className="text-xs text-muted-foreground">Score: {match.relevance?.toFixed(SCORE_DISPLAY_PRECISION)}</span>
                                            </span>
                                        </CardTitle>
                                    </CardHeader>
                                    <CardContent className="p-4 text-sm">
                                        <p className="text-muted-foreground">{match.preview}</p>
                                        {match.session_id && (
                                            <Link
                                                to={`/activity/sessions/${match.session_id}`}
                                                className="text-xs text-primary hover:underline mt-2 inline-block"
                                            >
                                                View Session →
                                            </Link>
                                        )}
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    </div>
                )}

                {debouncedQuery && !isLoading && !hasResults ? (
                    <div className="text-center py-12 text-muted-foreground">{FALLBACK_MESSAGES.NO_RESULTS} for "{debouncedQuery}"</div>
                ) : null}
            </div>
        </div>
    )
}
