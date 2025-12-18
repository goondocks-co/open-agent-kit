"""Feature models for open-agent-kit."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class LifecycleHooks(BaseModel):
    """OAK system lifecycle hooks that features can subscribe to.

    Features declare subscriptions to OAK system events in their manifest.yaml.
    When an event occurs, OAK calls the specified handler for each subscribed feature.

    Hook values use format: "feature:action" (e.g., "constitution:sync_agent_files")
    The feature name routes to the appropriate service, and the action specifies
    which method to call.

    Example manifest.yaml:
        hooks:
          on_agents_changed: constitution:sync_agent_files
          on_upgrade: constitution:migrate_schema
    """

    # Agent lifecycle
    on_agents_changed: str | None = Field(
        default=None,
        description="Called when agents are added/removed via 'oak init'",
    )

    # Upgrade lifecycle
    on_pre_upgrade: str | None = Field(
        default=None,
        description="Called before 'oak upgrade' applies changes (can prepare/backup)",
    )
    on_post_upgrade: str | None = Field(
        default=None,
        description="Called after 'oak upgrade' completes successfully",
    )

    # Removal lifecycle
    on_pre_remove: str | None = Field(
        default=None,
        description="Called before 'oak remove' starts (can clean up resources)",
    )

    # Feature lifecycle
    on_feature_enabled: str | None = Field(
        default=None,
        description="Called when THIS feature is enabled",
    )
    on_feature_disabled: str | None = Field(
        default=None,
        description="Called when THIS feature is about to be disabled",
    )

    # IDE lifecycle
    on_ides_changed: str | None = Field(
        default=None,
        description="Called when IDEs are added/removed via 'oak init'",
    )

    # Project lifecycle
    on_init_complete: str | None = Field(
        default=None,
        description="Called after 'oak init' completes (fresh install or update)",
    )


class FeatureManifest(BaseModel):
    """Feature manifest model representing a feature's metadata and configuration."""

    name: str = Field(..., description="Feature identifier (e.g., 'rfc', 'constitution')")
    display_name: str = Field(..., description="Human-readable feature name")
    description: str = Field(..., description="Feature description")
    version: str = Field(default="1.0.0", description="Feature version")
    default_enabled: bool = Field(default=True, description="Whether enabled by default")
    is_core: bool = Field(
        default=False, description="Whether this is a core (non-selectable) feature"
    )
    dependencies: list[str] = Field(
        default_factory=list, description="Required feature dependencies"
    )
    commands: list[str] = Field(
        default_factory=list, description="Command names provided by this feature"
    )
    templates: list[str] = Field(
        default_factory=list, description="Template files provided by this feature"
    )
    skills: list[str] = Field(default_factory=list, description="Skills provided by this feature")
    hooks: LifecycleHooks = Field(
        default_factory=LifecycleHooks, description="OAK system lifecycle hook subscriptions"
    )
    config_defaults: dict[str, Any] = Field(
        default_factory=dict, description="Default configuration values"
    )

    @classmethod
    def load(cls, manifest_path: Path) -> "FeatureManifest":
        """Load feature manifest from YAML file.

        Args:
            manifest_path: Path to manifest.yaml file

        Returns:
            FeatureManifest instance

        Raises:
            FileNotFoundError: If manifest file doesn't exist
            ValueError: If manifest is invalid
        """
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found: {manifest_path}")

        with open(manifest_path) as f:
            data = yaml.safe_load(f)

        if not data:
            raise ValueError(f"Empty manifest: {manifest_path}")

        return cls(**data)

    def get_all_dependencies(self, all_features: dict[str, "FeatureManifest"]) -> list[str]:
        """Get all transitive dependencies for this feature.

        Args:
            all_features: Dictionary of all available features

        Returns:
            List of all dependency feature names (including transitive)
        """
        all_deps: set[str] = set()
        to_process = list(self.dependencies)

        while to_process:
            dep_name = to_process.pop(0)
            if dep_name in all_deps:
                continue
            all_deps.add(dep_name)

            if dep_name in all_features:
                dep_feature = all_features[dep_name]
                for sub_dep in dep_feature.dependencies:
                    if sub_dep not in all_deps:
                        to_process.append(sub_dep)

        return sorted(all_deps)
