"""Constants for Codebase Intelligence feature.

This module centralizes all magic strings and numbers used throughout the
CI feature, following the project's "no magic strings" principle from
.constitution.md §IV.4.

Constants are organized by domain:
- Search types
- Collection names
- Embedding providers
- Index status
- Agent names (for hooks)
- File patterns
- API defaults
"""

from typing import Final

# =============================================================================
# Search Types
# =============================================================================

SEARCH_TYPE_ALL: Final[str] = "all"
SEARCH_TYPE_CODE: Final[str] = "code"
SEARCH_TYPE_MEMORY: Final[str] = "memory"
SEARCH_TYPE_PLANS: Final[str] = "plans"
VALID_SEARCH_TYPES: Final[tuple[str, ...]] = (
    SEARCH_TYPE_ALL,
    SEARCH_TYPE_CODE,
    SEARCH_TYPE_MEMORY,
    SEARCH_TYPE_PLANS,
)

# =============================================================================
# Vector Store Collections
# =============================================================================

COLLECTION_CODE: Final[str] = "code"
COLLECTION_MEMORY: Final[str] = "memory"

# =============================================================================
# Embedding Providers
# =============================================================================

PROVIDER_OLLAMA: Final[str] = "ollama"
PROVIDER_OPENAI: Final[str] = "openai"
PROVIDER_LMSTUDIO: Final[str] = "lmstudio"
PROVIDER_FASTEMBED: Final[str] = "fastembed"
VALID_PROVIDERS: Final[tuple[str, ...]] = (
    PROVIDER_OLLAMA,
    PROVIDER_OPENAI,
    PROVIDER_LMSTUDIO,
    PROVIDER_FASTEMBED,
)

# Default embedding configuration
# Model must be selected by user after connecting to provider
DEFAULT_PROVIDER: Final[str] = PROVIDER_OLLAMA
DEFAULT_MODEL: Final[str] = ""  # Empty - user must select from discovered models
DEFAULT_BASE_URL: Final[str] = "http://localhost:11434"

# =============================================================================
# Index Status
# =============================================================================

INDEX_STATUS_IDLE: Final[str] = "idle"
INDEX_STATUS_INDEXING: Final[str] = "indexing"
INDEX_STATUS_READY: Final[str] = "ready"
INDEX_STATUS_ERROR: Final[str] = "error"
INDEX_STATUS_UPDATING: Final[str] = "updating"

# =============================================================================
# Daemon Status
# =============================================================================

DAEMON_STATUS_RUNNING: Final[str] = "running"
DAEMON_STATUS_STOPPED: Final[str] = "stopped"
DAEMON_STATUS_HEALTHY: Final[str] = "healthy"
DAEMON_STATUS_UNHEALTHY: Final[str] = "unhealthy"

# =============================================================================
# Agent Names (for hooks)
# =============================================================================

AGENT_CLAUDE: Final[str] = "claude"
AGENT_CURSOR: Final[str] = "cursor"
AGENT_GEMINI: Final[str] = "gemini"
SUPPORTED_HOOK_AGENTS: Final[tuple[str, ...]] = (
    AGENT_CLAUDE,
    AGENT_CURSOR,
    AGENT_GEMINI,
)

# =============================================================================
# File Names and Paths
# =============================================================================

HOOK_FILENAME: Final[str] = "hooks.json"
SETTINGS_FILENAME: Final[str] = "settings.json"
CURSOR_HOOKS_DIRNAME: Final[str] = "hooks"
CURSOR_HOOK_SCRIPT_NAME: Final[str] = "oak-ci-hook.sh"

# CI data directory structure (relative to .oak/)
CI_DATA_DIR: Final[str] = "ci"
CI_CHROMA_DIR: Final[str] = "chroma"
CI_ACTIVITIES_DB_FILENAME: Final[str] = "activities.db"
CI_LOG_FILE: Final[str] = "daemon.log"
CI_PID_FILE: Final[str] = "daemon.pid"
CI_PORT_FILE: Final[str] = "daemon.port"

# =============================================================================
# API Defaults
# =============================================================================

DEFAULT_SEARCH_LIMIT: Final[int] = 20
MAX_SEARCH_LIMIT: Final[int] = 100

DEFAULT_CONTEXT_LIMIT: Final[int] = 10
DEFAULT_CONTEXT_MEMORY_LIMIT: Final[int] = 5
DEFAULT_MAX_CONTEXT_TOKENS: Final[int] = 2000

# Preview and summary lengths
DEFAULT_PREVIEW_LENGTH: Final[int] = 200
DEFAULT_SUMMARY_PREVIEW_LENGTH: Final[int] = 100
DEFAULT_RELATED_QUERY_LENGTH: Final[int] = 500

