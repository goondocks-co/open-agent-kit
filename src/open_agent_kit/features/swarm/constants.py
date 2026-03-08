"""Swarm constants."""

from typing import Final

# =============================================================================
# Swarm
# =============================================================================

# Timeouts and intervals
SWARM_DEFAULT_SEARCH_TIMEOUT_SECONDS: Final[int] = 10
SWARM_DEFAULT_TOOL_TIMEOUT_SECONDS: Final[int] = 30
# Extra seconds added to httpx timeout to allow the daemon's internal timeout to fire first
SWARM_MCP_TIMEOUT_PADDING_SECONDS: Final[float] = 2.0
SWARM_HEARTBEAT_INTERVAL_SECONDS: Final[int] = 60
SWARM_STALE_THRESHOLD_SECONDS: Final[int] = 300  # 5 minutes
# Payload limits
SWARM_MAX_RESPONSE_BYTES: Final[int] = 1048576  # 1 MB

# Config keys (inside team.swarm section)
CI_CONFIG_KEY_SWARM: Final[str] = "swarm"
CI_CONFIG_SWARM_KEY_URL: Final[str] = "swarm_url"
CI_CONFIG_SWARM_KEY_TOKEN: Final[str] = "swarm_token"
CI_CONFIG_SWARM_KEY_SENSITIVITY: Final[str] = "sensitivity"
CI_CONFIG_SWARM_KEY_SWARM_ID: Final[str] = "swarm_id"
CI_CONFIG_SWARM_KEY_WORKER_NAME: Final[str] = "worker_name"
CI_CONFIG_SWARM_KEY_CUSTOM_DOMAIN: Final[str] = "custom_domain"
CI_CONFIG_SWARM_KEY_AGENT_TOKEN: Final[str] = "agent_token"

# API paths (Swarm Worker HTTP API)
SWARM_API_PATH_REGISTER: Final[str] = "/api/swarm/register"
SWARM_API_PATH_HEARTBEAT: Final[str] = "/api/swarm/heartbeat"
SWARM_API_PATH_SEARCH: Final[str] = "/api/swarm/search"
SWARM_API_PATH_BROADCAST: Final[str] = "/api/swarm/broadcast"
SWARM_API_PATH_NODES: Final[str] = "/api/swarm/nodes"
SWARM_API_PATH_UNREGISTER: Final[str] = "/api/swarm/unregister"
SWARM_API_PATH_CONFIG: Final[str] = "/api/swarm/config"
SWARM_API_PATH_CONFIG_MIN_OAK_VERSION: Final[str] = "/api/swarm/config/min-oak-version"
SWARM_API_PATH_FETCH: Final[str] = "/api/swarm/fetch"
SWARM_API_PATH_HEALTH_CHECK: Final[str] = "/api/swarm/health-check"

# Daemon API paths (local swarm daemon)
SWARM_DAEMON_API_PATH_HEALTH: Final[str] = "/api/health"
SWARM_DAEMON_API_PATH_SEARCH: Final[str] = "/api/swarm/search"
SWARM_DAEMON_API_PATH_NODES: Final[str] = "/api/swarm/nodes"
SWARM_DAEMON_API_PATH_STATUS: Final[str] = "/api/swarm/status"
SWARM_DAEMON_API_PATH_HEALTH_CHECK: Final[str] = "/api/swarm/health-check"
SWARM_DAEMON_API_PATH_CREDENTIALS: Final[str] = "/api/swarm/credentials"
# Daemon UI API paths (local swarm daemon - UI endpoints)
SWARM_DAEMON_API_PATH_RESTART: Final[str] = "/api/restart"
SWARM_DAEMON_API_PATH_CONFIG: Final[str] = "/api/config"
SWARM_DAEMON_API_PATH_LOGS: Final[str] = "/api/logs"

