"""Configuration models for open-agent-kit."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


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


class IssueProvidersConfig(BaseModel):
    """Top-level issue provider configuration."""

    provider: str | None = Field(default=None, description="Active issue provider key")
    azure_devops: AzureDevOpsProviderConfig = Field(
        default_factory=AzureDevOpsProviderConfig,
        description="Azure DevOps provider settings",
    )
    github: GitHubIssuesProviderConfig = Field(
        default_factory=GitHubIssuesProviderConfig,
        description="GitHub Issues provider settings",
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
    migrations: list[str] = Field(
        default_factory=list,
        description="Completed migration IDs (tracking for upgrade system)",
    )
    rfc: RFCConfig = Field(default_factory=RFCConfig, description="RFC configuration")
    issue: IssueProvidersConfig = Field(
        default_factory=IssueProvidersConfig, description="Issue provider configuration"
    )

    @classmethod
    def load(cls, config_path: Path) -> "OakConfig":
        """Load configuration from file.

        Handles migration from old 'agent: str' format to new 'agents: list[str]' format.
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
