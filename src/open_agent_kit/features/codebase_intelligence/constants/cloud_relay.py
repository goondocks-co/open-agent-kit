"""Cloud MCP relay constants."""

from typing import Final

# =============================================================================
# Cloud MCP Relay
# =============================================================================

# Timeouts and intervals
CLOUD_RELAY_DEFAULT_TOOL_TIMEOUT_SECONDS: Final[int] = 30
CLOUD_RELAY_DEFAULT_RECONNECT_MAX_SECONDS: Final[int] = 60
CLOUD_RELAY_HEARTBEAT_INTERVAL_SECONDS: Final[int] = 30
CLOUD_RELAY_HEARTBEAT_TIMEOUT_SECONDS: Final[int] = 10

# Payload limits
CLOUD_RELAY_MAX_RESPONSE_BYTES: Final[int] = 524288  # 512 KB
CLOUD_RELAY_TOKEN_BYTES: Final[int] = 32

# Config keys (inside codebase_intelligence.cloud_relay section)
CI_CONFIG_KEY_CLOUD_RELAY: Final[str] = "cloud_relay"
CI_CONFIG_CLOUD_RELAY_KEY_WORKER_URL: Final[str] = "worker_url"
CI_CONFIG_CLOUD_RELAY_KEY_TOKEN: Final[str] = "token"
CI_CONFIG_CLOUD_RELAY_KEY_AUTO_CONNECT: Final[str] = "auto_connect"
CI_CONFIG_CLOUD_RELAY_KEY_TOOL_TIMEOUT: Final[str] = "tool_timeout_seconds"
CI_CONFIG_CLOUD_RELAY_KEY_RECONNECT_MAX: Final[str] = "reconnect_max_seconds"
CI_CONFIG_CLOUD_RELAY_KEY_CUSTOM_DOMAIN: Final[str] = "custom_domain"

# API paths
CI_CLOUD_RELAY_API_PATH_CONNECT: Final[str] = "/api/cloud/connect"
CI_CLOUD_RELAY_API_PATH_DISCONNECT: Final[str] = "/api/cloud/disconnect"
CI_CLOUD_RELAY_API_PATH_STATUS: Final[str] = "/api/cloud/status"
CI_CLOUD_RELAY_API_URL_TEMPLATE: Final[str] = "{scheme}://{host}:{port}{path}"
CI_CLOUD_RELAY_ROUTE_TAG: Final[str] = "cloud-relay"

# Response keys
CLOUD_RELAY_RESPONSE_KEY_CONNECTED: Final[str] = "connected"
CLOUD_RELAY_RESPONSE_KEY_WORKER_URL: Final[str] = "worker_url"
CLOUD_RELAY_RESPONSE_KEY_CONNECTED_AT: Final[str] = "connected_at"
CLOUD_RELAY_RESPONSE_KEY_LAST_HEARTBEAT: Final[str] = "last_heartbeat"
CLOUD_RELAY_RESPONSE_KEY_ERROR: Final[str] = "error"
CLOUD_RELAY_RESPONSE_KEY_RECONNECT_ATTEMPTS: Final[str] = "reconnect_attempts"
CLOUD_RELAY_RESPONSE_KEY_CUSTOM_DOMAIN: Final[str] = "custom_domain"

# API status values
CLOUD_RELAY_API_STATUS_CONNECTED: Final[str] = "connected"
CLOUD_RELAY_API_STATUS_DISCONNECTED: Final[str] = "disconnected"
CLOUD_RELAY_API_STATUS_CONNECTING: Final[str] = "connecting"
CLOUD_RELAY_API_STATUS_ERROR: Final[str] = "error"
CLOUD_RELAY_API_STATUS_ALREADY_CONNECTED: Final[str] = "already_connected"
CLOUD_RELAY_API_STATUS_NOT_CONNECTED: Final[str] = "not_connected"

