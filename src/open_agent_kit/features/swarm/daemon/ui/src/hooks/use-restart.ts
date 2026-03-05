import { useState, useCallback, useRef } from "react";
import { fetchJson, postJson } from "@/lib/api";
import { API_ENDPOINTS, RESTART_POLL_INTERVAL_MS, RESTART_TIMEOUT_MS } from "@/lib/constants";

interface UseRestartReturn {
    restart: () => Promise<void>;
    isRestarting: boolean;
    error: string | null;
}

export function useRestart(): UseRestartReturn {
    const [isRestarting, setIsRestarting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const abortRef = useRef<AbortController | null>(null);

    const restart = useCallback(async () => {
        if (isRestarting) return;

        setIsRestarting(true);
        setError(null);

        try {
            await postJson(API_ENDPOINTS.RESTART, {});

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
            window.location.reload();
        } catch (err) {
            const message = err instanceof Error ? err.message : "Unknown error";
            if (message === "timeout") {
                setError("Restart timed out. Try: oak swarm restart --name <id>");
            } else {
                setError(message);
            }
            setIsRestarting(false);
        }
    }, [isRestarting]);

    return { restart, isRestarting, error };
}
