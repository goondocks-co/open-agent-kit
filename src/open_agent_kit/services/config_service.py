"""Configuration service for managing open-agent-kit configuration.

This module provides centralized configuration management for open-agent-kit projects,
handling .oak/config.yaml reading, writing, and validation.

Key Classes:
    ConfigService: Main service for configuration CRUD operations

Dependencies:
    - Pydantic models (OakConfig, RFCConfig, IssueConfig, PlanConfig, ConstitutionConfig)
    - YAML for serialization

Configuration Hierarchy:
    1. Built-in defaults (in constants.py)
    2. Project config (.oak/config.yaml)
    3. Environment variables (for sensitive data)
    4. Command-line arguments (highest priority)

Configuration Sections:
    - project: Name, description, version
    - agents: Configured AI agents (claude, copilot, etc.)
    - rfc: RFC settings (auto_number, format, template, validation)
    - issue: Issue provider configuration (Azure DevOps, GitHub)

Typical Usage:
    >>> service = ConfigService(project_root=Path.cwd())
    >>> config = service.load_config()
    >>> config.rfc.auto_number = True
    >>> service.save_config(config)

Issue Provider Configuration:
    >>> config_service.update_issue_provider(
    ...     "ado",
    ...     organization="myorg",
    ...     project="myproject",
    ...     pat_env="ADO_PAT"
    ... )
"""

from pathlib import Path
from typing import Any

from open_agent_kit.config.paths import CONFIG_FILE, OAK_DIR
from open_agent_kit.constants import (
    DEFAULT_CONFIG_YAML,
    DEFAULT_FEATURES,
    ISSUE_PROVIDER_CONFIG_MAP,
    VERSION,
)
from open_agent_kit.models.config import IssueConfig, OakConfig
from open_agent_kit.utils import file_exists, read_yaml, write_file