# Memory listing defaults
DEFAULT_MEMORY_LIST_LIMIT: Final[int] = 50

# Related chunks limit
DEFAULT_RELATED_CHUNKS_LIMIT: Final[int] = 5

# Token estimation: ~4 characters per token
CHARS_PER_TOKEN_ESTIMATE: Final[int] = 4

# =============================================================================
# Chunk Types
# =============================================================================

CHUNK_TYPE_FUNCTION: Final[str] = "function"
CHUNK_TYPE_CLASS: Final[str] = "class"
CHUNK_TYPE_METHOD: Final[str] = "method"
CHUNK_TYPE_MODULE: Final[str] = "module"
CHUNK_TYPE_UNKNOWN: Final[str] = "unknown"

# =============================================================================
# Memory Types
# =============================================================================
# NOTE: Memory types are now defined in schema.yaml (features/codebase-intelligence/schema.yaml)
# and loaded dynamically. The MemoryType enum in daemon/models.py provides validation.
# See: open_agent_kit.features.codebase_intelligence.activity.prompts.CISchema

# Special memory type for plans (indexed from prompt_batches, not memory_observations)
MEMORY_TYPE_PLAN: Final[str] = "plan"

# =============================================================================
# Batching and Performance
# =============================================================================

DEFAULT_EMBEDDING_BATCH_SIZE: Final[int] = 100
DEFAULT_INDEXING_BATCH_SIZE: Final[int] = 50

# Timeout for indexing operations (1 hour default - large codebases need time)
DEFAULT_INDEXING_TIMEOUT_SECONDS: Final[float] = 3600.0

# =============================================================================
# Resiliency and Recovery
# =============================================================================

# Auto-end batches stuck in 'active' status longer than this (5 minutes)
# This is a safety net - batches should normally be closed by Stop hook or
# the next UserPromptSubmit. A shorter timeout ensures eventual consistency.
BATCH_ACTIVE_TIMEOUT_SECONDS: Final[int] = 300

# Auto-end sessions inactive longer than this (1 hour)
SESSION_INACTIVE_TIMEOUT_SECONDS: Final[int] = 3600

# =============================================================================
# Backup Configuration
# =============================================================================

# Backup file location (in preserved oak/ directory, committed to git)
CI_HISTORY_BACKUP_DIR: Final[str] = "oak/data"
CI_HISTORY_BACKUP_FILE: Final[str] = "ci_history.sql"

# =============================================================================
# Logging
# =============================================================================

LOG_LEVEL_DEBUG: Final[str] = "DEBUG"
LOG_LEVEL_INFO: Final[str] = "INFO"
LOG_LEVEL_WARNING: Final[str] = "WARNING"
LOG_LEVEL_ERROR: Final[str] = "ERROR"
VALID_LOG_LEVELS: Final[tuple[str, ...]] = (
    LOG_LEVEL_DEBUG,
    LOG_LEVEL_INFO,
    LOG_LEVEL_WARNING,
    LOG_LEVEL_ERROR,
)

# =============================================================================
# Input Validation
# =============================================================================

MAX_QUERY_LENGTH: Final[int] = 10000
MIN_QUERY_LENGTH: Final[int] = 1
MAX_OBSERVATION_LENGTH: Final[int] = 50000

# =============================================================================
# Session and Hook Events
# =============================================================================

HOOK_EVENT_SESSION_START: Final[str] = "session-start"
HOOK_EVENT_SESSION_END: Final[str] = "session-end"
HOOK_EVENT_POST_TOOL_USE: Final[str] = "post-tool-use"
HOOK_EVENT_BEFORE_PROMPT: Final[str] = "before-prompt"
HOOK_EVENT_STOP: Final[str] = "stop"
HOOK_EVENT_PROMPT_SUBMIT: Final[str] = "prompt-submit"

# Hook origins for deduplication when multiple configs fire
HOOK_ORIGIN_CLAUDE_CONFIG: Final[str] = "claude_config"
HOOK_ORIGIN_CURSOR_CONFIG: Final[str] = "cursor_config"

# Hook payload field names
HOOK_FIELD_SESSION_ID: Final[str] = "session_id"
HOOK_FIELD_CONVERSATION_ID: Final[str] = "conversation_id"
HOOK_FIELD_AGENT: Final[str] = "agent"
HOOK_FIELD_PROMPT: Final[str] = "prompt"
HOOK_FIELD_TOOL_NAME: Final[str] = "tool_name"
HOOK_FIELD_TOOL_INPUT: Final[str] = "tool_input"
HOOK_FIELD_TOOL_OUTPUT_B64: Final[str] = "tool_output_b64"
HOOK_FIELD_HOOK_ORIGIN: Final[str] = "hook_origin"
HOOK_FIELD_HOOK_EVENT_NAME: Final[str] = "hook_event_name"
HOOK_FIELD_GENERATION_ID: Final[str] = "generation_id"
HOOK_FIELD_TOOL_USE_ID: Final[str] = "tool_use_id"

