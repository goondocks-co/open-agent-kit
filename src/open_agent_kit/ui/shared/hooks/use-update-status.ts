/**
 * Shared React Query hooks for self-update status, check, apply, and channel operations.
 *
 * Each hook accepts its endpoint and API function via dependency injection so that
 * team and swarm daemon UIs can bind their own local API clients.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { usePowerQuery } from "./use-power-query";
import type { UpdateStatus, StagedUpdate, LastCheck } from "../components/ui/about-dialog";

export type { UpdateStatus, StagedUpdate, LastCheck };

/** Result returned by a manual update check */
export interface CheckResult {
    update_available: boolean;
    latest_version: string | null;
    channel: string;
    error: string | null;
}

type FetchFn = (url: string, init?: RequestInit) => Promise<unknown>;
type PostFn = (url: string, body: unknown) => Promise<unknown>;
type PutFn = (url: string, body: unknown) => Promise<unknown>;

/** Base polling interval for update status (5 minutes).
 *  Power-scaled: active=5m, idle=10m, deep_sleep/hidden=stopped. */
const UPDATE_STATUS_POLL_INTERVAL_MS = 5 * 60_000;

/**
 * Poll current update status (running version, staged update, last check, etc.).
 *
 * Uses power-aware polling so checks naturally stop when the user is inactive
 * and resume when they return. The backend triggers a PyPI check on read when
 * the last check is stale, so no separate background loop is needed.
 */
export function useUpdateStatus(statusEndpoint: string, fetchJson: FetchFn) {
    return usePowerQuery<UpdateStatus>({
        queryKey: ["update-status"],
        queryFn: ({ signal }: { signal: AbortSignal }) =>
            fetchJson(statusEndpoint, { signal }) as Promise<UpdateStatus>,
        refetchInterval: UPDATE_STATUS_POLL_INTERVAL_MS,
        pollCategory: "standard",
    });
}

/**
 * Trigger an on-demand update check against PyPI.
 * Invalidates update-status on success so UI reflects the latest check result.
 */
export function useUpdateCheck(checkEndpoint: string, postJson: PostFn) {
    const queryClient = useQueryClient();
    return useMutation<CheckResult>({
        mutationFn: () => postJson(checkEndpoint, null) as Promise<CheckResult>,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["update-status"] });
        },
    });
}

/**
 * Apply a staged update (installs the downloaded wheel and restarts).
 */
export function useUpdateApply(applyEndpoint: string, postJson: PostFn) {
    return useMutation({
        mutationFn: () => postJson(applyEndpoint, null),
    });
}

/**
 * Switch the update channel (e.g. "stable" → "beta").
 * Invalidates update-status on success so the new channel is reflected immediately.
 */
export function useUpdateChannel(channelEndpoint: string, putJson: PutFn) {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: (channel: string) =>
            putJson(channelEndpoint, { channel }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["update-status"] });
        },
    });
}
