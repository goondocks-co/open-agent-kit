"""Governance constants (actions, modes, tool categories)."""

from typing import Final

# =============================================================================
# Governance
# =============================================================================

# Governance actions
GOVERNANCE_ACTION_ALLOW: Final[str] = "allow"
GOVERNANCE_ACTION_DENY: Final[str] = "deny"
GOVERNANCE_ACTION_WARN: Final[str] = "warn"
GOVERNANCE_ACTION_OBSERVE: Final[str] = "observe"
GOVERNANCE_ACTIONS: Final[tuple[str, ...]] = (
    GOVERNANCE_ACTION_ALLOW,
    GOVERNANCE_ACTION_DENY,
    GOVERNANCE_ACTION_WARN,
    GOVERNANCE_ACTION_OBSERVE,
)

# Governance enforcement modes
GOVERNANCE_MODE_OBSERVE: Final[str] = "observe"
GOVERNANCE_MODE_ENFORCE: Final[str] = "enforce"
GOVERNANCE_MODES: Final[tuple[str, ...]] = (
    GOVERNANCE_MODE_OBSERVE,
    GOVERNANCE_MODE_ENFORCE,
)

# Governance tool categories
GOVERNANCE_TOOL_CATEGORY_FILESYSTEM: Final[str] = "filesystem"
GOVERNANCE_TOOL_CATEGORY_SHELL: Final[str] = "shell"
GOVERNANCE_TOOL_CATEGORY_NETWORK: Final[str] = "network"
GOVERNANCE_TOOL_CATEGORY_AGENT: Final[str] = "agent"
GOVERNANCE_TOOL_CATEGORY_OTHER: Final[str] = "other"
GOVERNANCE_TOOL_CATEGORIES: Final[tuple[str, ...]] = (
    GOVERNANCE_TOOL_CATEGORY_FILESYSTEM,
    GOVERNANCE_TOOL_CATEGORY_SHELL,
    GOVERNANCE_TOOL_CATEGORY_NETWORK,
    GOVERNANCE_TOOL_CATEGORY_AGENT,
    GOVERNANCE_TOOL_CATEGORY_OTHER,
)

# Tool name -> category mapping
GOVERNANCE_FILESYSTEM_TOOLS: Final[frozenset[str]] = frozenset(
    {
        "Read",
        "Write",
        "Edit",
        "MultiEdit",
        "Glob",
        "Grep",
        "NotebookEdit",
    }
)
GOVERNANCE_SHELL_TOOLS: Final[frozenset[str]] = frozenset({"Bash"})
GOVERNANCE_NETWORK_TOOLS: Final[frozenset[str]] = frozenset({"WebFetch", "WebSearch"})
GOVERNANCE_AGENT_TOOLS: Final[frozenset[str]] = frozenset({"Task", "SendMessage"})

# Governance audit retention
GOVERNANCE_RETENTION_DAYS_DEFAULT: Final[int] = 30
GOVERNANCE_RETENTION_DAYS_MIN: Final[int] = 1
GOVERNANCE_RETENTION_DAYS_MAX: Final[int] = 365

# =============================================================================
# Data Collection Policy Defaults
# =============================================================================

DATA_COLLECTION_SYNC_OBSERVATIONS_DEFAULT: Final[bool] = True
DATA_COLLECTION_FEDERATED_TOOLS_DEFAULT: Final[bool] = True
