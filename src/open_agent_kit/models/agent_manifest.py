"""Agent manifest models for open-agent-kit.

This module defines the AgentManifest model which represents an AI coding agent's
configuration, capabilities, and installation requirements. Agent manifests are
stored in agents/{agent-name}/manifest.yaml and are loaded during oak init/upgrade.

Unlike the previous AgentConfig model (which was designed for LLM API configuration),
AgentManifest focuses on:
- Installation targets (where to install commands)
- Agent capabilities (for conditional prompt rendering)
- Lifecycle management (install, upgrade, customize)
"""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class AgentCapabilities(BaseModel):
    """Agent capabilities for conditional command rendering.

    These flags are used by the FeatureService to conditionally render
    command templates based on what each agent can do. For example,
    Claude Code can use background agents for parallel research, while
    Codex CLI cannot.

    Capability tiers enable adaptive prompt complexity:
    - reasoning_tier: Determines how much autonomous decision-making to allow
    - context_handling: Affects prompt length and detail level
    - model_consistency: Influences reliance on structured vs flexible prompts
    """

    has_background_agents: bool = Field(
        default=False,
        description="Whether agent supports background/parallel agent execution",
    )
    background_agent_instructions: str = Field(
        default="Use your agent's parallel execution capability.",
        description="Agent-specific instructions for launching background agents",
    )
    has_native_web: bool = Field(
        default=False,
        description="Whether agent has built-in web search capabilities",
    )
    has_mcp: bool = Field(
        default=False,
        description="Whether agent supports MCP (Model Context Protocol) servers",
    )
    research_strategy: str = Field(
        default="Use general knowledge and codebase exploration.",
        description="Agent-specific guidance for research tasks",
    )

    # Capability tiers for adaptive prompt complexity
    reasoning_tier: str = Field(
        default="medium",
        description="Reasoning capability: 'high' (autonomous), 'medium' (guided), 'basic' (explicit), 'variable' (model-dependent)",
    )
    context_handling: str = Field(
        default="medium",
        description="Context window handling: 'large' (1M+), 'medium' (100K+), 'small' (<100K)",
    )
    model_consistency: str = Field(
        default="variable",
        description="Model consistency: 'high' (first-party), 'medium' (curated), 'variable' (user choice)",
    )

    # Skills support
    has_skills: bool = Field(
        default=False,
        description="Whether agent supports SKILL.md files for domain expertise",
    )
    skills_folder: str | None = Field(
        default=None,
        description="Override base folder for skills (e.g., '.agent' for Gemini). If None, uses installation.folder",
    )
    skills_directory: str = Field(
        default="skills",
        description="Subdirectory within skills folder for skills (e.g., 'skills' -> .claude/skills/)",
    )


class AgentTranscriptConfig(BaseModel):
    """Transcript file configuration for agents that store conversation history.

    Defines how to locate and parse transcript files for response summary extraction.
    Used when the Stop hook doesn't fire (e.g., user queues messages during agent response).
    """

    # Transcript location
    base_dir: str | None = Field(
        default=None,
        description="Base directory for transcripts relative to home (e.g., '.claude/projects'). Set to null if agent doesn't use file-based transcripts.",
    )

    # Path pattern with placeholders: {session_id}, {encoded_project}
    path_pattern: str = Field(
        default="{encoded_project}/{session_id}.jsonl",
        description="Path pattern within base_dir. Placeholders: {session_id}, {encoded_project}",
    )

    # How project paths are encoded in the transcript directory name
    project_encoding: str = Field(
        default="slash-to-dash",
        description="How project paths are encoded: 'slash-to-dash' (/foo/bar -> -foo-bar), 'url-encode', 'none'",
    )


