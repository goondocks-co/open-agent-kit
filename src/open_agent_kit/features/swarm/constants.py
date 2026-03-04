"""Swarm constants."""

from typing import Final

from open_agent_kit.utils.worker_deploy_shared import (
    WORKER_DEPLOY_NPM_INSTALL_TIMEOUT,
    WORKER_DEPLOY_NPM_NOT_FOUND,
    WORKER_DEPLOY_NPX_NOT_FOUND,
    WORKER_DEPLOY_WRANGLER_TIMEOUT,
    WORKER_DEPLOY_WRANGLER_URL_PATTERN,
    WORKER_DEPLOY_WRANGLER_WHOAMI_TIMEOUT,
)
from open_agent_kit.utils.worker_scaffold_shared import (
    WORKER_JINJA2_EXTENSION,
    WORKER_NAME_FALLBACK,
    WORKER_NAME_MAX_LENGTH,
    WORKER_SCAFFOLD_GITIGNORE_ENTRIES,
    WORKER_SCAFFOLD_NODE_MODULES_DIR,
    WORKER_SCAFFOLD_PACKAGE_JSON,
    WORKER_SCAFFOLD_WRANGLER_TOML,
    WORKER_TOKEN_BYTES,
)

# =============================================================================
# Swarm
# =============================================================================

# Timeouts and intervals
SWARM_DEFAULT_SEARCH_TIMEOUT_SECONDS: Final[int] = 10
SWARM_DEFAULT_TOOL_TIMEOUT_SECONDS: Final[int] = 30
SWARM_HEARTBEAT_INTERVAL_SECONDS: Final[int] = 60
SWARM_STALE_THRESHOLD_SECONDS: Final[int] = 300  # 5 minutes
SWARM_TOKEN_BYTES: Final[int] = WORKER_TOKEN_BYTES

# Payload limits
SWARM_MAX_RESPONSE_BYTES: Final[int] = 1048576  # 1 MB

# Config keys (inside codebase_intelligence.swarm section)
CI_CONFIG_KEY_SWARM: Final[str] = "swarm"
CI_CONFIG_SWARM_KEY_URL: Final[str] = "swarm_url"
CI_CONFIG_SWARM_KEY_TOKEN: Final[str] = "swarm_token"
CI_CONFIG_SWARM_KEY_SENSITIVITY: Final[str] = "sensitivity"
CI_CONFIG_SWARM_KEY_SWARM_ID: Final[str] = "swarm_id"

# API paths (Swarm Worker HTTP API)
SWARM_API_PATH_REGISTER: Final[str] = "/api/swarm/register"
SWARM_API_PATH_HEARTBEAT: Final[str] = "/api/swarm/heartbeat"
SWARM_API_PATH_SEARCH: Final[str] = "/api/swarm/search"
SWARM_API_PATH_TOOL_CALL: Final[str] = "/api/swarm/tool-call"
SWARM_API_PATH_BROADCAST: Final[str] = "/api/swarm/broadcast"
SWARM_API_PATH_NODES: Final[str] = "/api/swarm/nodes"
SWARM_API_PATH_UNREGISTER: Final[str] = "/api/swarm/unregister"
SWARM_API_PATH_CONFIG: Final[str] = "/api/swarm/config"

# Daemon API paths (local swarm daemon)
SWARM_DAEMON_API_PATH_HEALTH: Final[str] = "/api/health"
SWARM_DAEMON_API_PATH_SEARCH: Final[str] = "/api/swarm/search"
SWARM_DAEMON_API_PATH_NODES: Final[str] = "/api/swarm/nodes"
SWARM_DAEMON_API_PATH_STATUS: Final[str] = "/api/swarm/status"
SWARM_DAEMON_API_PATH_TOOL_CALL: Final[str] = "/api/swarm/tool-call"
SWARM_DAEMON_API_PATH_BROADCAST: Final[str] = "/api/swarm/broadcast"
SWARM_DAEMON_API_PATH_AGENTS: Final[str] = "/api/agents"

# Daemon UI API paths (local swarm daemon - UI endpoints)
SWARM_DAEMON_API_PATH_RESTART: Final[str] = "/api/restart"
SWARM_DAEMON_API_PATH_LOGS: Final[str] = "/api/logs"
SWARM_DAEMON_API_PATH_DEPLOY_STATUS: Final[str] = "/api/deploy/status"
SWARM_DAEMON_API_PATH_DEPLOY_AUTH: Final[str] = "/api/deploy/auth"
SWARM_DAEMON_API_PATH_DEPLOY_SCAFFOLD: Final[str] = "/api/deploy/scaffold"
SWARM_DAEMON_API_PATH_DEPLOY_INSTALL: Final[str] = "/api/deploy/install"
SWARM_DAEMON_API_PATH_DEPLOY_RUN: Final[str] = "/api/deploy/run"

