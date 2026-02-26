"""Team sync constants."""

from typing import Final

# =============================================================================
# Team Sync
# =============================================================================

# Config keys (inside codebase_intelligence.team section)
CI_CONFIG_KEY_TEAM: Final[str] = "team"
CI_CONFIG_TEAM_KEY_SERVER_URL: Final[str] = "server_url"
CI_CONFIG_TEAM_KEY_TOKEN: Final[str] = "token"
CI_CONFIG_TEAM_KEY_AUTO_SYNC: Final[str] = "auto_sync"
CI_CONFIG_TEAM_KEY_SYNC_INTERVAL: Final[str] = "sync_interval_seconds"
CI_CONFIG_TEAM_KEY_PULL_INTERVAL: Final[str] = "pull_interval_seconds"
CI_CONFIG_TEAM_KEY_PROJECT_SLUG: Final[str] = "project_slug"
CI_CONFIG_TEAM_KEY_TRANSPORT: Final[str] = "transport"
CI_CONFIG_TEAM_KEY_SERVER_MODE: Final[str] = "server_mode"
CI_CONFIG_TEAM_KEY_BIND_HOST: Final[str] = "bind_host"
CI_CONFIG_TEAM_KEY_BIND_PORT: Final[str] = "bind_port"
CI_CONFIG_TEAM_KEY_RELAY_WORKER_URL: Final[str] = "relay_worker_url"
CI_CONFIG_TEAM_KEY_RELAY_WORKER_NAME: Final[str] = "relay_worker_name"
CI_CONFIG_TEAM_KEY_SERVER_SIDE_LLM: Final[str] = "server_side_llm"

# Transport types
TEAM_TRANSPORT_DIRECT: Final[str] = "direct"
TEAM_TRANSPORT_RELAY: Final[str] = "relay"
VALID_TEAM_TRANSPORTS: Final[tuple[str, ...]] = (TEAM_TRANSPORT_DIRECT, TEAM_TRANSPORT_RELAY)

# Default values
TEAM_DEFAULT_SYNC_INTERVAL_SECONDS: Final[int] = 3
TEAM_DEFAULT_PULL_INTERVAL_SECONDS: Final[int] = 15
TEAM_DEFAULT_BIND_HOST: Final[str] = "127.0.0.1"
TEAM_DEFAULT_BIND_PORT: Final[int] = 8600
TEAM_MIN_SYNC_INTERVAL_SECONDS: Final[int] = 1
TEAM_MAX_SYNC_INTERVAL_SECONDS: Final[int] = 60
TEAM_MIN_PULL_INTERVAL_SECONDS: Final[int] = 5
TEAM_MAX_PULL_INTERVAL_SECONDS: Final[int] = 300

# Event types
TEAM_EVENT_OBSERVATION_UPSERT: Final[str] = "observation_upsert"
TEAM_EVENT_OBSERVATION_RESOLVED: Final[str] = "observation_resolved"
TEAM_EVENT_SESSION_UPSERT: Final[str] = "session_upsert"
TEAM_EVENT_SESSION_SUMMARY_UPDATE: Final[str] = "session_summary_update"
TEAM_EVENT_RAW_SESSION: Final[str] = "raw_session"  # Mode 2 groundwork
VALID_TEAM_EVENT_TYPES: Final[tuple[str, ...]] = (
    TEAM_EVENT_OBSERVATION_UPSERT,
    TEAM_EVENT_OBSERVATION_RESOLVED,
    TEAM_EVENT_SESSION_UPSERT,
    TEAM_EVENT_SESSION_SUMMARY_UPDATE,
)

# Outbox statuses
TEAM_OUTBOX_STATUS_PENDING: Final[str] = "pending"
TEAM_OUTBOX_STATUS_SENT: Final[str] = "sent"
TEAM_OUTBOX_STATUS_FAILED: Final[str] = "failed"
VALID_TEAM_OUTBOX_STATUSES: Final[tuple[str, ...]] = (
    TEAM_OUTBOX_STATUS_PENDING,
    TEAM_OUTBOX_STATUS_SENT,
    TEAM_OUTBOX_STATUS_FAILED,
)

