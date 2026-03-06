import { createApiClient } from "@oak/ui/lib/api";

/** Read the auth token injected by the server into a meta tag (cached after first read). */
let cachedAuthToken: string | null | undefined;
function getAuthToken(): string | null {
    if (cachedAuthToken === undefined) {
        cachedAuthToken = document.querySelector('meta[name="oak-auth-token"]')?.getAttribute('content') ?? null;
    }
    return cachedAuthToken;
}

const client = createApiClient("", { getAuthToken });

export const API_BASE = client.API_BASE;
export const fetchJson = client.fetchJson;
export const postJson = client.postJson;
export const patchJson = client.patchJson;
export const deleteJson = client.deleteJson;

/** Headers required for devtools mutating endpoints. */
export function devtoolsHeaders(): HeadersInit {
    return { 'X-Devtools-Confirm': 'true' };
}

/** Backup configuration sent/received via the config endpoint under the "backup" key. */
export interface BackupConfig {
    auto_enabled: boolean;
    include_activities: boolean;
    on_upgrade: boolean;
}
