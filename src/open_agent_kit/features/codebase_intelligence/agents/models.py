"""Pydantic models for the CI Agent subsystem.

This module defines the data structures for agent definitions, runs,
execution tracking, and agent tasks.

Agent Tasks are user-configured specializations of agent templates.
Templates define capabilities (tools, permissions, system prompt).
Tasks define what to do (default_task, maintained_files, ci_queries).
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# =============================================================================
# Task Configuration Models
# =============================================================================


class MaintainedFile(BaseModel):
    """A file or pattern that an agent task maintains.

    Used by tasks to declare which files they're responsible for,
    enabling focused documentation, code generation, or maintenance tasks.
    """

    path: str = Field(..., description="File path or glob pattern (e.g., 'docs/api/*.md')")
    purpose: str = Field(default="", description="Why this file is maintained")
    naming: str | None = Field(default=None, description="Naming convention for new files")
    auto_create: bool = Field(default=False, description="Create file if it doesn't exist")


class CIQueryTemplate(BaseModel):
    """A CI query template for agent tasks.

    Defines queries that tasks run against CI tools (search, memories, etc.)
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


class AgentTask(BaseModel):
    """User-configured agent task.

    Tasks are stored in the project's agent config directory and define:
    - Which template to use (agent_type)
    - What task to perform (default_task - REQUIRED)
    - What files to maintain
    - What CI queries to run
    - Optional schedule for periodic execution

    Templates cannot be run directly - only tasks can be executed.
    """

    # Identity
    name: str = Field(..., min_length=1, max_length=50, description="Unique ID (filename)")
    display_name: str = Field(..., min_length=1, max_length=100, description="Human-readable name")
    agent_type: str = Field(..., description="Template reference (e.g., 'documentation')")
    description: str = Field(default="", description="What this task does")

    # Task (REQUIRED - no ad-hoc prompts)
    default_task: str = Field(..., min_length=1, description="Task to execute when run")

    # Execution limits (optional - overrides template defaults)
    execution: "AgentExecution | None" = Field(
        default=None,
        description="Execution config override (timeout_seconds, max_turns, permission_mode)",
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
        default_factory=dict, description="Additional task-specific config"
    )

    # Metadata
    task_path: str | None = Field(default=None, description="Path to task YAML (set by registry)")
    is_builtin: bool = Field(
        default=False, description="True if this is a built-in task shipped with OAK"
    )
    schema_version: int = Field(default=1, ge=1, description="Task schema version")


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