# CLI messages
CI_CLOUD_RELAY_MESSAGE_DAEMON_NOT_RUNNING: Final[str] = (
    "Daemon is not running. Start it first: oak ci start"
)
CI_CLOUD_RELAY_MESSAGE_CONNECTING: Final[str] = "Connecting to cloud relay..."
CI_CLOUD_RELAY_MESSAGE_CONNECTED: Final[str] = "Cloud relay connected: {worker_url}"
CI_CLOUD_RELAY_MESSAGE_CONNECTED_AT: Final[str] = "  Connected: {connected_at}"
CI_CLOUD_RELAY_MESSAGE_LAST_HEARTBEAT: Final[str] = "  Last heartbeat: {last_heartbeat}"
CI_CLOUD_RELAY_MESSAGE_RECONNECT_ATTEMPTS: Final[str] = "  Reconnect attempts: {reconnect_attempts}"
CI_CLOUD_RELAY_MESSAGE_ALREADY_CONNECTED: Final[str] = "Cloud relay already connected: {worker_url}"
CI_CLOUD_RELAY_MESSAGE_FAILED_CONNECT: Final[str] = "Failed to connect: {detail}"
CI_CLOUD_RELAY_MESSAGE_CONNECT_ERROR: Final[str] = "Cannot connect to daemon."
CI_CLOUD_RELAY_MESSAGE_TIMEOUT_CONNECT: Final[str] = (
    "Request timed out. Connection may still be in progress."
)
CI_CLOUD_RELAY_MESSAGE_NOT_CONNECTED: Final[str] = "Cloud relay is not connected."
CI_CLOUD_RELAY_MESSAGE_DISCONNECTED: Final[str] = "Cloud relay disconnected."
CI_CLOUD_RELAY_MESSAGE_FAILED_DISCONNECT: Final[str] = "Failed to disconnect: {detail}"
CI_CLOUD_RELAY_MESSAGE_TIMEOUT: Final[str] = "Request timed out."
CI_CLOUD_RELAY_MESSAGE_FAILED_STATUS: Final[str] = "Failed to get status: {detail}"

# Error messages (daemon-side)
CI_CLOUD_RELAY_ERROR_DAEMON_NOT_INITIALIZED: Final[str] = "Daemon not initialized"
CI_CLOUD_RELAY_ERROR_CONFIG_NOT_LOADED: Final[str] = "Configuration not loaded"
CI_CLOUD_RELAY_ERROR_NO_WORKER_URL: Final[str] = (
    "Worker URL not configured. Set cloud_relay.worker_url in .oak/config.yaml"
)
CI_CLOUD_RELAY_ERROR_NO_TOKEN: Final[str] = (
    "Relay token not configured. Set cloud_relay.token in .oak/config.yaml"
)
CI_CLOUD_RELAY_ERROR_CONNECT_FAILED: Final[str] = "Failed to connect to cloud relay: {error}"
CI_CLOUD_RELAY_ERROR_DISCONNECT_FAILED: Final[str] = "Error disconnecting: {error}"
CI_CLOUD_RELAY_ERROR_UNKNOWN: Final[str] = "Unknown error"

# Log messages (daemon-side)
CI_CLOUD_RELAY_LOG_CONNECTING: Final[str] = "Connecting to cloud relay at {worker_url}..."
CI_CLOUD_RELAY_LOG_CONNECTED: Final[str] = "Cloud relay connected: {worker_url}"
CI_CLOUD_RELAY_LOG_DISCONNECTED: Final[str] = "Cloud relay disconnected"
CI_CLOUD_RELAY_LOG_RECONNECTING: Final[str] = "Cloud relay reconnecting (attempt {attempt})..."
CI_CLOUD_RELAY_LOG_HEARTBEAT: Final[str] = "Cloud relay heartbeat sent"
CI_CLOUD_RELAY_LOG_HEARTBEAT_TIMEOUT: Final[str] = "Cloud relay heartbeat timed out"
CI_CLOUD_RELAY_LOG_ERROR: Final[str] = "Cloud relay error: {error}"
CI_CLOUD_RELAY_LOG_AUTO_CONNECT: Final[str] = "Auto-connecting cloud relay..."
CI_CLOUD_RELAY_LOG_AUTO_CONNECT_FAILED: Final[str] = "Cloud relay auto-connect failed: {error}"

