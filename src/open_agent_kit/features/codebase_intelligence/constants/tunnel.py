"""Tunnel sharing constants (cloudflared, ngrok)."""

from typing import Final

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

# Cloudflared URL parsing
CLOUDFLARED_URL_PATTERN: Final[str] = r"https://[a-z0-9-]+\.trycloudflare\.com"

# ngrok JSON log key for tunnel URL
# ngrok outputs JSON logs with --log-format json; the tunnel URL appears in
# a log line with "msg":"started tunnel" and "url":"https://xxx.ngrok-free.app"
NGROK_LOG_MSG_STARTED: Final[str] = "started tunnel"
NGROK_LOG_KEY_URL: Final[str] = "url"
NGROK_LOG_KEY_MSG: Final[str] = "msg"