class ConfigService:
    """Service for managing configuration."""

    def __init__(self, project_root: Path | None = None):
        """Initialize config service.

        Args:
            project_root: Project root directory (defaults to current directory)
        """
        self.project_root = project_root or Path.cwd()
        self.config_path = self.project_root / CONFIG_FILE

    def load_config(self, auto_migrate: bool = True) -> OakConfig:
        """Load configuration from file.

        Args:
            auto_migrate: If True, automatically migrates old config format and saves

        Returns:
            OakConfig object

        If config file doesn't exist, returns default configuration.
        Automatically migrates old 'agent: str' format to 'agents: list[str]'.
        """
        if not file_exists(self.config_path):
            return OakConfig()

        try:
            # Load raw data to check for migration
            data = read_yaml(self.config_path)
            needs_migration = "agent" in data and "agents" not in data

            # Load via model (handles migration)
            config = OakConfig.load(self.config_path)

            # Auto-save migrated config
            if auto_migrate and needs_migration:
                self.save_config(config)

            return config
        except Exception:
            # Return default config if parsing fails
            return OakConfig()

    def save_config(self, config: OakConfig) -> None:
        """Save configuration to file.

        Args:
            config: OakConfig object to save
        """
        config.save(self.config_path)

    def create_default_config(
        self,
        agents: list[str] | None = None,
        ides: list[str] | None = None,
        features: list[str] | None = None,
    ) -> OakConfig:
        """Create and save default configuration.

        Args:
            agents: List of agent types (optional)
            ides: List of IDE types (optional)
            features: List of feature names (optional, defaults to DEFAULT_FEATURES)

        Returns:
            Created OakConfig object
        """
        # Format agents list for YAML
        agents_yaml = "[]"
        if agents:
            # Create YAML list format
            agents_yaml = "[" + ", ".join(agents) + "]"

        # Format ides list for YAML
        ides_yaml = "[]"
        if ides:
            # Create YAML list format
            ides_yaml = "[" + ", ".join(ides) + "]"

        # Create config from template
        config_content = DEFAULT_CONFIG_YAML.format(
            version=VERSION,
            agents=agents_yaml,
            ides=ides_yaml,
        )

        # Write to file
        write_file(self.config_path, config_content)

        # Load config
        config = self.load_config()

        # Set features (defaults to DEFAULT_FEATURES if not specified)
        if features is None:
            features = list(DEFAULT_FEATURES)
        config.features.enabled = features
        self.save_config(config)

        return config

    def update_config(self, **kwargs: Any) -> OakConfig:
        """Update configuration with provided values.

        Args:
            **kwargs: Configuration values to update

        Returns:
            Updated OakConfig object
        """
        config = self.load_config()

        # Update values
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)

        # Save and return
        self.save_config(config)
        return config

    def config_exists(self) -> bool:
        """Check if configuration file exists.

        Returns:
            True if config file exists, False otherwise
        """
        return file_exists(self.config_path)

    def get_oak_dir(self) -> Path:
        """Get .oak directory path.

        Returns:
            Path to .oak directory
        """
        return self.project_root / OAK_DIR

    def get_rfc_dir(self) -> Path:
        """Get RFC directory path from config.

        Returns:
            Path to RFC directory
        """
        config = self.load_config()
        return self.project_root / config.rfc.directory

    def get_templates_dir(self) -> Path:
        """Get templates directory path.

        Returns:
            Path to templates directory
        """
        return self.get_oak_dir() / "templates"

    def get_commands_dir(self) -> Path:
        """Get commands directory path.

        Returns:
            Path to commands directory
        """
        return self.get_oak_dir() / "commands"

    def get_issue_dir(self) -> Path:
        """Get issue artifacts directory path.

        Note: Issue directory is now hardcoded to oak/issue since issue contexts
        can be stored either standalone or within plan directories.

        Returns:
            Path to issue directory (oak/issue)
        """
        return self.project_root / "oak" / "issue"

    def get_plan_dir(self) -> Path:
        """Get plan artifacts directory path from config.

        Returns:
            Path to plan directory
        """
        config = self.load_config()
        return self.project_root / config.plan.directory

    def get_constitution_dir(self) -> Path:
        """Get constitution directory path from config.

        Returns:
            Path to constitution directory
        """
        config = self.load_config()
        return self.project_root / config.constitution.directory

    def get_agents(self) -> list[str]:
        """Get configured agents list.

        Returns:
            List of agent names
        """
        config = self.load_config()
        return config.agents

    def update_agents(self, agents: list[str]) -> OakConfig:
        """Update agents list in configuration.

        Args:
            agents: List of agent names

        Returns:
            Updated OakConfig object
        """
        return self.update_config(agents=agents)

    def add_agents(self, new_agents: list[str]) -> OakConfig:
        """Add agents to configuration (merges with existing).

        Also updates the config version to current package version.

        Args:
            new_agents: List of agent names to add

        Returns:
            Updated OakConfig object
        """
        existing_agents = self.get_agents()
        # Merge and deduplicate
        all_agents = list(set(existing_agents + new_agents))
        # Update both agents and version
        return self.update_config(agents=all_agents, version=VERSION)

    def get_ides(self) -> list[str]:
        """Get configured IDEs list.

        Returns:
            List of IDE names
        """
        config = self.load_config()
        return config.ides

    def update_ides(self, ides: list[str]) -> OakConfig:
        """Update IDEs list in configuration.

        Args:
            ides: List of IDE names

        Returns:
            Updated OakConfig object
        """
        return self.update_config(ides=ides)

    def add_ides(self, new_ides: list[str]) -> OakConfig:
        """Add IDEs to configuration (merges with existing).

        Also updates the config version to current package version.

        Args:
            new_ides: List of IDE names to add

        Returns:
            Updated OakConfig object
        """
        existing_ides = self.get_ides()
        # Merge and deduplicate
        all_ides = list(set(existing_ides + new_ides))
        # Update both ides and version
        return self.update_config(ides=all_ides, version=VERSION)

    def get_issue_config(self) -> IssueConfig:
        """Get issue configuration.

        Returns:
            IssueConfig object
        """
        config = self.load_config()
        return config.issue

    def get_active_issue_provider(self) -> str | None:
        """Get the active issue provider key.

        Returns:
            Provider key or None
        """
        issue_config = self.get_issue_config()
        return issue_config.provider

    def update_issue_provider(
        self,
        provider_key: str,
        **settings: Any,
    ) -> IssueConfig:
        """Update issue provider configuration and set it active.

        Args:
            provider_key: Provider identifier (e.g., 'ado', 'github')
            **settings: Provider-specific settings

        Returns:
            Updated IssueConfig object
        """
        provider_attr = ISSUE_PROVIDER_CONFIG_MAP.get(provider_key)
        if not provider_attr:
            raise ValueError(f"Unsupported issue provider: {provider_key}")

        config = self.load_config()
        provider_config = getattr(config.issue, provider_attr, None)
        if provider_config is None:
            raise ValueError(f"No configuration section for provider '{provider_key}'")

        # Apply provided settings
        for key, value in settings.items():
            if value is None:
                continue
            if hasattr(provider_config, key):
                setattr(provider_config, key, value)

        config.issue.provider = provider_key
        self.save_config(config)
        return config.issue

    def get_provider_settings(self, provider_key: str | None = None) -> dict[str, Any]:
        """Get provider-specific settings as dictionary.

        Args:
            provider_key: Provider identifier (defaults to active provider)

        Returns:
            Dictionary of provider settings
        """
        issue_config = self.get_issue_config()
        resolved_key = provider_key or issue_config.provider
        if not resolved_key:
            return {}

        provider_attr = ISSUE_PROVIDER_CONFIG_MAP.get(resolved_key)
        if not provider_attr:
            return {}

        provider_config = getattr(issue_config, provider_attr, None)
        if provider_config is None:
            return {}

        result: dict[str, Any] = provider_config.model_dump(mode="json", exclude_none=True)
        return result

    def validate_config(self) -> tuple[bool, list[str]]:
        """Validate current configuration.

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        if not self.config_exists():
            return (False, ["Configuration file does not exist"])

        try:
            config = self.load_config()
            errors = []

            # Validate agents
            if config.agents:
                from open_agent_kit.services.agent_service import AgentService

                agent_service = AgentService()
                available_agents = agent_service.list_available_agents()
                for agent in config.agents:
                    if agent.lower() not in available_agents:
                        errors.append(f"Invalid agent: {agent}")

            # Validate RFC config
            if not config.rfc.directory:
                errors.append("RFC directory not configured")

            if not config.rfc.template:
                errors.append("RFC template not configured")

            return (len(errors) == 0, errors)

        except Exception as e:
            return (False, [f"Failed to validate config: {str(e)}"])

    def get_config_dict(self) -> dict:
        """Get configuration as dictionary.

        Returns:
            Configuration dictionary
        """
        config = self.load_config()
        return config.model_dump(mode="json", exclude_none=True)

    def reset_config(self) -> None:
        """Reset configuration to defaults."""
        self.create_default_config()

    def get_completed_migrations(self) -> list[str]:
        """Get list of completed migration IDs.

        Delegates to StateService for state management.

        Returns:
            List of migration IDs that have been completed
        """
        from open_agent_kit.services.state_service import StateService

        state_service = StateService(self.project_root)
        return state_service.get_applied_migrations()

    def add_completed_migrations(self, migration_ids: list[str]) -> OakConfig:
        """Add migration IDs to the completed migrations list.

        Delegates to StateService for state management.

        Args:
            migration_ids: List of migration IDs to mark as completed

        Returns:
            Current OakConfig object (migrations stored in state, not config)
        """
        from open_agent_kit.services.state_service import StateService

        state_service = StateService(self.project_root)
        state_service.add_applied_migrations(migration_ids)
        return self.load_config()

    def get_features(self) -> list[str]:
        """Get configured features list.

        Returns:
            List of enabled feature names
        """
        config = self.load_config()
        return config.features.enabled

    def update_features(self, features: list[str]) -> OakConfig:
        """Update features list in configuration.

        Args:
            features: List of feature names

        Returns:
            Updated OakConfig object
        """
        config = self.load_config()
        config.features.enabled = features
        self.save_config(config)
        return config

    def add_features(self, new_features: list[str]) -> OakConfig:
        """Add features to configuration (merges with existing).

        Args:
            new_features: List of feature names to add

        Returns:
            Updated OakConfig object
        """
        existing = self.get_features()
        all_features = list(set(existing + new_features))
        return self.update_features(all_features)

    def remove_features(self, features_to_remove: list[str]) -> OakConfig:
        """Remove features from configuration.

        Args:
            features_to_remove: List of feature names to remove

        Returns:
            Updated OakConfig object
        """
        existing = self.get_features()
        remaining = [f for f in existing if f not in features_to_remove]
        return self.update_features(remaining)


def get_config_service(project_root: Path | None = None) -> ConfigService:
    """Get a ConfigService instance.

    Args:
        project_root: Project root directory (defaults to current directory)

    Returns:
        ConfigService instance
    """
    return ConfigService(project_root)