# Config keys (inside swarm config.json — daemon-level settings)
CI_CONFIG_SWARM_KEY_LOG_LEVEL: Final[str] = "log_level"
SWARM_DAEMON_DEFAULT_LOG_LEVEL: Final[str] = "INFO"
CI_CONFIG_SWARM_KEY_LOG_ROTATION: Final[str] = "log_rotation"

# Log rotation defaults and limits (must match UI constants)
SWARM_LOG_ROTATION_DEFAULT_ENABLED: Final[bool] = True
SWARM_LOG_ROTATION_DEFAULT_MAX_SIZE_MB: Final[int] = 10
SWARM_LOG_ROTATION_DEFAULT_BACKUP_COUNT: Final[int] = 3
SWARM_LOG_ROTATION_MIN_SIZE_MB: Final[int] = 1
SWARM_LOG_ROTATION_MAX_SIZE_MB: Final[int] = 100
SWARM_LOG_ROTATION_MAX_BACKUP_COUNT: Final[int] = 10

# Swarm config keys (inside swarm_config table in Swarm DO)
SWARM_CONFIG_KEY_MIN_OAK_VERSION: Final[str] = "min_oak_version"

# Advisory severity levels
SWARM_ADVISORY_SEVERITY_INFO: Final[str] = "info"
SWARM_ADVISORY_SEVERITY_WARNING: Final[str] = "warning"
SWARM_ADVISORY_SEVERITY_CRITICAL: Final[str] = "critical"

# Advisory types
SWARM_ADVISORY_TYPE_VERSION_DRIFT: Final[str] = "version_drift"
SWARM_ADVISORY_TYPE_CAPABILITY_GAP: Final[str] = "capability_gap"
SWARM_ADVISORY_TYPE_GENERAL: Final[str] = "general"

# WebSocket protocol message types (node <-> Team Worker)
SWARM_WS_TYPE_SEARCH: Final[str] = "swarm_search"
SWARM_WS_TYPE_SEARCH_RESULT: Final[str] = "swarm_search_result"
SWARM_WS_TYPE_NODES: Final[str] = "swarm_nodes"
SWARM_WS_TYPE_NODE_LIST: Final[str] = "swarm_node_list"

# Response keys
SWARM_RESPONSE_KEY_SWARM_ID: Final[str] = "swarm_id"
SWARM_RESPONSE_KEY_TEAM_COUNT: Final[str] = "team_count"
SWARM_RESPONSE_KEY_TEAMS: Final[str] = "teams"
SWARM_RESPONSE_KEY_RESULTS: Final[str] = "results"
SWARM_RESPONSE_KEY_ERROR: Final[str] = "error"
SWARM_RESPONSE_KEY_CONNECTED: Final[str] = "connected"
SWARM_RESPONSE_KEY_STATUS: Final[str] = "status"
SWARM_RESPONSE_KEY_PROJECT_SLUG: Final[str] = "project_slug"
SWARM_RESPONSE_KEY_SWARM_URL: Final[str] = "swarm_url"
SWARM_RESPONSE_KEY_CALLBACK_TOKEN: Final[str] = "callback_token"

# Status values
SWARM_STATUS_CONNECTED: Final[str] = "connected"
SWARM_STATUS_DISCONNECTED: Final[str] = "disconnected"
SWARM_STATUS_STALE: Final[str] = "stale"

# Sensitivity levels
SWARM_SENSITIVITY_STANDARD: Final[str] = "standard"
SWARM_SENSITIVITY_RESTRICTED: Final[str] = "restricted"

# Capability identifiers
SWARM_CAPABILITY_SEARCH: Final[str] = "swarm_search_v1"
SWARM_CAPABILITY_MANAGEMENT: Final[str] = "swarm_management_v1"

# Scaffold constants
SWARM_WORKER_TEMPLATE_DIR: Final[str] = "worker_template"
SWARM_SCAFFOLD_OUTPUT_DIR: Final[str] = ".oak/ci/swarm-worker"

