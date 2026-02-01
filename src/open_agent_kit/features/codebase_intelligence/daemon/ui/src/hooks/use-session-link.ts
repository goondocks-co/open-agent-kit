import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { API_BASE, fetchJson } from "@/lib/api";
import {
    getSessionLineageEndpoint,
    getLinkSessionEndpoint,
    getRegenerateSummaryEndpoint,
    getSuggestedParentEndpoint,
    getDismissSuggestionEndpoint,
    getRelatedSessionsEndpoint,
    getAddRelatedEndpoint,
    getRemoveRelatedEndpoint,
    getSuggestedRelatedEndpoint,
} from "@/lib/constants";

// =============================================================================
// Types
// =============================================================================

export interface SessionLineageItem {
    id: string;
    title: string | null;
    first_prompt_preview: string | null;
    started_at: string;
    ended_at: string | null;
    status: string;
    parent_session_reason: string | null;
    prompt_batch_count: number;
}

export interface SessionLineageResponse {
    session_id: string;
    ancestors: SessionLineageItem[];
    children: SessionLineageItem[];
}

export interface LinkSessionRequest {
    parent_session_id: string;
    reason?: string;
}

export interface LinkSessionResponse {
    success: boolean;
    session_id: string;
    parent_session_id: string;
    reason: string;
    message: string;
}

export interface UnlinkSessionResponse {
    success: boolean;
    session_id: string;
    previous_parent_id: string | null;
    message: string;
}

export interface RegenerateSummaryResponse {
    success: boolean;
    session_id: string;
    summary: string | null;
    message: string;
}

// =============================================================================
// Query Hooks
// =============================================================================

/**
 * Hook to fetch the lineage (ancestors and children) of a session.
 */
export function useSessionLineage(sessionId: string | undefined) {
    return useQuery<SessionLineageResponse>({
        queryKey: ["session_lineage", sessionId],
        queryFn: () => fetchJson(getSessionLineageEndpoint(sessionId!)),
        enabled: !!sessionId,
    });
}

// =============================================================================
// Mutation Hooks
// =============================================================================

async function postJson<TRequest, TResponse>(
    endpoint: string,
    body: TRequest
): Promise<TResponse> {
    const url = `${API_BASE}${endpoint}`;
    const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });

    if (!response.ok) {
        const error = await response.text();
        throw new Error(`Request failed: ${response.status} - ${error}`);
    }

    return response.json();
}

async function deleteResource<T>(endpoint: string): Promise<T> {
    const url = `${API_BASE}${endpoint}`;
    const response = await fetch(url, { method: "DELETE" });

    if (!response.ok) {
        const error = await response.text();
        throw new Error(`Delete failed: ${response.status} - ${error}`);
    }

    return response.json();
}

/**
 * Hook to link a session to a parent session.
 * Invalidates session and lineage queries on success.
 */
export function useLinkSession() {
    const queryClient = useQueryClient();

    return useMutation<
        LinkSessionResponse,
        Error,
        { sessionId: string; parentSessionId: string; reason?: string }
    >({
        mutationFn: ({ sessionId, parentSessionId, reason }) =>
            postJson<LinkSessionRequest, LinkSessionResponse>(
                getLinkSessionEndpoint(sessionId),
                { parent_session_id: parentSessionId, reason: reason || "manual" }
            ),
        onSuccess: (_data, { sessionId }) => {
            // Invalidate session detail
            queryClient.invalidateQueries({ queryKey: ["session", sessionId] });
            // Invalidate lineage
            queryClient.invalidateQueries({ queryKey: ["session_lineage", sessionId] });
            // Invalidate sessions list (parent/child counts may have changed)
            queryClient.invalidateQueries({ queryKey: ["sessions"] });
        },
    });
}

/**
 * Hook to unlink a session from its parent.
 * Invalidates session and lineage queries on success.
 */
