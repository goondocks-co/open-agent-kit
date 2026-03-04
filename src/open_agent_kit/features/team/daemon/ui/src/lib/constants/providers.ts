/**
 * Provider configuration constants.
 *
 * Covers embedding providers, agent providers, display names, URLs,
 * recommended models, and provider dropdown options.
 */

// =============================================================================
// Embedding Provider Configuration
// =============================================================================

/** Supported embedding/LLM provider types */
export const PROVIDER_TYPES = {
    OLLAMA: "ollama",
    LMSTUDIO: "lmstudio",
    OPENAI: "openai",
} as const;

export type ProviderType = typeof PROVIDER_TYPES[keyof typeof PROVIDER_TYPES];

/** Default base URLs for each provider */
export const DEFAULT_PROVIDER_URLS: Record<ProviderType, string> = {
    [PROVIDER_TYPES.OLLAMA]: "http://localhost:11434",
    [PROVIDER_TYPES.LMSTUDIO]: "http://localhost:1234",
    [PROVIDER_TYPES.OPENAI]: "http://localhost:1234",
};

/** Human-readable provider display names */
export const PROVIDER_DISPLAY_NAMES: Record<ProviderType, string> = {
    [PROVIDER_TYPES.OLLAMA]: "Ollama",
    [PROVIDER_TYPES.LMSTUDIO]: "LM Studio",
    [PROVIDER_TYPES.OPENAI]: "OpenAI Compatible",
};

/** Provider options for Select dropdowns */
export const PROVIDER_OPTIONS = [
    { value: PROVIDER_TYPES.OLLAMA, label: PROVIDER_DISPLAY_NAMES.ollama },
    { value: PROVIDER_TYPES.LMSTUDIO, label: PROVIDER_DISPLAY_NAMES.lmstudio },
    { value: PROVIDER_TYPES.OPENAI, label: PROVIDER_DISPLAY_NAMES.openai },
] as const;

/**
 * Get the default URL for a provider type.
 */
export function getDefaultProviderUrl(provider: string): string {
    return DEFAULT_PROVIDER_URLS[provider as ProviderType] ?? DEFAULT_PROVIDER_URLS.ollama;
}

// =============================================================================
// Agent Provider Configuration (for Claude Agent SDK)
// =============================================================================

/** Agent execution provider types (different from embedding providers) */
export const AGENT_PROVIDER_TYPES = {
    CLOUD: "cloud",
    OLLAMA: "ollama",
    LMSTUDIO: "lmstudio",
} as const;

export type AgentProviderType = typeof AGENT_PROVIDER_TYPES[keyof typeof AGENT_PROVIDER_TYPES];

/** Local provider reliability disclaimer shown in Agent Settings UI */
export const AGENT_LOCAL_PROVIDER_EXPERIMENTAL_NOTE =
    "Local provider APIs are experimental and may not work consistently due to upstream changes outside OAK's control.";

/** Human-readable agent provider display names */
export const AGENT_PROVIDER_DISPLAY_NAMES: Record<AgentProviderType, string> = {
    [AGENT_PROVIDER_TYPES.CLOUD]: "Claude Code (Default)",
    [AGENT_PROVIDER_TYPES.OLLAMA]: "Ollama (Local, Experimental)",
    [AGENT_PROVIDER_TYPES.LMSTUDIO]: "LM Studio (Local, Experimental)",
};

/** Default base URLs for agent providers */
export const AGENT_PROVIDER_DEFAULT_URLS: Record<AgentProviderType, string> = {
    [AGENT_PROVIDER_TYPES.CLOUD]: "",  // No URL needed for cloud
    [AGENT_PROVIDER_TYPES.OLLAMA]: "http://localhost:11434",
    [AGENT_PROVIDER_TYPES.LMSTUDIO]: "http://localhost:1234",
};

/** Agent provider options for Select dropdowns */
export const AGENT_PROVIDER_OPTIONS = [
    { value: AGENT_PROVIDER_TYPES.CLOUD, label: AGENT_PROVIDER_DISPLAY_NAMES.cloud },
    { value: AGENT_PROVIDER_TYPES.OLLAMA, label: AGENT_PROVIDER_DISPLAY_NAMES.ollama },
    { value: AGENT_PROVIDER_TYPES.LMSTUDIO, label: AGENT_PROVIDER_DISPLAY_NAMES.lmstudio },
] as const;

/** Recommended models for local providers */
export const AGENT_PROVIDER_RECOMMENDED_MODELS: Record<AgentProviderType, string[]> = {
    [AGENT_PROVIDER_TYPES.CLOUD]: [],
    [AGENT_PROVIDER_TYPES.OLLAMA]: ["qwen3:32b", "glm-4.7:latest", "gpt-oss:20b"],
    [AGENT_PROVIDER_TYPES.LMSTUDIO]: ["qwen-2.5-coder-32b", "llama-3.3-70b"],
};