class AgentProvider(BaseModel):
    """API provider configuration for agent execution.

    Enables using different API backends for agent execution:
    - cloud: Default Anthropic cloud API (uses logged-in account or ANTHROPIC_API_KEY)
    - ollama: Local Ollama server (v0.14.0+ with Messages API compatibility)
    - lmstudio: Local LM Studio server (uses Anthropic-compatible API)
    - bedrock: AWS Bedrock
    - openrouter: OpenRouter proxy

    The provider config sets environment variables that the Claude SDK uses
    to connect to the appropriate backend.

    API Compatibility Note:
    - Claude Agent SDK requires Anthropic API format (/v1/messages)
    - Ollama v0.14.0+ and LM Studio support Anthropic-compatible endpoints
    - Future SDKs (e.g., OpenAI-based) will use OpenAI API format (/v1/chat/completions)
    - The `api_format` property indicates which format the provider uses

    Important Ollama Requirements (from official docs):
    - Requires 64k+ context window for Claude Code compatibility
    - Recommended models: qwen3-coder, glm-4.7, gpt-oss-20b/120b
    - Use `ollama launch claude` for automatic setup, or configure manually

    Important LM Studio Requirements (from official docs):
    - Uses /v1/messages endpoint with Anthropic-compatible API
    - Supports both x-api-key and Authorization: Bearer headers
    """

    type: str = Field(
        default="cloud",
        description="Provider type: cloud, ollama, lmstudio, bedrock, openrouter",
    )
    base_url: str | None = Field(
        default=None,
        description="Base URL for API endpoint (e.g., 'http://localhost:11434' for Ollama)",
    )
    api_key: str | None = Field(
        default=None,
        description="API key override (defaults to ANTHROPIC_API_KEY for cloud)",
    )
    model: str | None = Field(
        default=None,
        description="Model name override (e.g., 'qwen2.5-coder:32b' for Ollama)",
    )

    @property
    def api_format(self) -> str:
        """Get the API format this provider uses.

        Returns:
            'anthropic' for Anthropic Messages API (/v1/messages)
            'openai' for OpenAI Chat API (/v1/chat/completions)

        Note: Claude Agent SDK requires 'anthropic' format.
        Future SDKs may support 'openai' format.
        """
        # All current providers use Anthropic-compatible API for Claude Agent SDK
        # Ollama v0.14.0+ and LM Studio both support Anthropic format
        anthropic_providers = {"cloud", "ollama", "lmstudio", "bedrock", "openrouter"}
        if self.type in anthropic_providers:
            return "anthropic"
        return "openai"  # Default for future OpenAI-compatible providers

    @property
    def default_base_url(self) -> str:
        """Get the default base URL for this provider type."""
        defaults = {
            "cloud": "https://api.anthropic.com",
            "ollama": "http://localhost:11434",
            "lmstudio": "http://localhost:1234",
            "bedrock": "",
            "openrouter": "https://openrouter.ai/api/v1",
        }
        return defaults.get(self.type, "")

    @property
    def recommended_models(self) -> list[str]:
        """Get recommended models for this provider type.

        Based on official documentation and compatibility requirements.
        """
        recommendations = {
            "cloud": [
                "claude-sonnet-4-20250514",
                "claude-opus-4-5-20251101",
                "claude-3-5-haiku-20241022",
            ],
            "ollama": [
                # From official Ollama Claude Code docs - requires 64k+ context
                "qwen3-coder",
                "glm-4.7",
                "gpt-oss:20b",
                "gpt-oss:120b",
                "qwen2.5-coder:32b",
            ],
            "lmstudio": [
                # Common capable models for LM Studio
                "qwen2.5-coder-32b-instruct",
                "deepseek-coder-v2",
                "codellama-70b",
            ],
            "bedrock": [
                "anthropic.claude-sonnet-4-20250514-v1:0",
                "anthropic.claude-opus-4-20250514-v1:0",
            ],
            "openrouter": [
                "anthropic/claude-sonnet-4",
                "anthropic/claude-opus-4",
            ],
        }
        return recommendations.get(self.type, [])

    @property
    def env_vars(self) -> dict[str, str]:
        """Get environment variables for this provider.

        Based on official documentation:
        - Ollama: https://docs.ollama.com/integrations/claude-code
        - LM Studio: https://lmstudio.ai/docs/developer/anthropic-compat

        Returns:
            Dictionary of environment variable name -> value.
        """
        env: dict[str, str] = {}

        if self.type == "cloud":
            # Default Anthropic cloud - no overrides needed
            # Uses ANTHROPIC_API_KEY from environment or logged-in account
            pass
        elif self.type == "ollama":
            # From official Ollama docs:
            # ANTHROPIC_AUTH_TOKEN=ollama, ANTHROPIC_API_KEY="" (empty)
            env["ANTHROPIC_BASE_URL"] = self.base_url or "http://localhost:11434"
            env["ANTHROPIC_AUTH_TOKEN"] = "ollama"
            env["ANTHROPIC_API_KEY"] = ""  # Empty string per docs
        elif self.type == "lmstudio":
            # From official LM Studio docs:
            # https://lmstudio.ai/docs/integrations/claude-code
            # ANTHROPIC_AUTH_TOKEN=lmstudio, ANTHROPIC_API_KEY="" (empty to prevent cloud auth)
            env["ANTHROPIC_BASE_URL"] = self.base_url or "http://localhost:1234"
            env["ANTHROPIC_AUTH_TOKEN"] = self.api_key or "lmstudio"
            env["ANTHROPIC_API_KEY"] = ""  # Empty string prevents cloud auth attempts
        elif self.type == "bedrock":
            env["CLAUDE_CODE_USE_BEDROCK"] = "1"
        elif self.type == "openrouter":
            env["ANTHROPIC_BASE_URL"] = "https://openrouter.ai/api/v1"
            if self.api_key:
                env["ANTHROPIC_API_KEY"] = self.api_key

        return env