export function useUnlinkSession() {
    const queryClient = useQueryClient();

    return useMutation<UnlinkSessionResponse, Error, string>({
        mutationFn: (sessionId: string) =>
            deleteResource<UnlinkSessionResponse>(getLinkSessionEndpoint(sessionId)),
        onSuccess: (_data, sessionId) => {
            // Invalidate session detail
            queryClient.invalidateQueries({ queryKey: ["session", sessionId] });
            // Invalidate lineage
            queryClient.invalidateQueries({ queryKey: ["session_lineage", sessionId] });
            // Invalidate sessions list
            queryClient.invalidateQueries({ queryKey: ["sessions"] });
        },
    });
}

/**
 * Hook to regenerate the summary for a session.
 * Invalidates session query on success.
 */
export function useRegenerateSummary() {
    const queryClient = useQueryClient();

    return useMutation<RegenerateSummaryResponse, Error, string>({
        mutationFn: (sessionId: string) =>
            postJson<object, RegenerateSummaryResponse>(
                getRegenerateSummaryEndpoint(sessionId),
                {}
            ),
        onSuccess: (_data, sessionId) => {
            // Invalidate session detail to show new summary
            queryClient.invalidateQueries({ queryKey: ["session", sessionId] });
            // Invalidate memories (summary creates a memory)
            queryClient.invalidateQueries({ queryKey: ["memories"] });
        },
    });
}

// =============================================================================
// Session Suggestion Types
// =============================================================================

export interface SuggestedParentResponse {
    session_id: string;
    has_suggestion: boolean;
    suggested_parent: SessionLineageItem | null;
    confidence: "high" | "medium" | "low" | null;
    confidence_score: number | null;
    reason: string | null;
    dismissed: boolean;
}

export interface DismissSuggestionResponse {
    success: boolean;
    session_id: string;
    message: string;
}

// =============================================================================
// Session Suggestion Hooks
// =============================================================================

/**
 * Hook to fetch the suggested parent for an unlinked session.
 * Uses vector similarity search to find the most likely parent.
 */
export function useSuggestedParent(sessionId: string | undefined) {
    return useQuery<SuggestedParentResponse>({
        queryKey: ["suggested_parent", sessionId],
        queryFn: () => fetchJson(getSuggestedParentEndpoint(sessionId!)),
        enabled: !!sessionId,
        // Don't refetch too aggressively as this involves vector search
        staleTime: 30000, // 30 seconds
        refetchOnWindowFocus: false,
    });
}

/**
 * Hook to dismiss a suggestion for a session.
 * After dismissing, the suggestion won't be shown again until the user
 * manually links or the dismissal is reset.
 */
export function useDismissSuggestion() {
    const queryClient = useQueryClient();

    return useMutation<DismissSuggestionResponse, Error, string>({
        mutationFn: (sessionId: string) =>
            postJson<object, DismissSuggestionResponse>(
                getDismissSuggestionEndpoint(sessionId),
                {}
            ),
        onSuccess: (_data, sessionId) => {
            // Invalidate the suggested parent query
            queryClient.invalidateQueries({ queryKey: ["suggested_parent", sessionId] });
        },
    });
}

/**
 * Hook to link a session to a suggested parent.
 * Uses "suggestion" as the link reason for analytics tracking.
 */
export function useAcceptSuggestion() {
    const queryClient = useQueryClient();

    return useMutation<
        LinkSessionResponse,
        Error,
        { sessionId: string; parentSessionId: string; confidenceScore?: number }
    >({
        mutationFn: ({ sessionId, parentSessionId }) =>
            postJson<LinkSessionRequest, LinkSessionResponse>(
                getLinkSessionEndpoint(sessionId),
                { parent_session_id: parentSessionId, reason: "suggestion" }
            ),
        onSuccess: (_data, { sessionId }) => {
            // Invalidate session detail
            queryClient.invalidateQueries({ queryKey: ["session", sessionId] });
            // Invalidate lineage
            queryClient.invalidateQueries({ queryKey: ["session_lineage", sessionId] });
            // Invalidate suggested parent (no longer needed)
            queryClient.invalidateQueries({ queryKey: ["suggested_parent", sessionId] });
            // Invalidate sessions list
            queryClient.invalidateQueries({ queryKey: ["sessions"] });
        },
    });
}


