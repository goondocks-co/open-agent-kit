"""Pydantic models for the CI Agent subsystem.

This module defines the data structures for agent definitions, runs,
and execution tracking.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


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
    """Agent summary for list endpoints."""

    name: str
    display_name: str
    description: str
    max_turns: int
    timeout_seconds: int


class AgentListResponse(BaseModel):
    """Response for listing available agents."""

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
