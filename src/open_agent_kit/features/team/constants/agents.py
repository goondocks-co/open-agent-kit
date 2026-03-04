"""Agent name and agent subsystem constants."""

from typing import Final

# =============================================================================
# Agent Names (for hooks)
# =============================================================================

AGENT_CLAUDE: Final[str] = "claude"
AGENT_CURSOR: Final[str] = "cursor"
AGENT_GEMINI: Final[str] = "gemini"
AGENT_COPILOT: Final[str] = "vscode-copilot"
AGENT_CODEX: Final[str] = "codex"
AGENT_UNKNOWN: Final[str] = "unknown"
SUPPORTED_HOOK_AGENTS: Final[tuple[str, ...]] = (
    AGENT_CLAUDE,
    AGENT_CURSOR,
    AGENT_GEMINI,
    AGENT_COPILOT,
    AGENT_CODEX,
)

# Agents that use the hookSpecificOutput protocol for context injection.
# Used by format_hook_output() in the daemon to wrap injected context in
# the hookSpecificOutput envelope.  Both Claude Code and VS Code Copilot
# understand this format for events that support it.
AGENTS_HOOK_SPECIFIC_OUTPUT: Final[tuple[str, ...]] = (
    AGENT_CLAUDE,
    AGENT_COPILOT,
)

# Agents that REQUIRE hookSpecificOutput in EVERY hook response.
# VS Code Copilot crashes if hookSpecificOutput is missing from any response
# (accesses .additionalContext on undefined).
# Claude Code does NOT belong here — it validates hookSpecificOutput against
# its schema and rejects empty objects for events without specific output
# (e.g. SessionEnd, Stop).  For Claude, the daemon already returns proper
# hookSpecificOutput for events that support it; no CLI safety net is needed.
AGENTS_REQUIRE_HOOK_SPECIFIC_OUTPUT: Final[tuple[str, ...]] = (AGENT_COPILOT,)

# Hook events where VS Code Copilot docs claim hookSpecificOutput is supported.
# Retained for reference, but empirically VS Code requires hookSpecificOutput
# in ALL hook responses — omitting it for ANY event crashes VS Code with:
#   "Cannot read properties of undefined (reading 'hookSpecificOutput')"
#
# The daemon format_hook_output() now returns hookSpecificOutput for ALL
# vscode-copilot events.  The CLI safety net in hooks.py also ensures
# hookSpecificOutput is always present for AGENTS_REQUIRE_HOOK_SPECIFIC_OUTPUT.
#
# Based on VS Code Copilot hook schema:
#   https://code.visualstudio.com/docs/copilot/customization/hooks
COPILOT_EVENTS_WITH_HOOK_SPECIFIC_OUTPUT: Final[tuple[str, ...]] = (
    "SessionStart",
    "PreToolUse",
    "PostToolUse",
    "SubagentStart",
    "SubagentStop",
    "Stop",
)

# =============================================================================
# Agent Subsystem Constants
# =============================================================================

# Agent definition directories
AGENTS_DIR: Final[str] = "agents"
AGENTS_DEFINITIONS_DIR: Final[str] = "definitions"
AGENTS_TASKS_SUBDIR: Final[str] = "tasks"  # Tasks subdirectory within each agent definition
AGENT_DEFINITION_FILENAME: Final[str] = "agent.yaml"
AGENT_PROMPTS_DIR: Final[str] = "prompts"
AGENT_SYSTEM_PROMPT_FILENAME: Final[str] = "system.md"
AGENT_TASK_TEMPLATE_FILENAME: Final[str] = "task.yaml"  # Jinja2 template for new tasks

# Agent execution defaults
DEFAULT_AGENT_MAX_TURNS: Final[int] = 50
DEFAULT_AGENT_TIMEOUT_SECONDS: Final[int] = 600
MAX_AGENT_MAX_TURNS: Final[int] = 500
MAX_AGENT_TIMEOUT_SECONDS: Final[int] = 3600
MIN_AGENT_TIMEOUT_SECONDS: Final[int] = 60

# Agent recovery and shutdown timeouts
AGENT_RUN_RECOVERY_BUFFER_SECONDS: Final[int] = 300  # 5 min grace before marking stale
SHUTDOWN_TASK_TIMEOUT_SECONDS: Final[float] = 10.0  # Timeout for canceling background tasks
SCHEDULER_STOP_TIMEOUT_SECONDS: Final[float] = 5.0  # Timeout for stopping scheduler loop
AGENT_INTERRUPT_GRACE_SECONDS: Final[float] = 2.0  # Grace period after interrupt before timeout

# Agent retry configuration (for transient failures)
AGENT_RETRY_MAX_ATTEMPTS: Final[int] = 3  # Maximum retry attempts for transient failures
AGENT_RETRY_BASE_DELAY: Final[float] = (
    1.0  # Base delay in seconds (exponential backoff: 1s, 2s, 4s)
)