# WebSocket protocol message types
CLOUD_RELAY_WS_TYPE_REGISTER: Final[str] = "register"
CLOUD_RELAY_WS_TYPE_TOOL_CALL: Final[str] = "tool_call"
CLOUD_RELAY_WS_TYPE_TOOL_RESULT: Final[str] = "tool_result"
CLOUD_RELAY_WS_TYPE_HEARTBEAT: Final[str] = "heartbeat"
CLOUD_RELAY_WS_TYPE_HEARTBEAT_ACK: Final[str] = "heartbeat_ack"
CLOUD_RELAY_WS_TYPE_ERROR: Final[str] = "error"
CLOUD_RELAY_WS_TYPE_REGISTERED: Final[str] = "registered"
CLOUD_RELAY_WS_TYPE_HTTP_REQUEST: Final[str] = "http_request"
CLOUD_RELAY_WS_TYPE_HTTP_RESPONSE: Final[str] = "http_response"
CLOUD_RELAY_WS_TYPE_OBS_PUSH: Final[str] = "obs_push"
CLOUD_RELAY_WS_TYPE_OBS_BATCH: Final[str] = "obs_batch"
CLOUD_RELAY_WS_TYPE_NODE_LIST: Final[str] = "node_list"
CLOUD_RELAY_WS_TYPE_SEARCH_QUERY: Final[str] = "search_query"
CLOUD_RELAY_WS_TYPE_SEARCH_RESULT: Final[str] = "search_result"

# WebSocket protocol field names
CLOUD_RELAY_WS_FIELD_TYPE: Final[str] = "type"
CLOUD_RELAY_WS_FIELD_TOKEN: Final[str] = "token"
CLOUD_RELAY_WS_FIELD_TOOLS: Final[str] = "tools"
CLOUD_RELAY_WS_FIELD_CALL_ID: Final[str] = "call_id"
CLOUD_RELAY_WS_FIELD_TOOL_NAME: Final[str] = "tool_name"
CLOUD_RELAY_WS_FIELD_ARGUMENTS: Final[str] = "arguments"
CLOUD_RELAY_WS_FIELD_RESULT: Final[str] = "result"
CLOUD_RELAY_WS_FIELD_ERROR: Final[str] = "error"
CLOUD_RELAY_WS_FIELD_TIMESTAMP: Final[str] = "timestamp"

# WebSocket close codes (RFC 6455)
CLOUD_RELAY_WS_CLOSE_NORMAL: Final[int] = 1000
CLOUD_RELAY_WS_CLOSE_GOING_AWAY: Final[int] = 1001
CLOUD_RELAY_WS_CLOSE_AUTH_FAILED: Final[int] = 4001
CLOUD_RELAY_WS_CLOSE_TOKEN_INVALID: Final[int] = 4003

# Scaffold constants
CLOUD_RELAY_WORKER_TEMPLATE_DIR: Final[str] = "worker_template"
CLOUD_RELAY_SCAFFOLD_OUTPUT_DIR: Final[str] = ".oak/ci/cloud-relay"
CLOUD_RELAY_JINJA2_EXTENSION: Final[str] = ".j2"

# Scaffold .gitignore entries
CLOUD_RELAY_SCAFFOLD_GITIGNORE_ENTRIES: Final[tuple[str, ...]] = (
    "wrangler.toml",
    "node_modules/",
    ".wrangler/",
)

# Deploy subprocess timeouts (seconds)
CLOUD_RELAY_DEPLOY_NPM_INSTALL_TIMEOUT: Final[int] = 120
CLOUD_RELAY_DEPLOY_WRANGLER_TIMEOUT: Final[int] = 60
CLOUD_RELAY_DEPLOY_WRANGLER_URL_PATTERN: Final[str] = r"https://[^\s]+\.workers\.dev[^\s]*"
CLOUD_RELAY_DEPLOY_WRANGLER_WHOAMI_TIMEOUT: Final[int] = 15

# Agent token config key
CI_CONFIG_CLOUD_RELAY_KEY_AGENT_TOKEN: Final[str] = "agent_token"

# Worker name config key and default prefix
CI_CONFIG_CLOUD_RELAY_KEY_WORKER_NAME: Final[str] = "worker_name"
CLOUD_RELAY_DEFAULT_WORKER_NAME_PREFIX: Final[str] = "oak-relay"

# Start/stop/preflight/settings API paths
CI_CLOUD_RELAY_API_PATH_START: Final[str] = "/api/cloud/start"
CI_CLOUD_RELAY_API_PATH_STOP: Final[str] = "/api/cloud/stop"
CI_CLOUD_RELAY_API_PATH_PREFLIGHT: Final[str] = "/api/cloud/preflight"
CI_CLOUD_RELAY_API_PATH_SETTINGS: Final[str] = "/api/cloud/settings"

