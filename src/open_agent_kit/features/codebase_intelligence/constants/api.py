"""API defaults, pagination, error messages, and input validation constants."""

from typing import Final

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
# Error Messages (Daemon API)
# =============================================================================

ERROR_MSG_ACTIVITY_STORE_NOT_INITIALIZED: Final[str] = "Activity store not initialized"
ERROR_MSG_PROJECT_ROOT_NOT_SET: Final[str] = "Project root not set"
ERROR_MSG_SESSION_NOT_FOUND: Final[str] = "Session not found"
ERROR_MSG_INVALID_JSON: Final[str] = "Invalid JSON"
ERROR_MSG_LOCALHOST_ONLY: Final[str] = "Only localhost URLs are allowed for security reasons"

# =============================================================================
# Input Validation
# =============================================================================

MAX_QUERY_LENGTH: Final[int] = 10000
MIN_QUERY_LENGTH: Final[int] = 1
MAX_OBSERVATION_LENGTH: Final[int] = 50000
RESPONSE_SUMMARY_MAX_LENGTH: Final[int] = 15000  # Agent response summary truncation
PLAN_CONTENT_MAX_LENGTH: Final[int] = (
    50000  # Plan content (inline/heuristic) — much larger than summary
)

# Heuristic plan detection: scan only the beginning of the response
PLAN_RESPONSE_SCAN_LENGTH: Final[int] = 500

# =============================================================================
# CLI Defaults
# =============================================================================

# Default number of log lines to show
DEFAULT_LOG_LINES: Final[int] = 50

# Max files to scan for language detection
MAX_LANGUAGE_DETECTION_FILES: Final[int] = 1000

# =============================================================================
# CI MCP tool names (exposed to agents)
# =============================================================================

CI_TOOL_SEARCH: Final[str] = "ci_search"
CI_TOOL_MEMORIES: Final[str] = "ci_memories"
CI_TOOL_SESSIONS: Final[str] = "ci_sessions"
CI_TOOL_PROJECT_STATS: Final[str] = "ci_project_stats"
CI_TOOL_QUERY: Final[str] = "ci_query"
CI_TOOL_REMEMBER: Final[str] = "ci_remember"
CI_TOOL_RESOLVE: Final[str] = "ci_resolve"
CI_TOOL_ARCHIVE: Final[str] = "ci_archive"
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

# =============================================================================
# Tool Name Constants
# =============================================================================

TOOL_NAME_READ: Final[str] = "Read"
TOOL_NAME_EDIT: Final[str] = "Edit"
TOOL_NAME_WRITE: Final[str] = "Write"
TOOL_NAME_BASH: Final[str] = "Bash"
TOOL_NAME_GREP: Final[str] = "Grep"
TOOL_NAME_GLOB: Final[str] = "Glob"

# =============================================================================
# Time and Formatting Constants
# =============================================================================

SECONDS_PER_DAY: Final[int] = 86400
CI_FORMAT_PREVIEW_LENGTH: Final[int] = 200
CI_FORMAT_TITLE_MAX_LENGTH: Final[int] = 80
CI_FORMAT_DATE_DISPLAY: Final[str] = "%Y-%m-%d %H:%M"
