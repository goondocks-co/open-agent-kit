"""Team sync constants."""

from typing import Final

# =============================================================================
# Team Sync
# =============================================================================

# Config keys (inside codebase_intelligence.team section)
CI_CONFIG_KEY_TEAM: Final[str] = "team"
CI_CONFIG_TEAM_KEY_SERVER_URL: Final[str] = "server_url"
CI_CONFIG_TEAM_KEY_API_KEY: Final[str] = "api_key"
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
TEAM_TRANSPORT_LOCAL: Final[str] = "local"
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
TEAM_EVENT_SESSION_END: Final[str] = "session_end"
TEAM_EVENT_SESSION_TITLE_UPDATE: Final[str] = "session_title_update"
TEAM_EVENT_PROMPT_BATCH_UPSERT: Final[str] = "prompt_batch_upsert"
TEAM_EVENT_PROMPT_BATCH_RESPONSE_UPDATE: Final[str] = "prompt_batch_response_update"
TEAM_EVENT_PROMPT_BATCH_META_UPDATE: Final[str] = "prompt_batch_meta_update"
TEAM_EVENT_ACTIVITY_UPSERT: Final[str] = "activity_upsert"
TEAM_EVENT_OBSERVATION_STATUS_UPDATE: Final[str] = "observation_status_update"
TEAM_EVENT_RAW_SESSION: Final[str] = "raw_session"  # Mode 2 groundwork
VALID_TEAM_EVENT_TYPES: Final[tuple[str, ...]] = (
    TEAM_EVENT_OBSERVATION_UPSERT,
    TEAM_EVENT_OBSERVATION_RESOLVED,
    TEAM_EVENT_OBSERVATION_STATUS_UPDATE,
    TEAM_EVENT_SESSION_UPSERT,
    TEAM_EVENT_SESSION_SUMMARY_UPDATE,
    TEAM_EVENT_SESSION_END,
    TEAM_EVENT_SESSION_TITLE_UPDATE,
    TEAM_EVENT_PROMPT_BATCH_UPSERT,
    TEAM_EVENT_PROMPT_BATCH_RESPONSE_UPDATE,
    TEAM_EVENT_PROMPT_BATCH_META_UPDATE,
    TEAM_EVENT_ACTIVITY_UPSERT,
)

# Redaction sentinel
TEAM_REDACTED_BY_POLICY: Final[str] = "[redacted by policy]"

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
TEAM_API_PATH_SERVE: Final[str] = "/api/team/serve"
TEAM_ROUTE_TAG: Final[str] = "team"

# Loopback server mode
TEAM_LOOPBACK_KEY_NAME: Final[str] = "_loopback"
TEAM_LOOPBACK_URL_TEMPLATE: Final[str] = "http://127.0.0.1:{port}"
TEAM_LOOPBACK_URL_PREFIX: Final[str] = "http://127.0.0.1:"

# API key constants
TEAM_API_KEY_PREFIX: Final[str] = "oak_team_"
TEAM_API_KEY_RANDOM_BYTES: Final[int] = 32
TEAM_API_KEY_PERMISSIONS_MEMBER: Final[str] = "member"
TEAM_API_KEY_PERMISSIONS_ADMIN: Final[str] = "admin"

# Outbox management
TEAM_OUTBOX_MAX_RETRY_COUNT: Final[int] = 5
TEAM_OUTBOX_PRUNE_AGE_HOURS: Final[int] = 24
TEAM_OUTBOX_FAILED_PRUNE_AGE_HOURS: Final[int] = 168  # 7 days
TEAM_OUTBOX_BATCH_SIZE: Final[int] = 250
TEAM_OUTBOX_BATCH_SIZE_BURST: Final[int] = 500  # used when queue depth > threshold
TEAM_OUTBOX_BURST_THRESHOLD: Final[int] = 1000  # queue depth that triggers burst mode

# Presence heartbeat rate limit (independent of sync_interval)
TEAM_HEARTBEAT_INTERVAL_SECONDS: Final[int] = 30

# Maximum backoff between sync/pull attempts after consecutive transport failures
TEAM_SYNC_MAX_BACKOFF_SECONDS: Final[int] = 300

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
TEAM_LOG_LOCAL_TRANSPORT: Final[str] = "Using local transport (server mode)"