class AgentSessionContinuationConfig(BaseModel):
    """Configuration for session continuation triggers.

    Defines which SessionStart sources this agent uses for continuation events.
    The actual behavior (creating batches, reactivating, etc.) is universal
    across all agents - only the triggers vary.

    Example: Claude fires SessionStart with source="clear" when user clears context,
    and source="compact" for auto-compaction. Cursor might use different sources.
    """

    # SessionStart sources that indicate continuation (not a fresh session)
    # When SessionStart fires with one of these sources, we know:
    # 1. This is a continuation, not a brand new session
    # 2. The agent may start executing tools before UserPromptSubmit fires
    # 3. We should create a system batch to capture the activity
    continuation_sources: list[str] = Field(
        default_factory=list,
        description="SessionStart source values that indicate session continuation (e.g., ['clear', 'compact'] for Claude). When detected, a system batch is created immediately.",
    )


class AgentCIConfig(BaseModel):
    """Codebase Intelligence configuration for an agent.

    These settings control how CI detects and processes agent-specific
    events like plan mode execution and exit. All plan-related settings
    are centralized here for declarative configuration.
    """

    # Resume command template for session continuation
    resume_command: str | None = Field(
        default=None,
        description="Template for resuming a session. Use {session_id} placeholder. (e.g., 'claude --resume {session_id}')",
    )

    # Plan storage configuration
    plans_subfolder: str | None = Field(
        default="plans",
        description="Subfolder for plan files within agent folder (e.g., 'plans' -> .claude/plans/). Set to null if agent doesn't support disk-based plans.",
    )

    # Plan detection configuration
    plan_execution_prefix: str | None = Field(
        default=None,
        description="Prefix that identifies auto-injected plan execution prompts (e.g., 'Implement the following plan:')",
    )
    exit_plan_tool: str | None = Field(
        default=None,
        description="Tool name that signals plan mode exit (e.g., 'ExitPlanMode'). When detected, re-reads plan file to capture final content.",
    )

    # Transcript configuration for response summary extraction
    transcript: AgentTranscriptConfig | None = Field(
        default=None,
        description="Transcript file configuration for response summary extraction. Set to null if agent uses notify handlers instead.",
    )

    # Session continuation configuration
    continuation: AgentSessionContinuationConfig = Field(
        default_factory=AgentSessionContinuationConfig,
        description="Configuration for session continuation batch creation (context compaction, cleared context, etc.)",
    )


class AgentInstallation(BaseModel):
    """Agent installation configuration.

    Defines where and how to install oak commands for this agent.
    """

    folder: str = Field(
        ...,
        description="Agent's root folder (e.g., '.claude/', '.cursor/')",
    )
    commands_subfolder: str = Field(
        default="commands",
        description="Subfolder for commands within agent folder",
    )
    file_extension: str = Field(
        default=".md",
        description="File extension for command files (e.g., '.md', '.agent.md')",
    )
    instruction_file: str | None = Field(
        default=None,
        description="Agent's instruction file path pattern (e.g., 'CLAUDE.md')",
    )


class AgentRequirements(BaseModel):
    """Agent CLI/tool requirements."""

    requires_cli: bool = Field(
        default=False,
        description="Whether agent requires a CLI tool to be installed",
    )
    install_url: str | None = Field(
        default=None,
        description="URL with installation instructions for the CLI",
    )
    min_version: str | None = Field(
        default=None,
        description="Minimum required CLI version (if applicable)",
    )


class AgentMcpCliConfig(BaseModel):
    """CLI commands for MCP server management.

    Optional CLI commands that can be used instead of direct JSON manipulation.
    Placeholders: {name} = server name, {command} = full command string
    """

    install: str | None = Field(
        default=None,
        description="CLI command to install MCP server (e.g., 'claude mcp add {name} --scope project -- {command}')",
    )
    remove: str | None = Field(
        default=None,
        description="CLI command to remove MCP server (e.g., 'claude mcp remove {name} --scope project')",
    )


