"""Daemon CORS, logging, auth, ACP, restart, and version constants."""

from typing import Final

# =============================================================================
# General CLI exit codes
# =============================================================================
CI_EXIT_CODE_FAILURE: Final[int] = 1

# =============================================================================
# CORS (Daemon API)
# =============================================================================

CI_CORS_SCHEME_HTTP: Final[str] = "http"
CI_CORS_HOST_LOCALHOST: Final[str] = "localhost"
CI_CORS_HOST_LOOPBACK: Final[str] = "127.0.0.1"
CI_CORS_ORIGIN_TEMPLATE: Final[str] = "{scheme}://{host}:{port}"
CI_CORS_ALLOWED_METHODS: Final[tuple[str, ...]] = ("GET", "POST", "PUT", "DELETE")
CI_CORS_ALLOWED_HEADERS: Final[tuple[str, ...]] = ("Content-Type", "Authorization")

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

# =============================================================================
# Log Configuration (Daemon API)
# =============================================================================

LOG_LINES_DEFAULT: Final[int] = 50
LOG_LINES_MIN: Final[int] = 1
LOG_LINES_MAX: Final[int] = 500

LOG_FILE_DAEMON: Final[str] = "daemon"
LOG_FILE_HOOKS: Final[str] = "hooks"
LOG_FILE_ACP: Final[str] = "acp"
VALID_LOG_FILES: Final[tuple[str, ...]] = (LOG_FILE_DAEMON, LOG_FILE_HOOKS, LOG_FILE_ACP)
LOG_FILE_DISPLAY_NAMES: Final[dict[str, str]] = {
    LOG_FILE_DAEMON: "Daemon Log",
    LOG_FILE_HOOKS: "Hook Events",
    LOG_FILE_ACP: "ACP Log",
}

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
# Daemon API Security
# =============================================================================

# Token file for bearer token authentication (stored in .oak/ci/)
CI_TOKEN_FILE: Final[str] = "daemon.token"

# Environment variable used to pass the auth token to the daemon subprocess
CI_AUTH_ENV_VAR: Final[str] = "OAK_CI_TOKEN"

# Bearer authentication scheme and header
CI_AUTH_SCHEME_BEARER: Final[str] = "Bearer"
CI_AUTH_HEADER_NAME: Final[str] = "authorization"

# Relay source header: identifies traffic origin for auth routing.
# When present with value "relay", middleware reads daemon auth from
# CI_RELAY_DAEMON_AUTH_HEADER instead of the standard Authorization header.
CI_RELAY_SOURCE_HEADER: Final[str] = "x-oak-source"
CI_RELAY_SOURCE_VALUE: Final[str] = "relay"
CI_RELAY_DAEMON_AUTH_HEADER: Final[str] = "x-oak-daemon-auth"

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

# Auth - ephemeral token generation
CI_AUTH_EPHEMERAL_TOKEN_BYTES: Final[int] = 32
CI_AUTH_WARNING_NO_TOKEN: Final[str] = (
    "No auth_token configured — generated ephemeral token. "
    "Set OAK_CI_AUTH_TOKEN for stable authentication."
)
CI_DEVTOOLS_ERROR_CONFIRM_REQUIRED: Final[str] = (
    "Destructive operation requires X-Devtools-Confirm: true header"
)

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

# Daemon start timeout (max time to wait for health after triggering start)
DAEMON_START_TIMEOUT_SECONDS: Final[int] = 30

# Health poll interval during daemon startup (seconds between checks)
DAEMON_HEALTH_POLL_INTERVAL: Final[float] = 0.5

# Daemon restart delay
DAEMON_RESTART_DELAY_SECONDS: Final[float] = 1.0

# =============================================================================
# Version Detection
# =============================================================================

CI_CLI_VERSION_FILE: Final[str] = "cli_version"
CI_VERSION_CHECK_INTERVAL_SECONDS: Final[int] = 60

# =============================================================================
# Restart
# =============================================================================

CI_RESTART_ROUTE_TAG: Final[str] = "restart"
CI_RESTART_API_PATH: Final[str] = "/api/self-restart"
CI_RESTART_SHUTDOWN_DELAY_SECONDS: Final[float] = 1.0
CI_RESTART_SUBPROCESS_DELAY_SECONDS: Final[int] = 2