# Scaffold subdirectory (inside swarm config dir)
SWARM_SCAFFOLD_WORKER_SUBDIR: Final[str] = "worker"

# Worker name
SWARM_DEFAULT_WORKER_NAME_PREFIX: Final[str] = "oak-swarm"

# Installed MCP server name (registered in agent MCP configs like .mcp.json)
SWARM_MCP_INSTALLED_SERVER_NAME: Final[str] = "oak-swarm"

# Environment variables set by SwarmDaemonManager.start() for the daemon process
SWARM_ENV_VAR_URL: Final[str] = "OAK_SWARM_URL"
SWARM_ENV_VAR_ID: Final[str] = "OAK_SWARM_ID"
SWARM_ENV_VAR_CUSTOM_DOMAIN: Final[str] = "OAK_SWARM_CUSTOM_DOMAIN"

# CLI command env var — set by SwarmDaemonManager.start() so the daemon
# process knows which CLI binary (oak / oak-dev / oak-beta) to use for
# self-restart.  Falls back to "oak" when unset.
SWARM_CLI_COMMAND_ENV_VAR: Final[str] = "OAK_CLI_COMMAND"

# Authentication
SWARM_AUTH_ENV_VAR: Final[str] = "OAK_SWARM_DAEMON_TOKEN"

# Legacy environment variable names (kept for migration from .env to user config)
SWARM_ENV_VAR_TOKEN: Final[str] = "OAK_SWARM_TOKEN"
SWARM_ENV_VAR_AGENT_TOKEN: Final[str] = "OAK_SWARM_AGENT_TOKEN"

# User config keys (stored in .oak/config.{machine_id}.yaml)
SWARM_USER_CONFIG_SECTION: Final[str] = "swarm"
SWARM_USER_CONFIG_KEY_TOKEN: Final[str] = "swarm_token"
SWARM_USER_CONFIG_KEY_AGENT_TOKEN: Final[str] = "agent_token"
SWARM_AUTH_HEADER_NAME: Final[str] = "authorization"
SWARM_AUTH_SCHEME_BEARER: Final[str] = "Bearer"
SWARM_AUTH_EPHEMERAL_TOKEN_BYTES: Final[int] = 32
SWARM_CONFIG_FILE_PERMISSIONS: Final[int] = 0o600
SWARM_AUTH_ERROR_MISSING: Final[str] = "Authorization header required"
SWARM_AUTH_ERROR_INVALID_SCHEME: Final[str] = "Expected 'Bearer <token>'"
SWARM_AUTH_ERROR_INVALID_TOKEN: Final[str] = "Invalid token"
SWARM_AUTH_WARNING_NO_TOKEN: Final[str] = (
    "No auth token configured; generated ephemeral token. "
    "Set OAK_SWARM_DAEMON_TOKEN for stable authentication."
)

# Daemon defaults
SWARM_DAEMON_DEFAULT_PORT: Final[int] = 38900
SWARM_DAEMON_STARTUP_TIMEOUT: Final[float] = 15.0
SWARM_DAEMON_HEALTH_CHECK_INTERVAL: Final[float] = 0.5
SWARM_DAEMON_CONFIG_DIR: Final[str] = "~/.oak/swarms"
SWARM_DAEMON_PID_FILE: Final[str] = "daemon.pid"
SWARM_DAEMON_PORT_FILE: Final[str] = "daemon.port"
SWARM_DAEMON_LOG_FILE: Final[str] = "daemon.log"
SWARM_DAEMON_CONFIG_FILE: Final[str] = "config.json"

