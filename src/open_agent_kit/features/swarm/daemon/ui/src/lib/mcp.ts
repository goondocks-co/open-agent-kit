/**
 * MCP envelope parsing utilities.
 *
 * The swarm worker proxies MCP tool-call responses which arrive in the
 * standard envelope format: `{content: [{type: "text", text: "...json..."}]}`.
 * These helpers extract and parse the inner payload.
 */

/**
 * Extract the text content from an MCP tool-call response envelope.
 *
 * Handles two shapes:
 * 1. Already-unwrapped JSON (passthrough)
 * 2. `{content: [{type: "text", text: "..."}]}` — standard MCP envelope
 *
 * Returns `null` if the envelope cannot be parsed.
 */
export function extractMcpText(raw: unknown): string | null {
    const obj = raw as Record<string, unknown>;

    if (Array.isArray(obj.content)) {
        const first = (obj.content as Array<Record<string, unknown>>)[0];
        if (first?.type === "text" && typeof first.text === "string") {
            return first.text;
        }
    }

    return null;
}

/**
 * Parse an MCP envelope, extracting and JSON-parsing the inner text payload.
 * If the response is already unwrapped (matches `guard`), returns it directly.
 *
 * @param raw - The raw response from the swarm daemon
 * @param guard - A function that checks if `raw` is already the expected shape
 */
export function parseMcpEnvelope<T>(
    raw: unknown,
    guard: (obj: Record<string, unknown>) => obj is Record<string, unknown> & T,
    fallback: T,
): T {
    const obj = raw as Record<string, unknown>;

    // Already unwrapped
    if (guard(obj)) {
        return obj as unknown as T;
    }

    // MCP envelope
    const text = extractMcpText(raw);
    if (text) {
        try {
            const parsed = JSON.parse(text) as Record<string, unknown>;
            if (guard(parsed)) {
                return parsed as unknown as T;
            }
        } catch {
            // fall through to fallback
        }
    }

    return fallback;
}
