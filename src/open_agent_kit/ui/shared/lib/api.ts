/**
 * Shared API client factory for daemon UIs.
 *
 * Each daemon UI calls `createApiClient(baseUrl, { getAuthToken })` to get
 * a set of typed fetch helpers that automatically inject the auth token
 * and resolve URLs relative to the daemon's base URL.
 */

interface ApiClientOptions {
    getAuthToken: () => string | null;
}

interface ApiClient {
    API_BASE: string;
    fetchJson: <T = unknown>(url: string, init?: RequestInit) => Promise<T>;
    postJson: <T = unknown>(url: string, body: unknown, extra?: RequestInit) => Promise<T>;
    putJson: <T = unknown>(url: string, body: unknown, extra?: RequestInit) => Promise<T>;
    patchJson: <T = unknown>(url: string, body: unknown, extra?: RequestInit) => Promise<T>;
    deleteJson: <T = unknown>(url: string) => Promise<T>;
}

export function createApiClient(baseUrl: string, options: ApiClientOptions): ApiClient {
    const API_BASE = baseUrl;

    function authHeaders(): HeadersInit {
        const token = options.getAuthToken();
        if (!token) return {};
        return { Authorization: `Bearer ${token}` };
    }

    async function fetchJson<T = unknown>(url: string, init?: RequestInit): Promise<T> {
        const fullUrl = url.startsWith("http") ? url : `${API_BASE}${url}`;
        const response = await fetch(fullUrl, {
            ...init,
            headers: {
                ...authHeaders(),
                ...init?.headers,
            },
        });
        if (!response.ok) {
            const text = await response.text().catch(() => "");
            throw new Error(`${response.status}: ${text}`);
        }
        return response.json() as Promise<T>;
    }

    async function postJson<T = unknown>(url: string, body: unknown, extra?: RequestInit): Promise<T> {
        return fetchJson<T>(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
            ...extra,
        });
    }

    async function putJson<T = unknown>(url: string, body: unknown, extra?: RequestInit): Promise<T> {
        return fetchJson<T>(url, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
            ...extra,
        });
    }

    async function patchJson<T = unknown>(url: string, body: unknown, extra?: RequestInit): Promise<T> {
        return fetchJson<T>(url, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
            ...extra,
        });
    }

    async function deleteJson<T = unknown>(url: string): Promise<T> {
        return fetchJson<T>(url, { method: "DELETE" });
    }

    return { API_BASE, fetchJson, postJson, putJson, patchJson, deleteJson };
}
