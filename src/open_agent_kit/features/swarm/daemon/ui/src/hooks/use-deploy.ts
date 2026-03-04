import { useMutation } from "@tanstack/react-query";
import { usePowerQuery } from "@oak/ui/hooks/use-power-query";
import { fetchJson, postJson } from "@/lib/api";
import { API_ENDPOINTS, DEPLOY_POLL_MS } from "@/lib/constants";

interface DeployStatus {
    scaffolded: boolean;
    scaffold_dir: string | null;
    node_modules_installed: boolean;
    worker_url: string | null;
    swarm_id: string;
}

interface AuthStatus {
    authenticated: boolean;
    wrangler_available: boolean;
    account_name: string | null;
    account_id?: string | null;
}

export function useDeployStatus() {
    return usePowerQuery<DeployStatus>({
        queryKey: ["deploy", "status"],
        queryFn: ({ signal }) => fetchJson(API_ENDPOINTS.DEPLOY_STATUS, { signal }),
        refetchInterval: DEPLOY_POLL_MS,
        pollCategory: "standard",
    });
}

export function useDeployAuth() {
    return usePowerQuery<AuthStatus>({
        queryKey: ["deploy", "auth"],
        queryFn: ({ signal }) => fetchJson(API_ENDPOINTS.DEPLOY_AUTH, { signal }),
        refetchInterval: false,
    });
}

export function useDeployScaffold() {
    return useMutation<{ success: boolean; error?: string }, Error, { force?: boolean }>({
        mutationFn: (params) => postJson(API_ENDPOINTS.DEPLOY_SCAFFOLD, params),
    });
}

export function useDeployInstall() {
    return useMutation<{ success: boolean; output: string }, Error, void>({
        mutationFn: () => postJson(API_ENDPOINTS.DEPLOY_INSTALL, {}),
    });
}

export function useDeployRun() {
    return useMutation<{ success: boolean; worker_url?: string; output: string }, Error, void>({
        mutationFn: () => postJson(API_ENDPOINTS.DEPLOY_RUN, {}),
    });
}
