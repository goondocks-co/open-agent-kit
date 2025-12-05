"""Feature service for managing OAK features."""

import re
from pathlib import Path
from typing import Any, cast

from open_agent_kit.config.paths import FEATURE_MANIFEST_FILE, FEATURES_DIR
from open_agent_kit.constants import FEATURE_CONFIG, SUPPORTED_FEATURES
from open_agent_kit.models.feature import FeatureManifest
from open_agent_kit.services.config_service import ConfigService
from open_agent_kit.services.state_service import StateService
from open_agent_kit.utils import ensure_dir, read_file, write_file

# Regex pattern to detect Jinja2 template syntax
JINJA2_PATTERN = re.compile(r"\{\{|\{%")


class FeatureService:
    """Service for managing OAK features with dependency resolution.

    Handles feature discovery, installation, removal, and dependency management.
    """

    def __init__(self, project_root: Path | None = None):
        """Initialize feature service.

        Args:
            project_root: Project root directory (defaults to current directory)
        """
        self.project_root = project_root or Path.cwd()
        self.config_service = ConfigService(project_root)
        self.state_service = StateService(project_root)

        # Package features directory (where feature manifests/templates are stored)
        self.package_features_dir = Path(__file__).parent.parent.parent.parent / FEATURES_DIR

    def _has_jinja2_syntax(self, content: str) -> bool:
        """Check if content contains Jinja2 template syntax.

        Args:
            content: String content to check

        Returns:
            True if content contains {{ or {% syntax
        """
        return bool(JINJA2_PATTERN.search(content))

    def _render_command_for_agent(self, content: str, agent_type: str) -> str:
        """Render command content with agent-specific context.

        If content contains Jinja2 syntax, renders it with agent context.
        Otherwise returns content unchanged.

        Args:
            content: Raw command content (may contain Jinja2 syntax)
            agent_type: Agent type (e.g., 'claude', 'cursor')

        Returns:
            Rendered content with agent-specific values
        """
        if not self._has_jinja2_syntax(content):
            return content

        # Import here to avoid circular dependency
        from open_agent_kit.services.agent_service import AgentService
        from open_agent_kit.services.template_service import TemplateService

        agent_service = AgentService(self.project_root)
        template_service = TemplateService(project_root=self.project_root)

        # Get agent context for rendering
        context = agent_service.get_agent_context(agent_type)

        # Render template with agent context
        return template_service.render_string(content, context)

    def list_available_features(self) -> list[FeatureManifest]:
        """List all available features from package.

        Returns:
            List of FeatureManifest objects for all available features
        """
        features = []
        for feature_name in SUPPORTED_FEATURES:
            manifest = self.get_feature_manifest(feature_name)
            if manifest:
                features.append(manifest)
        return features

    def get_feature_manifest(self, feature_name: str) -> FeatureManifest | None:
        """Get manifest for a specific feature.

        Args:
            feature_name: Name of the feature

        Returns:
            FeatureManifest or None if not found
        """
        manifest_path = self.package_features_dir / feature_name / FEATURE_MANIFEST_FILE
        if manifest_path.exists():
            return FeatureManifest.load(manifest_path)

        # Fall back to FEATURE_CONFIG if manifest doesn't exist
        if feature_name in FEATURE_CONFIG:
            config = FEATURE_CONFIG[feature_name]
            return FeatureManifest(
                name=feature_name,
                display_name=str(config["name"]),
                description=str(config["description"]),
                default_enabled=bool(config["default_enabled"]),
                dependencies=cast(list[str], config["dependencies"]),
                commands=cast(list[str], config["commands"]),
            )
        return None

    def list_installed_features(self) -> list[str]:
        """List features currently installed in the project.

        Returns:
            List of installed feature names
        """
        config = self.config_service.load_config()
        return config.features.enabled

    def is_feature_installed(self, feature_name: str) -> bool:
        """Check if a feature is installed.

        Args:
            feature_name: Name of the feature

        Returns:
            True if feature is installed
        """
        return feature_name in self.list_installed_features()

    def get_feature_dependencies(self, feature_name: str) -> list[str]:
        """Get direct dependencies for a feature.

        Args:
            feature_name: Name of the feature

        Returns:
            List of dependency feature names
        """
        manifest = self.get_feature_manifest(feature_name)
        if manifest:
            return manifest.dependencies
        return []

    def get_all_dependencies(self, feature_name: str) -> list[str]:
        """Get all transitive dependencies for a feature.

        Args:
            feature_name: Name of the feature

        Returns:
            List of all dependency feature names (including transitive)
        """
        manifest = self.get_feature_manifest(feature_name)
        if not manifest:
            return []

        all_features = {f.name: f for f in self.list_available_features()}
        return manifest.get_all_dependencies(all_features)

    def resolve_dependencies(self, features: list[str]) -> list[str]:
        """Resolve dependencies for a list of features.

        Adds any missing dependencies and returns features in installation order.

        Args:
            features: List of feature names to install

        Returns:
            List of feature names with dependencies resolved, in correct order
        """
        resolved: set[str] = set()
        result: list[str] = []

        def add_feature(name: str) -> None:
            if name in resolved:
                return

            # Add dependencies first
            deps = self.get_all_dependencies(name)
            for dep in deps:
                if dep not in resolved:
                    add_feature(dep)

            resolved.add(name)
            result.append(name)

        for feature in features:
            add_feature(feature)

        return result

    def get_features_requiring(self, feature_name: str) -> list[str]:
        """Get features that depend on the given feature.

        Args:
            feature_name: Name of the feature

        Returns:
            List of feature names that require this feature
        """
        dependents = []
        for manifest in self.list_available_features():
            if feature_name in manifest.dependencies:
                dependents.append(manifest.name)
        return dependents

    def can_remove_feature(self, feature_name: str) -> tuple[bool, list[str]]:
        """Check if a feature can be safely removed.

        Args:
            feature_name: Name of the feature

        Returns:
            Tuple of (can_remove, list_of_blocking_features)
        """
        installed = set(self.list_installed_features())
        dependents = self.get_features_requiring(feature_name)
        blocking = [d for d in dependents if d in installed]
        return (len(blocking) == 0, blocking)

    def get_feature_commands_dir(self, feature_name: str) -> Path:
        """Get commands directory for a feature.

        Args:
            feature_name: Name of the feature

        Returns:
            Path to feature's commands directory
        """
        return self.package_features_dir / feature_name / "commands"

    def get_feature_templates_dir(self, feature_name: str) -> Path:
        """Get templates directory for a feature.

        Args:
            feature_name: Name of the feature

        Returns:
            Path to feature's templates directory
        """
        return self.package_features_dir / feature_name / "templates"

    def get_feature_commands(self, feature_name: str) -> list[str]:
        """Get list of command names for a feature.

        Args:
            feature_name: Name of the feature

        Returns:
            List of command names (e.g., ['rfc-create', 'rfc-list'])
        """
        manifest = self.get_feature_manifest(feature_name)
        if manifest:
            return manifest.commands
        return []

    def install_feature(self, feature_name: str, agents: list[str]) -> dict[str, list[str]]:
        """Install a feature for the given agents.

        This installs the feature's commands to each agent's native directory.
        Does NOT handle dependencies - call resolve_dependencies first.

        Args:
            feature_name: Name of the feature to install
            agents: List of agent types to install for

        Returns:
            Dictionary with installation results:
            {
                'commands_installed': ['rfc-create', 'rfc-list'],
                'templates_copied': ['engineering.md', 'architecture.md'],
                'agents': ['claude', 'copilot']
            }
        """
        results: dict[str, list[str]] = {
            "commands_installed": [],
            "templates_copied": [],
            "agents": [],
        }

        manifest = self.get_feature_manifest(feature_name)
        if not manifest:
            return results

        # Install commands for each agent
        from open_agent_kit.services.agent_service import AgentService

        agent_service = AgentService(self.project_root)

        commands_dir = self.get_feature_commands_dir(feature_name)

        for agent_type in agents:
            agent_commands_dir = agent_service.create_agent_commands_dir(agent_type)

            for command_name in manifest.commands:
                # Read template from feature's commands directory
                template_file = commands_dir / f"oak.{command_name}.md"
                if not template_file.exists():
                    continue

                content = read_file(template_file)

                # Render with agent-specific context if command uses Jinja2 syntax
                rendered_content = self._render_command_for_agent(content, agent_type)

                # Write to agent's commands directory with proper extension
                filename = agent_service.get_command_filename(agent_type, command_name)
                file_path = agent_commands_dir / filename

                write_file(file_path, rendered_content)

                # Record the created file for smart removal later
                self.state_service.record_created_file(file_path, rendered_content)

                # Record the directory if this is the first file we're adding to it
                self.state_service.record_created_directory(agent_commands_dir)

                if command_name not in results["commands_installed"]:
                    results["commands_installed"].append(command_name)

            results["agents"].append(agent_type)

        # Create .oak/features/{feature}/ directory structure
        project_feature_dir = self.project_root / ".oak" / "features" / feature_name
        ensure_dir(project_feature_dir)

        # Copy commands to .oak/features/{feature}/commands/ (canonical install location)
        if commands_dir.exists() and manifest.commands:
            project_commands_dir = project_feature_dir / "commands"
            ensure_dir(project_commands_dir)

            for command_name in manifest.commands:
                src = commands_dir / f"oak.{command_name}.md"
                if src.exists():
                    dst = project_commands_dir / f"oak.{command_name}.md"
                    write_file(dst, read_file(src))

        # Copy templates to .oak/features/{feature}/templates/ if any exist
        templates_dir = self.get_feature_templates_dir(feature_name)
        if templates_dir.exists() and manifest.templates:
            project_templates_dir = project_feature_dir / "templates"
            ensure_dir(project_templates_dir)

            for template in manifest.templates:
                src = templates_dir / template
                if src.exists():
                    dst = project_templates_dir / template
                    write_file(dst, read_file(src))
                    results["templates_copied"].append(template)

        # Update config to mark feature as installed
        config = self.config_service.load_config()
        if feature_name not in config.features.enabled:
            config.features.enabled.append(feature_name)
            self.config_service.save_config(config)

        return results

    def remove_feature(
        self, feature_name: str, agents: list[str], remove_config: bool = False
    ) -> dict[str, list[str]]:
        """Remove a feature from the project.

        Does NOT check dependencies - call can_remove_feature first.

        Args:
            feature_name: Name of the feature to remove
            agents: List of agent types to remove from
            remove_config: Whether to remove feature config from config.yaml

        Returns:
            Dictionary with removal results
        """
        results: dict[str, list[str]] = {
            "commands_removed": [],
            "templates_removed": [],
            "agents": [],
        }

        manifest = self.get_feature_manifest(feature_name)
        if not manifest:
            return results

        # Remove commands from each agent
        from open_agent_kit.services.agent_service import AgentService

        agent_service = AgentService(self.project_root)

        for agent_type in agents:
            agent_commands_dir = agent_service.get_agent_commands_dir(agent_type)
            if not agent_commands_dir.exists():
                continue

            for command_name in manifest.commands:
                filename = agent_service.get_command_filename(agent_type, command_name)
                file_path = agent_commands_dir / filename

                if file_path.exists():
                    file_path.unlink()
                    if command_name not in results["commands_removed"]:
                        results["commands_removed"].append(command_name)

            results["agents"].append(agent_type)

        # Remove entire .oak/features/{feature}/ directory (commands and templates)
        project_feature_dir = self.project_root / ".oak" / "features" / feature_name
        if project_feature_dir.exists():
            import shutil

            shutil.rmtree(project_feature_dir)
            results["templates_removed"] = manifest.templates

        # Update config to mark feature as uninstalled
        config = self.config_service.load_config()
        if feature_name in config.features.enabled:
            config.features.enabled.remove(feature_name)
            self.config_service.save_config(config)

        return results

    def refresh_features(self) -> dict[str, Any]:
        """Refresh all installed features by re-rendering with current config.

        This re-renders command templates using current agent_capabilities,
        allowing users to update capabilities in config.yaml and apply changes
        without a package upgrade.

        Returns:
            Dictionary with refresh results:
            - features_refreshed: list of feature names
            - commands_rendered: dict of feature -> list of commands
            - agents: list of agents updated
        """
        results: dict[str, Any] = {
            "features_refreshed": [],
            "commands_rendered": {},
            "agents": [],
        }

        # Get installed features and configured agents
        config = self.config_service.load_config()
        installed_features = config.features.enabled
        agents = config.agents

        if not agents:
            return results

        results["agents"] = agents

        # Re-render each feature for all agents
        for feature_name in installed_features:
            manifest = self.get_feature_manifest(feature_name)
            if not manifest:
                continue

            feature_results = self.install_feature(feature_name, agents)
            results["features_refreshed"].append(feature_name)
            results["commands_rendered"][feature_name] = feature_results.get(
                "commands_installed", []
            )

        return results


def get_feature_service(project_root: Path | None = None) -> FeatureService:
    """Get a FeatureService instance.

    Args:
        project_root: Project root directory (defaults to current directory)

    Returns:
        FeatureService instance
    """
    return FeatureService(project_root)
