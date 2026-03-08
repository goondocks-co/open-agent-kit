import { useState, useCallback, useRef, useEffect } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface UseRestartOptions {
    /** POST endpoint that triggers the restart (e.g. "/api/self-restart"). */
    endpoint: string;
    /** GET endpoint polled until the daemon is back (e.g. "/api/health"). */
    healthEndpoint: string;
    /** Interval between health-check polls (ms). */
    pollIntervalMs: number;
    /** Maximum time to wait for the daemon to come back (ms). */
    timeoutMs: number;
    /** Hint shown in the timeout error message (e.g. "oak team restart"). */
    timeoutHint: string;
    /**
     * Status value that means "already up to date — just reload".
     * If the restart response's `status` field equals this, the hook skips
     * polling and reloads immediately.  Pass `undefined` to disable.
     */
    upToDateStatus?: string;
    /** Called after the daemon is confirmed healthy, just before reload. */
    onSuccess?: () => void;
    /**
     * Wrapper around `fetch` that returns parsed JSON.
     * Each consumer provides its own (e.g. the app-level `fetchJson`).
     */
    fetchJson: (url: string, init?: RequestInit) => Promise<unknown>;
    /**
     * Function used to POST the restart request.
     * Defaults to calling `fetchJson(endpoint, { method: "POST" })`.
     */
    postRestart?: (endpoint: string) => Promise<unknown>;
}

export interface UseRestartReturn {
    restart: () => Promise<void>;
    isRestarting: boolean;
    error: string | null;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useRestart(options: UseRestartOptions): UseRestartReturn {
    const {
        endpoint,
        healthEndpoint,
        pollIntervalMs,
        timeoutMs,
        timeoutHint,
        upToDateStatus,
        onSuccess,
        fetchJson,
        postRestart,
    } = options;

    const [isRestarting, setIsRestarting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const abortRef = useRef<AbortController | null>(null);

    // Abort polling on unmount so we don't leak timers.
    useEffect(() => () => abortRef.current?.abort(), []);

    const restart = useCallback(async () => {
        if (isRestarting) return;

        setIsRestarting(true);
        setError(null);

        try {
            // Trigger the restart (or upgrade-and-restart).
            const result = postRestart
                ? await postRestart(endpoint)
                : await fetchJson(endpoint, { method: "POST" });

            // If already up to date, just reload.
            if (
                upToDateStatus &&
                typeof result === "object" &&
                result !== null &&
                "status" in result &&
                (result as Record<string, unknown>).status === upToDateStatus
            ) {
                window.location.reload();
                return;
            }

            // Poll health endpoint until daemon is back.
            const deadline = Date.now() + timeoutMs;
            abortRef.current = new AbortController();

            const pollHealth = (): Promise<void> =>
                new Promise((resolve, reject) => {
                    const check = async () => {
                        if (abortRef.current?.signal.aborted) {
                            reject(new Error("aborted"));
                            return;
                        }
                        if (Date.now() > deadline) {
                            reject(new Error("timeout"));
                            return;
                        }
                        try {
                            await fetchJson(healthEndpoint, {
                                signal: abortRef.current?.signal,
                            });
                            resolve();
                        } catch {
                            setTimeout(check, pollIntervalMs);
                        }
                    };
                    // Initial delay to let daemon shut down.
                    setTimeout(check, pollIntervalMs);
                });

            await pollHealth();
            onSuccess?.();
            window.location.reload();
        } catch (err) {
            const message = err instanceof Error ? err.message : "Unknown error";
            if (message === "timeout") {
                setError(`Restart timed out. Try: ${timeoutHint}`);
            } else if (message !== "aborted") {
                setError(message);
            }
            setIsRestarting(false);
        }
    }, [
        isRestarting,
        endpoint,
        healthEndpoint,
        pollIntervalMs,
        timeoutMs,
        timeoutHint,
        upToDateStatus,
        onSuccess,
        fetchJson,
        postRestart,
    ]);

    return { restart, isRestarting, error };
}