# Hook deduplication configuration
HOOK_DEDUP_CACHE_MAX: Final[int] = 500
HOOK_DEDUP_HASH_ALGORITHM: Final[str] = "sha256"
HOOK_DROP_LOG_TAG: Final[str] = "[DROP]"

# Tags for auto-captured observations
TAG_AUTO_CAPTURED: Final[str] = "auto-captured"
TAG_SESSION_SUMMARY: Final[str] = "session-summary"

# =============================================================================
# Confidence Levels (model-agnostic)
# =============================================================================

# Confidence levels for search results.
# These are model-agnostic and based on relative positioning within
# a result set, not absolute similarity scores (which vary significantly
# across embedding models like nomic-embed-text vs bge-m3).
CONFIDENCE_HIGH: Final[str] = "high"
CONFIDENCE_MEDIUM: Final[str] = "medium"
CONFIDENCE_LOW: Final[str] = "low"
VALID_CONFIDENCE_LEVELS: Final[tuple[str, ...]] = (
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
    CONFIDENCE_LOW,
)

# Thresholds for confidence bands (based on normalized position in result set)
# These define what percentage of the score range qualifies for each level
CONFIDENCE_HIGH_THRESHOLD: Final[float] = 0.7  # Top 30% of score range
CONFIDENCE_MEDIUM_THRESHOLD: Final[float] = 0.4  # Top 60% of score range
# Minimum gap ratio to boost confidence (gap to next / total range)
CONFIDENCE_GAP_BOOST_THRESHOLD: Final[float] = 0.15
# Minimum score range to use range-based calculation (below this, use fallback)
CONFIDENCE_MIN_MEANINGFUL_RANGE: Final[float] = 0.001


# =============================================================================
# Summarization Providers
# =============================================================================

SUMMARIZATION_PROVIDER_OLLAMA: Final[str] = "ollama"
SUMMARIZATION_PROVIDER_OPENAI: Final[str] = "openai"
SUMMARIZATION_PROVIDER_LMSTUDIO: Final[str] = "lmstudio"
VALID_SUMMARIZATION_PROVIDERS: Final[tuple[str, ...]] = (
    SUMMARIZATION_PROVIDER_OLLAMA,
    SUMMARIZATION_PROVIDER_OPENAI,
    SUMMARIZATION_PROVIDER_LMSTUDIO,
)

# Default summarization configuration
# Model must be selected by user after connecting to provider
DEFAULT_SUMMARIZATION_PROVIDER: Final[str] = SUMMARIZATION_PROVIDER_OLLAMA
DEFAULT_SUMMARIZATION_MODEL: Final[str] = ""  # Empty - user must select from discovered models
DEFAULT_SUMMARIZATION_BASE_URL: Final[str] = "http://localhost:11434"
# Timeout for LLM inference (180s to accommodate local model loading + inference)
# Local Ollama can take 30-60s to load a model on first request, plus inference time
DEFAULT_SUMMARIZATION_TIMEOUT: Final[float] = 180.0
# Extended timeout for first LLM request when model may need loading (warmup)
WARMUP_TIMEOUT_MULTIPLIER: Final[float] = 2.0

# =============================================================================
# Prompt Source Types
# =============================================================================
# Source types categorize prompts by origin for different processing strategies.
# - user: User-initiated prompts (extract memories normally)
# - agent_notification: Background agent completions (preserve but skip memory extraction)
# - plan: Plan mode activities (extract plan as decision memory)
# - system: System messages (skip memory extraction)

PROMPT_SOURCE_USER: Final[str] = "user"
PROMPT_SOURCE_AGENT: Final[str] = "agent_notification"
PROMPT_SOURCE_SYSTEM: Final[str] = "system"
PROMPT_SOURCE_PLAN: Final[str] = "plan"

VALID_PROMPT_SOURCES: Final[tuple[str, ...]] = (
    PROMPT_SOURCE_USER,
    PROMPT_SOURCE_AGENT,
    PROMPT_SOURCE_SYSTEM,
    PROMPT_SOURCE_PLAN,
)

# =============================================================================
# Internal Message Detection
# =============================================================================
# Prefixes used to detect internal/system messages that should not generate memories.
# Plan detection is handled dynamically via AgentService.get_all_plan_directories().

INTERNAL_MESSAGE_PREFIXES: Final[tuple[str, ...]] = (
    "<task-notification>",  # Background agent completion messages
    "<system-",  # System reminder/prompt messages
)
