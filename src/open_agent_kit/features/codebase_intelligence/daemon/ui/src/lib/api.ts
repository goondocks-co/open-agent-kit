export const API_BASE = import.meta.env.DEV ? 'http://localhost:37800' : '';

export async function fetchJson<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const url = `${API_BASE}${endpoint}`;

    // Merge headers, ensuring Content-Type is set for JSON bodies
    const headers: HeadersInit = {
        ...(options?.body ? { 'Content-Type': 'application/json' } : {}),
        ...options?.headers,
    };

    const response = await fetch(url, {
        ...options,
        headers,
    });

    if (!response.ok) {
        throw new Error(`API Error ${response.status}: ${response.statusText}`);
    }

    return response.json();
}