// =============================================================================
// Session Relationships Types (many-to-many semantic links)
// =============================================================================

export interface RelatedSessionItem {
    id: string;
    title: string | null;
    first_prompt_preview: string | null;
    started_at: string;
    ended_at: string | null;
    status: string;
    prompt_batch_count: number;
    relationship_id: number;
    similarity_score: number | null;
    created_by: string;
    related_at: string;
}

export interface RelatedSessionsResponse {
    session_id: string;
    related: RelatedSessionItem[];
}

export interface AddRelatedRequest {
    related_session_id: string;
    similarity_score?: number;
}

export interface AddRelatedResponse {
    success: boolean;
    session_id: string;
    related_session_id: string;
    relationship_id: number | null;
    message: string;
}

export interface RemoveRelatedResponse {
    success: boolean;
    session_id: string;
    related_session_id: string;
    message: string;
}

export interface SuggestedRelatedItem {
    id: string;
    title: string | null;
    first_prompt_preview: string | null;
    started_at: string;
    ended_at: string | null;
    status: string;
    prompt_batch_count: number;
    confidence: "high" | "medium" | "low";
    confidence_score: number;
    reason: string;
}

export interface SuggestedRelatedResponse {
    session_id: string;
    suggestions: SuggestedRelatedItem[];
}


// =============================================================================
// Session Relationships Hooks
// =============================================================================

/**
 * Hook to fetch related sessions for a given session.
 * Returns sessions with many-to-many semantic relationships.
 */
export function useSessionRelated(sessionId: string | undefined) {
    return useQuery<RelatedSessionsResponse>({
        queryKey: ["session_related", sessionId],
        queryFn: () => fetchJson(getRelatedSessionsEndpoint(sessionId!)),
        enabled: !!sessionId,
    });
}

/**
 * Hook to fetch suggested related sessions.
 * Uses vector similarity to find semantically similar sessions.
 */
export function useSuggestedRelated(sessionId: string | undefined) {
    return useQuery<SuggestedRelatedResponse>({
        queryKey: ["suggested_related", sessionId],
        queryFn: () => fetchJson(getSuggestedRelatedEndpoint(sessionId!)),
        enabled: !!sessionId,
        // Don't refetch too aggressively as this involves vector search
        staleTime: 30000, // 30 seconds
        refetchOnWindowFocus: false,
    });
}

/**
 * Hook to add a related session relationship.
 */
export function useAddRelated() {
    const queryClient = useQueryClient();

    return useMutation<
        AddRelatedResponse,
        Error,
        { sessionId: string; relatedSessionId: string; similarityScore?: number }
    >({
        mutationFn: ({ sessionId, relatedSessionId, similarityScore }) =>
            postJson<AddRelatedRequest, AddRelatedResponse>(
                getAddRelatedEndpoint(sessionId),
                {
                    related_session_id: relatedSessionId,
                    similarity_score: similarityScore,
                }
            ),
        onSuccess: (_data, { sessionId, relatedSessionId }) => {
            // Invalidate related sessions for both sides
            queryClient.invalidateQueries({ queryKey: ["session_related", sessionId] });
            queryClient.invalidateQueries({ queryKey: ["session_related", relatedSessionId] });
            // Invalidate suggested related (one was accepted)
            queryClient.invalidateQueries({ queryKey: ["suggested_related", sessionId] });
        },
    });
}

/**
 * Hook to remove a related session relationship.
 */
export function useRemoveRelated() {
    const queryClient = useQueryClient();

    return useMutation<
        RemoveRelatedResponse,
        Error,
        { sessionId: string; relatedSessionId: string }
    >({
        mutationFn: ({ sessionId, relatedSessionId }) =>
            deleteResource<RemoveRelatedResponse>(
                getRemoveRelatedEndpoint(sessionId, relatedSessionId)
            ),
        onSuccess: (_data, { sessionId, relatedSessionId }) => {
            // Invalidate related sessions for both sides
            queryClient.invalidateQueries({ queryKey: ["session_related", sessionId] });
            queryClient.invalidateQueries({ queryKey: ["session_related", relatedSessionId] });
        },
    });
}