# Start endpoint response keys
CLOUD_RELAY_RESPONSE_KEY_STATUS: Final[str] = "status"
CLOUD_RELAY_RESPONSE_KEY_MCP_ENDPOINT: Final[str] = "mcp_endpoint"
CLOUD_RELAY_RESPONSE_KEY_AGENT_TOKEN: Final[str] = "agent_token"
CLOUD_RELAY_RESPONSE_KEY_PHASE: Final[str] = "phase"
CLOUD_RELAY_RESPONSE_KEY_CF_ACCOUNT_NAME: Final[str] = "cf_account_name"
CLOUD_RELAY_RESPONSE_KEY_SUGGESTION: Final[str] = "suggestion"
CLOUD_RELAY_RESPONSE_KEY_DETAIL: Final[str] = "detail"

# Start endpoint phase names
CLOUD_RELAY_PHASE_SCAFFOLD: Final[str] = "scaffold"
CLOUD_RELAY_PHASE_NPM_INSTALL: Final[str] = "npm_install"
CLOUD_RELAY_PHASE_AUTH_CHECK: Final[str] = "auth_check"
CLOUD_RELAY_PHASE_DEPLOY: Final[str] = "deploy"
CLOUD_RELAY_PHASE_CONNECT: Final[str] = "connect"
CLOUD_RELAY_PHASE_COMPLETE: Final[str] = "complete"

# Start endpoint status values
CLOUD_RELAY_START_STATUS_OK: Final[str] = "ok"
CLOUD_RELAY_START_STATUS_ERROR: Final[str] = "error"

# MCP endpoint suffix (appended to worker URL) — Streamable HTTP transport
CLOUD_RELAY_MCP_ENDPOINT_SUFFIX: Final[str] = "/mcp"

# CLI messages for cloud-init (start-based)
CI_CLOUD_RELAY_MESSAGE_STARTING: Final[str] = "Deploying cloud relay..."
CI_CLOUD_RELAY_MESSAGE_PHASE: Final[str] = "  Phase: {phase}"
CI_CLOUD_RELAY_MESSAGE_WORKER_URL: Final[str] = "Worker URL: {worker_url}"
CI_CLOUD_RELAY_MESSAGE_MCP_ENDPOINT: Final[str] = "MCP endpoint: {mcp_endpoint}"
CI_CLOUD_RELAY_MESSAGE_AGENT_TOKEN: Final[str] = "Agent token: {agent_token}"
CI_CLOUD_RELAY_MESSAGE_SAVE_TOKEN: Final[str] = "Save this token - it will not be shown again."
CI_CLOUD_RELAY_MESSAGE_FAILED_START: Final[str] = "Failed to deploy: {error}"
CI_CLOUD_RELAY_MESSAGE_SUGGESTION: Final[str] = "Suggestion: {suggestion}"
CI_CLOUD_RELAY_MESSAGE_DEPLOY_DETAIL: Final[str] = "Detail: {detail}"

# Deploy error suggestions
CLOUD_RELAY_SUGGESTION_INSTALL_NPM: Final[str] = "Install Node.js and npm: https://nodejs.org/"
CLOUD_RELAY_SUGGESTION_INSTALL_WRANGLER: Final[str] = "Install wrangler: npm install -g wrangler"
CLOUD_RELAY_SUGGESTION_WRANGLER_LOGIN: Final[str] = (
    "Run 'npx wrangler login' to authenticate with Cloudflare"
)
CLOUD_RELAY_SUGGESTION_NPM_INSTALL_FAILED: Final[str] = "Check network connectivity and try again"
CLOUD_RELAY_SUGGESTION_DEPLOY_FAILED: Final[str] = "Check wrangler output above for details"

# WebSocket client configuration
CLOUD_RELAY_WS_ENDPOINT_PATH: Final[str] = "/ws"
CLOUD_RELAY_RECONNECT_BASE_DELAY_SECONDS: Final[float] = 1.0
CLOUD_RELAY_RECONNECT_BACKOFF_FACTOR: Final[float] = 2.0
CLOUD_RELAY_DAEMON_CALL_OVERHEAD_SECONDS: Final[int] = 5
CLOUD_RELAY_CLIENT_NAME: Final[str] = "cloud-relay-websocket"

