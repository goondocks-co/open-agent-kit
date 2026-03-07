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

export const fetchJson = client.fetchJson;
export const postJson = client.postJson;
export const putJson = client.putJson;
export const patchJson = client.patchJson;
export const deleteJson = client.deleteJson;
