/**
 * React Query hooks for Team API endpoints (relay model).
 *
 * Provides hooks for:
 * - Team status and relay connection monitoring
 * - Online node directory
 * - Team configuration management (relay settings)
 * - Data collection policy toggles
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchJson, postJson } from "@/lib/api";
import { API_ENDPOINTS } from "@/lib/constants";
import { usePowerQuery } from "./use-power-query";

// =============================================================================
// Types
// =============================================================================

export interface TeamConfigResponse {
    relay_worker_url: string | null;
    api_key: string | null;
    auto_sync: boolean;
    sync_interval_seconds: number;
    keep_relay_alive: boolean;
}

export interface TeamConfigUpdate {
    relay_worker_url?: string | null;
    api_key?: string | null;
    auto_sync?: boolean | null;
    sync_interval_seconds?: number | null;
    keep_relay_alive?: boolean | null;
}

export interface OnlineNode {
    machine_id: string;
    online: boolean;
    oak_version?: string;
    template_hash?: string;
    capabilities?: string[];
}

export interface RelayStatus {
    connected: boolean;
    worker_url: string | null;
    connected_at: string | null;
    last_heartbeat: string | null;
    error: string | null;
    reconnect_attempts: number;
}

export interface SyncStatus {
    enabled: boolean;
    queue_depth: number;
    last_sync: string | null;
    last_error: string | null;
    events_sent_total: number;
}

export interface TeamStatusResponse {
    configured: boolean;
    connected: boolean;
    relay: RelayStatus | null;
    online_nodes: OnlineNode[];
    sync: SyncStatus | null;
    relay_pending: Record<string, number>;
}

export interface TeamMembersResponse {
    online_nodes: OnlineNode[];
    error?: string;
}

export interface PolicyResponse {
    sync_observations: boolean;
}

export interface PolicyUpdate {
    sync_observations?: boolean;
}

// =============================================================================
// Polling Constants
// =============================================================================

/** Polling interval for team status (5 seconds) */
const TEAM_STATUS_POLL_MS = 5000;

/** Polling interval for member list (15 seconds) */
const TEAM_MEMBERS_POLL_MS = 15000;

// =============================================================================
// Query Keys
// =============================================================================

const teamKeys = {
    all: ["team"] as const,
    status: () => [...teamKeys.all, "status"] as const,
    members: () => [...teamKeys.all, "members"] as const,
    config: () => [...teamKeys.all, "config"] as const,
    policy: () => [...teamKeys.all, "policy"] as const,
};

// =============================================================================
// Query Hooks
// =============================================================================

/** Fetch team status (relay info + online nodes). */
export function useTeamStatus() {
    return usePowerQuery<TeamStatusResponse>({
        queryKey: teamKeys.status(),
        queryFn: ({ signal }) => fetchJson<TeamStatusResponse>(API_ENDPOINTS.TEAM_STATUS, { signal }),
        refetchInterval: TEAM_STATUS_POLL_MS,
        pollCategory: "standard",
        staleTime: 3000,
    });
}

/** Fetch online nodes from the relay. */
export function useTeamMembers() {
    return usePowerQuery<TeamMembersResponse>({
        queryKey: teamKeys.members(),
        queryFn: ({ signal }) => fetchJson<TeamMembersResponse>(API_ENDPOINTS.TEAM_MEMBERS, { signal }),
        refetchInterval: TEAM_MEMBERS_POLL_MS,
        pollCategory: "standard",
        staleTime: 10000,
    });
}

/** Fetch team configuration (one-shot, no polling). */
export function useTeamConfig() {
    return useQuery<TeamConfigResponse>({
        queryKey: teamKeys.config(),
        queryFn: ({ signal }) => fetchJson<TeamConfigResponse>(API_ENDPOINTS.TEAM_CONFIG, { signal }),
    });
}

/** Fetch data collection policy (one-shot, no polling). */
export function useTeamPolicy() {
    return useQuery<PolicyResponse>({
        queryKey: teamKeys.policy(),
        queryFn: ({ signal }) => fetchJson<PolicyResponse>(API_ENDPOINTS.TEAM_POLICY, { signal }),
    });
}

// =============================================================================
// Mutation Hooks
// =============================================================================

/** Update team configuration. */
export function useUpdateTeamConfig() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (update: TeamConfigUpdate) =>
            postJson<TeamConfigResponse>(API_ENDPOINTS.TEAM_CONFIG, update),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: teamKeys.config() });
            queryClient.invalidateQueries({ queryKey: teamKeys.status() });
        },
    });
}

/** Leave the team: disconnect relay and clear all relay config. */
export function useTeamLeave() {
    const queryClient = useQueryClient();
    return useMutation<{ status: string }, Error, void>({
        mutationFn: () => postJson(API_ENDPOINTS.TEAM_LEAVE, {}),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: teamKeys.all });
            queryClient.invalidateQueries({ queryKey: ["cloud-relay-status"] });
        },
    });
}

/** Update data collection policy. */
export function useUpdateTeamPolicy() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (update: PolicyUpdate) =>
            postJson<PolicyResponse>(API_ENDPOINTS.TEAM_POLICY, update),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: teamKeys.policy() });
        },
    });
}
