import { useState, useCallback, useRef } from "react";
import { fetchJson } from "@/lib/api";
import { API_ENDPOINTS, RESTART_POLL_INTERVAL_MS, RESTART_TIMEOUT_MS, UPDATE_BANNER } from "@/lib/constants";

interface UseRestartOptions {
    endpoint?: string;
    onSuccess?: () => void;
    cliCommand?: string;
}

interface UseRestartReturn {
    restart: () => Promise<void>;
    isRestarting: boolean;
    error: string | null;
}

export function useRestart(options?: UseRestartOptions): UseRestartReturn {
    const endpoint = options?.endpoint ?? API_ENDPOINTS.SELF_RESTART;
    const onSuccess = options?.onSuccess;
    const cliCommand = options?.cliCommand || "oak";
    const [isRestarting, setIsRestarting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const abortRef = useRef<AbortController | null>(null);

    const restart = useCallback(async () => {
        if (isRestarting) return;

        setIsRestarting(true);
        setError(null);

        try {
            // Trigger upgrade-and-restart (or plain restart).
            // The server now runs the upgrade in-process and returns
            // success/failure before initiating the restart.
            const result = await fetchJson<{ status: string; detail?: string }>(
                endpoint,
                { method: "POST" },
            );

            // If already up to date, just reload
            if (result?.status === UPDATE_BANNER.STATUS_UP_TO_DATE) {
                window.location.reload();
                return;
            }

            // Poll health endpoint until daemon is back
            const deadline = Date.now() + RESTART_TIMEOUT_MS;
            abortRef.current = new AbortController();

            const pollHealth = (): Promise<void> =>
                new Promise((resolve, reject) => {
                    const check = async () => {
                        if (Date.now() > deadline) {
                            reject(new Error("timeout"));
                            return;
                        }
                        try {
                            await fetchJson(API_ENDPOINTS.HEALTH, {
                                signal: abortRef.current?.signal,
                            });
                            resolve();
                        } catch {
                            setTimeout(check, RESTART_POLL_INTERVAL_MS);
                        }
                    };
                    // Initial delay to let daemon shut down
                    setTimeout(check, RESTART_POLL_INTERVAL_MS);
                });

            await pollHealth();
            // Upgrade succeeded and daemon is back — notify caller before reload
            onSuccess?.();
            window.location.reload();
        } catch (err) {
            // Show the server's error detail when available (e.g. upgrade
            // failure reasons), otherwise fall back to generic messages.
            const message = err instanceof Error ? err.message : "Unknown error";
            if (message === "timeout") {
                setError(`Restart timed out. Try: ${cliCommand} team restart`);
            } else {
                setError(message);
            }
            setIsRestarting(false);
        }
    }, [isRestarting, endpoint, onSuccess, cliCommand]);

    return { restart, isRestarting, error };
}
