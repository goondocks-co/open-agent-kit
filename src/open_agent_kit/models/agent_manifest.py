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
    """

    has_background_agents: bool = Field(
        default=False,
        description="Whether agent supports background/parallel agent execution",
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
            "has_native_web": self.capabilities.has_native_web,
            "has_mcp": self.capabilities.has_mcp,
            "research_strategy": self.capabilities.research_strategy,
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
        return yaml.dump(data, default_flow_style=False, sort_keys=False)
