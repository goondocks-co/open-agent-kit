"""Constants for the ACP server feature.

All string literals and configuration values are centralized here
per OAK's zero-magic-strings rule.
"""

# Agent identity
ACP_AGENT_NAME = "oak"
ACP_AGENT_DISPLAY_NAME = "OAK Agent"
ACP_AGENT_DESCRIPTION = (
    "AI-powered development workflows with project conventions and codebase intelligence"
)

# Tool kind classification for ACP
ACP_READ_TOOLS = frozenset({"Read", "Glob", "Grep", "LS", "NotebookRead"})
ACP_EDIT_TOOLS = frozenset({"Edit", "MultiEdit", "Write", "NotebookEdit"})
ACP_COMMAND_TOOLS = frozenset({"Bash", "Task"})
# These values must match acp.schema.ToolKind literals
ACP_TOOL_KIND_READ = "read"
ACP_TOOL_KIND_EDIT = "edit"
ACP_TOOL_KIND_COMMAND = "execute"

# Session modes (advertised to editor via ACP)
ACP_MODE_DEFAULT = "default"
ACP_MODE_ACCEPT_EDITS = "acceptEdits"
ACP_MODE_PLAN = "plan"
ACP_VALID_MODES = frozenset({ACP_MODE_DEFAULT, ACP_MODE_ACCEPT_EDITS, ACP_MODE_PLAN})

# ACP session modes (editor-facing identifiers)
ACP_SESSION_MODE_CODE = "code"
ACP_SESSION_MODE_ARCHITECT = "architect"
ACP_SESSION_MODE_ASK = "ask"

# Config option IDs (ACP configOptions)
ACP_CONFIG_ID_MODE = "mode"
ACP_CONFIG_ID_FOCUS = "focus"
ACP_CONFIG_CATEGORY_FOCUS = "_focus"

# Focus values (match agent template names in the registry)
ACP_FOCUS_OAK = "oak"
ACP_FOCUS_DOCUMENTATION = "documentation"
ACP_FOCUS_ANALYSIS = "analysis"
ACP_FOCUS_ENGINEERING = "engineering"
ACP_FOCUS_MAINTENANCE = "maintenance"

ACP_VALID_FOCUSES = frozenset(
    {
        ACP_FOCUS_OAK,
        ACP_FOCUS_DOCUMENTATION,
        ACP_FOCUS_ANALYSIS,
        ACP_FOCUS_ENGINEERING,
        ACP_FOCUS_MAINTENANCE,
    }
)

# Daemon API endpoint for focus changes
ACP_DAEMON_FOCUS_ENDPOINT = "/api/acp/sessions/{session_id}/focus"

# Error messages
ACP_ERROR_SESSION_NOT_FOUND = "Session not found: {session_id}"
ACP_ERROR_INVALID_MODE = "Invalid permission mode: {mode}. Valid modes: {valid_modes}"
ACP_ERROR_INVALID_FOCUS = "Invalid focus: {focus}. Valid focuses: {valid_focuses}"
ACP_ERROR_NO_PROJECT_ROOT = "OAK is not initialized in the current directory. Run 'oak init' first."

# Daemon communication errors
ACP_ERROR_DAEMON_UNREACHABLE = "OAK daemon is not running. Start it with 'oak ci start'."
ACP_ERROR_DAEMON_SESSION_FAILED = "Failed to create daemon session: {error}"
ACP_ERROR_DAEMON_PROMPT_FAILED = "Failed to send prompt to daemon: {error}"

# Daemon API endpoints
ACP_DAEMON_SESSION_ENDPOINT = "/api/acp/sessions"
ACP_DAEMON_PROMPT_ENDPOINT = "/api/acp/sessions/{session_id}/prompt"
ACP_DAEMON_CANCEL_ENDPOINT = "/api/acp/sessions/{session_id}/cancel"
ACP_DAEMON_MODE_ENDPOINT = "/api/acp/sessions/{session_id}/mode"
ACP_DAEMON_APPROVE_PLAN_ENDPOINT = "/api/acp/sessions/{session_id}/approve-plan"
ACP_DAEMON_CLOSE_ENDPOINT = "/api/acp/sessions/{session_id}"

# Daemon discovery
ACP_DAEMON_PORT_FILE = "oak/daemon.port"
ACP_DAEMON_PORT_FILE_LOCAL = ".oak/ci/daemon.port"

# Logging
ACP_LOG_FILE = "acp.log"
ACP_LOG_SERVER_STARTING = "ACP server starting via stdio transport"
ACP_LOG_SESSION_CREATED = "ACP session created: {session_id} (cwd={cwd})"
ACP_LOG_PROMPT_RECEIVED = "ACP prompt received for session: {session_id}"
ACP_LOG_SESSION_CANCELLED = "ACP session cancelled: {session_id}"
ACP_LOG_DAEMON_CONNECTING = "Connecting to OAK daemon at {url}"
ACP_LOG_DAEMON_SESSION_CREATED = "Daemon session created: {session_id}"
