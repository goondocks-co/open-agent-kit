import { useMutation } from "@tanstack/react-query";
import { postJson } from "@/lib/api";
import { API_ENDPOINTS } from "@/lib/constants";
import { extractMcpText, parseMcpEnvelope } from "@/lib/mcp";

export interface FetchedChunk {
    id: string;
    content: string;
    tokens: number;
}

export interface FetchResult {
    results: FetchedChunk[];
    total_tokens: number;
}

export interface FetchParams {
    ids: string[];
    project_slug: string;
}

function isFetchResult(obj: Record<string, unknown>): obj is Record<string, unknown> & FetchResult {
    return Array.isArray(obj.results);
}

/**
 * Extract the inner payload from a tool-result envelope.
 *
 * The swarm daemon proxies MCP tool calls and returns the raw relay response:
 *   `{type: "tool_result", result: {isError, content: [{type: "text", text: "..."}]}}`
 *
 * If the response is already unwrapped, returns it as-is.
 */
function unwrapToolResult(raw: unknown): unknown {
    const obj = raw as Record<string, unknown>;

    // Direct error from swarm daemon
    if (obj.error && typeof obj.error === "string") {
        throw new Error(obj.error);
    }

    // MCP tool-result envelope from relay
    if (obj.type === "tool_result" && obj.result) {
        const result = obj.result as Record<string, unknown>;
        if (result.isError) {
            const text = extractMcpText(result);
            throw new Error(text ?? "Tool call failed");
        }
        const text = extractMcpText(result);
        if (text) {
            try {
                return JSON.parse(text);
            } catch {
                throw new Error(`Invalid JSON in tool result: ${text.slice(0, 200)}`);
            }
        }
    }

    return raw;
}

export function useSwarmFetch() {
    return useMutation<FetchResult, Error, FetchParams>({
        mutationFn: async (params) => {
            const raw = await postJson(API_ENDPOINTS.SWARM_FETCH, {
                ids: params.ids,
                project_slug: params.project_slug,
            });

            const unwrapped = unwrapToolResult(raw);
            const result = parseMcpEnvelope<FetchResult>(
                unwrapped,
                isFetchResult,
                { results: [], total_tokens: 0 },
            );

            if (result.results.length === 0) {
                throw new Error("No results returned for the requested IDs");
            }

            return result;
        },
    });
}