class AgentMcpConfig(BaseModel):
    """MCP (Model Context Protocol) server configuration for the agent.

    Defines where and how MCP servers are registered for this agent.
    Each agent may store MCP server configs in different locations with
    different key names (e.g., "mcpServers" vs "servers").
    """

    config_file: str = Field(
        ...,
        description="Path to the MCP config file relative to project root (e.g., '.mcp.json')",
    )
    format: str = Field(
        default="json",
        description="Config file format (currently only 'json' is supported)",
    )
    servers_key: str = Field(
        default="mcpServers",
        description="Key name in the config file where servers are registered (e.g., 'mcpServers' or 'servers')",
    )
    cli: AgentMcpCliConfig | None = Field(
        default=None,
        description="Optional CLI commands for install/remove (if agent has CLI support)",
    )
    entry_format: dict[str, Any] | None = Field(
        default=None,
        description="Template for the server entry JSON structure. Placeholders: {cmd}, {args}",
    )


class AgentOtelConfig(BaseModel):
    """OpenTelemetry configuration for agents that emit OTLP telemetry.

    Used for agents like Codex that don't support traditional hooks but
    emit OpenTelemetry events that can be translated to OAK CI activities.
    """

    enabled: bool = Field(
        default=False,
        description="Whether to configure OTLP receiver for this agent",
    )
    event_mapping: dict[str, str] = Field(
        default_factory=dict,
        description="Map OTel event names to OAK hook actions",
    )
    session_id_attribute: str = Field(
        default="conversation.id",
        description="OTel attribute containing session identifier",
    )
    agent_attribute: str = Field(
        default="slug",
        description="OTel attribute containing agent/service name for auto-detection",
    )
    config_template: str | None = Field(
        default=None,
        description="Jinja2 template for generating agent's OTel config",
    )
    config_section: str | None = Field(
        default=None,
        description="Section name in config file (e.g., 'otel' for [otel] in TOML)",
    )


class AgentNotifyConfig(BaseModel):
    """Agent notification configuration for notify-based event handlers.

    Used for agents like Codex that can emit structured notification events
    (e.g., agent-turn-complete) via a notify handler.
    """

    enabled: bool = Field(
        default=False,
        description="Whether notify handlers are enabled for this agent",
    )
    event_mapping: dict[str, str] = Field(
        default_factory=dict,
        description="Map agent notification event types to OAK actions",
    )
    session_id_field: str | None = Field(
        default=None,
        description="Notification field containing session identifier",
    )
    response_field: str | None = Field(
        default=None,
        description="Notification field containing agent response summary",
    )
    input_messages_field: str | None = Field(
        default=None,
        description="Notification field containing input messages list",
    )
    config_key: str | None = Field(
        default=None,
        description="Config key name for notify handler registration (e.g., 'notify')",
    )
    script_template: str | None = Field(
        default=None,
        description="Template filename for notify handler script",
    )
    script_path: str | None = Field(
        default=None,
        description="Path to install notify handler script relative to agent folder",
    )
    command: str | None = Field(
        default=None,
        description="Command to invoke notify handler (e.g., 'python3')",
    )
    args: list[str] | None = Field(
        default=None,
        description="Arguments to pass to notify command (e.g., ['ci', 'notify', '--agent', 'codex'])",
    )


class AgentNotificationsConfig(BaseModel):
    """Notifications configuration for Codebase Intelligence integration.

    Defines how agent notification handlers are installed for this agent.
    """

    type: str = Field(
        default="notify",
        description="Notification type: 'notify' for command-based handlers",
    )
    config_file: str | None = Field(
        default=None,
        description="Config file path relative to agent folder (e.g., 'config.toml')",
    )
    config_template: str | None = Field(
        default=None,
        description="Template filename for generating notify config entries",
    )
    notify: AgentNotifyConfig | None = Field(
        default=None,
        description="Notify handler configuration",
    )