# Daemon MCP forwarding (used by cloud relay client to call local daemon)
CLOUD_RELAY_DAEMON_MCP_CALL_URL_TEMPLATE: Final[str] = (
    "http://127.0.0.1:{port}/api/mcp/call?tool_name={tool_name}"
)
CLOUD_RELAY_DAEMON_MCP_TOOLS_URL_TEMPLATE: Final[str] = "http://127.0.0.1:{port}/api/mcp/tools"
CLOUD_RELAY_DAEMON_MCP_TOOLS_RESPONSE_KEY: Final[str] = "tools"
CLOUD_RELAY_DAEMON_TOOL_LIST_TIMEOUT_SECONDS: Final[float] = 10.0

# HTTP proxy forwarding (used by cloud relay client for team API proxying)
CLOUD_RELAY_DAEMON_HTTP_PROXY_URL_TEMPLATE: Final[str] = "http://127.0.0.1:{port}{path}"
CLOUD_RELAY_HTTP_PROXY_TIMEOUT_SECONDS: Final[float] = 30.0
CLOUD_RELAY_OBS_DRAIN_TIMEOUT_SECONDS: Final[float] = 30.0

# SSRF protection: only proxy requests to these path prefixes
CLOUD_RELAY_ALLOWED_PROXY_PREFIXES: Final[tuple[str, ...]] = ("/api/team/",)
CLOUD_RELAY_PROXY_FORBIDDEN_STATUS: Final[int] = 403

# Auth failure HTTP status codes (stop reconnect loop on these)
CLOUD_RELAY_AUTH_FAILURE_STATUS_CODES: Final[frozenset[int]] = frozenset({401, 403})

# WebSocket protocol — additional fields and default messages
CLOUD_RELAY_WS_FIELD_MESSAGE: Final[str] = "message"
CLOUD_RELAY_WS_FIELD_TIMEOUT_MS: Final[str] = "timeout_ms"
CLOUD_RELAY_WS_DEFAULT_REGISTRATION_REJECTED: Final[str] = "Registration rejected"
CLOUD_RELAY_WS_DEFAULT_UNKNOWN_RELAY_ERROR: Final[str] = "Unknown relay error"

# Scaffold file names
CLOUD_RELAY_SCAFFOLD_PACKAGE_JSON: Final[str] = "package.json"
CLOUD_RELAY_SCAFFOLD_WRANGLER_TOML: Final[str] = "wrangler.toml"
CLOUD_RELAY_SCAFFOLD_NODE_MODULES_DIR: Final[str] = "node_modules"

# Worker name constraints
CLOUD_RELAY_WORKER_NAME_MAX_LENGTH: Final[int] = 63
CLOUD_RELAY_WORKER_NAME_FALLBACK: Final[str] = "default"

# Deploy subprocess error strings (cross-referenced in route logic)
CLOUD_RELAY_DEPLOY_NPM_NOT_FOUND: Final[str] = "npm not found"
CLOUD_RELAY_DEPLOY_NPX_NOT_FOUND: Final[str] = "npx/wrangler not found"

# Start endpoint error messages
CLOUD_RELAY_ERROR_NPM_INSTALL_FAILED: Final[str] = "npm install failed"
CLOUD_RELAY_ERROR_NOT_AUTHENTICATED: Final[str] = "Not authenticated with Cloudflare"
CLOUD_RELAY_ERROR_DEPLOY_FAILED: Final[str] = "wrangler deploy failed"
CLOUD_RELAY_ERROR_NO_DEPLOY_URL: Final[str] = "Could not parse Worker URL from deploy output"
CLOUD_RELAY_ERROR_CONNECTION_FAILED: Final[str] = "Connection failed"

# Start endpoint phase log messages
CI_CLOUD_RELAY_LOG_PHASE_SCAFFOLD: Final[str] = "Cloud relay: scaffolding Worker project"
CI_CLOUD_RELAY_LOG_PHASE_SCAFFOLD_SKIP: Final[str] = (
    "Cloud relay: scaffold already exists, skipping"
)
CI_CLOUD_RELAY_LOG_PHASE_NPM_INSTALL: Final[str] = "Cloud relay: running npm install"
CI_CLOUD_RELAY_LOG_PHASE_NPM_INSTALL_SKIP: Final[str] = (
    "Cloud relay: node_modules exists, skipping npm install"
)
CI_CLOUD_RELAY_LOG_PHASE_AUTH_CHECK: Final[str] = "Cloud relay: checking wrangler authentication"
CI_CLOUD_RELAY_LOG_PHASE_DEPLOY: Final[str] = "Cloud relay: deploying Worker via wrangler"
CI_CLOUD_RELAY_LOG_PHASE_DEPLOY_SKIP: Final[str] = (
    "Cloud relay: worker_url already configured, skipping deploy"
)
CI_CLOUD_RELAY_LOG_HEALTH_404: Final[str] = (
    "Cloud relay: cached worker_url %s returned 404, re-deploying"
)
CI_CLOUD_RELAY_LOG_HEALTH_UNREACHABLE: Final[str] = (
    "Cloud relay: cached worker_url %s unreachable, re-deploying"
)

