/**
 * Power-aware query hook that wraps `useQuery` from React Query.
 *
 * ## Usage
 *
 * Use `usePowerQuery` for any query that polls (has `refetchInterval`).
 * Use `useQuery` directly only for one-shot or mutation-triggered queries.
 *
 * ```ts
 * // Fixed interval:
 * usePowerQuery({
 *   queryKey: ['schedules', 'list'],
 *   queryFn: ({ signal }) => fetchSchedules(signal),
 *   refetchInterval: 30_000,
 *   pollCategory: 'standard',
 * });
 *
 * // Callback interval (self-managing):
 * usePowerQuery({
 *   queryKey: ['agent-runs'],
 *   queryFn: ({ signal }) => fetchJson(...),
 *   refetchInterval: (query) => {
 *     const hasActive = query.state.data?.runs.some(r => r.status === 'running');
 *     return hasActive ? 3000 : false;
 *   },
 *   pollCategory: 'self_managing',
 * });
 * ```
 */

import { useQuery } from "@tanstack/react-query";
import type { UseQueryOptions, QueryKey } from "@tanstack/react-query";
import { useContext } from "react";
import { PowerContext } from "./use-power-state";
import type { PowerState } from "./use-power-state";
import {
    POWER_MULTIPLIERS,
    HEARTBEAT_HIDDEN_CAP_MS,
    HEARTBEAT_DEEP_SLEEP_CAP_MS,
} from "@/lib/constants";

// =============================================================================
// Types
// =============================================================================

export type PollCategory = "heartbeat" | "standard" | "realtime" | "self_managing";

type RefetchInterval<TData> =
    | number
    | false
    | ((query: { state: { data: TData | undefined } }) => number | false);

export interface UsePowerQueryOptions<
    TData = unknown,
    TError = Error,
    TQueryKey extends QueryKey = QueryKey,
> extends Omit<UseQueryOptions<TData, TError, TData, TQueryKey>, "refetchInterval"> {
    /** Polling category — determines how the interval scales with power state. */
    pollCategory?: PollCategory;
    /** Base refetch interval (number, false, or callback). */
    refetchInterval?: RefetchInterval<TData>;
}

// =============================================================================
// computePollInterval — pure function, exported for testability
// =============================================================================

/**
 * Apply power-state scaling to a base poll interval.
 *
 * | Category     | active | idle | deep_sleep    | hidden        |
 * |--------------|--------|------|---------------|---------------|
 * | heartbeat    | base   | 2x   | cap 120s      | cap 60s       |
 * | standard     | base   | 2x   | **stop**      | **stop**      |
 * | realtime     | base   | 2x   | **stop**      | **stop**      |
 * | self_managing| base   | 2x   | **stop**      | **stop**      |
 */
export function computePollInterval(
    baseMs: number | false,
    category: PollCategory,
    powerState: PowerState,
): number | false {
    // If the base interval is already disabled, keep it disabled
    if (baseMs === false || baseMs <= 0) return false;

    const multiplier = POWER_MULTIPLIERS[powerState];

    if (category === "heartbeat") {
        // Heartbeat always keeps running, but capped in sleep/hidden
        if (powerState === "hidden") {
            return Math.max(baseMs, HEARTBEAT_HIDDEN_CAP_MS);
        }
        if (powerState === "deep_sleep") {
            return Math.max(baseMs, HEARTBEAT_DEEP_SLEEP_CAP_MS);
        }
        return Math.round(baseMs * multiplier);
    }

    // All other categories: stop in deep_sleep and hidden
    if (!isFinite(multiplier)) return false;

    return Math.round(baseMs * multiplier);
}

// =============================================================================
// usePowerQuery — factory hook
// =============================================================================

export function usePowerQuery<
    TData = unknown,
    TError = Error,
    TQueryKey extends QueryKey = QueryKey,
>(options: UsePowerQueryOptions<TData, TError, TQueryKey>) {
    const { pollCategory, refetchInterval, ...restOptions } = options;
    const powerCtx = useContext(PowerContext);
    const powerState = powerCtx?.state ?? "active";

    // Compute the power-adjusted refetchInterval
    let adjustedInterval: UseQueryOptions<TData, TError, TData, TQueryKey>["refetchInterval"];

    if (refetchInterval === undefined || refetchInterval === false || !pollCategory) {
        // No polling or no category — pass through unchanged
        adjustedInterval = refetchInterval === undefined ? undefined : refetchInterval;
    } else if (typeof refetchInterval === "number") {
        // Fixed interval — compute directly
        adjustedInterval = computePollInterval(refetchInterval, pollCategory, powerState);
    } else {
        // Callback interval — wrap it so the original runs first, then we scale
        const originalFn = refetchInterval;
        adjustedInterval = (query: { state: { data: TData | undefined } }) => {
            const base = originalFn(query);
            return computePollInterval(base, pollCategory, powerState);
        };
    }

    // Heartbeat must keep polling even when the tab is hidden.
    // React Query's refetchIntervalInBackground defaults to false, which
    // stops ALL polling when document.visibilityState === "hidden".
    const refetchInBackground = pollCategory === "heartbeat" ? true : restOptions.refetchIntervalInBackground;

    return useQuery<TData, TError, TData, TQueryKey>({
        ...restOptions,
        refetchInterval: adjustedInterval,
        refetchIntervalInBackground: refetchInBackground,
    } as UseQueryOptions<TData, TError, TData, TQueryKey>);
}
