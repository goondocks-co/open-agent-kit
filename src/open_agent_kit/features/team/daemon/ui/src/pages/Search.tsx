import { useState } from "react";
import { useSearch } from "@/hooks/use-search";
import { useNetworkSearch } from "@/hooks/use-network-search";
import { useTeamStatus } from "@/hooks/use-team";
import { SearchBar, TypePills } from "@oak/ui/components/ui/search-bar";
import { Link, useSearchParams } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@oak/ui/components/ui/card";
import { Alert, AlertDescription } from "@oak/ui/components/ui/alert";
import {
    Search as SearchIcon,
    FileText,
    Brain,
    ClipboardList,
    MessageSquare,
    Globe,
    Loader2,
    AlertCircle,
} from "lucide-react";
import {
    FALLBACK_MESSAGES,
    SCORE_DISPLAY_PRECISION,
    CONFIDENCE_FILTER_OPTIONS,
    CONFIDENCE_BADGE_CLASSES,
    DOC_TYPE_BADGE_CLASSES,
    DOC_TYPE_LABELS,
    OBSERVATION_STATUS_BADGE_CLASSES,
    OBSERVATION_STATUS_LABELS,
    OBSERVATION_STATUSES,
    SEARCH_TYPE_OPTIONS,
    SEARCH_TYPES,
    type ConfidenceFilter,
    type ConfidenceLevel,
    type DocType,
    type ObservationStatus,
    type SearchType,
} from "@/lib/constants";
import type { CodeResult, MemoryResult, PlanResult, SessionResult } from "@/hooks/use-search";

// Valid search type values for URL param validation
const VALID_SEARCH_TYPES = Object.values(SEARCH_TYPES) as string[];

// Type pill options from SEARCH_TYPE_OPTIONS
const TYPE_PILL_OPTIONS = SEARCH_TYPE_OPTIONS.map((opt) => ({
    value: opt.value,
    label: opt.label.replace(" Only", ""),
}));

