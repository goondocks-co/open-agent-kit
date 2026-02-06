/**
 * Validation constants: chunk size config, field mappings, config sections.
 */

// =============================================================================
// Field Name Mappings (UI <-> API)
// =============================================================================

/**
 * Maps UI field names to API field names.
 */
export const FIELD_MAPPINGS = {
    /** UI 'max_tokens' maps to API 'context_tokens' */
    MAX_TOKENS_TO_CONTEXT: {
        ui: "max_tokens",
        api: "context_tokens",
    },
    /** UI 'chunk_size' maps to API 'max_chunk_chars' */
    CHUNK_SIZE_TO_MAX_CHUNK: {
        ui: "chunk_size",
        api: "max_chunk_chars",
    },
} as const;

// =============================================================================
// Configuration Sections
// =============================================================================

export const CONFIG_SECTIONS = {
    EMBEDDING: "embedding",
    SUMMARIZATION: "summarization",
} as const;

export type ConfigSection = typeof CONFIG_SECTIONS[keyof typeof CONFIG_SECTIONS];

// =============================================================================
// Validation Constants
// =============================================================================

/** Chunk size as a percentage of context window (80% is recommended) */
export const CHUNK_SIZE_PERCENTAGE = 0.8;

/** Warning threshold - warn if chunk size > this percentage of context */
export const CHUNK_SIZE_WARNING_THRESHOLD = 0.9;

/**
 * Calculate chunk size from context window using the standard percentage.
 */
export function calculateChunkSize(contextWindow: number): number {
    return Math.floor(contextWindow * CHUNK_SIZE_PERCENTAGE);
}

/**
 * Convert a value to an API-safe number (null for empty/invalid values).
 */
export function toApiNumber(value: unknown): number | null {
    if (value === "" || value === undefined || value === null) return null;
    const num = typeof value === "number" ? value : parseInt(String(value), 10);
    return isNaN(num) ? null : num;
}
