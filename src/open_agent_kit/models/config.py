"""Configuration models for open-agent-kit."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class AgentCapabilitiesConfig(BaseModel):
    """User-configurable agent capabilities.

    These override the defaults from the agent's manifest.yaml.
    Users can enable new capabilities or adjust existing ones.
    """

    has_background_agents: bool | None = Field(
        default=None,
        description="Whether agent supports background/parallel agent execution",
    )
    has_native_web: bool | None = Field(
        default=None,
        description="Whether agent has built-in web search capabilities",
    )
    has_mcp: bool | None = Field(
        default=None,
        description="Whether agent supports MCP (Model Context Protocol) servers",
    )
    research_strategy: str | None = Field(
        default=None,
        description="Agent-specific guidance for research tasks",
    )
    # Extensible: users can add custom capabilities
    custom: dict[str, Any] = Field(
        default_factory=dict,
        description="Custom capabilities for future features",
    )


class RFCConfig(BaseModel):
    """RFC-specific configuration."""

    directory: str = Field(default="oak/rfc", description="Directory for RFCs")
    template: str = Field(default="engineering", description="Default RFC template")
    auto_number: bool = Field(default=True, description="Automatically assign RFC numbers")
    number_format: str = Field(default="sequential", description="RFC number format")
    validate_on_create: bool = Field(default=True, description="Run validation after creating RFC")


class AzureDevOpsProviderConfig(BaseModel):
    """Azure DevOps issue provider configuration."""

    organization: str | None = Field(default=None, description="Azure DevOps organization name")
    project: str | None = Field(default=None, description="Azure DevOps project name")
    team: str | None = Field(default=None, description="Default team name")
    area_path: str | None = Field(default=None, description="Default area path")
    pat_env: str | None = Field(default=None, description="Environment variable containing PAT")
    default_branch: str = Field(
        default="main", description="Default branch to base new issue branches on"
    )


class GitHubIssuesProviderConfig(BaseModel):
    """GitHub Issues issue provider configuration."""

    owner: str | None = Field(default=None, description="Repository owner or organization")
    repo: str | None = Field(default=None, description="Repository name")
    token_env: str | None = Field(default=None, description="Environment variable containing token")
    default_branch: str = Field(
        default="main", description="Default branch to base new issue branches on"
    )


class IssueConfig(BaseModel):
    """Issue provider settings."""

    provider: str | None = Field(default=None, description="Active issue provider key")
    azure_devops: AzureDevOpsProviderConfig = Field(
        default_factory=AzureDevOpsProviderConfig,
        description="Azure DevOps provider settings",
    )
    github: GitHubIssuesProviderConfig = Field(
        default_factory=GitHubIssuesProviderConfig,
        description="GitHub Issues provider settings",
    )


class PlanConfig(BaseModel):
    """Plan feature configuration."""

    directory: str = Field(default="oak/plan", description="Directory for strategic plans")


class ConstitutionConfig(BaseModel):
    """Constitution feature configuration."""

    directory: str = Field(default="oak", description="Directory for constitution files")


class FeaturesConfig(BaseModel):
    """Features configuration tracking installed features and their settings."""

    enabled: list[str] = Field(
        default_factory=list,
        description="List of enabled feature names",
    )


class SkillsConfig(BaseModel):
    """Skills configuration tracking installed skills."""

    installed: list[str] = Field(
        default_factory=list,
        description="List of installed skill names",
    )
    auto_install: bool = Field(
        default=True,
        description="Auto-install skills when associated feature is enabled",
    )


class OakConfig(BaseModel):
    """Main open-agent-kit configuration."""

    version: str = Field(default="0.1.0", description="Config version")
    agents: list[str] = Field(
        default_factory=list,
        description="Configured AI agents (source of truth for installed agents)",
    )
    ides: list[str] = Field(
        default_factory=list,
        description="Configured IDEs (source of truth for installed IDE settings)",
    )
    agent_capabilities: dict[str, AgentCapabilitiesConfig] = Field(
        default_factory=dict,
        description="Per-agent capability overrides (merged with manifest defaults)",
    )
    rfc: RFCConfig = Field(default_factory=RFCConfig, description="RFC configuration")
    issue: IssueConfig = Field(default_factory=IssueConfig, description="Issue configuration")
    plan: PlanConfig = Field(default_factory=PlanConfig, description="Plan configuration")
    constitution: ConstitutionConfig = Field(
        default_factory=ConstitutionConfig, description="Constitution configuration"
    )
    features: FeaturesConfig = Field(
        default_factory=FeaturesConfig,
        description="Features configuration",
    )
    skills: SkillsConfig = Field(
        default_factory=SkillsConfig,
        description="Skills configuration",
    )

    @classmethod
    def load(cls, config_path: Path) -> "OakConfig":
        """Load configuration from file.

        Handles migration from old formats:
        - 'agent: str' to new 'agents: list[str]'
        - Infers enabled features from installed commands if features config is missing
        """
        import yaml

        if not config_path.exists():
            return cls()

        with open(config_path) as f:
            data = yaml.safe_load(f)
            if not data:
                return cls()

            # Migration: Convert old 'agent: str' to new 'agents: list[str]'
            if "agent" in data and "agents" not in data:
                agent_value = data.pop("agent")
                if agent_value and agent_value != "none":
                    data["agents"] = [agent_value]
                else:
                    data["agents"] = []

            # Convert agent_capabilities dict entries to AgentCapabilitiesConfig
            if "agent_capabilities" in data and isinstance(data["agent_capabilities"], dict):
                data["agent_capabilities"] = {
                    agent: AgentCapabilitiesConfig(**caps) if isinstance(caps, dict) else caps
                    for agent, caps in data["agent_capabilities"].items()
                }

            # Migration: Infer enabled features from installed commands
            if "features" not in data:
                enabled_features = set()
                claude_dir = config_path.parent.parent / ".claude"
                commands_dir = claude_dir / "commands"

                if commands_dir.exists():
                    # Map command prefixes to feature names
                    command_prefix_map = {
                        "oak.rfc-": "rfc",
                        "oak.constitution-": "constitution",
                        "oak.issue-": "issues",
                    }

                    # Scan for command files to infer features
                    for cmd_file in commands_dir.glob("oak.*.md"):
                        cmd_name = cmd_file.name
                        for prefix, feature in command_prefix_map.items():
                            if cmd_name.startswith(prefix):
                                enabled_features.add(feature)
                                break

                # Add dependencies for inferred features
                # constitution is a dependency of rfc and issues
                if "rfc" in enabled_features or "issues" in enabled_features:
                    enabled_features.add("constitution")

                data["features"] = {"enabled": sorted(enabled_features)}

            return cls(**data)

    def save(self, config_path: Path) -> None:
        """Save configuration to file."""

        # Custom representer to keep short lists inline (more readable)
        class InlineListDumper(yaml.SafeDumper):
            pass

        def represent_list(dumper: yaml.SafeDumper, data: list[Any]) -> yaml.nodes.Node:
            # Keep short lists (≤3 items) inline, longer ones multi-line
            if len(data) <= 3:
                return dumper.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=True)
            return dumper.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=False)

        InlineListDumper.add_representer(list, represent_list)

        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            yaml.dump(
                self.model_dump(mode="json", exclude_none=True),
                f,
                Dumper=InlineListDumper,
                default_flow_style=False,
                sort_keys=False,
            )
