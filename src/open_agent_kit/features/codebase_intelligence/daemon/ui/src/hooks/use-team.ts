/**
 * React Query hooks for Team API endpoints.
 *
 * Provides hooks for:
 * - Team status and connection monitoring
 * - Member directory
 * - Team configuration management
 * - Data collection policy toggles
 * - API key management (server mode)
 * - Sync control (flush/pull)
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchJson, postJson, deleteJson } from "@/lib/api";
import { API_ENDPOINTS } from "@/lib/constants";
import { usePowerQuery } from "./use-power-query";

// =============================================================================
// Types
// =============================================================================

export interface TeamConfigResponse {
    server_url: string | null;
    auto_sync: boolean;
    sync_interval_seconds: number;
    pull_interval_seconds: number;
    project_slug: string | null;
    transport: string;
    server_mode: boolean;
}

export interface TeamConfigUpdate {
    server_url?: string | null;
    api_key?: string | null;
    auto_sync?: boolean | null;
    sync_interval_seconds?: number | null;
    pull_interval_seconds?: number | null;
    project_slug?: string | null;
    transport?: string | null;
}

export interface TeamStatusResponse {
    configured: boolean;
    server_url: string | null;
    connected: boolean;
    project_id: string | null;
    sync: TeamSyncStatus | null;
    members_online: number;
    pending_approval?: boolean;
    pending_key_id?: string | null;
}

export interface TeamSyncStatus {
    queue_depth?: number;
    last_flush_at?: string | null;
    last_flush_count?: number;
    last_error?: string | null;
    events_sent?: number;
    [key: string]: unknown;
}

export interface TeamMember {
    display_name?: string;
    machine_id: string;
    last_seen?: string;
    event_count?: number;
    [key: string]: unknown;
}

export interface TeamMembersResponse {
    members: TeamMember[];
    error?: string;
}

export interface PolicyResponse {
    collect_activities: boolean;
    collect_prompts: boolean;
    sync_observations: boolean;
    sync_activities: boolean;
    sync_prompts: boolean;
    allow_server_llm: boolean;
}

export interface PolicyUpdate {
    collect_activities?: boolean;
    collect_prompts?: boolean;
    sync_observations?: boolean;
    sync_activities?: boolean;
    sync_prompts?: boolean;
    allow_server_llm?: boolean;
}

export interface KeyResponse {
    id: string;
    name: string;
    machine_id: string | null;
    created_at: string;
    last_used_at: string | null;
    revoked_at: string | null;
    permissions: string;
}

export interface KeyCreateResponse {
    id: string;
    name: string;
    key: string;
}

export interface TeamJoinRequest {
    server_url: string;
}

export interface TeamJoinResponse {
    status: string;
    key_id?: string;
    configured?: boolean;
    connected?: boolean;
}

export interface JoinStatusResponse {
    status: "pending" | "approved" | "rejected";
}

export interface PendingJoinEntry {
    key_id: string;
    display_name?: string;
    machine_id?: string;
    created_at: string;
}

export interface ServerModeResponse {
    enabled: boolean;
    server_url?: string;
    restart_required: boolean;
}

// =============================================================================
// Polling Constants
// =============================================================================

/** Aggressive polling interval for team status (5 seconds) */
const TEAM_STATUS_POLL_MS = 5000;

/** Standard polling interval for member list (15 seconds) */
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
    keys: () => [...teamKeys.all, "keys"] as const,
    pendingJoins: () => [...teamKeys.all, "pending-joins"] as const,
    joinStatus: (keyId: string) => [...teamKeys.all, "join-status", keyId] as const,
};

// =============================================================================
// Query Hooks
// =============================================================================

/** Fetch team connection and sync status with aggressive polling. */
export function useTeamStatus() {
    return usePowerQuery<TeamStatusResponse>({
        queryKey: teamKeys.status(),
        queryFn: ({ signal }) => fetchJson<TeamStatusResponse>(API_ENDPOINTS.TEAM_STATUS, { signal }),
        refetchInterval: TEAM_STATUS_POLL_MS,
        pollCategory: "standard",
        staleTime: 3000,
    });
}

/** Fetch team member directory with standard polling. */
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

