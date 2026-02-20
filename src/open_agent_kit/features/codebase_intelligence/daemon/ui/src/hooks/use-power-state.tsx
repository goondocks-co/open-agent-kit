/**
 * Power state management for the daemon UI.
 *
 * Tracks user activity and page visibility to determine a power state
 * (`active`, `idle`, `deep_sleep`, `hidden`) that polling hooks use to
 * scale back or stop their intervals when the user is away.
 *
 * ## State Machine
 *
 * ```
 * Active ──(60s idle)──> Idle ──(5min idle)──> DeepSleep
 *   ^                      ^                        |
 *   └──(user activity)─────┴───(user activity)──────┘
 *
 * Any ──(tab hidden)──> Hidden
 * Hidden ──(tab visible)──> Active
 * ```
 */

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
    POWER_IDLE_THRESHOLD_MS,
    POWER_DEEP_SLEEP_THRESHOLD_MS,
    POWER_ACTIVITY_DEBOUNCE_MS,
} from "@/lib/constants";

// =============================================================================
// Types
// =============================================================================

export type PowerState = "active" | "idle" | "deep_sleep" | "hidden";

interface PowerContextValue {
    state: PowerState;
    /** Call this to signal user activity and wake from idle/deep_sleep. */
    reportActivity: () => void;
}

// =============================================================================
// Context
// =============================================================================

/** Exported for direct `useContext` access in callbacks where the hook can't be used. */
export const PowerContext = createContext<PowerContextValue | null>(null);

// =============================================================================
// Provider
// =============================================================================

const ACTIVITY_EVENTS: (keyof DocumentEventMap)[] = [
    "mousemove",
    "mousedown",
    "keydown",
    "scroll",
    "touchstart",
];

export function PowerProvider({ children }: { children: ReactNode }) {
    const [state, setState] = useState<PowerState>(() =>
        document.visibilityState === "hidden" ? "hidden" : "active"
    );

    // Refs to manage timers without re-renders
    const idleTimerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
    const deepSleepTimerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
    const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
    const lastActivityRef = useRef(Date.now());

    const clearTimers = useCallback(() => {
        if (idleTimerRef.current !== undefined) {
            clearTimeout(idleTimerRef.current);
            idleTimerRef.current = undefined;
        }
        if (deepSleepTimerRef.current !== undefined) {
            clearTimeout(deepSleepTimerRef.current);
            deepSleepTimerRef.current = undefined;
        }
    }, []);

    const startTimers = useCallback(() => {
        clearTimers();
        idleTimerRef.current = setTimeout(() => {
            setState((prev) => (prev === "hidden" ? prev : "idle"));
        }, POWER_IDLE_THRESHOLD_MS);
        deepSleepTimerRef.current = setTimeout(() => {
            setState((prev) => (prev === "hidden" ? prev : "deep_sleep"));
        }, POWER_DEEP_SLEEP_THRESHOLD_MS);
    }, [clearTimers]);

    const reportActivity = useCallback(() => {
        lastActivityRef.current = Date.now();
        setState((prev) => (prev === "hidden" ? prev : "active"));
        startTimers();
    }, [startTimers]);

    // Debounced handler for high-frequency DOM events
    const handleActivity = useCallback(() => {
        if (debounceTimerRef.current !== undefined) return;
        debounceTimerRef.current = setTimeout(() => {
            debounceTimerRef.current = undefined;
            reportActivity();
        }, POWER_ACTIVITY_DEBOUNCE_MS);
    }, [reportActivity]);

    // Visibility change handler
    useEffect(() => {
        function handleVisibility() {
            if (document.visibilityState === "hidden") {
                clearTimers();
                setState("hidden");
            } else {
                // Tab became visible — go straight to active and restart timers
                setState("active");
                lastActivityRef.current = Date.now();
                startTimers();
            }
        }

        document.addEventListener("visibilitychange", handleVisibility);
        return () => document.removeEventListener("visibilitychange", handleVisibility);
    }, [clearTimers, startTimers]);

    // Window focus (catches alt-tab back without mouse movement)
    useEffect(() => {
        function handleFocus() {
            reportActivity();
        }
        window.addEventListener("focus", handleFocus);
        return () => window.removeEventListener("focus", handleFocus);
    }, [reportActivity]);

    // DOM activity events (mousemove, keydown, etc.)
    useEffect(() => {
        for (const event of ACTIVITY_EVENTS) {
            document.addEventListener(event, handleActivity, { passive: true });
        }
        return () => {
            for (const event of ACTIVITY_EVENTS) {
                document.removeEventListener(event, handleActivity);
            }
        };
    }, [handleActivity]);

    // Start idle/deep-sleep timers on mount
    useEffect(() => {
        startTimers();
        return clearTimers;
    }, [startTimers, clearTimers]);

    // Clean up debounce timer on unmount
    useEffect(() => {
        return () => {
            if (debounceTimerRef.current !== undefined) {
                clearTimeout(debounceTimerRef.current);
            }
        };
    }, []);

    return (
        <PowerContext.Provider value={{ state, reportActivity }}>
            {children}
        </PowerContext.Provider>
    );
}

// =============================================================================
// Hook
// =============================================================================

/** Read the current power state and access `reportActivity`. */
export function usePowerState(): PowerContextValue {
    const ctx = useContext(PowerContext);
    if (!ctx) {
        throw new Error("usePowerState must be used within a <PowerProvider>");
    }
    return ctx;
}
