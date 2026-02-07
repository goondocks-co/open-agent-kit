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


class ConstitutionConfig(BaseModel):
    """Constitution feature configuration."""

    directory: str = Field(default="oak", description="Directory for constitution files")


class LanguagesConfig(BaseModel):
    """Languages configuration for code intelligence parsers."""

    installed: list[str] = Field(
        default_factory=list,
        description="List of installed language parser names",
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
    rfc: RFCConfig = Field(default_factory=RFCConfig, description="RFC configuration")
    constitution: ConstitutionConfig = Field(
        default_factory=ConstitutionConfig, description="Constitution configuration"
    )
    languages: LanguagesConfig = Field(
        default_factory=LanguagesConfig,
        description="Languages configuration for code intelligence parsers",
    )
    skills: SkillsConfig = Field(
        default_factory=SkillsConfig,
        description="Skills configuration",
    )
    # Passthrough field for codebase-intelligence feature config
    # Stored here to preserve it when OakConfig.save() is called
    # The CI feature has its own config models and save/load logic
    codebase_intelligence: dict[str, Any] | None = Field(
        default=None,
        description="Codebase Intelligence configuration (managed by CI feature)",
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

            # Migration: Remove deprecated agent_capabilities section
            data.pop("agent_capabilities", None)

            # Migration: Convert old features config to languages config
            # Remove old features section if present
            if "features" in data:
                data.pop("features")

            # Initialize languages if not present
            if "languages" not in data:
                data["languages"] = {"installed": []}

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