# Health check constants
CLOUD_RELAY_HEALTH_CHECK_PATH: Final[str] = "/health"
CLOUD_RELAY_HEALTH_CHECK_TIMEOUT_SECONDS: Final[int] = 10

# Preflight response keys
CLOUD_RELAY_PREFLIGHT_KEY_NPM_AVAILABLE: Final[str] = "npm_available"
CLOUD_RELAY_PREFLIGHT_KEY_WRANGLER_AVAILABLE: Final[str] = "wrangler_available"
CLOUD_RELAY_PREFLIGHT_KEY_WRANGLER_AUTHENTICATED: Final[str] = "wrangler_authenticated"
CLOUD_RELAY_PREFLIGHT_KEY_CF_ACCOUNT_NAME: Final[str] = "cf_account_name"
CLOUD_RELAY_PREFLIGHT_KEY_CF_ACCOUNT_ID: Final[str] = "cf_account_id"
CLOUD_RELAY_PREFLIGHT_KEY_SCAFFOLDED: Final[str] = "scaffolded"
CLOUD_RELAY_PREFLIGHT_KEY_INSTALLED: Final[str] = "installed"
CLOUD_RELAY_PREFLIGHT_KEY_DEPLOYED: Final[str] = "deployed"
CLOUD_RELAY_PREFLIGHT_KEY_WORKER_URL: Final[str] = "worker_url"

# Request body keys (used by start endpoint and CLI)
CLOUD_RELAY_REQUEST_KEY_WORKER_URL: Final[str] = "worker_url"
CLOUD_RELAY_REQUEST_KEY_TOKEN: Final[str] = "token"
CLOUD_RELAY_REQUEST_KEY_FORCE: Final[str] = "force"
CLOUD_RELAY_REQUEST_KEY_AGENT_TOKEN: Final[str] = "agent_token"

# Worker name response key (used by UI to derive custom subdomain preview)
CLOUD_RELAY_RESPONSE_KEY_WORKER_NAME: Final[str] = "worker_name"

# Template hash config key (persisted in cloud_relay config section)
CI_CONFIG_CLOUD_RELAY_KEY_DEPLOYED_TEMPLATE_HASH: Final[str] = "deployed_template_hash"

# Status response key for Worker template update detection
CLOUD_RELAY_RESPONSE_KEY_UPDATE_AVAILABLE: Final[str] = "update_available"

# Observation stats endpoint path
CLOUD_RELAY_OBS_STATS_PATH: Final[str] = "/obs/stats"
CLOUD_RELAY_OBS_STATS_TIMEOUT_SECONDS: Final[float] = 5.0

# Capability identifiers (sent in RegisterMessage for feature negotiation)
CLOUD_RELAY_CAPABILITY_OBS_SYNC: Final[str] = "obs_sync_v1"
CLOUD_RELAY_CAPABILITY_FEDERATED_SEARCH: Final[str] = "federated_search_v1"

# Federated search
CLOUD_RELAY_FEDERATED_SEARCH_TIMEOUT_SECONDS: Final[float] = 3.0
CLOUD_RELAY_FEDERATED_SEARCH_DEFAULT_LIMIT: Final[int] = 10
CLOUD_RELAY_OBS_HISTORY_PATH: Final[str] = "/obs/history"
CLOUD_RELAY_SEARCH_PATH: Final[str] = "/search"

# Daemon local search forwarding (used by cloud relay client to query local daemon)
CLOUD_RELAY_DAEMON_SEARCH_URL_TEMPLATE: Final[str] = "http://127.0.0.1:{port}/api/search"
CLOUD_RELAY_DAEMON_SEARCH_TIMEOUT_SECONDS: Final[float] = 10.0

# CLI additional messages
CI_CLOUD_RELAY_MESSAGE_CONNECTING_RELAY: Final[str] = "Connecting to cloud relay..."
CI_CLOUD_RELAY_MESSAGE_LAST_ERROR: Final[str] = "  Last error: {error}"
