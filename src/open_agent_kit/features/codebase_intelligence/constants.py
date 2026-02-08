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
SEARCH_TYPE_SESSIONS: Final[str] = "sessions"
VALID_SEARCH_TYPES: Final[tuple[str, ...]] = (
    SEARCH_TYPE_ALL,
    SEARCH_TYPE_CODE,
    SEARCH_TYPE_MEMORY,
    SEARCH_TYPE_PLANS,
    SEARCH_TYPE_SESSIONS,
)

# =============================================================================
# Embedding Providers
# =============================================================================

PROVIDER_OLLAMA: Final[str] = "ollama"
PROVIDER_OPENAI: Final[str] = "openai"
PROVIDER_LMSTUDIO: Final[str] = "lmstudio"
VALID_PROVIDERS: Final[tuple[str, ...]] = (
    PROVIDER_OLLAMA,
    PROVIDER_OPENAI,
    PROVIDER_LMSTUDIO,
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
AGENT_COPILOT: Final[str] = "copilot"
AGENT_CODEX: Final[str] = "codex"
SUPPORTED_HOOK_AGENTS: Final[tuple[str, ...]] = (
    AGENT_CLAUDE,
    AGENT_CURSOR,
    AGENT_GEMINI,
    AGENT_COPILOT,
    AGENT_CODEX,
)

# =============================================================================
# File Names and Paths
# =============================================================================

# CI data directory structure (relative to .oak/)
CI_DATA_DIR: Final[str] = "ci"
CI_CHROMA_DIR: Final[str] = "chroma"
CI_ACTIVITIES_DB_FILENAME: Final[str] = "activities.db"
CI_LOG_FILE: Final[str] = "daemon.log"
CI_HOOKS_LOG_FILE: Final[str] = "hooks.log"
CI_PID_FILE: Final[str] = "daemon.pid"
CI_PORT_FILE: Final[str] = "daemon.port"

# Team-shared port configuration (git-tracked, in oak/)
# Priority: 1) .oak/ci/daemon.port (local override), 2) oak/daemon.port (team-shared)
CI_SHARED_PORT_DIR: Final[str] = "oak"
CI_SHARED_PORT_FILE: Final[str] = "daemon.port"

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
# Pagination Defaults (Daemon API)
# =============================================================================

PAGINATION_DEFAULT_LIMIT: Final[int] = 20
PAGINATION_DEFAULT_OFFSET: Final[int] = 0
PAGINATION_MIN_LIMIT: Final[int] = 1
PAGINATION_SESSIONS_MAX: Final[int] = 100
PAGINATION_ACTIVITIES_MAX: Final[int] = 200
PAGINATION_SEARCH_MAX: Final[int] = 200
PAGINATION_STATS_SESSION_LIMIT: Final[int] = 100
PAGINATION_STATS_DETAIL_LIMIT: Final[int] = 20

# =============================================================================
# Session & Batch Status Values
# =============================================================================

SESSION_STATUS_ACTIVE: Final[str] = "active"
SESSION_STATUS_COMPLETED: Final[str] = "completed"

# =============================================================================
# Error Messages (Daemon API)
# =============================================================================

ERROR_MSG_ACTIVITY_STORE_NOT_INITIALIZED: Final[str] = "Activity store not initialized"
ERROR_MSG_PROJECT_ROOT_NOT_SET: Final[str] = "Project root not set"
ERROR_MSG_SESSION_NOT_FOUND: Final[str] = "Session not found"
ERROR_MSG_INVALID_JSON: Final[str] = "Invalid JSON"
ERROR_MSG_LOCALHOST_ONLY: Final[str] = "Only localhost URLs are allowed for security reasons"

# =============================================================================
# Log Configuration (Daemon API)
# =============================================================================

LOG_LINES_DEFAULT: Final[int] = 50
LOG_LINES_MIN: Final[int] = 1
LOG_LINES_MAX: Final[int] = 500

LOG_FILE_DAEMON: Final[str] = "daemon"
LOG_FILE_HOOKS: Final[str] = "hooks"
VALID_LOG_FILES: Final[tuple[str, ...]] = (LOG_FILE_DAEMON, LOG_FILE_HOOKS)
LOG_FILE_DISPLAY_NAMES: Final[dict[str, str]] = {
    LOG_FILE_DAEMON: "Daemon Log",
    LOG_FILE_HOOKS: "Hook Events",
}

# =============================================================================
# CORS (Daemon API)
# =============================================================================

CI_CORS_SCHEME_HTTP: Final[str] = "http"
CI_CORS_HOST_LOCALHOST: Final[str] = "localhost"
CI_CORS_HOST_LOOPBACK: Final[str] = "127.0.0.1"
CI_CORS_ORIGIN_TEMPLATE: Final[str] = "{scheme}://{host}:{port}"
CI_CORS_ALLOWED_METHODS: Final[tuple[str, ...]] = ("GET", "POST", "PUT", "DELETE")
CI_CORS_ALLOWED_HEADERS: Final[tuple[str, ...]] = ("Content-Type", "Authorization")

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

# Deterministic ID prefix for session summaries (enables upsert on session reopen)
SESSION_SUMMARY_OBS_ID_PREFIX: Final[str] = "session_summary:"

# =============================================================================
# Memory Embedding Format
# =============================================================================

MEMORY_EMBED_LABEL_FILE: Final[str] = "file"
MEMORY_EMBED_LABEL_CONTEXT: Final[str] = "context"
MEMORY_EMBED_LABEL_SEPARATOR: Final[str] = ": "
MEMORY_EMBED_LABEL_TEMPLATE: Final[str] = "{label}{separator}{value}"
MEMORY_EMBED_LINE_SEPARATOR: Final[str] = "\n"

# =============================================================================
# Batching and Performance
# =============================================================================

DEFAULT_EMBEDDING_BATCH_SIZE: Final[int] = 100
DEFAULT_INDEXING_BATCH_SIZE: Final[int] = 50

# Timeout for indexing operations (1 hour default - large codebases need time)
DEFAULT_INDEXING_TIMEOUT_SECONDS: Final[float] = 3600.0

# =============================================================================
# HTTP Client Timeouts
# =============================================================================

# Quick operations: health checks, model listing, simple API calls
HTTP_TIMEOUT_QUICK: Final[float] = 5.0

# Standard operations: search queries, status checks
HTTP_TIMEOUT_STANDARD: Final[float] = 10.0

# Long operations: hook requests, indexing triggers
HTTP_TIMEOUT_LONG: Final[float] = 30.0

# Health check timeout (very quick, just checking if daemon is alive)
HTTP_TIMEOUT_HEALTH_CHECK: Final[float] = 2.0

# Daemon start timeout (subprocess)
DAEMON_START_TIMEOUT_SECONDS: Final[int] = 10

# Daemon restart delay
DAEMON_RESTART_DELAY_SECONDS: Final[float] = 1.0

# Hook stdin select timeout
HOOK_STDIN_TIMEOUT_SECONDS: Final[float] = 2.0

# =============================================================================
# CLI Defaults
# =============================================================================

# Default number of log lines to show
DEFAULT_LOG_LINES: Final[int] = 50

# Max files to scan for language detection
MAX_LANGUAGE_DETECTION_FILES: Final[int] = 1000

# =============================================================================
# Resiliency and Recovery
# =============================================================================

# Continuation prompt placeholder (used when session continues from another)
# This is used when activities are created without a prompt batch (e.g., during
# session transitions after "clear context and proceed")
RECOVERY_BATCH_PROMPT: Final[str] = "[Continued from previous session]"

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
CI_HISTORY_BACKUP_DIR: Final[str] = "oak/history"
CI_HISTORY_BACKUP_FILE: Final[str] = "ci_history.sql"  # Legacy single-file backup

# Multi-machine backup file pattern
# Format: {github_username}_{machine_hash}.sql (in oak/history/)
CI_HISTORY_BACKUP_FILE_PATTERN: Final[str] = "*.sql"
CI_HISTORY_BACKUP_FILE_PREFIX: Final[str] = ""  # No prefix - directory provides context
CI_HISTORY_BACKUP_FILE_SUFFIX: Final[str] = ".sql"
CI_BACKUP_HEADER_MAX_LINES: Final[int] = 10
CI_BACKUP_PATH_INVALID_ERROR: Final[str] = "Backup path must be within {backup_dir}"

# Environment variable for backup directory override
# Allows teams to store backups in external locations (shared drives, separate repos)
OAK_CI_BACKUP_DIR_ENV: Final[str] = "OAK_CI_BACKUP_DIR"

# =============================================================================
# Machine Identifier Configuration (privacy-preserving)
# =============================================================================
# Machine identifiers use format: {github_username}_{6_char_hash}
# This avoids exposing PII (hostname, system username) in git-tracked backup files.
# The hash is derived from hostname:username:MAC for uniqueness per machine.

MACHINE_ID_HASH_LENGTH: Final[int] = 6
MACHINE_ID_SEPARATOR: Final[str] = "_"
MACHINE_ID_FALLBACK_USERNAME: Final[str] = "anonymous"
MACHINE_ID_MAX_USERNAME_LENGTH: Final[int] = 30
MACHINE_ID_SUBPROCESS_TIMEOUT: Final[int] = 5
MACHINE_ID_CACHE_FILENAME: Final[str] = "machine_id"

# =============================================================================
# Session Quality Threshold
# =============================================================================
# Minimum activities (tool calls) for a session to be considered "quality".
# Sessions below this threshold:
# - Will NOT have titles generated (avoids hallucinated titles from minimal context)
# - Will NOT have summaries generated
# - Will NOT be embedded to ChromaDB
# - Will be deleted during stale session cleanup
# This matches the existing threshold in summaries.py:182 for summary generation.

MIN_SESSION_ACTIVITIES: Final[int] = 3

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

# Daemon log file handling
CI_DAEMON_LOG_OPEN_MODE: Final[str] = "ab"
CI_NULL_DEVICE_POSIX: Final[str] = "/dev/null"
CI_NULL_DEVICE_WINDOWS: Final[str] = "NUL"
CI_NULL_DEVICE_OPEN_MODE: Final[str] = "w"
CI_TEXT_ENCODING: Final[str] = "utf-8"
CI_LINE_SEPARATOR: Final[str] = "\n"
CI_LOG_FALLBACK_MESSAGE: Final[str] = (
    "Failed to open daemon log file {log_file}: {error}. Falling back to null device."
)

# =============================================================================
# Log Rotation
# =============================================================================

# Default log rotation settings
DEFAULT_LOG_ROTATION_ENABLED: Final[bool] = True
DEFAULT_LOG_MAX_SIZE_MB: Final[int] = 10
DEFAULT_LOG_BACKUP_COUNT: Final[int] = 3

# Log rotation limits for validation
MIN_LOG_MAX_SIZE_MB: Final[int] = 1
MAX_LOG_MAX_SIZE_MB: Final[int] = 100
MAX_LOG_BACKUP_COUNT: Final[int] = 10

# =============================================================================
# Input Validation
# =============================================================================

MAX_QUERY_LENGTH: Final[int] = 10000
MIN_QUERY_LENGTH: Final[int] = 1
MAX_OBSERVATION_LENGTH: Final[int] = 50000
RESPONSE_SUMMARY_MAX_LENGTH: Final[int] = 5000  # Agent response summary truncation

# =============================================================================
# Session and Hook Events
# =============================================================================

HOOK_EVENT_SESSION_START: Final[str] = "session-start"
HOOK_EVENT_SESSION_END: Final[str] = "session-end"
HOOK_EVENT_POST_TOOL_USE: Final[str] = "post-tool-use"
HOOK_EVENT_POST_TOOL_USE_FAILURE: Final[str] = "post-tool-use-failure"
HOOK_EVENT_BEFORE_PROMPT: Final[str] = "before-prompt"
HOOK_EVENT_STOP: Final[str] = "stop"
HOOK_EVENT_PROMPT_SUBMIT: Final[str] = "prompt-submit"
HOOK_EVENT_SUBAGENT_START: Final[str] = "subagent-start"
HOOK_EVENT_SUBAGENT_STOP: Final[str] = "subagent-stop"
HOOK_EVENT_AGENT_THOUGHT: Final[str] = "agent-thought"
HOOK_EVENT_PRE_COMPACT: Final[str] = "pre-compact"

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
HOOK_FIELD_ERROR_MESSAGE: Final[str] = "error_message"

# Stop hook fields (for transcript parsing)
HOOK_FIELD_TRANSCRIPT_PATH: Final[str] = "transcript_path"

# Subagent hook fields
HOOK_FIELD_AGENT_ID: Final[str] = "agent_id"
HOOK_FIELD_AGENT_TYPE: Final[str] = "agent_type"
HOOK_FIELD_AGENT_TRANSCRIPT_PATH: Final[str] = "agent_transcript_path"
HOOK_FIELD_STOP_HOOK_ACTIVE: Final[str] = "stop_hook_active"

# Hook deduplication configuration
HOOK_DEDUP_CACHE_MAX: Final[int] = 500
HOOK_DEDUP_HASH_ALGORITHM: Final[str] = "sha256"
HOOK_DROP_LOG_TAG: Final[str] = "[DROP]"

# Hook types
HOOK_TYPE_JSON: Final[str] = "json"
HOOK_TYPE_PLUGIN: Final[str] = "plugin"
HOOK_TYPE_OTEL: Final[str] = "otel"

# =============================================================================
# OpenTelemetry (OTLP) Configuration
# =============================================================================

# OTLP HTTP defaults
OTLP_LOGS_ENDPOINT: Final[str] = "/v1/logs"
OTLP_CONTENT_TYPE_PROTOBUF: Final[str] = "application/x-protobuf"
OTLP_CONTENT_TYPE_JSON: Final[str] = "application/json"

# HTTP constants
HTTP_HEADER_CONTENT_TYPE: Final[str] = "Content-Type"
HTTP_METHOD_POST: Final[str] = "POST"
ENCODING_UTF8: Final[str] = "utf-8"

# Environment variable for daemon port (used by OTEL agents like Codex)
# Agents can reference this in config files: ${OAK_CI_PORT}
OAK_CI_PORT_ENV_VAR: Final[str] = "OAK_CI_PORT"

# Codex OTel event names (from Codex telemetry docs)
OTEL_EVENT_CODEX_CONVERSATION_STARTS: Final[str] = "codex.conversation_starts"
OTEL_EVENT_CODEX_USER_PROMPT: Final[str] = "codex.user_prompt"
OTEL_EVENT_CODEX_TOOL_RESULT: Final[str] = "codex.tool_result"
OTEL_EVENT_CODEX_TOOL_DECISION: Final[str] = "codex.tool_decision"
OTEL_EVENT_CODEX_API_REQUEST: Final[str] = "codex.api_request"
OTEL_EVENT_CODEX_SSE_EVENT: Final[str] = "codex.sse_event"

# Codex notify events (agent notifications)
AGENT_NOTIFY_EVENT_TURN_COMPLETE: Final[str] = "agent-turn-complete"
AGENT_NOTIFY_ACTION_RESPONSE_SUMMARY: Final[str] = "response-summary"

# Notify payload fields
AGENT_NOTIFY_FIELD_TYPE: Final[str] = "type"
AGENT_NOTIFY_FIELD_THREAD_ID: Final[str] = "thread-id"
AGENT_NOTIFY_FIELD_TURN_ID: Final[str] = "turn-id"
AGENT_NOTIFY_FIELD_CWD: Final[str] = "cwd"
AGENT_NOTIFY_FIELD_INPUT_MESSAGES: Final[str] = "input-messages"
AGENT_NOTIFY_FIELD_LAST_ASSISTANT_MESSAGE: Final[str] = "last-assistant-message"
AGENT_NOTIFY_FIELD_AGENT: Final[str] = "agent"
AGENT_NOTIFY_PAYLOAD_DEFAULT: Final[str] = ""
AGENT_NOTIFY_PAYLOAD_JOIN_SEPARATOR: Final[str] = " "

# Notify installer configuration
AGENT_NOTIFY_CONFIG_TYPE: Final[str] = "notify"
AGENT_NOTIFY_CONFIG_KEY: Final[str] = "notify"
AGENT_NOTIFY_COMMAND_OAK: Final[str] = "oak"
AGENT_NOTIFY_DEFAULT_COMMAND: Final[str] = AGENT_NOTIFY_COMMAND_OAK
AGENT_NOTIFY_DEFAULT_ARGS: Final[tuple[str, ...]] = ("ci", "notify")
AGENT_NOTIFY_COMMAND_ARGS_CODEX: Final[tuple[str, ...]] = (
    "ci",
    "notify",
    "--agent",
    AGENT_CODEX,
)
AGENT_NOTIFY_ENDPOINT: Final[str] = "/api/oak/ci/notify"

# OTel attribute keys for data extraction (from Codex PR #2103)
OTEL_ATTR_CONVERSATION_ID: Final[str] = "conversation.id"
OTEL_ATTR_APP_VERSION: Final[str] = "app.version"
OTEL_ATTR_MODEL: Final[str] = "model"
OTEL_ATTR_TERMINAL_TYPE: Final[str] = "terminal.type"

# Tool-related attributes
OTEL_ATTR_TOOL_NAME: Final[str] = "tool_name"
OTEL_ATTR_TOOL_CALL_ID: Final[str] = "call_id"
OTEL_ATTR_TOOL_ARGUMENTS: Final[str] = "arguments"
OTEL_ATTR_TOOL_DURATION_MS: Final[str] = "duration_ms"
OTEL_ATTR_TOOL_SUCCESS: Final[str] = "success"
OTEL_ATTR_TOOL_OUTPUT: Final[str] = "output"

# Prompt-related attributes
OTEL_ATTR_PROMPT_LENGTH: Final[str] = "prompt_length"
OTEL_ATTR_PROMPT: Final[str] = "prompt"

# Decision-related attributes
OTEL_ATTR_DECISION: Final[str] = "decision"
OTEL_ATTR_DECISION_SOURCE: Final[str] = "source"

# Token metrics (from sse_event)
OTEL_ATTR_INPUT_TOKENS: Final[str] = "input_token_count"
OTEL_ATTR_OUTPUT_TOKENS: Final[str] = "output_token_count"
OTEL_ATTR_TOOL_TOKENS: Final[str] = "tool_token_count"

# Tags for auto-captured observations
TAG_AUTO_CAPTURED: Final[str] = "auto-captured"
TAG_SESSION_SUMMARY: Final[str] = "session-summary"

# =============================================================================
# Session Linking
# =============================================================================
# When a session starts with source="clear", we try to link it to the previous
# session using a tiered approach:
# 1. Tier 1 (immediate): Session ended within SESSION_LINK_IMMEDIATE_GAP_SECONDS
# 2. Tier 2 (race fix): Active session (SessionEnd not yet processed)
# 3. Tier 3 (stale): Completed session within SESSION_LINK_FALLBACK_MAX_HOURS

# Parent session reasons (why a session is linked to another)
SESSION_LINK_REASON_CLEAR: Final[str] = "clear"  # Immediate transition (< 5s)
SESSION_LINK_REASON_CLEAR_ACTIVE: Final[str] = "clear_active"  # Race condition fix
SESSION_LINK_REASON_COMPACT: Final[str] = "compact"  # Auto-compact
SESSION_LINK_REASON_INFERRED: Final[str] = "inferred"  # Stale/next-day fallback
SESSION_LINK_REASON_MANUAL: Final[str] = "manual"  # User manually linked

# Timing windows for session linking
SESSION_LINK_IMMEDIATE_GAP_SECONDS: Final[int] = 5  # Tier 1: just-ended sessions
SESSION_LINK_FALLBACK_MAX_HOURS: Final[int] = 24  # Tier 3: stale session fallback

# Legacy alias (deprecated, use SESSION_LINK_IMMEDIATE_GAP_SECONDS)
SESSION_LINK_MAX_GAP_SECONDS: Final[int] = SESSION_LINK_IMMEDIATE_GAP_SECONDS

# User-accepted suggestion (distinct from auto-linked)
SESSION_LINK_REASON_SUGGESTION: Final[str] = "suggestion"

# =============================================================================
# Session Link Event Types (for analytics tracking)
# =============================================================================
# Event types logged to session_link_events table for understanding user behavior

LINK_EVENT_AUTO_LINKED: Final[str] = "auto_linked"
LINK_EVENT_SUGGESTION_ACCEPTED: Final[str] = "suggestion_accepted"
LINK_EVENT_SUGGESTION_REJECTED: Final[str] = "suggestion_rejected"
LINK_EVENT_MANUAL_LINKED: Final[str] = "manual_linked"
LINK_EVENT_UNLINKED: Final[str] = "unlinked"

# =============================================================================
# Suggestion Confidence
# =============================================================================
# Confidence levels for parent session suggestions based on vector + LLM scoring

SUGGESTION_CONFIDENCE_HIGH: Final[str] = "high"
SUGGESTION_CONFIDENCE_MEDIUM: Final[str] = "medium"
SUGGESTION_CONFIDENCE_LOW: Final[str] = "low"
VALID_SUGGESTION_CONFIDENCE_LEVELS: Final[tuple[str, ...]] = (
    SUGGESTION_CONFIDENCE_HIGH,
    SUGGESTION_CONFIDENCE_MEDIUM,
    SUGGESTION_CONFIDENCE_LOW,
)

# Confidence thresholds for categorizing suggestions
# These are intentionally conservative to avoid showing poor-quality suggestions
# With LLM refinement enabled, scores combine vector similarity (40%) + LLM (60%)
SUGGESTION_HIGH_THRESHOLD: Final[float] = 0.8  # Strong match - high confidence
SUGGESTION_MEDIUM_THRESHOLD: Final[float] = 0.65  # Decent match - worth considering
SUGGESTION_LOW_THRESHOLD: Final[float] = 0.5  # Minimum to show any suggestion

# Time bonus thresholds for suggestion scoring
SUGGESTION_TIME_BONUS_1H_SECONDS: Final[int] = 3600  # < 1 hour: +0.1 bonus
SUGGESTION_TIME_BONUS_6H_SECONDS: Final[int] = 21600  # < 6 hours: +0.05 bonus
SUGGESTION_TIME_BONUS_1H_VALUE: Final[float] = 0.1
SUGGESTION_TIME_BONUS_6H_VALUE: Final[float] = 0.05

# Weights for combining vector similarity and LLM score
SUGGESTION_VECTOR_WEIGHT: Final[float] = 0.4
SUGGESTION_LLM_WEIGHT: Final[float] = 0.6

# Max candidate sessions to consider for LLM refinement
SUGGESTION_MAX_CANDIDATES: Final[int] = 5

# Max age in days for suggestion candidates
SUGGESTION_MAX_AGE_DAYS: Final[int] = 7

# =============================================================================
# Session Relationships (many-to-many semantic links)
# =============================================================================
# These complement parent-child links (temporal continuity) with semantic
# relationships that can span any time gap.

# Relationship types
RELATIONSHIP_TYPE_RELATED: Final[str] = "related"

# Created by sources
RELATIONSHIP_CREATED_BY_SUGGESTION: Final[str] = "suggestion"
RELATIONSHIP_CREATED_BY_MANUAL: Final[str] = "manual"

# =============================================================================
# Tunnel Sharing
# =============================================================================

# Tunnel providers
TUNNEL_PROVIDER_CLOUDFLARED: Final[str] = "cloudflared"
TUNNEL_PROVIDER_NGROK: Final[str] = "ngrok"
VALID_TUNNEL_PROVIDERS: Final[tuple[str, ...]] = (
    TUNNEL_PROVIDER_CLOUDFLARED,
    TUNNEL_PROVIDER_NGROK,
)
DEFAULT_TUNNEL_PROVIDER: Final[str] = TUNNEL_PROVIDER_CLOUDFLARED

# Tunnel timeouts
TUNNEL_STARTUP_TIMEOUT_SECONDS: Final[float] = 30.0
TUNNEL_URL_PARSE_TIMEOUT_SECONDS: Final[float] = 15.0
TUNNEL_SHUTDOWN_TIMEOUT_SECONDS: Final[float] = 5.0

# Activity store schema version
CI_ACTIVITY_SCHEMA_VERSION: Final[int] = 1

# Activity store columns
CI_SESSION_COLUMN_TRANSCRIPT_PATH: Final[str] = "transcript_path"

# Tunnel status values
TUNNEL_STATUS_ACTIVE: Final[str] = "active"
TUNNEL_STATUS_INACTIVE: Final[str] = "inactive"
TUNNEL_STATUS_ERROR: Final[str] = "error"
TUNNEL_STATUS_STARTING: Final[str] = "starting"

# Tunnel API routes
CI_TUNNEL_API_PATH_START: Final[str] = "/api/tunnel/start"
CI_TUNNEL_API_PATH_STOP: Final[str] = "/api/tunnel/stop"
CI_TUNNEL_API_PATH_STATUS: Final[str] = "/api/tunnel/status"
CI_TUNNEL_API_URL_TEMPLATE: Final[str] = "{scheme}://{host}:{port}{path}"
CI_TUNNEL_ROUTE_TAG: Final[str] = "tunnel"
CI_STATUS_KEY_TUNNEL: Final[str] = "tunnel"

# Tunnel config keys
CI_CONFIG_KEY_TUNNEL: Final[str] = "tunnel"
CI_CONFIG_TUNNEL_KEY_PROVIDER: Final[str] = "provider"
CI_CONFIG_TUNNEL_KEY_AUTO_START: Final[str] = "auto_start"
CI_CONFIG_TUNNEL_KEY_CLOUDFLARED_PATH: Final[str] = "cloudflared_path"
CI_CONFIG_TUNNEL_KEY_NGROK_PATH: Final[str] = "ngrok_path"

# Tunnel API response keys
TUNNEL_RESPONSE_KEY_STATUS: Final[str] = "status"
TUNNEL_RESPONSE_KEY_ACTIVE: Final[str] = "active"
TUNNEL_RESPONSE_KEY_PUBLIC_URL: Final[str] = "public_url"
TUNNEL_RESPONSE_KEY_PROVIDER: Final[str] = "provider"
TUNNEL_RESPONSE_KEY_STARTED_AT: Final[str] = "started_at"
TUNNEL_RESPONSE_KEY_ERROR: Final[str] = "error"

# Tunnel API status values
TUNNEL_API_STATUS_ALREADY_ACTIVE: Final[str] = "already_active"
TUNNEL_API_STATUS_STARTED: Final[str] = "started"
TUNNEL_API_STATUS_ERROR: Final[str] = "error"
TUNNEL_API_STATUS_NOT_ACTIVE: Final[str] = "not_active"
TUNNEL_API_STATUS_STOPPED: Final[str] = "stopped"

# Tunnel CLI messages
CI_TUNNEL_MESSAGE_DAEMON_NOT_RUNNING_START: Final[str] = (
    "Daemon is not running. Start it first: oak ci start"
)
CI_TUNNEL_MESSAGE_DAEMON_NOT_RUNNING: Final[str] = "Daemon is not running."
CI_TUNNEL_MESSAGE_STARTING: Final[str] = "Starting tunnel..."
CI_TUNNEL_MESSAGE_ACTIVE: Final[str] = "Tunnel active: {public_url}"
CI_TUNNEL_MESSAGE_PROVIDER: Final[str] = "  Provider: {provider}"
CI_TUNNEL_MESSAGE_STARTED: Final[str] = "  Started: {started_at}"
CI_TUNNEL_MESSAGE_ALREADY_ACTIVE: Final[str] = "Tunnel already active: {public_url}"
CI_TUNNEL_MESSAGE_FAILED_START: Final[str] = "Failed to start tunnel: {detail}"
CI_TUNNEL_MESSAGE_CONNECT_ERROR: Final[str] = "Cannot connect to daemon."
CI_TUNNEL_MESSAGE_TIMEOUT_START: Final[str] = "Request timed out. Tunnel may still be starting."
CI_TUNNEL_MESSAGE_NO_TUNNEL: Final[str] = "No tunnel is active."
CI_TUNNEL_MESSAGE_STOPPED: Final[str] = "Tunnel stopped."
CI_TUNNEL_MESSAGE_FAILED_STOP: Final[str] = "Failed to stop tunnel: {detail}"
CI_TUNNEL_MESSAGE_TIMEOUT: Final[str] = "Request timed out."
CI_TUNNEL_MESSAGE_FAILED_STATUS: Final[str] = "Failed to get tunnel status: {detail}"
CI_TUNNEL_MESSAGE_LAST_ERROR: Final[str] = "  Last error: {error}"

# Tunnel API error messages
CI_TUNNEL_ERROR_DAEMON_NOT_INITIALIZED: Final[str] = "Daemon not initialized"
CI_TUNNEL_ERROR_CONFIG_NOT_LOADED: Final[str] = "Configuration not loaded"
CI_TUNNEL_ERROR_CREATE_PROVIDER: Final[str] = "Failed to create tunnel provider: {error}"
CI_TUNNEL_ERROR_PROVIDER_UNAVAILABLE: Final[str] = (
    "Tunnel provider '{provider}' is not available. {install_hint}"
)
CI_TUNNEL_ERROR_UNKNOWN: Final[str] = "Unknown error"
CI_TUNNEL_ERROR_START_UNKNOWN: Final[str] = "Unknown error starting tunnel"
CI_TUNNEL_ERROR_STOP: Final[str] = "Error stopping tunnel: {error}"
CI_TUNNEL_ERROR_INVALID_PROVIDER: Final[str] = "Invalid tunnel provider: {provider}"
CI_TUNNEL_ERROR_INVALID_PROVIDER_EXPECTED: Final[str] = "one of {providers}"

# Tunnel API log messages
CI_TUNNEL_LOG_START: Final[str] = "Starting {provider} tunnel on port {port}..."
CI_TUNNEL_LOG_ACTIVE: Final[str] = "Tunnel active: {public_url}"
CI_TUNNEL_LOG_FAILED_START: Final[str] = "Tunnel failed to start: {error}"
CI_TUNNEL_LOG_STOPPED: Final[str] = "Tunnel stopped"
CI_TUNNEL_LOG_AUTO_START: Final[str] = "Auto-starting tunnel..."
CI_TUNNEL_LOG_AUTO_START_UNAVAILABLE: Final[str] = (
    "Tunnel auto-start skipped: provider '{provider}' not available"
)
CI_TUNNEL_LOG_AUTO_START_FAILED: Final[str] = "Tunnel auto-start failed: {error}"

# Tunnel install hints
CI_TUNNEL_INSTALL_HINT_NGROK: Final[str] = "Install from: https://ngrok.com/download"
CI_TUNNEL_INSTALL_HINT_CLOUDFLARED: Final[str] = "Install with: brew install cloudflared"
CI_TUNNEL_INSTALL_HINT_DEFAULT: Final[str] = "See docs for installation"

# Tunnel misc constants
CI_TUNNEL_PROVIDER_UNKNOWN: Final[str] = "unknown"
CI_EXIT_CODE_FAILURE: Final[int] = 1

# Tunnel command constants
TUNNEL_LOCALHOST_URL_TEMPLATE: Final[str] = "http://127.0.0.1:{port}"
TUNNEL_CLOUDFLARED_SUBCOMMAND: Final[str] = "tunnel"
TUNNEL_CLOUDFLARED_FLAG_URL: Final[str] = "--url"
TUNNEL_NGROK_SUBCOMMAND_HTTP: Final[str] = "http"
TUNNEL_NGROK_FLAG_LOG: Final[str] = "--log"
TUNNEL_NGROK_FLAG_LOG_FORMAT: Final[str] = "--log-format"
TUNNEL_NGROK_LOG_TARGET_STDOUT: Final[str] = "stdout"
TUNNEL_NGROK_LOG_FORMAT_JSON: Final[str] = "json"

# Tunnel provider logging
TUNNEL_LOG_START_CLOUDFLARED: Final[str] = "Starting cloudflared tunnel: {command}"
TUNNEL_LOG_START_NGROK: Final[str] = "Starting ngrok tunnel: {command}"
TUNNEL_LOG_CLOUDFLARED_PREFIX: Final[str] = "cloudflared: {line}"
TUNNEL_LOG_NGROK_PREFIX: Final[str] = "ngrok: {line}"
TUNNEL_LOG_TUNNEL_URL: Final[str] = "Tunnel URL: {public_url}"
TUNNEL_LOG_STOP_CLOUDFLARED: Final[str] = "Stopping cloudflared tunnel..."
TUNNEL_LOG_STOP_NGROK: Final[str] = "Stopping ngrok tunnel..."
TUNNEL_LOG_STOP_CLOUDFLARED_DONE: Final[str] = "Cloudflared tunnel stopped"
TUNNEL_LOG_STOP_NGROK_DONE: Final[str] = "ngrok tunnel stopped"
TUNNEL_LOG_STOP_CLOUDFLARED_KILL: Final[str] = "cloudflared did not stop gracefully, killing"
TUNNEL_LOG_STOP_NGROK_KILL: Final[str] = "ngrok did not stop gracefully, killing"

# Tunnel provider errors
TUNNEL_ERROR_CLOUDFLARED_BINARY_MISSING: Final[str] = (
    "cloudflared binary not found. Install from "
    "https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
)
TUNNEL_ERROR_NGROK_BINARY_MISSING: Final[str] = (
    "ngrok binary not found. Install from https://ngrok.com/download"
)
TUNNEL_ERROR_CLOUDFLARED_BINARY_NOT_FOUND: Final[str] = "cloudflared binary not found: {path}"
TUNNEL_ERROR_NGROK_BINARY_NOT_FOUND: Final[str] = "ngrok binary not found: {path}"
TUNNEL_ERROR_START_CLOUDFLARED: Final[str] = "Failed to start cloudflared: {error}"
TUNNEL_ERROR_START_NGROK: Final[str] = "Failed to start ngrok: {error}"
TUNNEL_ERROR_CLOUDFLARED_EXITED: Final[str] = "cloudflared exited with code {code}"
TUNNEL_ERROR_NGROK_EXITED: Final[str] = "ngrok exited with code {code}"
TUNNEL_ERROR_TIMEOUT_URL: Final[str] = "Timed out waiting for tunnel URL ({timeout}s)"
TUNNEL_ERROR_CLOUDFLARED_STOP: Final[str] = "Error stopping cloudflared: {error}"
TUNNEL_ERROR_NGROK_STOP: Final[str] = "Error stopping ngrok: {error}"
TUNNEL_ERROR_CLOUDFLARED_EXITED_UNEXPECTED: Final[str] = (
    "cloudflared exited unexpectedly (code {code})"
)
TUNNEL_ERROR_NGROK_EXITED_UNEXPECTED: Final[str] = "ngrok exited unexpectedly (code {code})"
TUNNEL_ERROR_UNKNOWN_PROVIDER: Final[str] = "Unknown tunnel provider: {provider}"
TUNNEL_ERROR_UNKNOWN_PROVIDER_EXPECTED: Final[str] = "one of ({cloudflared}, {ngrok})"

# Tunnel IO constants
TUNNEL_ENCODING_UTF8: Final[str] = "utf-8"
TUNNEL_ENCODING_ERROR_REPLACE: Final[str] = "replace"
TUNNEL_THREAD_CLOUDFLARED_STDERR: Final[str] = "cloudflared-stderr"
TUNNEL_THREAD_NGROK_STDOUT: Final[str] = "ngrok-stdout"

# CORS (Dynamic middleware)
CI_CORS_SCOPE_HTTP: Final[str] = "http"
CI_CORS_METHOD_OPTIONS: Final[str] = "OPTIONS"
CI_CORS_HEADER_ORIGIN: Final[str] = "origin"
CI_CORS_HEADER_ORIGIN_CAP: Final[str] = "Origin"
CI_CORS_HEADER_ALLOW_ORIGIN: Final[str] = "access-control-allow-origin"
CI_CORS_HEADER_ALLOW_METHODS: Final[str] = "access-control-allow-methods"
CI_CORS_HEADER_ALLOW_HEADERS: Final[str] = "access-control-allow-headers"
CI_CORS_HEADER_MAX_AGE: Final[str] = "access-control-max-age"
CI_CORS_HEADER_VARY: Final[str] = "vary"
CI_CORS_MAX_AGE_SECONDS: Final[int] = 600
CI_CORS_WILDCARD: Final[str] = "*"
CI_CORS_RESPONSE_START_TYPE: Final[str] = "http.response.start"
CI_CORS_RESPONSE_BODY_TYPE: Final[str] = "http.response.body"
CI_CORS_EMPTY_BODY: Final[bytes] = b""

# Cloudflared URL parsing
CLOUDFLARED_URL_PATTERN: Final[str] = r"https://[a-z0-9-]+\.trycloudflare\.com"

# ngrok JSON log key for tunnel URL
# ngrok outputs JSON logs with --log-format json; the tunnel URL appears in
# a log line with "msg":"started tunnel" and "url":"https://xxx.ngrok-free.app"
NGROK_LOG_MSG_STARTED: Final[str] = "started tunnel"
NGROK_LOG_KEY_URL: Final[str] = "url"
NGROK_LOG_KEY_MSG: Final[str] = "msg"

# Extended age limit for related session suggestions (effectively unlimited)
# Unlike parent suggestions (7 days), related sessions can span any time gap
# because they're based on semantic similarity, not temporal proximity.
RELATED_SUGGESTION_MAX_AGE_DAYS: Final[int] = 365

# =============================================================================
# Daemon API Security
# =============================================================================

# Token file for bearer token authentication (stored in .oak/ci/)
CI_TOKEN_FILE: Final[str] = "daemon.token"

# Environment variable used to pass the auth token to the daemon subprocess
CI_AUTH_ENV_VAR: Final[str] = "OAK_CI_TOKEN"

# Bearer authentication scheme and header
CI_AUTH_SCHEME_BEARER: Final[str] = "Bearer"
CI_AUTH_HEADER_NAME: Final[str] = "authorization"

# Maximum request body size (10 MB) to prevent memory exhaustion
CI_MAX_REQUEST_BODY_BYTES: Final[int] = 10 * 1024 * 1024

# Header required for destructive devtools operations
CI_DEVTOOLS_CONFIRM_HEADER: Final[str] = "x-devtools-confirm"

# File permissions for token file (owner read/write only)
CI_TOKEN_FILE_PERMISSIONS: Final[int] = 0o600

# Error messages for auth middleware
CI_AUTH_ERROR_MISSING: Final[str] = "Missing Authorization header"
CI_AUTH_ERROR_INVALID_SCHEME: Final[str] = "Invalid authentication scheme. Use: Bearer <token>"
CI_AUTH_ERROR_INVALID_TOKEN: Final[str] = "Invalid authentication token"
CI_AUTH_ERROR_PAYLOAD_TOO_LARGE: Final[str] = "Request body too large"
CI_DEVTOOLS_ERROR_CONFIRM_REQUIRED: Final[str] = (
    "Destructive operation requires X-Devtools-Confirm: true header"
)


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
# Importance Levels (for memory observations)
# =============================================================================
# Importance is stored on a 1-10 scale in SQLite/ChromaDB.
# These thresholds map the scale to high/medium/low categories.

IMPORTANCE_HIGH_THRESHOLD: Final[int] = 7  # >= 7 is high importance
IMPORTANCE_MEDIUM_THRESHOLD: Final[int] = 4  # >= 4 is medium importance
# Below 4 is low importance

# =============================================================================
# Combined Retrieval Scoring
# =============================================================================
# Weights for combining semantic confidence with importance in retrieval.
# combined_score = (confidence_weight * confidence) + (importance_weight * importance_normalized)

RETRIEVAL_CONFIDENCE_WEIGHT: Final[float] = 0.7
RETRIEVAL_IMPORTANCE_WEIGHT: Final[float] = 0.3

# Confidence score mapping for combined scoring (confidence level -> numeric score)
CONFIDENCE_SCORE_HIGH: Final[float] = 1.0
CONFIDENCE_SCORE_MEDIUM: Final[float] = 0.6
CONFIDENCE_SCORE_LOW: Final[float] = 0.3


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
# Plan synthesized from TaskCreate activities
PROMPT_SOURCE_DERIVED_PLAN: Final[str] = "derived_plan"

VALID_PROMPT_SOURCES: Final[tuple[str, ...]] = (
    PROMPT_SOURCE_USER,
    PROMPT_SOURCE_AGENT,
    PROMPT_SOURCE_SYSTEM,
    PROMPT_SOURCE_PLAN,
    PROMPT_SOURCE_DERIVED_PLAN,
)

# =============================================================================
# Session Continuation Labels
# =============================================================================
# Labels for system-created batches during session continuation events.
# These are descriptive labels shown in the UI, not agent-specific behavior.
# The actual triggers (SessionStart sources) are defined in agent manifests.

# When user explicitly clears context to continue in a new session
BATCH_LABEL_CLEARED_CONTEXT: Final[str] = "[Session continuation from cleared context]"

# When agent automatically compacts context mid-session
BATCH_LABEL_CONTEXT_COMPACTION: Final[str] = "[Continuation after context compaction]"

# Generic fallback for other continuation scenarios
BATCH_LABEL_SESSION_CONTINUATION: Final[str] = "[Session continuation]"

# Batch reactivation timeout (seconds) - universal across agents
# If a batch was completed within this time and tools are still executing,
# reactivate it instead of creating a new batch
BATCH_REACTIVATION_TIMEOUT_SECONDS: Final[int] = 60

# =============================================================================
# Internal Message Detection
# =============================================================================
# Prefixes used to detect internal/system messages that should not generate memories.
# Plan detection is handled dynamically via AgentService.get_all_plan_directories().

INTERNAL_MESSAGE_PREFIXES: Final[tuple[str, ...]] = (
    "<task-notification>",  # Background agent completion messages
    "<system-",  # System reminder/prompt messages
)

# =============================================================================
# Context Injection Limits
# =============================================================================
# Limits for context injected into AI agent conversations via hooks.

# Code injection limits
INJECTION_MAX_CODE_CHUNKS: Final[int] = 3
INJECTION_MAX_LINES_PER_CHUNK: Final[int] = 50

# Memory injection limits
INJECTION_MAX_MEMORIES: Final[int] = 10
INJECTION_MAX_SESSION_SUMMARIES: Final[int] = 3

# Summary generation limits
SUMMARY_MAX_PLAN_CONTEXT_LENGTH: Final[int] = 1500

# Session start injection text
INJECTION_SESSION_SUMMARIES_TITLE: Final[str] = "## Recent Session Summaries (most recent first)"
INJECTION_SESSION_START_REMINDER_TITLE: Final[str] = "## OAK CI Tools"
INJECTION_SESSION_START_REMINDER_LINES: Final[tuple[str, ...]] = (
    "- MCP tools: `oak_search` (code/memories), `oak_context` (task context), "
    "`oak_remember` (store learnings).",
)
INJECTION_SESSION_START_REMINDER_BLOCK: Final[str] = MEMORY_EMBED_LINE_SEPARATOR.join(
    (INJECTION_SESSION_START_REMINDER_TITLE, *INJECTION_SESSION_START_REMINDER_LINES)
)


# =============================================================================
# Agent Scheduler/Executor Configuration
# =============================================================================

# Scheduler interval: how often the scheduler checks for due schedules
DEFAULT_SCHEDULER_INTERVAL_SECONDS: Final[int] = 60
MIN_SCHEDULER_INTERVAL_SECONDS: Final[int] = 10
MAX_SCHEDULER_INTERVAL_SECONDS: Final[int] = 3600

# Executor cache size: max runs to keep in memory
DEFAULT_EXECUTOR_CACHE_SIZE: Final[int] = 100
MIN_EXECUTOR_CACHE_SIZE: Final[int] = 10
MAX_EXECUTOR_CACHE_SIZE: Final[int] = 1000

# Background processing interval: how often activity processor runs
DEFAULT_BACKGROUND_PROCESSING_INTERVAL_SECONDS: Final[int] = 60
MIN_BACKGROUND_PROCESSING_INTERVAL_SECONDS: Final[int] = 10
MAX_BACKGROUND_PROCESSING_INTERVAL_SECONDS: Final[int] = 600

# =============================================================================
# Agent Subsystem Constants
# =============================================================================

# Agent definition directories
AGENTS_DIR: Final[str] = "agents"
AGENTS_DEFINITIONS_DIR: Final[str] = "definitions"
AGENTS_TASKS_SUBDIR: Final[str] = "tasks"  # Tasks subdirectory within each agent definition
AGENT_DEFINITION_FILENAME: Final[str] = "agent.yaml"
AGENT_PROMPTS_DIR: Final[str] = "prompts"
AGENT_SYSTEM_PROMPT_FILENAME: Final[str] = "system.md"
AGENT_TASK_TEMPLATE_FILENAME: Final[str] = "task.yaml"  # Jinja2 template for new tasks

# Agent execution defaults
DEFAULT_AGENT_MAX_TURNS: Final[int] = 50
DEFAULT_AGENT_TIMEOUT_SECONDS: Final[int] = 600
MAX_AGENT_MAX_TURNS: Final[int] = 500
MAX_AGENT_TIMEOUT_SECONDS: Final[int] = 3600
MIN_AGENT_TIMEOUT_SECONDS: Final[int] = 60

# Agent recovery and shutdown timeouts
AGENT_RUN_RECOVERY_BUFFER_SECONDS: Final[int] = 300  # 5 min grace before marking stale
SHUTDOWN_TASK_TIMEOUT_SECONDS: Final[float] = 10.0  # Timeout for canceling background tasks
SCHEDULER_STOP_TIMEOUT_SECONDS: Final[float] = 5.0  # Timeout for stopping scheduler loop
AGENT_INTERRUPT_GRACE_SECONDS: Final[float] = 2.0  # Grace period after interrupt before timeout

# Agent retry configuration (for transient failures)
AGENT_RETRY_MAX_ATTEMPTS: Final[int] = 3  # Maximum retry attempts for transient failures
AGENT_RETRY_BASE_DELAY: Final[float] = (
    1.0  # Base delay in seconds (exponential backoff: 1s, 2s, 4s)
)

# Agent run status values (match AgentRunStatus enum)
AGENT_STATUS_PENDING: Final[str] = "pending"
AGENT_STATUS_RUNNING: Final[str] = "running"
AGENT_STATUS_COMPLETED: Final[str] = "completed"
AGENT_STATUS_FAILED: Final[str] = "failed"
AGENT_STATUS_CANCELLED: Final[str] = "cancelled"
AGENT_STATUS_TIMEOUT: Final[str] = "timeout"

# Agent run tracking
AGENT_RUNS_MAX_HISTORY: Final[int] = 100
AGENT_RUNS_CLEANUP_THRESHOLD: Final[int] = 150

# Default tools allowed for agents
AGENT_DEFAULT_ALLOWED_TOOLS: Final[tuple[str, ...]] = (
    "Read",
    "Write",
    "Edit",
    "Glob",
    "Grep",
)

# Tools that are never allowed for agents (security)
AGENT_FORBIDDEN_TOOLS: Final[tuple[str, ...]] = (
    "Bash",  # Shell commands - too dangerous
    "Task",  # Sub-agents - avoid recursion
)

# Default paths that agents cannot access (security)
AGENT_DEFAULT_DISALLOWED_PATHS: Final[tuple[str, ...]] = (
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.crt",
    "**/credentials*",
    "**/secrets*",
)

# CI MCP tool names (exposed to agents)
CI_TOOL_SEARCH: Final[str] = "ci_search"
CI_TOOL_MEMORIES: Final[str] = "ci_memories"
CI_TOOL_SESSIONS: Final[str] = "ci_sessions"
CI_TOOL_PROJECT_STATS: Final[str] = "ci_project_stats"
CI_TOOL_QUERY: Final[str] = "ci_query"
CI_MCP_SERVER_NAME: Final[str] = "oak-ci"
CI_MCP_SERVER_VERSION: Final[str] = "1.0.0"

# CI query tool configuration (read-only SQL execution)
CI_QUERY_MAX_ROWS: Final[int] = 500
CI_QUERY_DEFAULT_LIMIT: Final[int] = 100
CI_QUERY_FORBIDDEN_KEYWORDS: Final[tuple[str, ...]] = (
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "CREATE",
    "ATTACH",
    "DETACH",
    "REPLACE",
    "PRAGMA",
    "VACUUM",
    "REINDEX",
)

# Agent insights output directory (git-tracked, team-shareable)
AGENT_INSIGHTS_DIR: Final[str] = "oak/insights"

# Agent-generated documentation directory (git-tracked, team-shareable)
AGENT_DOCS_DIR: Final[str] = "oak/docs"

# Project-level agent configuration
# Config files are stored in oak/agents/{agent_name}.yaml (git-tracked, project-specific)
AGENT_PROJECT_CONFIG_DIR: Final[str] = "oak/agents"
AGENT_PROJECT_CONFIG_EXTENSION: Final[str] = ".yaml"

# =============================================================================
# Agent Task Constants
# =============================================================================

# Task schema version (for future migrations)
AGENT_TASK_SCHEMA_VERSION: Final[int] = 1

# Task name validation
AGENT_TASK_NAME_MIN_LENGTH: Final[int] = 1
AGENT_TASK_NAME_MAX_LENGTH: Final[int] = 50
AGENT_TASK_NAME_PATTERN: Final[str] = r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$"

# CI query confidence levels for task config
CI_QUERY_CONFIDENCE_HIGH: Final[str] = "high"
CI_QUERY_CONFIDENCE_MEDIUM: Final[str] = "medium"
CI_QUERY_CONFIDENCE_LOW: Final[str] = "low"
CI_QUERY_CONFIDENCE_ALL: Final[str] = "all"
VALID_CI_QUERY_CONFIDENCE_LEVELS: Final[tuple[str, ...]] = (
    CI_QUERY_CONFIDENCE_HIGH,
    CI_QUERY_CONFIDENCE_MEDIUM,
    CI_QUERY_CONFIDENCE_LOW,
    CI_QUERY_CONFIDENCE_ALL,
)

# CI tools available for instance queries
CI_QUERY_TOOL_SEARCH: Final[str] = "ci_search"
CI_QUERY_TOOL_MEMORIES: Final[str] = "ci_memories"
CI_QUERY_TOOL_SESSIONS: Final[str] = "ci_sessions"
CI_QUERY_TOOL_PROJECT_STATS: Final[str] = "ci_project_stats"
VALID_CI_QUERY_TOOLS: Final[tuple[str, ...]] = (
    CI_QUERY_TOOL_SEARCH,
    CI_QUERY_TOOL_MEMORIES,
    CI_QUERY_TOOL_SESSIONS,
    CI_QUERY_TOOL_PROJECT_STATS,
)

# Default CI query limits
DEFAULT_CI_QUERY_LIMIT: Final[int] = 10
MAX_CI_QUERY_LIMIT: Final[int] = 100

# =============================================================================
# Schedule Trigger Types
# =============================================================================
# Trigger types define when an agent schedule runs.
# - cron: Time-based scheduling via cron expression
# - manual: Run only when manually triggered by user

SCHEDULE_TRIGGER_CRON: Final[str] = "cron"
SCHEDULE_TRIGGER_MANUAL: Final[str] = "manual"
VALID_SCHEDULE_TRIGGER_TYPES: Final[tuple[str, ...]] = (
    SCHEDULE_TRIGGER_CRON,
    SCHEDULE_TRIGGER_MANUAL,
)