class AgentHooksConfig(BaseModel):
    """Hooks configuration for Codebase Intelligence integration.

    Defines how CI hooks are installed for this agent. Hooks enable
    session tracking, activity capture, and context injection.

    Three types are supported:
    - "json": Hooks are added to a JSON config file (Claude, Cursor, Gemini, Copilot)
    - "plugin": Hooks are installed as a plugin file (OpenCode)
    - "otel": Hooks use OpenTelemetry events translated via OTLP receiver (Codex)
    """

    type: str = Field(
        default="json",
        description="Hook type: 'json' for JSON config, 'plugin' for file copy, 'otel' for OTLP",
    )
    config_file: str | None = Field(
        default=None,
        description="Config file path relative to agent folder (e.g., 'settings.json', 'hooks.json')",
    )
    hooks_key: str = Field(
        default="hooks",
        description="Key name in config file where hooks are stored",
    )
    format: str = Field(
        default="nested",
        description="Hook structure format: 'nested' (Claude/Gemini), 'flat' (Cursor), 'copilot' (bash/powershell)",
    )
    version_key: str | None = Field(
        default=None,
        description="Optional version field to add to config (e.g., 'version' -> {version: 1})",
    )
    template_file: str = Field(
        default="hooks.json",
        description="Template filename in hooks/{agent}/ directory",
    )
    # Plugin-specific fields (for type="plugin")
    plugin_dir: str | None = Field(
        default=None,
        description="Directory for plugins relative to agent folder (e.g., 'plugins')",
    )
    plugin_file: str | None = Field(
        default=None,
        description="Plugin filename to install (e.g., 'oak-ci.ts')",
    )
    # OTEL-specific fields (for type="otel")
    otel: AgentOtelConfig | None = Field(
        default=None,
        description="OpenTelemetry receiver configuration for OTLP-emitting agents",
    )