class AgentExecution(BaseModel):
    """Execution configuration for an agent."""

    max_turns: int = Field(default=50, ge=1, le=500, description="Maximum agentic turns")
    timeout_seconds: int = Field(default=600, ge=60, le=3600, description="Execution timeout")
    permission_mode: AgentPermissionMode = Field(
        default=AgentPermissionMode.ACCEPT_EDITS,
        description="How to handle file permission prompts",
    )
    model: str | None = Field(
        default=None,
        description="Claude model to use (e.g., 'claude-sonnet-4-20250514', 'claude-opus-4-5-20251101')",
    )
    provider: AgentProvider | None = Field(
        default=None,
        description="API provider configuration (cloud, ollama, lmstudio, bedrock, openrouter)",
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
    input_tokens: int | None = Field(default=None, description="Input tokens used")
    output_tokens: int | None = Field(default=None, description="Output tokens generated")

    # Files modified
    files_created: list[str] = Field(default_factory=list)
    files_modified: list[str] = Field(default_factory=list)
    files_deleted: list[str] = Field(default_factory=list)

    # Warnings (non-fatal issues during execution)
    warnings: list[str] = Field(default_factory=list)

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
    """Agent summary for list endpoints (legacy - use TemplateListItem/TaskListItem)."""

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
    Users create tasks from templates.
    """

    name: str = Field(..., description="Template identifier")
    display_name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="What this template does")
    max_turns: int = Field(..., description="Default max turns for tasks")
    timeout_seconds: int = Field(..., description="Default timeout for tasks")


class AgentTaskListItem(BaseModel):
    """Task summary for list endpoints.

    Tasks are runnable - they have a configured default_task.
    """

    name: str = Field(..., description="Task identifier (filename without .yaml)")
    display_name: str = Field(..., description="Human-readable name")
    agent_type: str = Field(..., description="Template this task uses")
    description: str = Field(default="", description="What this task does")
    default_task: str = Field(..., description="Task executed when run")
    max_turns: int = Field(
        ..., description="Effective max turns (task override or template default)"
    )
    timeout_seconds: int = Field(
        ..., description="Effective timeout (task override or template default)"
    )
    has_execution_override: bool = Field(
        default=False, description="True if task overrides template execution config"
    )
    is_builtin: bool = Field(
        default=False, description="True if this is a built-in task shipped with OAK"
    )


class AgentListResponse(BaseModel):
    """Response for listing available agents.

    Returns both templates (not directly runnable) and tasks (runnable).
    """

    # Structured response
    templates: list[AgentTemplateListItem] = Field(default_factory=list)
    tasks: list[AgentTaskListItem] = Field(default_factory=list)

    # Path information for UI display
    tasks_dir: str = Field(
        default="",
        description="Directory where task YAML files are stored (e.g., 'oak/ci/agents')",
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


class CreateTaskRequest(BaseModel):
    """Request to create a new agent task from a template."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=50,
        pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$",
        description="Task name (becomes filename, lowercase with hyphens)",
    )
    display_name: str = Field(..., min_length=1, max_length=100, description="Human-readable name")
    description: str = Field(default="", description="What this task does")
    default_task: str = Field(..., min_length=1, description="Task to execute when run")