# CLI messages
TEAM_MESSAGE_JOIN_SUCCESS: Final[str] = "Joined team server: {server_url}"
TEAM_MESSAGE_JOIN_PENDING: Final[str] = (
    "Join request submitted to {server_url}. Waiting for admin approval."
)
TEAM_MESSAGE_JOIN_PENDING_POLL: Final[str] = (
    "Check status in the dashboard or run: oak ci team status"
)
TEAM_MESSAGE_LEAVE_SUCCESS: Final[str] = "Left team server"
TEAM_MESSAGE_NOT_CONFIGURED: Final[str] = "Team sync not configured"
TEAM_MESSAGE_ALREADY_CONFIGURED: Final[str] = "Already connected to team server: {server_url}"
TEAM_MESSAGE_INVALID_URL: Final[str] = "Invalid server URL: must start with http:// or https://"
TEAM_MESSAGE_CONNECTION_TEST_FAILED: Final[str] = "Failed to connect to team server: {error}"
TEAM_MESSAGE_DAEMON_NOT_RUNNING: Final[str] = "Daemon is not running. Start with: oak ci start"
TEAM_MESSAGE_REQUEST_TIMED_OUT: Final[str] = "Request timed out"
TEAM_MESSAGE_SERVER_URL: Final[str] = "Server URL: {server_url}"
TEAM_MESSAGE_AUTO_SYNC: Final[str] = "Auto Sync: {auto_sync}"
TEAM_MESSAGE_SYNC_ENABLED: Final[str] = "enabled"
TEAM_MESSAGE_SYNC_DISABLED: Final[str] = "disabled"
TEAM_MESSAGE_KEY_CREATED: Final[str] = "API key created: {name}"
TEAM_MESSAGE_KEY_SAVE_WARNING: Final[str] = "Save this key -- it will not be shown again:"
TEAM_MESSAGE_KEY_REVOKED: Final[str] = "API key revoked: {key_id}"
TEAM_MESSAGE_KEY_NOT_FOUND: Final[str] = "API key not found: {key_id}"
TEAM_MESSAGE_NO_KEYS: Final[str] = "No API keys found"
TEAM_MESSAGE_NO_MEMBERS: Final[str] = "No team members found"
TEAM_MESSAGE_SERVE_STARTING: Final[str] = "Starting daemon in team server mode on {host}:{port}"
TEAM_MESSAGE_SERVER_ENABLED: Final[str] = "Server mode enabled. Restart required."
TEAM_MESSAGE_SERVER_DISABLED: Final[str] = "Server mode disabled. Restart required."
TEAM_MESSAGE_API_KEY_PROMPT: Final[str] = "Team API key"

# CLI env var for team API key
TEAM_API_KEY_ENV_VAR: Final[str] = "OAK_TEAM_API_KEY"

# CLI daemon API URL template (reuse pattern from cloud relay)
TEAM_CLI_API_URL_TEMPLATE: Final[str] = "http://localhost:{port}{path}"

# Validation error messages
TEAM_ERROR_INVALID_TRANSPORT: Final[str] = "Invalid transport: {transport}"
TEAM_ERROR_INVALID_TRANSPORT_EXPECTED: Final[str] = "one of {transports}"
TEAM_ERROR_RELAY_URL_REQUIRED: Final[str] = "relay_worker_url is required when transport is 'relay'"
TEAM_ERROR_SYNC_INTERVAL_RANGE: Final[str] = "sync_interval_seconds must be between {min} and {max}"
TEAM_ERROR_PULL_INTERVAL_RANGE: Final[str] = "pull_interval_seconds must be between {min} and {max}"

# Server mode env var
TEAM_SERVER_MODE_ENV_VAR: Final[str] = "OAK_CI_TEAM_SERVER"

# =============================================================================
# Server-side constants
# =============================================================================

# Auth error messages
TEAM_AUTH_ERROR_MISSING: Final[str] = "Missing Authorization header"
TEAM_AUTH_ERROR_INVALID_SCHEME: Final[str] = "Invalid authorization scheme, expected Bearer"
TEAM_AUTH_ERROR_INVALID_KEY: Final[str] = "Invalid or revoked API key"
TEAM_AUTH_HEADER_NAME: Final[str] = "authorization"
TEAM_AUTH_SCHEME_BEARER: Final[str] = "Bearer"

# Server log messages
TEAM_SERVER_LOG_INIT: Final[str] = "Team server tables initialized"
TEAM_SERVER_LOG_EVENT_STORED: Final[str] = "Stored {count} events from {machine_id}"
TEAM_SERVER_LOG_EVENT_DEDUP: Final[str] = "Deduplicated {count} events (already received)"
TEAM_SERVER_LOG_MEMBER_REGISTERED: Final[str] = "Member registered: {machine_id} ({display_name})"