# API paths
TEAM_API_PATH_EVENTS_PUSH: Final[str] = "/api/team/events/push"
TEAM_API_PATH_EVENTS_PULL: Final[str] = "/api/team/events/pull"
TEAM_API_PATH_MEMBERS_REGISTER: Final[str] = "/api/team/members/register"
TEAM_API_PATH_MEMBERS: Final[str] = "/api/team/members"
TEAM_API_PATH_STATUS: Final[str] = "/api/team/status"
TEAM_API_PATH_CONFIG: Final[str] = "/api/team/config"
TEAM_API_PATH_JOIN: Final[str] = "/api/team/join"
TEAM_API_PATH_LEAVE: Final[str] = "/api/team/leave"
TEAM_API_PATH_POLICY: Final[str] = "/api/team/policy"
TEAM_API_PATH_KEYS: Final[str] = "/api/team/keys"
TEAM_API_PATH_SYNC_FLUSH: Final[str] = "/api/team/sync/flush"
TEAM_API_PATH_SYNC_PULL: Final[str] = "/api/team/sync/pull"
TEAM_ROUTE_TAG: Final[str] = "team"

# API key constants
TEAM_API_KEY_PREFIX: Final[str] = "oak_team_"
TEAM_API_KEY_RANDOM_BYTES: Final[int] = 32
TEAM_API_KEY_PERMISSIONS_MEMBER: Final[str] = "member"
TEAM_API_KEY_PERMISSIONS_ADMIN: Final[str] = "admin"

# Outbox management
TEAM_OUTBOX_MAX_RETRY_COUNT: Final[int] = 5
TEAM_OUTBOX_PRUNE_AGE_HOURS: Final[int] = 24
TEAM_OUTBOX_BATCH_SIZE: Final[int] = 50

# Pull defaults
TEAM_PULL_DEFAULT_LIMIT: Final[int] = 50

# Project identity
TEAM_PROJECT_ID_SEPARATOR: Final[str] = ":"
TEAM_REMOTE_HASH_LENGTH: Final[int] = 8

# Log messages
TEAM_LOG_SYNC_STARTED: Final[str] = "Team sync worker started (interval={interval}s)"
TEAM_LOG_SYNC_STOPPED: Final[str] = "Team sync worker stopped"
TEAM_LOG_SYNC_FLUSH: Final[str] = "Flushed {count} events to team server"
TEAM_LOG_SYNC_ERROR: Final[str] = "Team sync error: {error}"
TEAM_LOG_PULL_STARTED: Final[str] = "Team pull worker started (interval={interval}s)"
TEAM_LOG_PULL_STOPPED: Final[str] = "Team pull worker stopped"
TEAM_LOG_PULL_APPLIED: Final[str] = "Applied {count} events from team server"
TEAM_LOG_PULL_ERROR: Final[str] = "Team pull error: {error}"

# CLI messages
TEAM_MESSAGE_JOIN_SUCCESS: Final[str] = "Joined team server: {server_url}"
TEAM_MESSAGE_LEAVE_SUCCESS: Final[str] = "Left team server"
TEAM_MESSAGE_NOT_CONFIGURED: Final[str] = "Team sync not configured"
TEAM_MESSAGE_ALREADY_CONFIGURED: Final[str] = "Already connected to team server: {server_url}"

# Validation error messages
TEAM_ERROR_INVALID_TRANSPORT: Final[str] = "Invalid transport: {transport}"
TEAM_ERROR_INVALID_TRANSPORT_EXPECTED: Final[str] = "one of {transports}"
TEAM_ERROR_RELAY_URL_REQUIRED: Final[str] = "relay_worker_url is required when transport is 'relay'"
TEAM_ERROR_SYNC_INTERVAL_RANGE: Final[str] = "sync_interval_seconds must be between {min} and {max}"
TEAM_ERROR_PULL_INTERVAL_RANGE: Final[str] = "pull_interval_seconds must be between {min} and {max}"

# Server mode env var
TEAM_SERVER_MODE_ENV_VAR: Final[str] = "OAK_CI_TEAM_SERVER"