# CLI messages
SWARM_MESSAGE_CREATING: Final[str] = "Creating swarm '{name}'..."
SWARM_MESSAGE_CREATED: Final[str] = "Swarm created successfully."
SWARM_MESSAGE_SWARM_URL: Final[str] = "Swarm URL: {swarm_url}"
SWARM_MESSAGE_SWARM_TOKEN: Final[str] = "Swarm token: {swarm_token}"
SWARM_MESSAGE_SAVE_TOKEN: Final[str] = "Save this token - it will not be shown again."
SWARM_MESSAGE_DESTROYING: Final[str] = "Destroying swarm '{name}'..."
SWARM_MESSAGE_DESTROYED: Final[str] = "Swarm destroyed."
SWARM_MESSAGE_STARTING: Final[str] = "Starting swarm daemon..."
SWARM_MESSAGE_STARTED: Final[str] = "Swarm daemon started on port {port}."
SWARM_MESSAGE_STOPPING: Final[str] = "Stopping swarm daemon..."
SWARM_MESSAGE_STOPPED: Final[str] = "Swarm daemon stopped."
SWARM_MESSAGE_NOT_RUNNING: Final[str] = "Swarm daemon is not running."
SWARM_MESSAGE_ALREADY_RUNNING: Final[str] = "Swarm daemon is already running on port {port}."
SWARM_MESSAGE_NO_SWARM_CONFIG: Final[str] = (
    "No swarm configuration found. Run 'oak swarm create' first."
)
SWARM_MESSAGE_DAEMON_NOT_RUNNING: Final[str] = (
    "Daemon is not running. Start it first: oak swarm start"
)
SWARM_MESSAGE_DEPLOY_STARTING: Final[str] = "Deploying swarm worker..."
SWARM_MESSAGE_DEPLOY_SUCCESS: Final[str] = "Swarm worker deployed successfully."
SWARM_MESSAGE_START_HINT: Final[str] = "Start the daemon with: oak swarm start -n {name}"
SWARM_MESSAGE_WRANGLER_NOT_AVAILABLE: Final[str] = (
    "npx wrangler is not available. Install wrangler first: npm install -g wrangler"
)
SWARM_MESSAGE_NPM_INSTALL_FAILED: Final[str] = "npm install failed: {output}"
SWARM_MESSAGE_DEPLOY_FAILED: Final[str] = "Deploy failed: {output}"
SWARM_MESSAGE_RESTARTING: Final[str] = "Restarting swarm daemon..."
SWARM_MESSAGE_RESTARTED: Final[str] = "Swarm daemon restarted at http://localhost:{port}"
SWARM_MESSAGE_RESTART_FAILED: Final[str] = "Failed to restart swarm daemon. Check logs: {log_file}"
SWARM_MESSAGE_DAEMON_START_FAILED: Final[str] = (
    "Swarm daemon failed to start. Check logs for details."
)
SWARM_MESSAGE_MCP_HINT: Final[str] = (
    "Run 'oak init' to install the swarm MCP server for your agents."
)
# Deploy route error messages
SWARM_DEPLOY_ERROR_NO_SWARM_ID: Final[str] = "No swarm ID configured"
SWARM_DEPLOY_ERROR_NO_SCAFFOLD_DIR: Final[str] = "Cannot determine scaffold directory"
SWARM_DEPLOY_ERROR_NO_TOKEN: Final[str] = "No swarm token in daemon state"
SWARM_DEPLOY_ERROR_NOT_SCAFFOLDED: Final[str] = "Worker not scaffolded. Run scaffold first."

# Error messages
SWARM_ERROR_NOT_CONNECTED: Final[str] = "Not connected to swarm"
SWARM_ERROR_SEARCH_FAILED: Final[str] = "Swarm search failed: {error}"
SWARM_ERROR_REGISTRATION_FAILED: Final[str] = "Swarm registration failed: {error}"
SWARM_ERROR_INVALID_TOKEN: Final[str] = "Invalid swarm token"
SWARM_ERROR_TEAM_NOT_FOUND: Final[str] = "Team '{team_id}' not found in swarm"

