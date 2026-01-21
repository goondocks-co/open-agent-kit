import { useQuery } from "@tanstack/react-query";
import { fetchJson } from "@/lib/api";
import { API_ENDPOINTS, type ConfidenceLevel, type ConfidenceFilter, CONFIDENCE_LEVELS, type DocType } from "@/lib/constants";

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
}

export interface SearchResponse {
    query: string;
    code: CodeResult[];
    memory: MemoryResult[];
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
    applyDocTypeWeights: boolean = true
) {
    const queryResult = useQuery<SearchResponse>({
        queryKey: ["search", query, applyDocTypeWeights],
        queryFn: () => fetchJson(
            `${API_ENDPOINTS.SEARCH}?query=${encodeURIComponent(query)}&apply_doc_type_weights=${applyDocTypeWeights}`
        ),
        enabled: query.length > MIN_SEARCH_QUERY_LENGTH,
        staleTime: SEARCH_STALE_TIME_MS,
    });

    // Apply client-side confidence filtering
    const filteredData = queryResult.data
        ? {
              ...queryResult.data,
              code: filterByConfidence(queryResult.data.code, confidenceFilter),
              memory: filterByConfidence(queryResult.data.memory, confidenceFilter),
          }
        : undefined;

    return {
        ...queryResult,
        data: filteredData,
    };
}
