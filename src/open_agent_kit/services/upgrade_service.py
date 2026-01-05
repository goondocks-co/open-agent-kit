"""Upgrade service for updating templates and commands."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict, cast

if TYPE_CHECKING:
    from open_agent_kit.services.skill_service import SkillService

from open_agent_kit.config.paths import FEATURES_DIR, OAK_DIR
from open_agent_kit.constants import FEATURE_CONFIG, SUPPORTED_FEATURES
from open_agent_kit.services.agent_service import AgentService
from open_agent_kit.services.config_service import ConfigService
from open_agent_kit.services.ide_settings_service import IDESettingsService
from open_agent_kit.services.migrations import run_migrations
from open_agent_kit.services.template_service import TemplateService
from open_agent_kit.utils import (
    dir_exists,
    ensure_dir,
    read_file,
    write_file,
)

# Regex pattern to detect Jinja2 template syntax
JINJA2_PATTERN = re.compile(r"\{\{|\{%")


class UpgradeCategoryResults(TypedDict):
    upgraded: list[str]
    failed: list[str]


class UpgradeResults(TypedDict):
    commands: UpgradeCategoryResults
    templates: UpgradeCategoryResults
    ide_settings: UpgradeCategoryResults
    migrations: UpgradeCategoryResults
    obsolete_removed: UpgradeCategoryResults
    skills: UpgradeCategoryResults
    structural_repairs: list[str]
    version_updated: bool


class UpgradePlanCommand(TypedDict):
    """A single command upgrade plan item."""

    agent: str
    command: str
    file: str
    package_path: Path
    installed_path: Path


class UpgradePlanMigration(TypedDict):
    """A single migration plan item."""

    id: str
    description: str


class UpgradePlanSkillItem(TypedDict):
    """A single skill plan item."""

    skill: str
    feature: str


class UpgradePlanSkills(TypedDict):
    """Skills upgrade plan."""

    install: list[UpgradePlanSkillItem]
    upgrade: list[UpgradePlanSkillItem]


class UpgradePlan(TypedDict):
    """Structure returned by plan_upgrade()."""

    commands: list[UpgradePlanCommand]
    templates: list[str]
    templates_customized: bool
    obsolete_templates: list[str]
    ide_settings: list[str]
    skills: UpgradePlanSkills
    migrations: list[UpgradePlanMigration]
    structural_repairs: list[str]
    version_outdated: bool
    current_version: str
    package_version: str


class UpgradeService:
    """Service for upgrading open-agent-kit templates and commands."""

    def __init__(self, project_root: Path | None = None):
        """Initialize upgrade service.

        Args:
            project_root: Project root directory (defaults to current directory)
        """
        self.project_root = project_root or Path.cwd()
        self.config_service = ConfigService(project_root)
        self.agent_service = AgentService(project_root)
        self.template_service = TemplateService(project_root=project_root)
        self.ide_settings_service = IDESettingsService(project_root=project_root)

        # Package features directory (source of truth for commands)
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

        # Get agent context for rendering
        context = self.agent_service.get_agent_context(agent_type)

        # Render template with agent context
        return self.template_service.render_string(content, context)

    def is_initialized(self) -> bool:
        """Check if open-agent-kit is initialized.

        Returns:
            True if initialized, False otherwise
        """
        return dir_exists(self.project_root / OAK_DIR)

    def plan_upgrade(
        self,
        commands: bool = True,
        templates: bool = True,
        ide_settings: bool = True,
        skills: bool = True,
    ) -> UpgradePlan:
        """Plan what needs to be upgraded.

        Args:
            commands: Whether to upgrade agent commands
            templates: Whether to upgrade RFC templates
            ide_settings: Whether to upgrade IDE settings
            skills: Whether to install/upgrade skills

        Returns:
            UpgradePlan with upgrade details
        """
        from open_agent_kit.constants import VERSION
        from open_agent_kit.services.migrations import get_migrations

        # Check config version
        config = self.config_service.load_config()
        current_version = config.version
        version_outdated = current_version != VERSION

        plan: UpgradePlan = {
            "commands": [],
            "templates": [],
            "templates_customized": False,
            "obsolete_templates": [],
            "ide_settings": [],
            "skills": {"install": [], "upgrade": []},
            "migrations": [],
            "structural_repairs": [],
            "version_outdated": version_outdated,
            "current_version": current_version,
            "package_version": VERSION,
        }

        # Check for structural issues (missing feature directories, old structure)
        plan["structural_repairs"] = self._get_structural_repairs()

        # Plan agent command upgrades
        if commands:
            configured_agents = self.config_service.get_agents()
            for agent in configured_agents:
                agent_commands = self._get_upgradeable_commands(agent)
                plan["commands"].extend(agent_commands)

        # Templates are read directly from the package - no project copies to upgrade
        # These fields are kept for backward compatibility with the plan structure
        plan["templates"] = []
        plan["templates_customized"] = False
        plan["obsolete_templates"] = []

        # Plan IDE settings upgrades (only for configured IDEs)
        if ide_settings:
            configured_ides = self.config_service.get_ides()
            upgradeable_ide_settings = []
            for ide in configured_ides:
                if self.ide_settings_service.needs_upgrade(ide):
                    upgradeable_ide_settings.append(ide)
            plan["ide_settings"] = upgradeable_ide_settings

        # Plan skill installations and upgrades
        if skills:
            skill_plan = self._get_upgradeable_skills()
            plan["skills"] = skill_plan

        # Plan migrations (one-time upgrade tasks)
        completed_migrations = set(self.config_service.get_completed_migrations())
        all_migrations = get_migrations()
        for migration_id, description, _ in all_migrations:
            if migration_id not in completed_migrations:
                plan["migrations"].append({"id": migration_id, "description": description})

        return plan

    def execute_upgrade(self, plan: UpgradePlan) -> UpgradeResults:
        """Execute the upgrade plan.

        Updates config version to current package version after successful upgrades.
        Runs any pending migrations as part of the upgrade process.

        Args:
            plan: Upgrade plan from plan_upgrade()

        Returns:
            UpgradeResults with upgrade outcomes
        """
        results: UpgradeResults = {
            "commands": {"upgraded": [], "failed": []},
            "templates": {"upgraded": [], "failed": []},
            "ide_settings": {"upgraded": [], "failed": []},
            "migrations": {"upgraded": [], "failed": []},
            "obsolete_removed": {"upgraded": [], "failed": []},
            "skills": {"upgraded": [], "failed": []},
            "structural_repairs": [],
            "version_updated": False,
        }

        # Repair structural issues first (missing dirs, old structure)
        if plan.get("structural_repairs"):
            results["structural_repairs"] = self._repair_structure()

        # Upgrade agent commands
        for cmd in plan["commands"]:
            try:
                self._upgrade_agent_command(cmd)
                results["commands"]["upgraded"].append(cmd["file"])
            except Exception as e:
                results["commands"]["failed"].append(f"{cmd['file']}: {e}")

        # Note: Template upgrades are no longer needed - templates are read from package

        # Upgrade IDE settings
        for ide in plan["ide_settings"]:
            try:
                self._upgrade_ide_settings(ide)
                results["ide_settings"]["upgraded"].append(ide)
            except Exception as e:
                results["ide_settings"]["failed"].append(f"{ide}: {e}")

        # Install and upgrade skills
        skill_plan = plan["skills"]
        for skill_info in skill_plan["install"]:
            try:
                self._install_skill(skill_info["skill"], skill_info["feature"])
                results["skills"]["upgraded"].append(skill_info["skill"])
            except Exception as e:
                results["skills"]["failed"].append(f"{skill_info['skill']}: {e}")

        for skill_info in skill_plan["upgrade"]:
            try:
                self._upgrade_skill(skill_info["skill"])
                results["skills"]["upgraded"].append(skill_info["skill"])
            except Exception as e:
                results["skills"]["failed"].append(f"{skill_info['skill']}: {e}")

        # Run migrations (one-time upgrade tasks)
        completed_migrations = set(self.config_service.get_completed_migrations())
        successful_migrations, failed_migrations = run_migrations(
            self.project_root, completed_migrations
        )

        # Track successful migrations
        if successful_migrations:
            self.config_service.add_completed_migrations(successful_migrations)
            results["migrations"]["upgraded"] = successful_migrations

        # Track failed migrations
        if failed_migrations:
            results["migrations"]["failed"] = [
                f"{migration_id}: {error}" for migration_id, error in failed_migrations
            ]

        # Update config version if any upgrades were successful OR if version is outdated
        total_upgraded = (
            len(results["commands"]["upgraded"])
            + len(results["templates"]["upgraded"])
            + len(results["obsolete_removed"]["upgraded"])
            + len(results["ide_settings"]["upgraded"])
            + len(results["skills"]["upgraded"])
            + len(results["migrations"]["upgraded"])
            + len(results["structural_repairs"])
        )
        version_outdated = plan.get("version_outdated", False)

        if total_upgraded > 0 or version_outdated:
            try:
                from open_agent_kit.constants import VERSION

                self.config_service.update_config(version=VERSION)
                results["version_updated"] = True
            except Exception:
                # Don't fail the whole upgrade if version update fails
                pass

        return results

    def _get_upgradeable_commands(self, agent: str) -> list[UpgradePlanCommand]:
        """Get agent commands that can be upgraded.

        Args:
            agent: Agent type name

        Returns:
            List of command dictionaries with upgrade info
        """
        upgradeable: list[UpgradePlanCommand] = []

        # Get agent's commands directory
        try:
            commands_dir = self.agent_service.get_agent_commands_dir(agent)
        except ValueError:
            return []

        # Get enabled features from config
        config = self.config_service.load_config()
        enabled_features = (
            config.features.enabled if config.features.enabled else SUPPORTED_FEATURES
        )

        # Check each enabled feature's commands
        for feature_name in enabled_features:
            feature_config = FEATURE_CONFIG.get(feature_name, {})
            command_names = cast(list[str], feature_config.get("commands", []))
            feature_commands_dir = self.package_features_dir / feature_name / "commands"

            if not feature_commands_dir.exists():
                continue

            for command_name in command_names:
                package_template = feature_commands_dir / f"oak.{command_name}.md"
                if not package_template.exists():
                    continue

                # Get installed command file
                filename = self.agent_service.get_command_filename(agent, command_name)
                installed_file = commands_dir / filename

                # Check if needs upgrade (file exists and content differs) OR is new
                if installed_file.exists():
                    # Compare rendered package template with installed file
                    # (installed files are rendered during init, so we must render
                    # the package template before comparing to avoid false positives)
                    needs_upgrade = self._command_needs_upgrade(
                        package_template, installed_file, agent
                    )
                    if needs_upgrade:
                        upgradeable.append(
                            {
                                "agent": agent,
                                "command": command_name,
                                "file": filename,
                                "package_path": package_template,
                                "installed_path": installed_file,
                            }
                        )
                else:
                    # New command that doesn't exist in project yet
                    upgradeable.append(
                        {
                            "agent": agent,
                            "command": command_name,
                            "file": filename,
                            "package_path": package_template,
                            "installed_path": installed_file,
                        }
                    )

        return upgradeable

    def _get_upgradeable_skills(self) -> UpgradePlanSkills:
        """Get skills that need to be installed or upgraded.

        Checks all enabled features for skills that:
        - Are not installed yet (need installation)
        - Are installed but differ from package version (need upgrade)

        Returns:
            UpgradePlanSkills with install and upgrade lists
        """
        from open_agent_kit.services.skill_service import SkillService

        result: UpgradePlanSkills = {"install": [], "upgrade": []}

        # Check if any agent supports skills
        skill_service = SkillService(self.project_root)
        if not skill_service._has_skills_capable_agent():
            return result

        # Get enabled features
        config = self.config_service.load_config()
        enabled_features = (
            config.features.enabled if config.features.enabled else SUPPORTED_FEATURES
        )

        # Get currently installed skills
        installed_skills = set(skill_service.list_installed_skills())

        # Check each enabled feature for skills
        for feature_name in enabled_features:
            feature_skills = skill_service.get_skills_for_feature(feature_name)

            for skill_name in feature_skills:
                if skill_name not in installed_skills:
                    # Skill needs installation
                    result["install"].append(
                        {
                            "skill": skill_name,
                            "feature": feature_name,
                        }
                    )
                else:
                    # Check if skill needs upgrade (content differs)
                    if self._skill_needs_upgrade(skill_service, skill_name):
                        result["upgrade"].append(
                            {
                                "skill": skill_name,
                                "feature": feature_name,
                            }
                        )

        return result

    def _skill_needs_upgrade(self, skill_service: SkillService, skill_name: str) -> bool:
        """Check if an installed skill differs from the package version.

        Args:
            skill_service: SkillService instance
            skill_name: Name of the skill

        Returns:
            True if skill content differs from package version
        """
        from open_agent_kit.models.skill import SkillManifest

        # Get package manifest
        package_manifest = skill_service.get_skill_manifest(skill_name)
        if not package_manifest:
            return False

        # Get installed manifest from first agent with skills support
        agents_with_skills = skill_service._get_agents_with_skills_support()
        if not agents_with_skills:
            return False

        _, skills_dir, _ = agents_with_skills[0]
        installed_skill_file = skills_dir / skill_name / "SKILL.md"

        if not installed_skill_file.exists():
            return False

        try:
            installed_manifest = SkillManifest.load(installed_skill_file)
            # Compare serialized content
            return package_manifest.to_skill_file() != installed_manifest.to_skill_file()
        except (FileNotFoundError, ValueError):
            return False

    def _upgrade_agent_command(self, cmd: UpgradePlanCommand) -> None:
        """Upgrade a single agent command.

        Args:
            cmd: Command dictionary from _get_upgradeable_commands()
        """
        package_path = cmd["package_path"]
        installed_path = cmd["installed_path"]
        agent_type = cmd["agent"]

        # Read package template
        content = read_file(package_path)

        # Render with agent-specific context (same as during init)
        rendered_content = self._render_command_for_agent(content, agent_type)

        # Ensure directory exists
        ensure_dir(installed_path.parent)

        # Write rendered content to installed location
        write_file(installed_path, rendered_content)

    def _upgrade_ide_settings(self, ide: str) -> None:
        """Upgrade IDE settings.

        Args:
            ide: IDE name (e.g., "vscode", "cursor")
        """
        # Use the IDE settings service to install/merge settings
        self.ide_settings_service.install_settings(ide, force=False)

    def _install_skill(self, skill_name: str, feature_name: str) -> None:
        """Install a skill for a feature.

        Args:
            skill_name: Name of the skill to install
            feature_name: Name of the feature the skill belongs to
        """
        from open_agent_kit.services.skill_service import SkillService

        skill_service = SkillService(self.project_root)
        result = skill_service.install_skill(skill_name, feature_name)

        if "error" in result:
            raise ValueError(result["error"])

    def _upgrade_skill(self, skill_name: str) -> None:
        """Upgrade a skill to the latest package version.

        Args:
            skill_name: Name of the skill to upgrade
        """
        from open_agent_kit.services.skill_service import SkillService

        skill_service = SkillService(self.project_root)
        result = skill_service.upgrade_skill(skill_name)

        if "error" in result:
            raise ValueError(result["error"])

    def _files_differ(self, file1: Path, file2: Path) -> bool:
        """Check if two files have different content.

        Args:
            file1: First file path
            file2: Second file path

        Returns:
            True if files differ, False if identical
        """
        try:
            content1 = read_file(file1)
            content2 = read_file(file2)
            return content1 != content2
        except Exception:
            return False

    def _command_needs_upgrade(
        self, package_path: Path, installed_path: Path, agent_type: str
    ) -> bool:
        """Check if a command needs upgrading by comparing rendered content.

        Unlike _files_differ(), this method renders the package template with
        agent-specific context before comparing, since installed files are
        rendered during init.

        Args:
            package_path: Path to package template file
            installed_path: Path to installed command file
            agent_type: Agent type for rendering context

        Returns:
            True if command needs upgrade (rendered content differs)
        """
        try:
            # Read package template and render with agent context
            package_content = read_file(package_path)
            rendered_package = self._render_command_for_agent(package_content, agent_type)

            # Read installed file (already rendered)
            installed_content = read_file(installed_path)

            return rendered_package != installed_content
        except Exception:
            return False

    def _get_structural_repairs(self) -> list[str]:
        """Check for structural issues that need repair.

        Note: .oak/features/ is no longer used - feature assets are read from the package.
        This method now only checks for old structures that should be cleaned up.

        Returns:
            List of repair descriptions
        """
        repairs = []

        # Check for old .oak/features/ structure that needs cleanup
        features_dir = self.project_root / ".oak" / "features"
        if features_dir.exists():
            repairs.append(
                "Remove obsolete .oak/features/ directory (assets now read from package)"
            )

        # Check for old structure that needs cleanup
        old_templates_dir = self.project_root / ".oak" / "templates"
        if old_templates_dir.exists():
            for subdir in ["constitution", "rfc", "commands", "ide"]:
                if (old_templates_dir / subdir).exists():
                    repairs.append(f"Remove old .oak/templates/{subdir}/ directory")
                    break  # Only report once

        return repairs

    def _repair_structure(self) -> list[str]:
        """Repair structural issues in the installation.

        Note: .oak/features/ is no longer used - feature assets are read from the package.
        This method now removes obsolete structures.

        Returns:
            List of repairs performed
        """
        import shutil

        repaired = []

        # Remove obsolete .oak/features/ directory (assets now read from package)
        features_dir = self.project_root / ".oak" / "features"
        if features_dir.exists():
            try:
                shutil.rmtree(features_dir)
                repaired.append("Removed obsolete .oak/features/ directory")
            except Exception:
                pass

        # Clean up old .oak/templates/ structure
        old_templates_dir = self.project_root / ".oak" / "templates"
        if old_templates_dir.exists():
            for subdir in ["constitution", "rfc", "commands", "ide"]:
                old_subdir = old_templates_dir / subdir
                if old_subdir.exists():
                    try:
                        shutil.rmtree(old_subdir)
                        repaired.append(f"Removed old .oak/templates/{subdir}/")
                    except Exception:
                        pass

            # Remove templates dir if empty
            try:
                if old_templates_dir.exists() and not any(old_templates_dir.iterdir()):
                    old_templates_dir.rmdir()
                    repaired.append("Removed empty .oak/templates/")
            except Exception:
                pass

        return repaired


def get_upgrade_service(project_root: Path | None = None) -> UpgradeService:
    """Get an UpgradeService instance.

    Args:
        project_root: Project root directory (defaults to current directory)

    Returns:
        UpgradeService instance
    """
    return UpgradeService(project_root)
