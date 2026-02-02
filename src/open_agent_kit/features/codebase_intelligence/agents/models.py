"""Pydantic models for the CI Agent subsystem.

This module defines the data structures for agent definitions, runs,
execution tracking, and agent instances.

Agent Instances are user-configured specializations of agent templates.
Templates define capabilities (tools, permissions, system prompt).
Instances define tasks (default_task, maintained_files, ci_queries).
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# =============================================================================
# Schedule Configuration Models
# =============================================================================


class ScheduleDefinition(BaseModel):
    """Cron schedule definition for agent instances.

    Enables periodic execution of agent tasks. The schedule is defined
    in the instance YAML and runtime state is tracked in the database.
    """

    cron: str = Field(..., description="Cron expression (e.g., '0 0 * * MON' for weekly Monday)")
    description: str = Field(default="", description="Human-readable schedule description")


# =============================================================================
# Instance Configuration Models
# =============================================================================


class MaintainedFile(BaseModel):
    """A file or pattern that an agent instance maintains.

    Used by instances to declare which files they're responsible for,
    enabling focused documentation, code generation, or maintenance tasks.
    """

    path: str = Field(..., description="File path or glob pattern (e.g., 'docs/api/*.md')")
    purpose: str = Field(default="", description="Why this file is maintained")
    naming: str | None = Field(default=None, description="Naming convention for new files")
    auto_create: bool = Field(default=False, description="Create file if it doesn't exist")


class CIQueryTemplate(BaseModel):
    """A CI query template for agent instances.

    Defines queries that instances run against CI tools (search, memories, etc.)
    to gather context before executing their task.
    """

    tool: str = Field(
        ..., description="CI tool: ci_search, ci_memories, ci_sessions, ci_project_stats"
    )
    query_template: str = Field(default="", description="Query template with {placeholders}")
    search_type: str | None = Field(
        default=None, description="Search type: all, code, memory, plans"
    )
    min_confidence: str = Field(
        default="medium", description="Minimum confidence: high, medium, low, all"
    )
    filter: str | None = Field(default=None, description="Optional filter expression")
    limit: int = Field(default=10, ge=1, le=100, description="Maximum results")
    purpose: str = Field(default="", description="Why this query is needed")
    required: bool = Field(default=False, description="Fail if query returns no results")


class AgentInstance(BaseModel):
    """User-configured agent instance.

    Instances are stored in the project's agent config directory and define:
    - Which template to use (agent_type)
    - What task to perform (default_task - REQUIRED)
    - What files to maintain
    - What CI queries to run
    - Optional schedule for periodic execution

    Templates cannot be run directly - only instances can be executed.
    """

    # Identity
    name: str = Field(..., min_length=1, max_length=50, description="Unique ID (filename)")
    display_name: str = Field(..., min_length=1, max_length=100, description="Human-readable name")
    agent_type: str = Field(..., description="Template reference (e.g., 'documentation')")
    description: str = Field(default="", description="What this instance does")

    # Task (REQUIRED - no ad-hoc prompts)
    default_task: str = Field(..., min_length=1, description="Task to execute when run")

    # Execution limits (optional - overrides template defaults)
    execution: "AgentExecution | None" = Field(
        default=None,
        description="Execution config override (timeout_seconds, max_turns, permission_mode)",
    )

    # Schedule (optional - for periodic execution)
    schedule: ScheduleDefinition | None = Field(
        default=None, description="Cron schedule for periodic execution"
    )

    # Configuration
    maintained_files: list[MaintainedFile] = Field(
        default_factory=list, description="Files this agent maintains"
    )
    ci_queries: dict[str, list[CIQueryTemplate]] = Field(
        default_factory=dict, description="CI queries by phase (discovery, validation, etc.)"
    )
    output_requirements: dict[str, Any] = Field(
        default_factory=dict, description="Required sections, format, etc."
    )
    style: dict[str, Any] = Field(
        default_factory=dict, description="Style preferences (tone, examples, etc.)"
    )
    extra: dict[str, Any] = Field(
        default_factory=dict, description="Additional instance-specific config"
    )

    # Metadata
    instance_path: str | None = Field(
        default=None, description="Path to instance YAML (set by registry)"
    )
    is_builtin: bool = Field(
        default=False, description="True if this is a built-in task shipped with OAK"
    )
    schema_version: int = Field(default=1, ge=1, description="Instance schema version")


# =============================================================================
# Run Status and Execution Models
# =============================================================================


class AgentRunStatus(str, Enum):
    """Status of an agent run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class AgentPermissionMode(str, Enum):
    """Permission modes for agent file operations.

    Maps to claude-code-sdk permission_mode options.
    """

    # Require approval for all edits
    DEFAULT = "default"
    # Auto-accept file edits
    ACCEPT_EDITS = "acceptEdits"
    # Bypass all permission checks (dangerous)
    BYPASS_PERMISSIONS = "bypassPermissions"