# Log messages
SWARM_LOG_REGISTERING: Final[str] = "Registering with swarm at {swarm_url}..."
SWARM_LOG_REGISTERED: Final[str] = "Registered with swarm: {swarm_id}"
SWARM_LOG_HEARTBEAT: Final[str] = "Swarm heartbeat sent"
SWARM_LOG_SEARCH: Final[str] = "Swarm search: query={query}"
SWARM_LOG_DISCONNECTED: Final[str] = "Disconnected from swarm"
SWARM_LOG_ERROR: Final[str] = "Swarm error: {error}"

# MCP tool names
SWARM_TOOL_SEARCH: Final[str] = "swarm_search"
SWARM_TOOL_NODES: Final[str] = "swarm_nodes"
SWARM_TOOL_STATUS: Final[str] = "swarm_status"
SWARM_TOOL_FETCH: Final[str] = "swarm_fetch"
SWARM_TOOL_HEALTH_CHECK: Final[str] = "swarm_health_check"

# Health check
SWARM_HEALTH_CHECK_PATH: Final[str] = "/health"
SWARM_HEALTH_CHECK_TIMEOUT_SECONDS: Final[int] = 10
SWARM_HEALTH_STATUS_OK: Final[str] = "ok"

# Restart
SWARM_RESTART_SHUTDOWN_DELAY_SECONDS: Final[float] = 0.5
SWARM_RESTART_SUBPROCESS_DELAY_SECONDS: Final[int] = 2
SWARM_RESTART_STATUS_RESTARTING: Final[str] = "restarting"
SWARM_RESTART_ROUTE_TAG: Final[str] = "health"
SWARM_RESTART_ERROR_NO_SWARM_ID: Final[str] = "Cannot restart: no swarm ID in environment"
SWARM_RESTART_ERROR_SPAWN_DETAIL: Final[str] = "Failed to spawn restart process: {error}"
SWARM_RESTART_LOG_SPAWNING: Final[str] = "Spawning restart subprocess: %s"
SWARM_RESTART_LOG_SPAWN_FAILED: Final[str] = "Failed to spawn restart process: %s"
SWARM_RESTART_LOG_SCHEDULING_SHUTDOWN: Final[str] = "Scheduling shutdown in {delay}s"
SWARM_RESTART_LOG_SIGTERM: Final[str] = "Sending SIGTERM to self for restart"

# Swarm route tag
SWARM_ROUTE_TAG: Final[str] = "swarm"

# Config key for daemon port (inside swarm config.json)
CI_CONFIG_SWARM_KEY_PORT: Final[str] = "daemon_port"

# Port auto-assignment range (probes SWARM_DAEMON_DEFAULT_PORT + 0..99)
SWARM_DAEMON_PORT_RANGE_SIZE: Final[int] = 100

# Daemon API paths (deploy routes)
SWARM_DAEMON_API_PATH_DEPLOY_STATUS: Final[str] = "/api/deploy/status"
SWARM_DAEMON_API_PATH_DEPLOY_AUTH: Final[str] = "/api/deploy/auth"
SWARM_DAEMON_API_PATH_DEPLOY_SCAFFOLD: Final[str] = "/api/deploy/scaffold"
SWARM_DAEMON_API_PATH_DEPLOY_INSTALL: Final[str] = "/api/deploy/install"
SWARM_DAEMON_API_PATH_DEPLOY_RUN: Final[str] = "/api/deploy/run"
SWARM_DAEMON_API_PATH_DEPLOY_SETTINGS: Final[str] = "/api/deploy/settings"

# Daemon API path (node removal)
SWARM_DAEMON_API_PATH_NODE_REMOVE: Final[str] = "/api/swarm/nodes/remove"

# Fetch (detail expansion)
SWARM_DAEMON_API_PATH_FETCH: Final[str] = "/api/swarm/fetch"
SWARM_DEFAULT_FETCH_TIMEOUT_SECONDS: Final[int] = 15
MCP_TOOL_FETCH: Final[str] = "oak_fetch"