# Agent run status values (match AgentRunStatus enum)
AGENT_STATUS_PENDING: Final[str] = "pending"
AGENT_STATUS_RUNNING: Final[str] = "running"
AGENT_STATUS_COMPLETED: Final[str] = "completed"
AGENT_STATUS_FAILED: Final[str] = "failed"
AGENT_STATUS_CANCELLED: Final[str] = "cancelled"
AGENT_STATUS_TIMEOUT: Final[str] = "timeout"

# Agent run tracking
AGENT_RUNS_MAX_HISTORY: Final[int] = 100
AGENT_RUNS_CLEANUP_THRESHOLD: Final[int] = 150

# Default model for agent tasks (cost-effective for routine work)
AGENT_DEFAULT_TASK_MODEL: Final[str] = "claude-sonnet-4-6"

# Default tools allowed for agents
AGENT_DEFAULT_ALLOWED_TOOLS: Final[tuple[str, ...]] = (
    "Read",
    "Write",
    "Edit",
    "Glob",
    "Grep",
)

# Tools that are never allowed for agents (security)
AGENT_FORBIDDEN_TOOLS: Final[tuple[str, ...]] = (
    "Bash",  # Shell commands - too dangerous
    "Task",  # Sub-agents - avoid recursion
)

# Default paths that agents cannot access (security)
AGENT_DEFAULT_DISALLOWED_PATHS: Final[tuple[str, ...]] = (
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.crt",
    "**/credentials*",
    "**/secrets*",
)

# Engineering Agent
AGENT_ENGINEERING_NAME: Final[str] = "engineering"
AGENT_ENGINEERING_MAX_TURNS: Final[int] = 200
AGENT_ENGINEERING_TIMEOUT_SECONDS: Final[int] = 1800

# Agent insights output directory (git-tracked, team-shareable)
AGENT_INSIGHTS_DIR: Final[str] = "oak/insights"

# Agent-generated documentation directory (git-tracked, team-shareable)
AGENT_DOCS_DIR: Final[str] = "oak/docs"

# Project-level agent configuration
# Config files are stored in oak/agents/{agent_name}.yaml (git-tracked, project-specific)
AGENT_PROJECT_CONFIG_DIR: Final[str] = "oak/agents"
AGENT_PROJECT_CONFIG_EXTENSION: Final[str] = ".yaml"

# =============================================================================
# Agent Task Constants
# =============================================================================

# Task schema version (for future migrations)
AGENT_TASK_SCHEMA_VERSION: Final[int] = 1

# Task name validation
AGENT_TASK_NAME_MIN_LENGTH: Final[int] = 1
AGENT_TASK_NAME_MAX_LENGTH: Final[int] = 50
AGENT_TASK_NAME_PATTERN: Final[str] = r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$"

# CI query confidence levels for task config
CI_QUERY_CONFIDENCE_HIGH: Final[str] = "high"
CI_QUERY_CONFIDENCE_MEDIUM: Final[str] = "medium"
CI_QUERY_CONFIDENCE_LOW: Final[str] = "low"
CI_QUERY_CONFIDENCE_ALL: Final[str] = "all"
VALID_CI_QUERY_CONFIDENCE_LEVELS: Final[tuple[str, ...]] = (
    CI_QUERY_CONFIDENCE_HIGH,
    CI_QUERY_CONFIDENCE_MEDIUM,
    CI_QUERY_CONFIDENCE_LOW,
    CI_QUERY_CONFIDENCE_ALL,
)

# CI tools available for instance queries
CI_QUERY_TOOL_SEARCH: Final[str] = "ci_search"
CI_QUERY_TOOL_MEMORIES: Final[str] = "ci_memories"
CI_QUERY_TOOL_SESSIONS: Final[str] = "ci_sessions"
CI_QUERY_TOOL_PROJECT_STATS: Final[str] = "ci_project_stats"
VALID_CI_QUERY_TOOLS: Final[tuple[str, ...]] = (
    CI_QUERY_TOOL_SEARCH,
    CI_QUERY_TOOL_MEMORIES,
    CI_QUERY_TOOL_SESSIONS,
    CI_QUERY_TOOL_PROJECT_STATS,
)

# Default CI query limits
DEFAULT_CI_QUERY_LIMIT: Final[int] = 10
MAX_CI_QUERY_LIMIT: Final[int] = 100

# =============================================================================
# Schedule Trigger Types
# =============================================================================
# Trigger types define when an agent schedule runs.
# - cron: Time-based scheduling via cron expression
# - manual: Run only when manually triggered by user

SCHEDULE_TRIGGER_CRON: Final[str] = "cron"
SCHEDULE_TRIGGER_MANUAL: Final[str] = "manual"
VALID_SCHEDULE_TRIGGER_TYPES: Final[tuple[str, ...]] = (
    SCHEDULE_TRIGGER_CRON,
    SCHEDULE_TRIGGER_MANUAL,
)