class AgentManifest(BaseModel):
    """Agent manifest model representing an AI coding agent's configuration.

    Agent manifests define how oak interacts with different AI coding assistants.
    They specify:
    - Where to install commands (.claude/commands/, .cursor/commands/, etc.)
    - What capabilities the agent has (for conditional prompt rendering)
    - CLI requirements and installation guidance
    - Custom agent-specific settings

    Example manifest (agents/claude/manifest.yaml):
        name: claude
        display_name: "Claude Code"
        version: "1.0.0"
        description: "Anthropic's Claude Code CLI agent"

        installation:
          folder: ".claude/"
          commands_subfolder: "commands"
          file_extension: ".md"
          instruction_file: "CLAUDE.md"

        requirements:
          requires_cli: true
          install_url: "https://docs.anthropic.com/en/docs/claude-code"

        capabilities:
          has_background_agents: true
          has_native_web: true
          has_mcp: true
          research_strategy: "Use Claude's web tools or MCP web-search"
    """

    # Identity
    name: str = Field(
        ...,
        description="Agent identifier (e.g., 'claude', 'cursor')",
    )
    display_name: str = Field(
        ...,
        description="Human-readable agent name",
    )
    version: str = Field(
        default="1.0.0",
        description="Manifest version for upgrade tracking",
    )
    description: str = Field(
        default="",
        description="Agent description",
    )

    # Installation configuration
    installation: AgentInstallation = Field(
        ...,
        description="Installation paths and file patterns",
    )

    # Requirements
    requirements: AgentRequirements = Field(
        default_factory=AgentRequirements,
        description="CLI and tool requirements",
    )

    # Capabilities for command rendering
    capabilities: AgentCapabilities = Field(
        default_factory=AgentCapabilities,
        description="Agent capabilities for conditional rendering",
    )

    # Custom settings (extensible)
    settings: dict[str, Any] = Field(
        default_factory=dict,
        description="Agent-specific custom settings",
    )

    # MCP server configuration
    mcp: AgentMcpConfig | None = Field(
        default=None,
        description="MCP server registration configuration",
    )

    # Hooks configuration for Codebase Intelligence
    hooks: AgentHooksConfig | None = Field(
        default=None,
        description="Hooks configuration for CI integration",
    )

    # Agent notifications configuration (notify handlers)
    notifications: AgentNotificationsConfig | None = Field(
        default=None,
        description="Agent notification configuration for CI integration",
    )

    # Codebase Intelligence configuration
    ci: AgentCIConfig = Field(
        default_factory=AgentCIConfig,
        description="Codebase Intelligence configuration for plan mode detection",
    )

    @classmethod
    def load(cls, manifest_path: Path) -> "AgentManifest":
        """Load agent manifest from YAML file.

        Args:
            manifest_path: Path to manifest.yaml file

        Returns:
            AgentManifest instance

        Raises:
            FileNotFoundError: If manifest file doesn't exist
            ValueError: If manifest is invalid
        """
        if not manifest_path.exists():
            raise FileNotFoundError(f"Agent manifest not found: {manifest_path}")

        with open(manifest_path) as f:
            data = yaml.safe_load(f)

        if not data:
            raise ValueError(f"Empty agent manifest: {manifest_path}")

        return cls(**data)

    def get_commands_dir(self) -> str:
        """Get the full commands directory path.

        Returns:
            Relative path to commands directory (e.g., '.claude/commands')
        """
        folder = self.installation.folder.rstrip("/")
        subfolder = self.installation.commands_subfolder
        return f"{folder}/{subfolder}"

    def get_plans_dir(self) -> str | None:
        """Get the full plans directory path.

        Plans are where agents store implementation plans during plan mode.
        This enables detection of plan-related activities for special handling
        (e.g., storing plans as decision memories rather than extracting arbitrary memories).

        Returns:
            Relative path to plans directory (e.g., '.claude/plans'), or None if
            agent doesn't support disk-based plans.
        """
        subfolder = self.ci.plans_subfolder
        if not subfolder:
            return None
        folder = self.installation.folder.rstrip("/")
        return f"{folder}/{subfolder}"

    def get_transcript_config(self) -> AgentTranscriptConfig | None:
        """Get transcript configuration for response summary extraction.

        Returns:
            AgentTranscriptConfig if agent uses file-based transcripts, None otherwise.
            Agents using notify handlers (like Codex) return None.
        """
        return self.ci.transcript

    def get_command_filename(self, command_name: str) -> str:
        """Get the full filename for a command.

        Args:
            command_name: Command name (e.g., 'rfc-create')

        Returns:
            Full filename with extension (e.g., 'oak.rfc-create.md')
        """
        extension = self.installation.file_extension
        return f"oak.{command_name}{extension}"

    def get_instruction_file_path(self) -> str | None:
        """Get the full path to the agent's instruction file.

        The instruction_file can be:
        - A filename relative to the agent folder (e.g., 'CLAUDE.md' -> '.claude/CLAUDE.md')
        - An absolute path from project root starting with '.' or '/' (used as-is)
        - A project-root filename (e.g., 'AGENTS.md' -> 'AGENTS.md')

        Returns:
            Relative path to instruction file from project root, or None if not defined
        """
        if not self.installation.instruction_file:
            return None

        instruction_file = self.installation.instruction_file

        # If the path starts with '.' (like '.windsurf/rules/rules.md' or './AGENTS.md')
        # or contains a slash (indicating a path), use it as-is
        if instruction_file.startswith(".") or "/" in instruction_file:
            # Remove leading './' if present
            if instruction_file.startswith("./"):
                instruction_file = instruction_file[2:]
            return instruction_file

        # Otherwise, it's relative to the folder
        folder = self.installation.folder.rstrip("/")
        return f"{folder}/{instruction_file}"

    def get_template_context(self) -> dict[str, Any]:
        """Get template context for Jinja2 rendering.

        This context is passed to command templates during feature installation
        to enable conditional rendering based on agent capabilities.

        Returns:
            Dictionary with agent context for template rendering
        """
        return {
            "agent_type": self.name,
            "agent_name": self.display_name,
            "agent_folder": self.installation.folder,
            "file_extension": self.installation.file_extension,
            # Capability flags for conditional rendering
            "has_background_agents": self.capabilities.has_background_agents,
            "background_agent_instructions": self.capabilities.background_agent_instructions,
            "has_native_web": self.capabilities.has_native_web,
            "has_mcp": self.capabilities.has_mcp,
            "research_strategy": self.capabilities.research_strategy,
            # Capability tiers for adaptive prompt complexity
            "reasoning_tier": self.capabilities.reasoning_tier,
            "context_handling": self.capabilities.context_handling,
            "model_consistency": self.capabilities.model_consistency,
            # Convenience booleans for common tier checks
            "is_high_reasoning": self.capabilities.reasoning_tier == "high",
            "is_basic_reasoning": self.capabilities.reasoning_tier == "basic",
            "is_variable_reasoning": self.capabilities.reasoning_tier == "variable",
        }

    def validate_installation(self, project_root: Path) -> tuple[bool, list[str]]:
        """Validate agent installation in a project.

        Args:
            project_root: Project root directory

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues: list[str] = []

        # Check if commands directory exists
        commands_dir = project_root / self.get_commands_dir()
        if not commands_dir.exists():
            issues.append(
                f"Commands directory not found: {commands_dir}. "
                f"Run 'oak init --agent {self.name}' to create it."
            )

        # Check for any oak commands
        if commands_dir.exists():
            pattern = f"oak.*{self.installation.file_extension}"
            commands = list(commands_dir.glob(pattern))
            if not commands:
                issues.append(
                    f"No oak commands found in {commands_dir}. "
                    "Run 'oak init' to install default commands."
                )

        return (len(issues) == 0, issues)

    def to_yaml(self) -> str:
        """Serialize manifest to YAML string.

        Returns:
            YAML representation of the manifest
        """
        data = self.model_dump(exclude_none=True, exclude_defaults=False)
        result: str = yaml.dump(data, default_flow_style=False, sort_keys=False)
        return result

    def get_oak_managed_paths(self) -> list[str]:
        """Get paths managed by OAK that should be excluded from code indexing.

        These are directories and files that OAK installs/manages (commands, skills,
        settings) - not user-generated content like AGENT.md or constitution files.

        Returns:
            List of relative paths that OAK manages for this agent.
            Only includes project-relative paths (excludes home directory paths like ~/.codex/).
        """
        paths: list[str] = []
        folder = self.installation.folder.rstrip("/")

        # Skip paths outside project root (e.g., ~/.codex/)
        if folder.startswith("~") or folder.startswith("/"):
            return paths

        # Commands directory (always managed by OAK)
        commands_dir = f"{folder}/{self.installation.commands_subfolder}"
        paths.append(commands_dir)

        # Skills directory (if agent supports skills)
        if self.capabilities.has_skills and self.capabilities.skills_directory:
            # Use skills_folder override if specified, otherwise use installation folder
            skills_base = self.capabilities.skills_folder or folder
            skills_base = skills_base.rstrip("/")
            # Skip paths outside project root
            if not skills_base.startswith("~") and not skills_base.startswith("/"):
                skills_dir = f"{skills_base}/{self.capabilities.skills_directory}"
                paths.append(skills_dir)

        # Settings file (if auto_approve is configured)
        if self.settings.get("auto_approve", {}).get("file"):
            settings_file = self.settings["auto_approve"]["file"]
            # Skip home directory paths
            if not settings_file.startswith("~") and not settings_file.startswith("/"):
                paths.append(settings_file)

        # MCP config file (if configured)
        if self.mcp and self.mcp.config_file:
            mcp_file = self.mcp.config_file
            # Skip home directory paths
            if not mcp_file.startswith("~") and not mcp_file.startswith("/"):
                paths.append(mcp_file)

        return paths
