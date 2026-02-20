/**
 * React Query hooks for governance API.
 *
 * Provides hooks for:
 * - Fetching governance config (rules + enforcement mode)
 * - Saving governance config
 * - Querying audit events with filters
 * - Getting audit summary stats
 * - Testing a tool call against policy
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchJson, postJson } from "@/lib/api";
import { API_ENDPOINTS } from "@/lib/constants";
import { usePowerQuery } from "./use-power-query";

// =============================================================================
// Types
// =============================================================================

export interface GovernanceRule {
    id: string;
    description: string;
    enabled: boolean;
    tool: string;
    pattern: string;
    path_pattern: string;
    action: string;
    message: string;
}

export interface GovernanceConfig {
    enabled: boolean;
    enforcement_mode: string;
    log_allowed: boolean;
    retention_days: number;
    rules: GovernanceRule[];
}

export interface AuditEvent {
    id: number;
    session_id: string;
    agent: string;
    tool_name: string;
    tool_use_id: string | null;
    tool_category: string | null;
    rule_id: string | null;
    rule_description: string | null;
    action: string;
    reason: string | null;
    matched_pattern: string | null;
    tool_input_summary: string | null;
    enforcement_mode: string;
    created_at: string;
    created_at_epoch: number;
    evaluation_ms: number | null;
    source_machine_id: string | null;
    session_title: string | null;
}

export interface AuditListResponse {
    events: AuditEvent[];
    total: number;
    limit: number;
    offset: number;
}

export interface AuditSummaryResponse {
    total: number;
    by_action: Record<string, number>;
    by_tool: Record<string, number>;
    by_rule: Record<string, number>;
    days: number;
}

export interface GovernanceTestRequest {
    tool_name: string;
    tool_input: Record<string, unknown>;
}

export interface GovernanceTestResponse {
    action: string;
    rule_id: string | null;
    reason: string;
    matched_pattern: string | null;
    tool_category: string;
}

export interface AuditQueryParams {
    since?: number;
    action?: string;
    agent?: string;
    tool?: string;
    rule_id?: string;
    limit?: number;
    offset?: number;
}

// =============================================================================
// Query Keys
// =============================================================================

const governanceKeys = {
    all: ["governance"] as const,
    config: () => [...governanceKeys.all, "config"] as const,
    audit: (params: AuditQueryParams) => [...governanceKeys.all, "audit", params] as const,
    auditSummary: (days: number) => [...governanceKeys.all, "audit-summary", days] as const,
};

// =============================================================================
// API Functions
// =============================================================================

async function fetchGovernanceConfig(signal?: AbortSignal): Promise<GovernanceConfig> {
    return fetchJson<GovernanceConfig>(API_ENDPOINTS.GOVERNANCE_CONFIG, { signal });
}

async function saveGovernanceConfig(config: GovernanceConfig): Promise<{ status: string; config: GovernanceConfig }> {
    return fetchJson<{ status: string; config: GovernanceConfig }>(API_ENDPOINTS.GOVERNANCE_CONFIG, {
        method: "PUT",
        body: JSON.stringify(config),
    });
}

async function fetchAuditEvents(params: AuditQueryParams, signal?: AbortSignal): Promise<AuditListResponse> {
    const searchParams = new URLSearchParams();
    if (params.since !== undefined) searchParams.set("since", String(params.since));
    if (params.action) searchParams.set("action", params.action);
    if (params.agent) searchParams.set("agent", params.agent);
    if (params.tool) searchParams.set("tool", params.tool);
    if (params.rule_id) searchParams.set("rule_id", params.rule_id);
    if (params.limit !== undefined) searchParams.set("limit", String(params.limit));
    if (params.offset !== undefined) searchParams.set("offset", String(params.offset));

    const query = searchParams.toString();
    return fetchJson<AuditListResponse>(
        `${API_ENDPOINTS.GOVERNANCE_AUDIT}${query ? `?${query}` : ""}`,
        { signal }
    );
}

async function fetchAuditSummary(days: number, signal?: AbortSignal): Promise<AuditSummaryResponse> {
    return fetchJson<AuditSummaryResponse>(
        `${API_ENDPOINTS.GOVERNANCE_AUDIT_SUMMARY}?days=${days}`,
        { signal }
    );
}

async function testGovernanceRule(request: GovernanceTestRequest): Promise<GovernanceTestResponse> {
    return postJson<GovernanceTestResponse>(API_ENDPOINTS.GOVERNANCE_TEST, request);
}

async function pruneAuditEvents(): Promise<{ deleted: number; retention_days: number }> {
    return postJson<{ deleted: number; retention_days: number }>(API_ENDPOINTS.GOVERNANCE_AUDIT_PRUNE, {});
}

// =============================================================================
// Hooks
// =============================================================================

/** Fetch current governance configuration. */
export function useGovernanceConfig() {
    return useQuery({
        queryKey: governanceKeys.config(),
        queryFn: ({ signal }) => fetchGovernanceConfig(signal),
        staleTime: 10000,
    });
}

/** Save updated governance configuration. */
export function useSaveGovernanceConfig() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (config: GovernanceConfig) => saveGovernanceConfig(config),
        onSuccess: (data) => {
            queryClient.setQueryData(governanceKeys.config(), data.config);
            queryClient.invalidateQueries({ queryKey: governanceKeys.config() });
        },
    });
}

/** Fetch audit events with filters. */
export function useGovernanceAudit(params: AuditQueryParams) {
    return usePowerQuery({
        queryKey: governanceKeys.audit(params),
        queryFn: ({ signal }) => fetchAuditEvents(params, signal),
        refetchInterval: 15000,
        pollCategory: "realtime",
        placeholderData: (previousData: AuditListResponse | undefined) => previousData,
    });
}

/** Fetch audit summary stats for dashboard. */
export function useGovernanceAuditSummary(days = 7) {
    return usePowerQuery({
        queryKey: governanceKeys.auditSummary(days),
        queryFn: ({ signal }) => fetchAuditSummary(days, signal),
        refetchInterval: 30000,
        pollCategory: "standard",
    });
}

/** Test a hypothetical tool call against policy. */
export function useTestGovernanceRule() {
    return useMutation({
        mutationFn: (request: GovernanceTestRequest) => testGovernanceRule(request),
    });
}

/** Manually trigger audit event retention pruning. */
export function usePruneAuditEvents() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: () => pruneAuditEvents(),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: governanceKeys.all });
        },
    });
}