export default function Search() {
    const [searchParams, setSearchParams] = useSearchParams();
    const [query, setQuery] = useState("");
    const [debouncedQuery, setDebouncedQuery] = useState("");
    const [confidenceFilter, setConfidenceFilter] = useState<ConfidenceFilter>("all");
    const [applyDocTypeWeights, setApplyDocTypeWeights] = useState(true);
    const [includeResolved, setIncludeResolved] = useState(false);

    // Initialize searchType from URL param, defaulting to ALL
    const tabParam = searchParams.get("tab");
    const initialSearchType = tabParam && VALID_SEARCH_TYPES.includes(tabParam)
        ? tabParam as SearchType
        : SEARCH_TYPES.ALL;
    const [searchType, setSearchType] = useState<SearchType>(initialSearchType);

    // Sync URL when searchType changes
    const handleSearchTypeChange = (newType: string) => {
        const st = newType as SearchType;
        setSearchType(st);
        if (st === SEARCH_TYPES.ALL) {
            searchParams.delete("tab");
        } else {
            searchParams.set("tab", st);
        }
        setSearchParams(searchParams, { replace: true });
    };

    const [includeNetwork, setIncludeNetwork] = useState(false);

    const { data: teamStatus } = useTeamStatus();
    const relayConnected = teamStatus?.connected ?? false;

    const { data: results, isLoading, error } = useSearch(debouncedQuery, confidenceFilter, applyDocTypeWeights, searchType, includeResolved);

    const isCodeSearch = searchType === SEARCH_TYPES.CODE;
    const networkEnabled = includeNetwork && !isCodeSearch && relayConnected;
    const { data: networkResults, isLoading: networkLoading } = useNetworkSearch(
        debouncedQuery,
        searchType,
        20,
        networkEnabled,
    );

    const handleSearch = () => {
        setDebouncedQuery(query);
    };

    if (error) {
        return (
            <div className="space-y-6">
                <div>
                    <h1 className="text-2xl font-bold">Search</h1>
                    <p className="text-muted-foreground text-sm mt-1">
                        Search across your codebase, memories, and plans
                    </p>
                </div>
                <Alert variant="destructive">
                    <AlertCircle className="h-4 w-4" />
                    <AlertDescription>
                        Search unavailable. {error instanceof Error ? error.message : "Backend error."}{" "}
                        Check your <Link to="/config" className="underline font-semibold">configuration</Link>.
                    </AlertDescription>
                </Alert>
            </div>
        );
    }

    const hasResults = results?.code?.length || results?.memory?.length || results?.plans?.length || results?.sessions?.length;

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold">Search</h1>
                <p className="text-muted-foreground text-sm mt-1">
                    Search across your codebase, memories, and plans
                </p>
            </div>

            <Card>
                <CardContent className="pt-6">
                    <SearchBar
                        query={query}
                        onQueryChange={setQuery}
                        onSearch={handleSearch}
                        isSearching={isLoading}
                        placeholder="e.g. 'How is authentication handled?'"
                        filters={
                            <>
                                <TypePills
                                    options={TYPE_PILL_OPTIONS}
                                    value={searchType}
                                    onChange={handleSearchTypeChange}
                                />
                                <select
                                    value={confidenceFilter}
                                    onChange={(e) => setConfidenceFilter(e.target.value as ConfidenceFilter)}
                                    className="rounded-md border border-input bg-background px-2 py-1.5 text-xs"
                                >
                                    {CONFIDENCE_FILTER_OPTIONS.map((opt) => (
                                        <option key={opt.value} value={opt.value}>
                                            {opt.label}
                                        </option>
                                    ))}
                                </select>
                                <label className="flex items-center gap-1.5 text-xs text-muted-foreground whitespace-nowrap cursor-pointer">
                                    <input
                                        type="checkbox"
                                        checked={applyDocTypeWeights}
                                        onChange={(e) => setApplyDocTypeWeights(e.target.checked)}
                                        className="rounded border-gray-300"
                                    />
                                    Weighted
                                </label>
                                <label className="flex items-center gap-1.5 text-xs text-muted-foreground whitespace-nowrap cursor-pointer">
                                    <input
                                        type="checkbox"
                                        checked={includeResolved}
                                        onChange={(e) => setIncludeResolved(e.target.checked)}
                                        className="rounded border-gray-300"
                                    />
                                    Resolved
                                </label>
                                {relayConnected && (
                                    <label
                                        className="flex items-center gap-1.5 text-xs text-muted-foreground whitespace-nowrap cursor-pointer"
                                        title={isCodeSearch ? "Code search is project-specific" : "Search across connected team nodes"}
                                    >
                                        <input
                                            type="checkbox"
                                            checked={includeNetwork && !isCodeSearch}
                                            onChange={(e) => setIncludeNetwork(e.target.checked)}
                                            disabled={isCodeSearch}
                                            className="rounded border-gray-300"
                                        />
                                        Network
                                    </label>
                                )}
                            </>
                        }
                    />
                </CardContent>
            </Card>

            {/* Loading skeleton */}
            {isLoading && (
                <div className="space-y-4">
                    {[1, 2, 3].map((i) => (
                        <Card key={i}>
                            <CardContent className="pt-6 space-y-3 animate-pulse">
                                <div className="h-5 bg-muted rounded w-1/3" />
                                <div className="h-16 bg-muted rounded" />
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}

            {/* Results */}
            {!isLoading && (
                <div className="space-y-6">
                    {results?.code && results.code.length > 0 && (
                        <ResultSection
                            icon={<FileText className="w-4 h-4" />}
                            title="Code"
                            count={results.code.length}
                        >
                            {results.code.map((match: CodeResult, i: number) => (
                                <Card key={`code-${i}`} className="overflow-hidden">
                                    <CardHeader className="py-3 bg-muted/30 space-y-1.5">
                                        <CardTitle className="text-sm font-mono truncate">
                                            <span className="text-primary">{match.filepath}</span>
                                            {match.name && <span className="text-muted-foreground"> ({match.name})</span>}
                                        </CardTitle>
                                        <div className="flex items-center gap-2">
                                            <span className={`text-xs px-2 py-0.5 rounded ${DOC_TYPE_BADGE_CLASSES[match.doc_type as DocType] || ""}`}>
                                                {DOC_TYPE_LABELS[match.doc_type as DocType] || match.doc_type}
                                            </span>
                                            <ConfidenceBadge confidence={match.confidence} />
                                            <ScoreLabel score={match.relevance} />
                                        </div>
                                    </CardHeader>
                                    <CardContent className="p-4">
                                        <pre className="text-xs overflow-x-auto p-2 bg-muted/50 rounded-md">
                                            {match.preview || FALLBACK_MESSAGES.NO_PREVIEW}
                                        </pre>
                                    </CardContent>
                                </Card>
                            ))}
                        </ResultSection>
                    )}

                    {results?.memory && results.memory.length > 0 && (
                        <ResultSection
                            icon={<Brain className="w-4 h-4" />}
                            title="Memories"
                            count={results.memory.length}
                        >
                            {results.memory.map((match: MemoryResult, i: number) => (
                                <Card key={`mem-${i}`} className={`overflow-hidden${match.status && match.status !== OBSERVATION_STATUSES.ACTIVE ? " opacity-60" : ""}`}>
                                    <CardHeader className="py-3 bg-muted/30">
                                        <CardTitle className="text-sm font-medium flex items-center gap-2">
                                            <span className="capitalize">{match.memory_type}</span>
                                            {match.status && match.status !== OBSERVATION_STATUSES.ACTIVE && (
                                                <span className={`text-xs px-2 py-0.5 rounded-full ${OBSERVATION_STATUS_BADGE_CLASSES[match.status as ObservationStatus] || ""}`}>
                                                    {OBSERVATION_STATUS_LABELS[match.status as ObservationStatus] || match.status}
                                                </span>
                                            )}
                                            <span className="ml-auto flex items-center gap-2">
                                                <ConfidenceBadge confidence={match.confidence} />
                                                <ScoreLabel score={match.relevance} />
                                            </span>
                                        </CardTitle>
                                    </CardHeader>
                                    <CardContent className="p-4 text-sm">
                                        {match.summary}
                                    </CardContent>
                                </Card>
                            ))}
                        </ResultSection>
                    )}

                    {results?.plans && results.plans.length > 0 && (
                        <ResultSection
                            icon={<ClipboardList className="w-4 h-4" />}
                            title="Plans"
                            count={results.plans.length}
                        >
                            {results.plans.map((match: PlanResult, i: number) => (
                                <Card key={`plan-${i}`} className="overflow-hidden">
                                    <CardHeader className="py-3 bg-amber-500/5 border-l-2 border-amber-500">
                                        <CardTitle className="text-sm font-medium flex items-center gap-2">
                                            <span className="text-amber-600">{match.title || "Untitled Plan"}</span>
                                            <span className="ml-auto flex items-center gap-2">
                                                <ConfidenceBadge confidence={match.confidence} />
                                                <ScoreLabel score={match.relevance} />
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
                        </ResultSection>
                    )}

                    {results?.sessions && results.sessions.length > 0 && (
                        <ResultSection
                            icon={<MessageSquare className="w-4 h-4" />}
                            title="Sessions"
                            count={results.sessions.length}
                        >
                            {results.sessions.map((match: SessionResult, i: number) => (
                                <Card key={`session-${i}`} className="overflow-hidden">
                                    <CardHeader className="py-3 bg-blue-500/5 border-l-2 border-blue-500">
                                        <CardTitle className="text-sm font-medium flex items-center gap-2">
                                            <span className="text-blue-600">{match.title || "Untitled Session"}</span>
                                            <span className="ml-auto flex items-center gap-2">
                                                <ConfidenceBadge confidence={match.confidence} />
                                                <ScoreLabel score={match.relevance} />
                                            </span>
                                        </CardTitle>
                                    </CardHeader>
                                    <CardContent className="p-4 text-sm">
                                        <p className="text-muted-foreground">{match.preview}</p>
                                        <Link
                                            to={`/activity/sessions/${match.id}`}
                                            className="text-xs text-primary hover:underline mt-2 inline-block"
                                        >
                                            View Session →
                                        </Link>
                                    </CardContent>
                                </Card>
                            ))}
                        </ResultSection>
                    )}

                    {networkEnabled && networkLoading && (
                        <div className="flex items-center gap-2 text-muted-foreground text-sm">
                            <Loader2 className="w-4 h-4 animate-spin" />
                            Searching team network...
                        </div>
                    )}

                    {networkResults?.results && networkResults.results.length > 0 && (
                        <ResultSection
                            icon={<Globe className="w-4 h-4" />}
                            title="Network"
                            count={networkResults.results.length}
                        >
                            {networkResults.results.map((match, i) => {
                                const body = match.observation || match.summary || match.preview || "";
                                const subtitle = (match.title && body !== match.title) ? match.title : undefined;
                                const typeLabel = match.memory_type || match._result_type;
                                if (!body) return null;

                                return (
                                    <Card key={`network-${i}`} className="overflow-hidden">
                                        <CardHeader className="py-3 bg-teal-500/5 border-l-2 border-teal-500">
                                            <CardTitle className="text-sm font-medium flex items-center gap-2">
                                                <span className="text-xs px-2 py-0.5 rounded bg-teal-500/10 text-teal-600 font-mono">
                                                    {match.machine_id}
                                                </span>
                                                {typeLabel && (
                                                    <span className="capitalize text-muted-foreground">{typeLabel}</span>
                                                )}
                                                <span className="ml-auto flex items-center gap-2">
                                                    {match.confidence && (
                                                        <ConfidenceBadge confidence={match.confidence as ConfidenceLevel} />
                                                    )}
                                                    {match.relevance != null && (
                                                        <ScoreLabel score={match.relevance} />
                                                    )}
                                                </span>
                                            </CardTitle>
                                        </CardHeader>
                                        <CardContent className="p-4 text-sm">
                                            {subtitle && <p className="font-medium mb-1">{subtitle}</p>}
                                            {body}
                                        </CardContent>
                                    </Card>
                                );
                            })}
                        </ResultSection>
                    )}

                    {debouncedQuery && !isLoading && !hasResults && !(networkResults?.results?.length) && (
                        <Card>
                            <CardContent className="pt-6 text-center py-12">
                                <SearchIcon className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                                <p className="text-muted-foreground">No results found for "{debouncedQuery}"</p>
                                <p className="text-xs text-muted-foreground mt-2">
                                    Try different keywords or broaden your search type
                                </p>
                            </CardContent>
                        </Card>
                    )}
                </div>
            )}

            {/* Initial empty state (before any search) */}
            {!debouncedQuery && !isLoading && (
                <Card>
                    <CardContent className="pt-6 text-center py-12">
                        <SearchIcon className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                        <p className="text-muted-foreground">Search across your project</p>
                        <p className="text-xs text-muted-foreground mt-2">
                            Try "authentication flow" or "database schema"
                        </p>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}

// =============================================================================
// Helper Components
// =============================================================================

function ResultSection({ icon, title, count, children }: {
    icon: React.ReactNode;
    title: string;
    count: number;
    children: React.ReactNode;
}) {
    return (
        <div>
            <h2 className="text-sm font-semibold mb-3 flex items-center gap-2 text-muted-foreground uppercase tracking-wide">
                {icon} {title} ({count})
            </h2>
            <div className="space-y-3">
                {children}
            </div>
        </div>
    );
}

function ConfidenceBadge({ confidence }: { confidence: ConfidenceLevel }) {
    return (
        <span className={`text-xs px-2 py-0.5 rounded capitalize ${CONFIDENCE_BADGE_CLASSES[confidence] || ""}`}>
            {confidence}
        </span>
    );
}

function ScoreLabel({ score }: { score?: number }) {
    if (score == null) return null;
    return (
        <span className="text-xs text-muted-foreground">
            {score.toFixed(SCORE_DISPLAY_PRECISION)}
        </span>
    );
}