# Restart response/error constants
CI_RESTART_STATUS_RESTARTING: Final[str] = "restarting"
CI_RESTART_ERROR_NO_PROJECT_ROOT: Final[str] = "Project root not set"
CI_RESTART_LOG_SPAWNING: Final[str] = "Spawning restart subprocess: {command}"
CI_RESTART_LOG_SPAWN_FAILED: Final[str] = "Failed to spawn restart subprocess: %s"
CI_RESTART_ERROR_SPAWN_DETAIL: Final[str] = "Failed to spawn restart process: {error}"
CI_RESTART_LOG_SCHEDULING_SHUTDOWN: Final[str] = "Scheduling graceful shutdown in {delay}s"

# Upgrade-and-restart route constants
CI_UPGRADE_AND_RESTART_API_PATH: Final[str] = "/api/upgrade-and-restart"
CI_UPGRADE_AND_RESTART_STATUS: Final[str] = "upgrading"
CI_UPGRADE_AND_RESTART_STATUS_UP_TO_DATE: Final[str] = "up_to_date"
CI_UPGRADE_AND_RESTART_STATUS_UPGRADED: Final[str] = "upgraded"
CI_UPGRADE_AND_RESTART_LOG_SPAWNING: Final[str] = "Upgrade-and-restart: spawning '{command}'"
CI_UPGRADE_AND_RESTART_LOG_PARTIAL_FAILURE: Final[str] = "Upgrade partially failed: %s"
CI_UPGRADE_AND_RESTART_LOG_FAILED: Final[str] = "In-process upgrade failed: %s"
CI_UPGRADE_AND_RESTART_ERROR_PARTIAL_FAILURE: Final[str] = "Upgrade partially failed: {detail}"
CI_UPGRADE_AND_RESTART_ERROR_FAILED: Final[str] = "Upgrade failed: {error}"
CI_UPGRADE_AND_RESTART_ERROR_SPAWN_FAILED: Final[str] = (
    "Restart spawn failed after successful upgrade: %s"
)
CI_UPGRADE_AND_RESTART_DETAIL_RESTART_FAILED: Final[str] = (
    "Upgrade succeeded but daemon restart failed. Run: {cli_command} team restart"
)

# Shared shutdown constants
CI_SHUTDOWN_LOG_SIGTERM: Final[str] = "Sending SIGTERM for graceful shutdown"

# CLI hint constants
CI_CLI_HINT_VERSION_MISMATCH: Final[str] = (
    "Hint: Daemon running v{running}, installed v{installed}. "
    "Run '{cli_command} team restart' or visit the dashboard."
)
CI_CLI_HINT_TIMEOUT: Final[float] = 1.0

# Daemon status response key (used across CLI commands)
CI_DAEMON_STATUS_KEY_PORT: Final[str] = "port"

# =============================================================================
# ACP Management
# =============================================================================

CI_ACP_ROUTE_TAG: Final[str] = "acp"
CI_ACP_API_PATH_STATUS: Final[str] = "/api/acp/status"
CI_ACP_API_PATH_START: Final[str] = "/api/acp/start"
CI_ACP_API_PATH_STOP: Final[str] = "/api/acp/stop"
CI_ACP_API_PATH_LOGS: Final[str] = "/api/acp/logs"
CI_ACP_LOG_FILE: Final[str] = "acp.log"
CI_ACP_LOG_LINES_DEFAULT: Final[int] = 100
CI_ACP_STATUS_RUNNING: Final[str] = "running"
CI_ACP_STATUS_STOPPED: Final[str] = "stopped"
CI_ACP_ERROR_NOT_RUNNING: Final[str] = "ACP server is not running"
CI_ACP_ERROR_ALREADY_RUNNING: Final[str] = "ACP server is already running"
CI_ACP_ERROR_START_FAILED: Final[str] = "Failed to start ACP server: {error}"
CI_ACP_ERROR_NO_PROJECT_ROOT: Final[str] = "Daemon not initialized: no project root"
CI_ACP_LOG_STARTING: Final[str] = "Starting ACP server via stdio transport"
CI_ACP_LOG_STOPPED: Final[str] = "ACP server stopped"
CI_ACP_LOG_STOP_FAILED: Final[str] = "Failed to stop ACP server: {error}"