/** Fetch API keys (server mode only, one-shot). */
export function useTeamKeys() {
    return useQuery<KeyResponse[]>({
        queryKey: teamKeys.keys(),
        queryFn: ({ signal }) => fetchJson<KeyResponse[]>(API_ENDPOINTS.TEAM_KEYS, { signal }),
        retry: false,
    });
}

// =============================================================================
// Mutation Hooks
// =============================================================================

/** Join a team server (simplified: only server_url needed). */
export function useJoinTeam() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (req: TeamJoinRequest) =>
            postJson<TeamJoinResponse>(API_ENDPOINTS.TEAM_JOIN, req),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: teamKeys.all });
        },
    });
}

/** Leave (disconnect from) a team server. */
export function useLeaveTeam() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: () =>
            postJson<{ status: string }>(API_ENDPOINTS.TEAM_LEAVE, {}),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: teamKeys.all });
        },
    });
}

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

/** Force-flush the outbox to the team server. */
export function useFlushSync() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: () =>
            postJson<{ flushed: number }>(API_ENDPOINTS.TEAM_SYNC_FLUSH, {}),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: teamKeys.status() });
        },
    });
}

/** Force-pull events from the team server. */
export function usePullSync() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: () =>
            postJson<{ applied?: number; status?: string }>(API_ENDPOINTS.TEAM_SYNC_PULL, {}),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: teamKeys.status() });
        },
    });
}

/** Create a new API key (server mode only). */
export function useCreateKey() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (name: string) =>
            postJson<KeyCreateResponse>(API_ENDPOINTS.TEAM_KEYS, { name }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: teamKeys.keys() });
        },
    });
}

/** Revoke an API key (server mode only). */
export function useRevokeKey() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (keyId: string) =>
            deleteJson<{ revoked: boolean }>(`${API_ENDPOINTS.TEAM_KEYS}/${keyId}`),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: teamKeys.keys() });
        },
    });
}

/** Toggle server mode (enable/disable). Requires restart. */
export function useToggleServerMode() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (enable: boolean) =>
            postJson<ServerModeResponse>(API_ENDPOINTS.TEAM_SERVE, { enable }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: teamKeys.all });
        },
    });
}

// =============================================================================
// Join Approval Hooks (server mode)
// =============================================================================

/** Polling interval for join status checks (5 seconds). */
const JOIN_STATUS_POLL_MS = 5000;

/** Fetch pending join requests (server mode only). */
export function usePendingJoins() {
    return useQuery<PendingJoinEntry[]>({
        queryKey: teamKeys.pendingJoins(),
        queryFn: ({ signal }) =>
            fetchJson<PendingJoinEntry[]>(API_ENDPOINTS.TEAM_PENDING_JOINS, { signal }),
        retry: false,
    });
}

/** Approve a pending join request (server mode only). */
export function useApproveJoin() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (keyId: string) =>
            postJson<{ status: string }>(`${API_ENDPOINTS.TEAM_APPROVE_JOIN}/${keyId}`, {}),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: teamKeys.pendingJoins() });
            queryClient.invalidateQueries({ queryKey: teamKeys.members() });
            queryClient.invalidateQueries({ queryKey: teamKeys.keys() });
        },
    });
}

/** Reject a pending join request (server mode only). */
export function useRejectJoin() {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: (keyId: string) =>
            postJson<{ status: string }>(`${API_ENDPOINTS.TEAM_REJECT_JOIN}/${keyId}`, {}),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: teamKeys.pendingJoins() });
            queryClient.invalidateQueries({ queryKey: teamKeys.keys() });
        },
    });
}

/** Poll join status after submitting a join request (client mode). */
export function useJoinStatus(keyId: string | null) {
    return usePowerQuery<JoinStatusResponse>({
        queryKey: teamKeys.joinStatus(keyId ?? ""),
        queryFn: ({ signal }) =>
            fetchJson<JoinStatusResponse>(
                `${API_ENDPOINTS.TEAM_JOIN_STATUS}/${keyId}`,
                { signal },
            ),
        refetchInterval: JOIN_STATUS_POLL_MS,
        pollCategory: "standard",
        enabled: !!keyId,
    });
}