class AgentCIAccess(BaseModel):
    """Configuration for agent access to CI data.

    Controls what CI data the agent can access via MCP tools.
    """

    code_search: bool = Field(default=True, description="Allow searching code chunks")
    memory_search: bool = Field(default=True, description="Allow searching memories")
    session_history: bool = Field(default=True, description="Allow accessing session history")
    project_stats: bool = Field(default=True, description="Allow accessing project stats")


class AgentExecution(BaseModel):
    """Execution configuration for an agent."""

    max_turns: int = Field(default=50, ge=1, le=500, description="Maximum agentic turns")
    timeout_seconds: int = Field(default=600, ge=60, le=3600, description="Execution timeout")
    permission_mode: AgentPermissionMode = Field(
        default=AgentPermissionMode.ACCEPT_EDITS,
        description="How to handle file permission prompts",
    )


class AgentDefinition(BaseModel):
    """Definition of an agent loaded from YAML.

    Agents are defined in agents/definitions/{name}/agent.yaml
    with optional prompts in agents/definitions/{name}/prompts/
    """

    # Identity
    name: str = Field(..., min_length=1, max_length=50, description="Unique agent identifier")
    display_name: str = Field(..., min_length=1, max_length=100, description="Human-readable name")
    description: str = Field(..., min_length=1, description="What this agent does")

    # Execution settings
    execution: AgentExecution = Field(default_factory=AgentExecution)

    # Tool permissions
    allowed_tools: list[str] = Field(
        default_factory=lambda: ["Read", "Write", "Edit", "Glob", "Grep"],
        description="Tools the agent can use",
    )
    disallowed_tools: list[str] = Field(
        default_factory=list,
        description="Tools explicitly denied (overrides allowed_tools)",
    )

    # File path restrictions
    allowed_paths: list[str] = Field(
        default_factory=list,
        description="Glob patterns for allowed file paths (empty = all allowed)",
    )
    disallowed_paths: list[str] = Field(
        default_factory=lambda: [".env", ".env.*", "*.pem", "*.key"],
        description="Glob patterns for denied file paths",
    )

    # CI data access
    ci_access: AgentCIAccess = Field(default_factory=AgentCIAccess)

    # System prompt (loaded from file or inline)
    system_prompt: str | None = Field(default=None, description="System prompt for the agent")

    # Source path (set by registry)
    definition_path: str | None = Field(
        default=None, description="Path to agent.yaml (set by registry)"
    )

    # Project-specific configuration (loaded from agent config directory)
    project_config: dict[str, Any] | None = Field(
        default=None,
        description="Project-specific config from agent config directory",
    )

    def get_effective_tools(self) -> list[str]:
        """Get the effective list of allowed tools after applying disallowed list."""
        return [t for t in self.allowed_tools if t not in self.disallowed_tools]


