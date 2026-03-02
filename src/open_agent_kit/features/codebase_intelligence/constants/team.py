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
CI_CONFIG_TEAM_KEY_PROJECT_SLUG: Final[str] = "project_slug"
CI_CONFIG_TEAM_KEY_RELAY_WORKER_URL: Final[str] = "relay_worker_url"
CI_CONFIG_TEAM_KEY_RELAY_WORKER_NAME: Final[str] = "relay_worker_name"
CI_CONFIG_TEAM_KEY_KEEP_RELAY_ALIVE: Final[str] = "keep_relay_alive"

# Default values
TEAM_DEFAULT_SYNC_INTERVAL_SECONDS: Final[int] = 3
TEAM_MIN_SYNC_INTERVAL_SECONDS: Final[int] = 1
TEAM_MAX_SYNC_INTERVAL_SECONDS: Final[int] = 60

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

# Outbox statuses
TEAM_OUTBOX_STATUS_PENDING: Final[str] = "pending"
TEAM_OUTBOX_STATUS_SENT: Final[str] = "sent"
TEAM_OUTBOX_STATUS_FAILED: Final[str] = "failed"

# API paths (only paths still used by daemon routes and CLI)
TEAM_API_PATH_MEMBERS: Final[str] = "/api/team/members"
TEAM_API_PATH_STATUS: Final[str] = "/api/team/status"
TEAM_API_PATH_CONFIG: Final[str] = "/api/team/config"
TEAM_API_PATH_LEAVE: Final[str] = "/api/team/leave"
TEAM_API_PATH_POLICY: Final[str] = "/api/team/policy"
TEAM_ROUTE_TAG: Final[str] = "team"

# Outbox management
TEAM_OUTBOX_MAX_RETRY_COUNT: Final[int] = 5
TEAM_OUTBOX_PRUNE_AGE_HOURS: Final[int] = 24
TEAM_OUTBOX_FAILED_PRUNE_AGE_HOURS: Final[int] = 168  # 7 days
TEAM_OUTBOX_BATCH_SIZE: Final[int] = 250
TEAM_OUTBOX_BATCH_SIZE_BURST: Final[int] = 500  # used when queue depth > threshold
TEAM_OUTBOX_BURST_THRESHOLD: Final[int] = 1000  # queue depth that triggers burst mode

# Maximum backoff between sync/pull attempts after consecutive transport failures
TEAM_SYNC_MAX_BACKOFF_SECONDS: Final[int] = 300

# Project identity
TEAM_PROJECT_ID_SEPARATOR: Final[str] = ":"
TEAM_REMOTE_HASH_LENGTH: Final[int] = 8

# Log messages
TEAM_LOG_SYNC_STARTED: Final[str] = "Team sync worker started (interval={interval}s)"
TEAM_LOG_SYNC_STOPPED: Final[str] = "Team sync worker stopped"
TEAM_LOG_SYNC_FLUSH: Final[str] = "Flushed {count} events to team server"
TEAM_LOG_SYNC_ERROR: Final[str] = "Team sync error: {error}"
TEAM_LOG_RELAY_POWER_DISCONNECT: Final[str] = "Power state: disconnecting cloud relay (deep sleep)"
TEAM_LOG_RELAY_POWER_RECONNECT: Final[str] = "Power state: reconnecting cloud relay (wake)"
TEAM_LOG_SYNC_WORKER_POWER_STOP: Final[str] = "Power state: stopping team sync worker (sleep)"
TEAM_LOG_SYNC_WORKER_POWER_RESTART: Final[str] = "Power state: restarting team sync worker (wake)"
TEAM_LOG_KEEP_RELAY_ALIVE: Final[str] = (
    "Power state: keep_relay_alive=True, skipping team subsystem suspension"
)

# CLI messages (only those still used by commands/ci/team.py)
TEAM_MESSAGE_NOT_CONFIGURED: Final[str] = "Team sync not configured"
TEAM_MESSAGE_DAEMON_NOT_RUNNING: Final[str] = "Daemon is not running. Start with: oak ci start"
TEAM_MESSAGE_REQUEST_TIMED_OUT: Final[str] = "Request timed out"
TEAM_MESSAGE_NO_MEMBERS: Final[str] = "No team members found"

# CLI env var for team API key
TEAM_API_KEY_ENV_VAR: Final[str] = "OAK_TEAM_API_KEY"

# CLI daemon API URL template (reuse pattern from cloud relay)
TEAM_CLI_API_URL_TEMPLATE: Final[str] = "http://localhost:{port}{path}"

# Validation error messages
TEAM_ERROR_SYNC_INTERVAL_RANGE: Final[str] = "sync_interval_seconds must be between {min} and {max}"

# =============================================================================
# Remote observation defaults
# =============================================================================

# ISO-8601 epoch timestamp used as fallback when a remote observation
# arrives without a ``started_at`` or ``created_at`` value.
TEAM_REMOTE_OBS_EPOCH: Final[str] = "1970-01-01T00:00:00+00:00"

# Fallback agent label used when a remote session stub has no agent field.
TEAM_REMOTE_OBS_UNKNOWN_AGENT: Final[str] = "unknown"

# Default importance for remote observations that arrive without an importance field.
TEAM_REMOTE_OBS_DEFAULT_IMPORTANCE: Final[int] = 5

# =============================================================================
# Backfill
# =============================================================================

TEAM_BACKFILL_CHUNK_SIZE: Final[int] = 100
TEAM_BACKFILL_STATE_KEY_COMPLETED_AT: Final[str] = "backfill_completed_at"
TEAM_BACKFILL_STATE_KEY_SCHEMA_VERSION: Final[str] = "backfill_schema_version"
TEAM_BACKFILL_STATE_KEY_COUNTS: Final[str] = "backfill_counts"