# WebSocket protocol message types (node <-> Team Worker)
SWARM_WS_TYPE_SEARCH: Final[str] = "swarm_search"
SWARM_WS_TYPE_SEARCH_RESULT: Final[str] = "swarm_search_result"
SWARM_WS_TYPE_TOOL_CALL: Final[str] = "swarm_tool_call"
SWARM_WS_TYPE_TOOL_RESULT: Final[str] = "swarm_tool_result"
SWARM_WS_TYPE_BROADCAST: Final[str] = "swarm_broadcast"
SWARM_WS_TYPE_BROADCAST_RESULT: Final[str] = "swarm_broadcast_result"
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
SWARM_CAPABILITY_TOOLS: Final[str] = "swarm_tools_v1"

# Scaffold constants
SWARM_WORKER_TEMPLATE_DIR: Final[str] = "worker_template"
SWARM_SCAFFOLD_OUTPUT_DIR: Final[str] = ".oak/ci/swarm-worker"
SWARM_JINJA2_EXTENSION: Final[str] = WORKER_JINJA2_EXTENSION
SWARM_SCAFFOLD_GITIGNORE_ENTRIES: Final[tuple[str, ...]] = WORKER_SCAFFOLD_GITIGNORE_ENTRIES
SWARM_SCAFFOLD_PACKAGE_JSON: Final[str] = WORKER_SCAFFOLD_PACKAGE_JSON
SWARM_SCAFFOLD_WRANGLER_TOML: Final[str] = WORKER_SCAFFOLD_WRANGLER_TOML
SWARM_SCAFFOLD_NODE_MODULES_DIR: Final[str] = WORKER_SCAFFOLD_NODE_MODULES_DIR

# Scaffold subdirectory (inside swarm config dir)
SWARM_SCAFFOLD_WORKER_SUBDIR: Final[str] = "worker"

# Worker name
SWARM_DEFAULT_WORKER_NAME_PREFIX: Final[str] = "oak-swarm"
SWARM_WORKER_NAME_MAX_LENGTH: Final[int] = WORKER_NAME_MAX_LENGTH
SWARM_WORKER_NAME_FALLBACK: Final[str] = WORKER_NAME_FALLBACK

# Deploy timeouts
SWARM_DEPLOY_NPM_INSTALL_TIMEOUT: Final[int] = WORKER_DEPLOY_NPM_INSTALL_TIMEOUT
SWARM_DEPLOY_WRANGLER_TIMEOUT: Final[int] = WORKER_DEPLOY_WRANGLER_TIMEOUT
SWARM_DEPLOY_WRANGLER_URL_PATTERN: Final[str] = WORKER_DEPLOY_WRANGLER_URL_PATTERN
SWARM_DEPLOY_WRANGLER_WHOAMI_TIMEOUT: Final[int] = WORKER_DEPLOY_WRANGLER_WHOAMI_TIMEOUT
SWARM_DEPLOY_NPM_NOT_FOUND: Final[str] = WORKER_DEPLOY_NPM_NOT_FOUND
SWARM_DEPLOY_NPX_NOT_FOUND: Final[str] = WORKER_DEPLOY_NPX_NOT_FOUND

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

# Error messages
SWARM_ERROR_NOT_CONNECTED: Final[str] = "Not connected to swarm"
SWARM_ERROR_SEARCH_FAILED: Final[str] = "Swarm search failed: {error}"
SWARM_ERROR_TOOL_CALL_FAILED: Final[str] = "Swarm tool call failed: {error}"
SWARM_ERROR_BROADCAST_FAILED: Final[str] = "Swarm broadcast failed: {error}"
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
SWARM_TOOL_CALL: Final[str] = "swarm_call"
SWARM_TOOL_BROADCAST: Final[str] = "swarm_broadcast"
SWARM_TOOL_STATUS: Final[str] = "swarm_status"

# Health check
SWARM_HEALTH_CHECK_PATH: Final[str] = "/health"
SWARM_HEALTH_CHECK_TIMEOUT_SECONDS: Final[int] = 10

# Swarm route tag
SWARM_ROUTE_TAG: Final[str] = "swarm"