class AgentRun(BaseModel):
    """Record of an agent execution run."""

    # Identity
    id: str = Field(..., description="Unique run identifier")
    agent_name: str = Field(..., description="Name of the agent that ran")

    # Execution
    task: str = Field(..., description="Task description provided by user")
    status: AgentRunStatus = Field(default=AgentRunStatus.PENDING)

    # Timing
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: datetime | None = Field(default=None)
    completed_at: datetime | None = Field(default=None)

    # Results
    result: str | None = Field(default=None, description="Final result/summary from agent")
    error: str | None = Field(default=None, description="Error message if failed")
    turns_used: int = Field(default=0, description="Number of agentic turns used")
    cost_usd: float | None = Field(default=None, description="Total cost in USD")

    # Files modified
    files_created: list[str] = Field(default_factory=list)
    files_modified: list[str] = Field(default_factory=list)
    files_deleted: list[str] = Field(default_factory=list)

    @property
    def duration_seconds(self) -> float | None:
        """Calculate run duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def is_terminal(self) -> bool:
        """Check if run is in a terminal state."""
        return self.status in (
            AgentRunStatus.COMPLETED,
            AgentRunStatus.FAILED,
            AgentRunStatus.CANCELLED,
            AgentRunStatus.TIMEOUT,
        )


class AgentRunRequest(BaseModel):
    """Request to trigger an agent run."""

    task: str = Field(..., min_length=1, max_length=10000, description="Task for the agent")
    context: dict[str, Any] | None = Field(
        default=None, description="Additional context to provide"
    )


class AgentRunResponse(BaseModel):
    """Response after triggering an agent run."""

    run_id: str
    status: AgentRunStatus
    message: str = ""


class AgentListItem(BaseModel):
    """Agent summary for list endpoints (legacy - use TemplateListItem/InstanceListItem)."""

    name: str
    display_name: str
    description: str
    max_turns: int
    timeout_seconds: int
    project_config: dict[str, Any] | None = Field(
        default=None,
        description="Project-specific config from agent config directory",
    )


class AgentTemplateListItem(BaseModel):
    """Template summary for list endpoints.

    Templates define agent capabilities but cannot be run directly.
    Users create instances from templates.
    """

    name: str = Field(..., description="Template identifier")
    display_name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="What this template does")
    max_turns: int = Field(..., description="Default max turns for instances")
    timeout_seconds: int = Field(..., description="Default timeout for instances")


class AgentInstanceListItem(BaseModel):
    """Instance summary for list endpoints.

    Instances are runnable - they have a configured default_task.
    """

    name: str = Field(..., description="Instance identifier (filename without .yaml)")
    display_name: str = Field(..., description="Human-readable name")
    agent_type: str = Field(..., description="Template this instance uses")
    description: str = Field(default="", description="What this instance does")
    default_task: str = Field(..., description="Task executed when run")
    max_turns: int = Field(
        ..., description="Effective max turns (instance override or template default)"
    )
    timeout_seconds: int = Field(
        ..., description="Effective timeout (instance override or template default)"
    )
    has_execution_override: bool = Field(
        default=False, description="True if instance overrides template execution config"
    )
    is_builtin: bool = Field(
        default=False, description="True if this is a built-in task shipped with OAK"
    )
    schedule: ScheduleDefinition | None = Field(
        default=None, description="Cron schedule if configured"
    )


class AgentListResponse(BaseModel):
    """Response for listing available agents.

    Returns both templates (not directly runnable) and instances (runnable).
    """

    # New structured response
    templates: list[AgentTemplateListItem] = Field(default_factory=list)
    instances: list[AgentInstanceListItem] = Field(default_factory=list)

    # Path information for UI display
    instances_dir: str = Field(
        default="",
        description="Directory where instance YAML files are stored (e.g., 'oak/ci/agents')",
    )

    # Legacy fields for backwards compatibility
    agents: list[AgentListItem] = Field(default_factory=list)
    total: int = 0


class AgentDetailResponse(BaseModel):
    """Detailed agent information."""

    agent: AgentDefinition
    recent_runs: list[AgentRun] = Field(default_factory=list)


class AgentRunListResponse(BaseModel):
    """Response for listing agent runs."""

    runs: list[AgentRun] = Field(default_factory=list)
    total: int = 0
    limit: int = 20
    offset: int = 0


class AgentRunDetailResponse(BaseModel):
    """Detailed run information."""

    run: AgentRun


class CreateInstanceRequest(BaseModel):
    """Request to create a new agent instance from a template."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=50,
        pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$",
        description="Instance name (becomes filename, lowercase with hyphens)",
    )
    display_name: str = Field(..., min_length=1, max_length=100, description="Human-readable name")
    description: str = Field(default="", description="What this instance does")
    default_task: str = Field(..., min_length=1, description="Task to execute when run")
