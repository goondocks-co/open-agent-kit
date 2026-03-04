import { useQuery } from "@tanstack/react-query";
import { fetchJson } from "@/lib/api";
import {
    API_ENDPOINTS,
    type ConfidenceLevel,
    type ConfidenceFilter,
    CONFIDENCE_LEVELS,
    type DocType,
    type SearchType,
    SEARCH_TYPES,
} from "@/lib/constants";

export interface CodeResult {
    id: string;
    chunk_type: string;
    name: string | null;
    filepath: string;
    start_line: number;
    end_line: number;
    relevance: number;
    confidence: ConfidenceLevel;
    doc_type: DocType;
    preview: string | null;
}

export interface MemoryResult {
    id: string;
    memory_type: string;
    summary: string;
    relevance: number;
    confidence: ConfidenceLevel;
    status?: string;
}

export interface PlanResult {
    id: string;
    title: string;
    preview: string;
    relevance: number;
    confidence: ConfidenceLevel;
    session_id: string | null;
    created_at: string | null;
}

export interface SessionResult {
    id: string;
    title: string | null;
    preview: string;
    relevance: number;
    confidence: ConfidenceLevel;
    status?: string;
    started_at?: string | null;
    ended_at?: string | null;
    prompt_batch_count?: number;
}

export interface SearchResponse {
    query: string;
    code: CodeResult[];
    memory: MemoryResult[];
    plans: PlanResult[];
    sessions: SessionResult[];
    total_tokens_available: number;
}

/** Minimum query length to trigger a search */
const MIN_SEARCH_QUERY_LENGTH = 2;

/** How long search results stay fresh (1 minute) */
const SEARCH_STALE_TIME_MS = 60000;

/**
 * Filter results by minimum confidence level.
 *
 * - "all": Show all results (no filtering)
 * - "high": Only high confidence results
 * - "medium": High and medium confidence results
 * - "low": All results (high, medium, and low)
 */
function filterByConfidence<T extends { confidence: ConfidenceLevel }>(
    results: T[],
    minConfidence: ConfidenceFilter
): T[] {
    if (minConfidence === "all" || minConfidence === CONFIDENCE_LEVELS.LOW) {
        return results;
    }

    const allowedLevels: Set<ConfidenceLevel> = new Set([CONFIDENCE_LEVELS.HIGH]);
    if (minConfidence === CONFIDENCE_LEVELS.MEDIUM) {
        allowedLevels.add(CONFIDENCE_LEVELS.MEDIUM);
    }

    return results.filter((r) => allowedLevels.has(r.confidence));
}

export function useSearch(
    query: string,
    confidenceFilter: ConfidenceFilter = "all",
    applyDocTypeWeights: boolean = true,
    searchType: SearchType = SEARCH_TYPES.ALL,
    includeResolved: boolean = false,
) {
    const queryResult = useQuery<SearchResponse>({
        queryKey: ["search", query, applyDocTypeWeights, searchType, includeResolved],
        queryFn: ({ signal }) => fetchJson(
            `${API_ENDPOINTS.SEARCH}?query=${encodeURIComponent(query)}&apply_doc_type_weights=${applyDocTypeWeights}&search_type=${searchType}&include_resolved=${includeResolved}`,
            { signal }
        ),
        enabled: query.length > MIN_SEARCH_QUERY_LENGTH,
        staleTime: SEARCH_STALE_TIME_MS,
    });

    // Apply client-side confidence filtering
    const filteredData = queryResult.data
        ? {
              ...queryResult.data,
              code: filterByConfidence(queryResult.data.code || [], confidenceFilter),
              memory: filterByConfidence(queryResult.data.memory || [], confidenceFilter),
              plans: filterByConfidence(queryResult.data.plans || [], confidenceFilter),
              sessions: filterByConfidence(queryResult.data.sessions || [], confidenceFilter),
          }
        : undefined;

    return {
        ...queryResult,
        data: filteredData,
    };
}
