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
VALID_SEARCH_TYPES: Final[tuple[str, ...]] = (
    SEARCH_TYPE_ALL,
    SEARCH_TYPE_CODE,
    SEARCH_TYPE_MEMORY,
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

# CI data directory structure (relative to .oak/)
CI_DATA_DIR: Final[str] = "ci"
CI_CHROMA_DIR: Final[str] = "chroma"
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
