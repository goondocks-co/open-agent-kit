"""Shared constants for the CI daemon.

Constants-first approach per .constitution.md §IV:
- Magic numbers and strings should be defined as constants
- Constants provide single source of truth for configuration values
"""

from pathlib import Path

# =============================================================================
# Daemon Status Values
# =============================================================================


class DaemonStatus:
    """Daemon health and operational status values."""

    HEALTHY = "healthy"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class IndexStatus:
    """Index operation status values."""

    IDLE = "idle"
    INDEXING = "indexing"
    COMPLETED = "completed"
    FAILED = "failed"


# =============================================================================
# Session & Activity Status
# =============================================================================


class SessionStatus:
    """Session lifecycle status values."""

    ACTIVE = "active"
    COMPLETED = "completed"


class BatchStatus:
    """Prompt batch processing status values."""

    ACTIVE = "active"
    COMPLETED = "completed"


# =============================================================================
# Log Configuration
# =============================================================================


class LogLevels:
    """Available log level values."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"

    VALID_LEVELS = [DEBUG, INFO, WARNING, ERROR]


class LogLimits:
    """Log retrieval limits."""

    DEFAULT_LINES = 50
    MIN_LINES = 1
    MAX_LINES = 500


# =============================================================================
# Pagination Defaults
# =============================================================================


class Pagination:
    """Default pagination values for API endpoints."""

    DEFAULT_LIMIT = 20
    DEFAULT_OFFSET = 0

    # Endpoint-specific limits
    SESSIONS_MAX = 100
    ACTIVITIES_MAX = 200
    SEARCH_MAX = 200
    STATS_SESSION_LIMIT = 100
    STATS_DETAIL_LIMIT = 20

    # Minimum values
    MIN_LIMIT = 1


# =============================================================================
# Timing Constants
# =============================================================================


class Timing:
    """Timing-related constants."""

    # Background processing
    MEMORY_PROCESS_INTERVAL_SECONDS = 60
    FILE_WATCHER_DEBOUNCE_MS = 500

    # HTTP timeouts
    PROVIDER_TIMEOUT_SECONDS = 5.0
    EMBEDDING_TIMEOUT_SECONDS = 30.0

    # Polling intervals (for reference, used by UI)
    STATUS_POLL_INTERVAL_MS = 2000


# =============================================================================
# File Paths
# =============================================================================


class Paths:
    """Standard file and directory paths relative to project root."""

    # .oak directory structure
    OAK_DIR = ".oak"
    CI_DIR = "ci"
    LOG_FILE = "daemon.log"
    CONFIG_FILE = "ci_config.yaml"
    DB_FILE = "activity.db"
    CHROMA_DIR = "chroma"

    @classmethod
    def get_log_path(cls, project_root: Path) -> Path:
        """Get the daemon log file path."""
        return project_root / cls.OAK_DIR / cls.CI_DIR / cls.LOG_FILE

    @classmethod
    def get_config_path(cls, project_root: Path) -> Path:
        """Get the CI config file path."""
        return project_root / cls.OAK_DIR / cls.CI_DIR / cls.CONFIG_FILE

    @classmethod
    def get_db_path(cls, project_root: Path) -> Path:
        """Get the activity database path."""
        return project_root / cls.OAK_DIR / cls.CI_DIR / cls.DB_FILE

    @classmethod
    def get_chroma_path(cls, project_root: Path) -> Path:
        """Get the ChromaDB directory path."""
        return project_root / cls.OAK_DIR / cls.CI_DIR / cls.CHROMA_DIR


# =============================================================================
# HTTP Status Codes (use with FastAPI)
# =============================================================================

# Note: Prefer using fastapi.status constants directly (e.g., status.HTTP_404_NOT_FOUND)
# These are provided for documentation and consistency checks


class HTTPStatus:
    """Common HTTP status codes used in the daemon API."""

    OK = 200
    CREATED = 201
    BAD_REQUEST = 400
    NOT_FOUND = 404
    INTERNAL_ERROR = 500
    SERVICE_UNAVAILABLE = 503


# =============================================================================
# Error Messages
# =============================================================================


class ErrorMessages:
    """Standard error messages for API responses."""

    ACTIVITY_STORE_NOT_INITIALIZED = "Activity store not initialized"
    PROJECT_ROOT_NOT_SET = "Project root not set"
    SESSION_NOT_FOUND = "Session not found"
    INVALID_JSON = "Invalid JSON"
    LOCALHOST_ONLY = "Only localhost URLs are allowed for security reasons"


# =============================================================================
# Search Threshold Multipliers
# =============================================================================


class ThresholdMultipliers:
    """Multipliers for model-aware relevance thresholds.

    These multipliers are applied to the model's base threshold to achieve
    different precision/recall trade-offs:
    - HIGH_PRECISION: For when only highly relevant results are wanted
    - BROAD_RECALL: For when casting a wider net to ensure coverage
    - STANDARD: No multiplier, use base threshold
    """

    # Higher precision (fewer, more relevant results)
    # e.g., for injecting context where noise is costly
    HIGH_PRECISION = 1.3

    # Broader recall (more results, may include less relevant)
    # e.g., for exploratory "get me anything related" queries
    BROAD_RECALL = 0.33

    # Standard (no multiplier)
    STANDARD = 1.0


# =============================================================================
# Default Values
# =============================================================================


class Defaults:
    """Default values for various settings."""

    # Agent identification
    AGENT_NAME = "claude-code"

    # Embedding defaults
    EMBEDDING_DIMENSIONS = 768
    CONTEXT_WINDOW = 8192
    CHUNK_SIZE_PERCENTAGE = 0.8

    # Server configuration
    DAEMON_PORT = 37800
    DAEMON_HOST = "127.0.0.1"