# Server status
TEAM_SERVER_STATUS_OK: Final[str] = "ok"
TEAM_SERVER_STATUS_KEY_SERVER_MODE: Final[str] = "server_mode"

# Router prefix
TEAM_ROUTER_PREFIX: Final[str] = "/api/team"

# Transport error messages
TEAM_TRANSPORT_ERROR_NOT_IMPLEMENTED: Final[str] = "Relay transport not yet implemented"
TEAM_TRANSPORT_ERROR_CONNECTION: Final[str] = "Failed to connect to team server: {error}"
TEAM_TRANSPORT_ERROR_PUSH: Final[str] = "Failed to push events: {error}"
TEAM_TRANSPORT_ERROR_PULL: Final[str] = "Failed to pull events: {error}"

# HTTP transport timeout
TEAM_HTTP_TIMEOUT_SECONDS: Final[float] = 10.0

# HTTP transport paths (relative, without prefix — used by HttpTransport)
TEAM_HTTP_PUSH_PATH: Final[str] = "/events/push"
TEAM_HTTP_PULL_PATH: Final[str] = "/events/pull"
TEAM_HTTP_STATUS_PATH: Final[str] = "/status"
TEAM_HTTP_REQUEST_JOIN_PATH: Final[str] = "/request-join"
TEAM_HTTP_JOIN_STATUS_PATH: Final[str] = "/join-status"
TEAM_HTTP_MEMBERS_PATH: Final[str] = "/members"
TEAM_HTTP_HEARTBEAT_PATH: Final[str] = "/members/heartbeat"

# =============================================================================
# Join request / approval flow
# =============================================================================

# Server-side API paths for join flow (full paths, used by daemon routes)
TEAM_API_PATH_REQUEST_JOIN: Final[str] = "/api/team/request-join"
TEAM_API_PATH_PENDING_JOINS: Final[str] = "/api/team/pending-joins"
TEAM_API_PATH_APPROVE_JOIN: Final[str] = "/api/team/approve-join"
TEAM_API_PATH_REJECT_JOIN: Final[str] = "/api/team/reject-join"
TEAM_API_PATH_JOIN_STATUS: Final[str] = "/api/team/join-status"

# Join request statuses
TEAM_JOIN_STATUS_PENDING: Final[str] = "pending"
TEAM_JOIN_STATUS_APPROVED: Final[str] = "approved"
TEAM_JOIN_STATUS_REJECTED: Final[str] = "rejected"

# Auto-generated key format
TEAM_AUTO_KEY_PREFIX: Final[str] = "team_"
TEAM_AUTO_KEY_RANDOM_BYTES: Final[int] = 32

# Config keys for join flow persistence
CI_CONFIG_TEAM_KEY_PENDING_KEY_ID: Final[str] = "pending_key_id"

# Log messages for join flow
TEAM_LOG_KEY_GENERATED: Final[str] = "Auto-generated team API key"
TEAM_LOG_KEY_PRESERVED: Final[str] = "Existing team API key preserved"
TEAM_LOG_JOIN_REQUEST_CREATED: Final[str] = (
    "Join request created: key_id={key_id}, machine_id={machine_id}"
)
TEAM_LOG_JOIN_APPROVED: Final[str] = "Join request approved: key_id={key_id}"
TEAM_LOG_JOIN_REJECTED: Final[str] = "Join request rejected: key_id={key_id}"
TEAM_LOG_JOIN_PENDING_KEY_VERIFY: Final[str] = (
    "Key verification failed: pending approval (key_id={key_id})"
)
TEAM_LOG_JOIN_STATUS_POLL: Final[str] = "Join status polled: key_id={key_id}, status={status}"

# =============================================================================
# Backfill & reconciliation
# =============================================================================

TEAM_BACKFILL_CHUNK_SIZE: Final[int] = 100
TEAM_BACKFILL_STATE_KEY_COMPLETED_AT: Final[str] = "backfill_completed_at"
TEAM_BACKFILL_STATE_KEY_SCHEMA_VERSION: Final[str] = "backfill_schema_version"
TEAM_BACKFILL_STATE_KEY_COUNTS: Final[str] = "backfill_counts"

TEAM_RECONCILE_INTERVAL_HOURS: Final[int] = 1
TEAM_RECONCILE_SLEEP_THRESHOLD_MINUTES: Final[int] = 30
TEAM_API_PATH_BACKFILL: Final[str] = "/api/team/backfill"
TEAM_API_PATH_BACKFILL_STATUS: Final[str] = "/api/team/backfill/status"
TEAM_API_PATH_RECONCILE: Final[str] = "/api/team/reconcile"
