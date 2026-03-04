"""Agent Runtime constants.

These constants are owned by the agent_runtime feature and used across
its modules (executor, registry, scheduler, tools, interactive, models).

Other features (team, swarm) may re-export these for backward compatibility
but the canonical definitions live here.
"""

from typing import Final

# =============================================================================
# Agent Definition Filesystem Layout
# =============================================================================

AGENTS_DEFINITIONS_DIR: Final[str] = "definitions"
AGENTS_TASKS_SUBDIR: Final[str] = "tasks"
AGENT_DEFINITION_FILENAME: Final[str] = "agent.yaml"
AGENT_PROMPTS_DIR: Final[str] = "prompts"
AGENT_SYSTEM_PROMPT_FILENAME: Final[str] = "system.md"
AGENT_TASK_TEMPLATE_FILENAME: Final[str] = "task.yaml"

# =============================================================================
# Agent Execution Limits
# =============================================================================

MAX_AGENT_MAX_TURNS: Final[int] = 500
MAX_AGENT_TIMEOUT_SECONDS: Final[int] = 3600
MIN_AGENT_TIMEOUT_SECONDS: Final[int] = 60

# =============================================================================
# Agent Execution Timing
# =============================================================================

SCHEDULER_STOP_TIMEOUT_SECONDS: Final[float] = 5.0
AGENT_INTERRUPT_GRACE_SECONDS: Final[float] = 2.0
AGENT_RETRY_MAX_ATTEMPTS: Final[int] = 3
AGENT_RETRY_BASE_DELAY: Final[float] = 1.0

# =============================================================================
# Agent Tool Restrictions
# =============================================================================

AGENT_FORBIDDEN_TOOLS: Final[tuple[str, ...]] = (
    "Bash",
    "Task",
)

TOOL_NAME_BASH: Final[str] = "Bash"
TOOL_NAME_EDIT: Final[str] = "Edit"
TOOL_NAME_WRITE: Final[str] = "Write"

# =============================================================================
# Agent Task Configuration
# =============================================================================

AGENT_PROJECT_CONFIG_DIR: Final[str] = "oak/agents"
AGENT_PROJECT_CONFIG_EXTENSION: Final[str] = ".yaml"
AGENT_TASK_SCHEMA_VERSION: Final[int] = 1
AGENT_TASK_NAME_PATTERN: Final[str] = r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$"

# =============================================================================
# OAK MCP Server (tools exposed to agents)
# =============================================================================

OAK_MCP_SERVER_NAME: Final[str] = "oak"
OAK_MCP_SERVER_VERSION: Final[str] = "1.0.0"

OAK_TOOL_SEARCH: Final[str] = "oak_search"
OAK_TOOL_MEMORIES: Final[str] = "oak_memories"
OAK_TOOL_SESSIONS: Final[str] = "oak_sessions"
OAK_TOOL_PROJECT_STATS: Final[str] = "oak_project_stats"
OAK_TOOL_QUERY: Final[str] = "oak_query"
OAK_TOOL_REMEMBER: Final[str] = "oak_remember"
OAK_TOOL_RESOLVE: Final[str] = "oak_resolve"
OAK_TOOL_ARCHIVE: Final[str] = "oak_archive"

# =============================================================================
# Schedule Trigger Types
# =============================================================================

SCHEDULE_TRIGGER_CRON: Final[str] = "cron"

# =============================================================================
# Provider Defaults
# =============================================================================

DEFAULT_BASE_URL: Final[str] = "http://localhost:11434"

# =============================================================================
# Interactive Session Constants
# =============================================================================

PROMPT_SOURCE_PLAN: Final[str] = "plan"

# =============================================================================
# Backward Compatibility Aliases (deprecated — use OAK_* names)
# =============================================================================

CI_MCP_SERVER_NAME = OAK_MCP_SERVER_NAME
CI_MCP_SERVER_VERSION = OAK_MCP_SERVER_VERSION
CI_TOOL_SEARCH = OAK_TOOL_SEARCH
CI_TOOL_MEMORIES = OAK_TOOL_MEMORIES
CI_TOOL_SESSIONS = OAK_TOOL_SESSIONS
CI_TOOL_PROJECT_STATS = OAK_TOOL_PROJECT_STATS
CI_TOOL_QUERY = OAK_TOOL_QUERY
CI_TOOL_REMEMBER = OAK_TOOL_REMEMBER
CI_TOOL_RESOLVE = OAK_TOOL_RESOLVE
CI_TOOL_ARCHIVE = OAK_TOOL_ARCHIVE
