"""Feature service for managing OAK features."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from open_agent_kit.config.paths import FEATURE_MANIFEST_FILE, FEATURES_DIR
from open_agent_kit.models.results import FeatureRefreshResult

if TYPE_CHECKING:
    from open_agent_kit.services.template_service import TemplateService
from open_agent_kit.constants import FEATURE_CONFIG, SUPPORTED_FEATURES
from open_agent_kit.models.feature import FeatureManifest
from open_agent_kit.services.config_service import ConfigService
from open_agent_kit.services.hook_dispatcher import HookDispatcher
from open_agent_kit.services.package_installer_service import PackageInstallerService
from open_agent_kit.services.prerequisite_checker import PrerequisiteChecker
from open_agent_kit.services.state_service import StateService
from open_agent_kit.utils import (
    add_gitignore_entries,
    read_file,
    remove_gitignore_entries,
    write_file,
)
from open_agent_kit.utils.naming import feature_name_to_dir as _feature_name_to_dir

logger = logging.getLogger(__name__)


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
        self._package_installer = PackageInstallerService()
        self._prerequisite_checker = PrerequisiteChecker()
        self._hook_dispatcher = HookDispatcher()

        # Package features directory (where feature manifests/templates are stored)
        # Path: services/feature_service.py -> services/ -> open_agent_kit/
        self.package_features_dir = Path(__file__).parent.parent / FEATURES_DIR
        self._template_service: TemplateService | None = None

    @property
    def template_service(self) -> "TemplateService":
        """Lazy-load template service to avoid circular dependencies."""
        if self._template_service is None:
            from open_agent_kit.services.template_service import TemplateService

            self._template_service = TemplateService(project_root=self.project_root)
        return self._template_service

    # =========================================================================
    # Feature Discovery & Dependency Resolution
    # =========================================================================

    def list_available_features(self) -> list[FeatureManifest]:
        """List all available features from package."""
        features = []
        for feature_name in SUPPORTED_FEATURES:
            manifest = self.get_feature_manifest(feature_name)
            if manifest:
                features.append(manifest)
        return features

    def get_feature_manifest(self, feature_name: str) -> FeatureManifest | None:
        """Get manifest for a specific feature, or None if not found."""
        feature_dir = _feature_name_to_dir(feature_name)
        manifest_path = self.package_features_dir / feature_dir / FEATURE_MANIFEST_FILE
        if manifest_path.exists():
            return FeatureManifest.load(manifest_path)

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
        """List installed feature names (all features are always installed)."""
        return list(SUPPORTED_FEATURES)

    def is_feature_installed(self, feature_name: str) -> bool:
        """Check if a feature is installed."""
        return feature_name in self.list_installed_features()

    def get_feature_dependencies(self, feature_name: str) -> list[str]:
        """Get direct dependencies for a feature."""
        manifest = self.get_feature_manifest(feature_name)
        if manifest:
            return manifest.dependencies
        return []

    def get_all_dependencies(self, feature_name: str) -> list[str]:
        """Get all transitive dependencies for a feature."""
        manifest = self.get_feature_manifest(feature_name)
        if not manifest:
            return []

        all_features = {f.name: f for f in self.list_available_features()}
        return manifest.get_all_dependencies(all_features)

    def resolve_dependencies(self, features: list[str]) -> list[str]:
        """Resolve dependencies, returning features in installation order."""
        resolved: set[str] = set()
        result: list[str] = []

        def add_feature(name: str) -> None:
            if name in resolved:
                return
            for dep in self.get_all_dependencies(name):
                if dep not in resolved:
                    add_feature(dep)
            resolved.add(name)
            result.append(name)

        for feature in features:
            add_feature(feature)

        return result

    def get_features_requiring(self, feature_name: str) -> list[str]:
        """Get features that depend on the given feature."""
        return [m.name for m in self.list_available_features() if feature_name in m.dependencies]

    def can_remove_feature(self, feature_name: str) -> tuple[bool, list[str]]:
        """Check if a feature can be safely removed (no installed dependents)."""
        installed = set(self.list_installed_features())
        blocking = [d for d in self.get_features_requiring(feature_name) if d in installed]
        return (len(blocking) == 0, blocking)

    def get_feature_commands_dir(self, feature_name: str) -> Path:
        """Get commands directory for a feature."""
        feature_dir = _feature_name_to_dir(feature_name)
        return self.package_features_dir / feature_dir / "commands"

    def get_feature_templates_dir(self, feature_name: str) -> Path:
        """Get templates directory for a feature."""
        feature_dir = _feature_name_to_dir(feature_name)
        return self.package_features_dir / feature_dir / "templates"

    def get_feature_commands(self, feature_name: str) -> list[str]:
        """Get list of command names for a feature."""
        manifest = self.get_feature_manifest(feature_name)
        if manifest:
            return manifest.commands
        return []

    # =========================================================================
    # Feature Installation
    # =========================================================================

    def install_feature(self, feature_name: str, agents: list[str]) -> dict[str, list[str]]:
        """Install a feature's commands to each agent's native directory.

        Does NOT handle dependencies -- call resolve_dependencies first.
        """
        results: dict[str, Any] = {
            "commands_installed": [],
            "templates_copied": [],
            "agents": [],
            "pip_packages_installed": [],
            "prerequisites_checked": False,
            "prerequisites_warnings": [],
        }

        manifest = self.get_feature_manifest(feature_name)
        if not manifest:
            return results

        self._install_feature_packages(manifest, feature_name, results)
        self._install_feature_commands(manifest, feature_name, agents, results)
        self._finalize_feature_install(manifest, feature_name, results)

        return results

    def _install_feature_packages(
        self, manifest: FeatureManifest, feature_name: str, results: dict[str, Any]
    ) -> None:
        """Check prerequisites and install pip packages. Raises on failure."""
        # Check prerequisites if declared
        if manifest.prerequisites:
            prereq_result = self._prerequisite_checker.check(manifest.prerequisites)
            results["prerequisites_checked"] = True
            results["prerequisites_warnings"] = prereq_result.get("warnings", [])

            if prereq_result.get("missing"):
                from open_agent_kit.utils import print_warning

                for missing in prereq_result["missing"]:
                    print_warning(f"\nMissing prerequisite: {missing['name']}")
                    if missing.get("instructions"):
                        print_warning(f"Installation instructions:\n{missing['instructions']}")

        # Install pip packages if declared
        if manifest.pip_packages:
            packages_installed = self._package_installer.install(
                manifest.pip_packages, feature_name
            )
            if packages_installed:
                results["pip_packages_installed"] = manifest.pip_packages
            else:
                from open_agent_kit.utils import print_error

                print_error(
                    f"Failed to install required packages for '{feature_name}'. "
                    f"The feature cannot function without these dependencies."
                )
                print_error(
                    "You can try installing manually: "
                    f"pip install {' '.join(manifest.pip_packages)}"
                )
                raise RuntimeError(
                    f"Required pip packages for feature '{feature_name}' failed to install"
                )

        # Add gitignore entries if declared
        if manifest.gitignore:
            added = add_gitignore_entries(
                self.project_root,
                manifest.gitignore,
                section_comment=f"open-agent-kit: {manifest.display_name}",
            )
            if added:
                results["gitignore_added"] = added

    def _install_feature_commands(
        self,
        manifest: FeatureManifest,
        feature_name: str,
        agents: list[str],
        results: dict[str, Any],
    ) -> None:
        """Render and install feature command templates for each agent."""
        from open_agent_kit.services.agent_service import AgentService

        agent_service = AgentService(self.project_root)
        commands_dir = self.get_feature_commands_dir(feature_name)

        for agent_type in agents:
            agent_commands_dir = agent_service.create_agent_commands_dir(agent_type)

            for command_name in manifest.commands:
                template_file = commands_dir / f"oak.{command_name}.md"
                if not template_file.exists():
                    continue

                content = read_file(template_file)
                rendered_content = self.template_service.render_command_for_agent(
                    content, agent_type
                )

                filename = agent_service.get_command_filename(agent_type, command_name)
                file_path = agent_commands_dir / filename

                write_file(file_path, rendered_content)
                self.state_service.record_created_file(file_path, rendered_content)
                self.state_service.record_created_directory(agent_commands_dir)

                if command_name not in results["commands_installed"]:
                    results["commands_installed"].append(command_name)

            results["agents"].append(agent_type)

    def _finalize_feature_install(
        self, manifest: FeatureManifest, feature_name: str, results: dict[str, Any]
    ) -> None:
        """Run post-install hooks and auto-install skills for a new feature."""
        config = self.config_service.load_config()
        was_disabled = not self.state_service.is_feature_initialized(feature_name)
        if was_disabled:
            self.state_service.mark_feature_initialized(feature_name)

        # Trigger feature enabled hook if this is a new install
        if was_disabled:
            try:
                hook_result = self.trigger_feature_enabled_hook(feature_name)
                for f_name, result in hook_result.items():
                    if not result.get("success"):
                        from open_agent_kit.utils import print_warning

                        error = result.get("error", "Unknown error")
                        print_warning(f"Feature hook for {f_name} failed: {error}")
                        logger.warning(f"Feature hook for {f_name} failed: {error}")
            except Exception as e:
                from open_agent_kit.utils import print_warning

                print_warning(f"Failed to run initialization hook for {feature_name}: {e}")
                logger.warning(f"Failed to trigger feature enabled hook for {feature_name}: {e}")

        # Auto-install associated skills if enabled
        if was_disabled and config.skills.auto_install:
            try:
                from open_agent_kit.services.skill_service import SkillService

                skill_service = SkillService(self.project_root)
                skill_results = skill_service.install_skills_for_feature(feature_name)
                if skill_results.get("skills_installed"):
                    results["skills_installed"] = skill_results["skills_installed"]
            except Exception as e:
                logger.warning(f"Failed to auto-install skills for {feature_name}: {e}")

    # =========================================================================
    # Feature Removal
    # =========================================================================

    def remove_feature(
        self, feature_name: str, agents: list[str], remove_config: bool = False
    ) -> dict[str, list[str]]:
        """Remove a feature's commands and skills. Call can_remove_feature first."""
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

        # Remove gitignore entries if declared
        if manifest.gitignore:
            removed_entries = remove_gitignore_entries(
                self.project_root,
                manifest.gitignore,
            )
            if removed_entries:
                results["gitignore_removed"] = removed_entries

        # Remove associated skills
        try:
            from open_agent_kit.services.skill_service import SkillService

            skill_service = SkillService(self.project_root)
            skill_results = skill_service.remove_skills_for_feature(feature_name)
            if skill_results.get("skills_removed"):
                results["skills_removed"] = skill_results["skills_removed"]
        except Exception as e:
            logger.warning(f"Failed to remove skills for {feature_name}: {e}")

        # Trigger feature disabled hook BEFORE updating state
        was_enabled = self.state_service.is_feature_initialized(feature_name)
        if was_enabled:
            try:
                self.trigger_feature_disabled_hook(feature_name)
            except Exception as e:
                logger.warning(f"Failed to trigger feature disabled hook for {feature_name}: {e}")

        # Update state to mark feature as uninitialized
        if was_enabled:
            self.state_service.unmark_feature_initialized(feature_name)

        return results

    # =========================================================================
    # Feature Refresh
    # =========================================================================

    def refresh_features(self) -> FeatureRefreshResult:
        """Re-render all feature command templates with current agent config."""
        results: FeatureRefreshResult = {
            "features_refreshed": [],
            "commands_rendered": {},
            "agents": [],
        }

        config = self.config_service.load_config()
        installed_features = SUPPORTED_FEATURES
        agents = config.agents

        if not agents:
            return results

        results["agents"] = agents

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

    # =========================================================================
    # Lifecycle Hook System
    #
    # Features declare hook subscriptions in manifest.yaml under 'hooks:'.
    # Hook spec format: "feature:action" (e.g., "constitution:sync_agent_files")
    # Dispatch is handled by HookDispatcher with registered handlers per feature.
    # =========================================================================

    def _trigger_hook(
        self, hook_name: str, features: list[str] | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        """Trigger hook_name for subscribed features, returning per-feature results."""
        results: dict[str, Any] = {}
        target_features = features if features is not None else self.list_installed_features()

        for feature_name in target_features:
            manifest = self.get_feature_manifest(feature_name)
            if not manifest:
                continue

            hook_spec = getattr(manifest.hooks, hook_name, None)
            if not hook_spec:
                continue

            try:
                hook_result = self._hook_dispatcher.dispatch(hook_spec, self.project_root, **kwargs)
                results[feature_name] = {"success": True, "result": hook_result}
            except Exception as e:
                results[feature_name] = {"success": False, "error": str(e)}

        return results

    def trigger_agents_changed_hooks(
        self, agents_added: list[str], agents_removed: list[str]
    ) -> dict[str, Any]:
        """Trigger on_agents_changed hooks (called from 'oak init')."""
        return self._trigger_hook(
            "on_agents_changed",
            agents_added=agents_added,
            agents_removed=agents_removed,
        )

    def trigger_ides_changed_hooks(
        self, ides_added: list[str], ides_removed: list[str]
    ) -> dict[str, Any]:
        """Trigger on_ides_changed hooks (called from 'oak init')."""
        return self._trigger_hook(
            "on_ides_changed",
            ides_added=ides_added,
            ides_removed=ides_removed,
        )

    def trigger_pre_upgrade_hooks(self, plan: dict[str, Any]) -> dict[str, Any]:
        """Trigger on_pre_upgrade hooks before 'oak upgrade' applies changes."""
        return self._trigger_hook("on_pre_upgrade", plan=plan)

    def trigger_post_upgrade_hooks(self, results: dict[str, Any]) -> dict[str, Any]:
        """Trigger on_post_upgrade hooks after 'oak upgrade' completes."""
        return self._trigger_hook("on_post_upgrade", results=results)

    def trigger_pre_remove_hooks(self) -> dict[str, Any]:
        """Trigger on_pre_remove hooks before 'oak remove' starts."""
        return self._trigger_hook("on_pre_remove")

    def trigger_feature_enabled_hook(self, feature_name: str) -> dict[str, Any]:
        """Trigger on_feature_enabled hook for a newly enabled feature."""
        return self._trigger_hook(
            "on_feature_enabled",
            features=[feature_name],
            feature_name=feature_name,
        )

    def trigger_feature_disabled_hook(self, feature_name: str) -> dict[str, Any]:
        """Trigger on_feature_disabled hook before a feature is removed."""
        config = self.config_service.load_config()
        return self._trigger_hook(
            "on_feature_disabled",
            features=[feature_name],
            feature_name=feature_name,
            agents=config.agents,
        )

    def trigger_init_complete_hooks(
        self, is_fresh_install: bool, agents: list[str], features: list[str]
    ) -> dict[str, Any]:
        """Trigger on_init_complete hooks after 'oak init' finishes."""
        return self._trigger_hook(
            "on_init_complete",
            is_fresh_install=is_fresh_install,
            agents=agents,
            features=features,
        )
