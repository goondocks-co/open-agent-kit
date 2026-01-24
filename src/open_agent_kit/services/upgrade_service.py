"""Upgrade service for updating templates and commands."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict, cast

import jinja2

if TYPE_CHECKING:
    from open_agent_kit.services.skill_service import SkillService

from open_agent_kit.config.paths import FEATURES_DIR, OAK_DIR
from open_agent_kit.constants import FEATURE_CONFIG, SUPPORTED_FEATURES
from open_agent_kit.services.agent_service import AgentService
from open_agent_kit.services.agent_settings_service import AgentSettingsService
from open_agent_kit.services.config_service import ConfigService
from open_agent_kit.services.migrations import run_migrations
from open_agent_kit.services.template_service import TemplateService
from open_agent_kit.utils import (
    add_gitignore_entries,
    dir_exists,
    ensure_dir,
    read_file,
    write_file,
)

logger = logging.getLogger(__name__)


def _feature_name_to_dir(feature_name: str) -> str:
    """Convert feature name to directory name (hyphens to underscores).

    Feature names use hyphens (codebase-intelligence) but Python packages
    use underscores (codebase_intelligence).

    Args:
        feature_name: Feature name with hyphens

    Returns:
        Directory name with underscores
    """
    return feature_name.replace("-", "_")


class UpgradeCategoryResults(TypedDict):
    upgraded: list[str]
    failed: list[str]


class UpgradeResults(TypedDict):
    commands: UpgradeCategoryResults
    templates: UpgradeCategoryResults
    agent_settings: UpgradeCategoryResults
    migrations: UpgradeCategoryResults
    obsolete_removed: UpgradeCategoryResults
    legacy_commands_removed: UpgradeCategoryResults
    skills: UpgradeCategoryResults
    hooks: UpgradeCategoryResults
    mcp_servers: UpgradeCategoryResults
    gitignore: UpgradeCategoryResults
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


class UpgradePlanObsoleteSkill(TypedDict):
    """An obsolete skill to be removed."""

    skill: str
    reason: str


class UpgradePlanSkills(TypedDict):
    """Skills upgrade plan."""

    install: list[UpgradePlanSkillItem]
    upgrade: list[UpgradePlanSkillItem]
    obsolete: list[UpgradePlanObsoleteSkill]


class UpgradePlanGitignoreItem(TypedDict):
    """A single gitignore entry to add."""

    feature: str
    entry: str


class UpgradePlanHookItem(TypedDict):
    """A single hook upgrade plan item."""

    feature: str
    agent: str
    source_path: Path
    target_description: str


class UpgradePlanMcpItem(TypedDict):
    """A single MCP server plan item."""

    agent: str
    feature: str


class UpgradePlanLegacyCommandItem(TypedDict):
    """A command file to remove for a skills-capable agent."""

    file: str
    path: Path


class UpgradePlanLegacyCommandsCleanup(TypedDict):
    """Legacy commands cleanup for a skills-capable agent."""

    agent: str
    commands: list[UpgradePlanLegacyCommandItem]


class UpgradePlan(TypedDict):
    """Structure returned by plan_upgrade()."""

    commands: list[UpgradePlanCommand]
    templates: list[str]
    templates_customized: bool
    obsolete_templates: list[str]
    agent_settings: list[str]
    skills: UpgradePlanSkills
    hooks: list[UpgradePlanHookItem]
    mcp_servers: list[UpgradePlanMcpItem]
    gitignore: list[UpgradePlanGitignoreItem]
    migrations: list[UpgradePlanMigration]
    structural_repairs: list[str]
    legacy_commands_cleanup: list[UpgradePlanLegacyCommandsCleanup]
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
        self.agent_settings_service = AgentSettingsService(project_root=project_root)

        # Package features directory (source of truth for commands)
        # Path: services/upgrade_service.py -> services/ -> open_agent_kit/
        self.package_features_dir = Path(__file__).parent.parent / FEATURES_DIR

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
        agent_settings: bool = True,
        skills: bool = True,
    ) -> UpgradePlan:
        """Plan what needs to be upgraded.

        Args:
            commands: Whether to upgrade agent commands
            templates: Whether to upgrade RFC templates (deprecated - read from package)
            agent_settings: Whether to upgrade agent auto-approval settings
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
            "agent_settings": [],
            "skills": {"install": [], "upgrade": [], "obsolete": []},
            "hooks": [],
            "mcp_servers": [],
            "gitignore": [],
            "migrations": [],
            "structural_repairs": [],
            "legacy_commands_cleanup": [],
            "version_outdated": version_outdated,
            "current_version": current_version,
            "package_version": VERSION,
        }

        # Check for structural issues (missing feature directories, old structure)
        plan["structural_repairs"] = self._get_structural_repairs()

        # Plan legacy command cleanup for skills-capable agents
        # This must run before command upgrades to remove obsolete commands
        plan["legacy_commands_cleanup"] = self._get_legacy_commands_for_cleanup()

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

        # Plan agent settings upgrades (only for configured agents with auto-approval enabled)
        if agent_settings:
            configured_agents = self.config_service.get_agents()
            plan["agent_settings"] = self.agent_settings_service.get_upgradeable_agents(
                configured_agents
            )

        # Plan skill installations and upgrades
        if skills:
            skill_plan = self._get_upgradeable_skills()
            plan["skills"] = skill_plan

        # Plan feature hook upgrades (for installed features with hooks)
        plan["hooks"] = self._get_upgradeable_hooks()

        # Plan MCP server installations (for features that provide MCP servers)
        plan["mcp_servers"] = self._get_mcp_servers_to_install()

        # Plan gitignore entries (ensure all declared entries are present)
        plan["gitignore"] = self._get_missing_gitignore_entries()

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
            "agent_settings": {"upgraded": [], "failed": []},
            "migrations": {"upgraded": [], "failed": []},
            "obsolete_removed": {"upgraded": [], "failed": []},
            "legacy_commands_removed": {"upgraded": [], "failed": []},
            "skills": {"upgraded": [], "failed": []},
            "hooks": {"upgraded": [], "failed": []},
            "mcp_servers": {"upgraded": [], "failed": []},
            "gitignore": {"upgraded": [], "failed": []},
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

        # Upgrade agent auto-approval settings
        for agent in plan.get("agent_settings", []):
            try:
                self._upgrade_agent_settings(agent)
                results["agent_settings"]["upgraded"].append(agent)
            except Exception as e:
                results["agent_settings"]["failed"].append(f"{agent}: {e}")

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

        # Add missing gitignore entries (grouped by feature for cleaner output)
        gitignore_plan = plan.get("gitignore", [])
        if gitignore_plan:
            # Group entries by feature
            entries_by_feature: dict[str, list[str]] = {}
            for item in gitignore_plan:
                feature = item["feature"]
                if feature not in entries_by_feature:
                    entries_by_feature[feature] = []
                entries_by_feature[feature].append(item["entry"])

            # Add entries for each feature
            for feature_name, entries in entries_by_feature.items():
                try:
                    # Get feature display name for comment
                    from open_agent_kit.models.feature import FeatureManifest

                    manifest_path = (
                        self.package_features_dir
                        / _feature_name_to_dir(feature_name)
                        / "manifest.yaml"
                    )
                    display_name = feature_name
                    if manifest_path.exists():
                        try:
                            manifest = FeatureManifest.load(manifest_path)
                            display_name = manifest.display_name
                        except (ValueError, OSError) as e:
                            logger.warning(f"Failed to load feature manifest {manifest_path}: {e}")

                    added = add_gitignore_entries(
                        self.project_root,
                        entries,
                        section_comment=f"open-agent-kit: {display_name}",
                    )
                    if added:
                        for entry in added:
                            results["gitignore"]["upgraded"].append(f"{feature_name}: {entry}")
                except Exception as e:
                    for entry in entries:
                        results["gitignore"]["failed"].append(f"{feature_name}: {entry}: {e}")

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
            + len(results["agent_settings"]["upgraded"])
            + len(results["skills"]["upgraded"])
            + len(results["gitignore"]["upgraded"])
            + len(results["migrations"]["upgraded"])
            + len(results["structural_repairs"])
        )
        version_outdated = plan.get("version_outdated", False)

        if total_upgraded > 0 or version_outdated:
            try:
                from open_agent_kit.constants import VERSION

                self.config_service.update_config(version=VERSION)
                results["version_updated"] = True
            except (OSError, ValueError) as e:
                # Don't fail the whole upgrade if version update fails
                logger.warning(f"Failed to update config version: {e}")

        return results

    def _get_upgradeable_commands(self, agent: str) -> list[UpgradePlanCommand]:
        """Get agent commands that can be upgraded.

        Commands are sub-agents (specialized expertise) installed for all agents.
        They are separate from skills (domain knowledge for workflows).

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
            feature_commands_dir = (
                self.package_features_dir / _feature_name_to_dir(feature_name) / "commands"
            )

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

    def _get_legacy_commands_for_cleanup(self) -> list[UpgradePlanLegacyCommandsCleanup]:
        """Get legacy commands that should be removed during upgrade.

        Removes ALL oak.* commands that don't match current valid commands
        from FEATURE_CONFIG. This cleans up commands that were removed or
        renamed in feature updates.

        Returns:
            List of legacy command cleanup items, one per agent with commands to remove
        """
        cleanup: list[UpgradePlanLegacyCommandsCleanup] = []
        configured_agents = self.config_service.get_agents()

        # Get all valid command names from current feature config
        valid_commands: set[str] = set()
        for feature_config in FEATURE_CONFIG.values():
            valid_commands.update(cast(list[str], feature_config.get("commands", [])))

        for agent in configured_agents:
            # Get existing commands for this agent
            try:
                commands_dir = self.agent_service.get_agent_commands_dir(agent)
                if not commands_dir.exists():
                    continue
            except ValueError:
                continue

            # Find oak.* command files that don't match any current valid command
            commands_to_remove: list[UpgradePlanLegacyCommandItem] = []
            for cmd_file in commands_dir.iterdir():
                if cmd_file.is_file() and cmd_file.name.startswith("oak."):
                    # Extract command name from filename (e.g., oak.create-rfc.md -> create-rfc)
                    filename = cmd_file.name
                    if filename.endswith(".agent.md"):
                        command_name = filename[4:-9]  # Remove "oak." and ".agent.md"
                    elif filename.endswith(".md"):
                        command_name = filename[4:-3]  # Remove "oak." and ".md"
                    else:
                        continue

                    # Mark as legacy if not in current valid commands
                    if command_name not in valid_commands:
                        commands_to_remove.append(
                            {
                                "file": cmd_file.name,
                                "path": cmd_file,
                            }
                        )

            if commands_to_remove:
                cleanup.append(
                    {
                        "agent": agent,
                        "commands": commands_to_remove,
                    }
                )

        return cleanup

    def _remove_legacy_command(self, agent: str, filename: str) -> bool:
        """Remove a legacy command file for a skills-capable agent.

        Args:
            agent: Agent type name
            filename: Command filename to remove (e.g., "oak.rfc-create.md")

        Returns:
            True if removed successfully, False otherwise
        """
        try:
            commands_dir = self.agent_service.get_agent_commands_dir(agent)
            cmd_path = commands_dir / filename
            if cmd_path.exists():
                cmd_path.unlink()
                logger.debug(f"Removed legacy command {filename} for {agent}")
                return True
        except Exception as e:
            logger.warning(f"Failed to remove legacy command {filename} for {agent}: {e}")
        return False

    def _get_missing_gitignore_entries(self) -> list[UpgradePlanGitignoreItem]:
        """Get gitignore entries declared by features that are missing from .gitignore.

        Checks all enabled features for gitignore patterns that should be present
        but aren't. This ensures features added in upgrades have their gitignore
        entries applied.

        Returns:
            List of missing gitignore entries with their source feature
        """
        from open_agent_kit.models.feature import FeatureManifest

        missing: list[UpgradePlanGitignoreItem] = []

        # Read current .gitignore patterns
        gitignore_path = self.project_root / ".gitignore"
        existing_patterns: set[str] = set()

        if gitignore_path.exists():
            try:
                content = gitignore_path.read_text()
                for line in content.splitlines():
                    stripped = line.strip()
                    if stripped and not stripped.startswith("#"):
                        existing_patterns.add(stripped)
            except OSError:
                pass

        # Get enabled features
        config = self.config_service.load_config()
        enabled_features = (
            config.features.enabled if config.features.enabled else SUPPORTED_FEATURES
        )

        # Check each feature's declared gitignore entries
        for feature_name in enabled_features:
            manifest_path = (
                self.package_features_dir / _feature_name_to_dir(feature_name) / "manifest.yaml"
            )
            if not manifest_path.exists():
                continue

            try:
                manifest = FeatureManifest.load(manifest_path)
                for entry in manifest.gitignore:
                    if entry.strip() not in existing_patterns:
                        missing.append(
                            {
                                "feature": feature_name,
                                "entry": entry.strip(),
                            }
                        )
            except (ValueError, OSError) as e:
                logger.warning(f"Failed to load feature manifest {feature_name}: {e}")
                continue

        return missing

    def _get_upgradeable_skills(self) -> UpgradePlanSkills:
        """Get skills that need to be installed, upgraded, or removed.

        Checks all enabled features for skills that:
        - Are not installed yet (need installation)
        - Are installed but differ from package version (need upgrade)
        - Are installed but no longer exist in any feature (obsolete, need removal)

        Returns:
            UpgradePlanSkills with install, upgrade, and obsolete lists
        """
        from open_agent_kit.services.skill_service import SkillService

        result: UpgradePlanSkills = {"install": [], "upgrade": [], "obsolete": []}

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

        # Build set of all valid skills from enabled features
        all_valid_skills: set[str] = set()
        for feature_name in enabled_features:
            feature_skills = skill_service.get_skills_for_feature(feature_name)
            all_valid_skills.update(feature_skills)

        # Check each enabled feature for skills to install/upgrade
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

        # Find obsolete skills (installed but no longer in any feature)
        for skill_name in installed_skills:
            if skill_name not in all_valid_skills:
                result["obsolete"].append(
                    {
                        "skill": skill_name,
                        "reason": "No longer exists in any enabled feature",
                    }
                )

        return result

    def _skill_needs_upgrade(self, skill_service: SkillService, skill_name: str) -> bool:
        """Check if an installed skill differs from the package version.

        Compares the entire skill directory, not just SKILL.md, to detect changes
        in subdirectories like references/, scripts/, etc.

        Args:
            skill_service: SkillService instance
            skill_name: Name of the skill

        Returns:
            True if skill content differs from package version
        """
        # Get package skill directory
        package_skill_dir = skill_service._find_skill_dir_in_features(skill_name)
        if not package_skill_dir:
            return False

        # Get installed skill directory from first agent with skills support
        agents_with_skills = skill_service._get_agents_with_skills_support()
        if not agents_with_skills:
            return False

        _, skills_dir, _ = agents_with_skills[0]
        installed_skill_dir = skills_dir / skill_name

        if not installed_skill_dir.exists():
            return False

        # Compare directory contents
        return self._skill_dirs_differ(package_skill_dir, installed_skill_dir)

    def _skill_dirs_differ(self, package_dir: Path, installed_dir: Path) -> bool:
        """Check if two skill directories have different content.

        Compares all files in both directories recursively.

        Args:
            package_dir: Package skill directory
            installed_dir: Installed skill directory

        Returns:
            True if directories differ
        """
        # Get all files in package directory (relative paths)
        package_files = {
            f.relative_to(package_dir): f for f in package_dir.rglob("*") if f.is_file()
        }
        installed_files = {
            f.relative_to(installed_dir): f for f in installed_dir.rglob("*") if f.is_file()
        }

        # Check if file sets differ
        if set(package_files.keys()) != set(installed_files.keys()):
            return True

        # Compare file contents
        for rel_path in package_files:
            package_file = package_files[rel_path]
            installed_file = installed_files[rel_path]
            if self._files_differ(package_file, installed_file):
                return True

        return False

    def _get_upgradeable_hooks(self) -> list[UpgradePlanHookItem]:
        """Get feature hooks that need to be upgraded.

        Checks all enabled features for hooks that need updating.
        Currently supports codebase-intelligence feature hooks.

        Returns:
            List of UpgradePlanHookItem for hooks that need upgrade
        """
        result: list[UpgradePlanHookItem] = []

        # Get enabled features and configured agents
        config = self.config_service.load_config()
        enabled_features = (
            config.features.enabled if config.features.enabled else SUPPORTED_FEATURES
        )
        configured_agents = config.agents

        # Check each enabled feature for hooks
        for feature_name in enabled_features:
            feature_hooks_dir = (
                self.package_features_dir / _feature_name_to_dir(feature_name) / "hooks"
            )
            if not feature_hooks_dir.exists():
                continue

            # Check each configured agent for hook updates
            for agent in configured_agents:
                agent_hook_template = feature_hooks_dir / agent / "hooks.json"
                if not agent_hook_template.exists():
                    continue

                # Check if hook needs upgrade
                if self._hook_needs_upgrade(feature_name, agent, agent_hook_template):
                    # Determine target description based on agent
                    if agent == "claude":
                        target_desc = ".claude/settings.json"
                    elif agent == "cursor":
                        target_desc = ".cursor/hooks.json"
                    elif agent == "gemini":
                        target_desc = ".gemini/settings.json"
                    else:
                        target_desc = f".{agent}/hooks"

                    result.append(
                        {
                            "feature": feature_name,
                            "agent": agent,
                            "source_path": agent_hook_template,
                            "target_description": target_desc,
                        }
                    )

        return result

    def _hook_needs_upgrade(self, feature_name: str, agent: str, source_template: Path) -> bool:
        """Check if a feature's agent hook needs to be upgraded.

        Compares the package hook template with what's currently installed.

        Args:
            feature_name: Name of the feature
            agent: Agent name (claude, cursor, gemini)
            source_template: Path to the package hook template

        Returns:
            True if hook content differs from installed version
        """
        import json
        import re

        # Load source template
        try:
            source_content = source_template.read_text()
        except OSError as e:
            logger.warning(f"Failed to read source template {source_template}: {e}")
            return False

        # Get installed hooks based on agent type
        if agent == "claude":
            settings_file = self.project_root / ".claude" / "settings.json"
            if not settings_file.exists():
                return True  # Not installed yet

            try:
                with open(settings_file) as f:
                    settings = json.load(f)
                installed_hooks = settings.get("hooks", {})
            except (OSError, json.JSONDecodeError) as e:
                logger.warning(f"Failed to read settings file {settings_file}: {e}")
                return True
        elif agent == "cursor":
            hooks_file = self.project_root / ".cursor" / "hooks.json"
            if not hooks_file.exists():
                return True

            try:
                with open(hooks_file) as f:
                    installed_hooks = json.load(f).get("hooks", {})
            except (OSError, json.JSONDecodeError) as e:
                logger.warning(f"Failed to read hooks file {hooks_file}: {e}")
                return True
        elif agent == "gemini":
            settings_file = self.project_root / ".gemini" / "settings.json"
            if not settings_file.exists():
                return True

            try:
                with open(settings_file) as f:
                    settings = json.load(f)
                installed_hooks = settings.get("hooks", {})
            except (OSError, json.JSONDecodeError) as e:
                logger.warning(f"Failed to read settings file {settings_file}: {e}")
                return True
        else:
            return False

        # Parse source template (strip placeholders for comparison)
        try:
            source_hooks = json.loads(source_content).get("hooks", {})
            # Normalize by removing port-specific values and placeholders
            source_normalized = re.sub(
                r"localhost:\d+", "localhost:PORT", json.dumps(source_hooks, sort_keys=True)
            )
            installed_normalized = re.sub(
                r"localhost:\d+", "localhost:PORT", json.dumps(installed_hooks, sort_keys=True)
            )

            # Normalize the {{PORT}} placeholder
            source_normalized = source_normalized.replace("{{PORT}}", "PORT")

            # Normalize the {{PROJECT_ROOT}} placeholder vs actual project path
            # The installed hooks have the actual path, source has the placeholder
            project_root_str = str(self.project_root)
            source_normalized = source_normalized.replace("{{PROJECT_ROOT}}", "PROJECT_ROOT")
            installed_normalized = installed_normalized.replace(project_root_str, "PROJECT_ROOT")

            return source_normalized != installed_normalized
        except (json.JSONDecodeError, re.error) as e:
            logger.warning(f"Failed to compare hooks content: {e}")
            return True

    def _get_mcp_servers_to_install(self) -> list[UpgradePlanMcpItem]:
        """Get MCP servers that need to be installed.

        Checks all enabled features for MCP server configurations and identifies
        agents that support MCP (has_mcp=True in manifest).

        Currently supports codebase-intelligence feature MCP servers.

        Returns:
            List of UpgradePlanMcpItem for MCP servers to install
        """
        result: list[UpgradePlanMcpItem] = []

        # Get enabled features and configured agents
        config = self.config_service.load_config()
        enabled_features = config.features.enabled if config.features.enabled else []
        configured_agents = config.agents

        # Check each enabled feature for MCP configurations
        for feature_name in enabled_features:
            feature_mcp_dir = self.package_features_dir / _feature_name_to_dir(feature_name) / "mcp"
            if not feature_mcp_dir.exists():
                continue

            # Check each configured agent for MCP support
            for agent in configured_agents:
                # Check if agent has MCP support (has_mcp=True in manifest)
                if not self._agent_has_mcp(agent):
                    continue

                # Check if there's an install script for this agent
                agent_mcp_install = feature_mcp_dir / agent / "install.sh"
                if not agent_mcp_install.exists():
                    continue

                # Check if MCP is already configured for this agent
                if self._mcp_is_configured(agent, feature_name):
                    continue

                result.append(
                    {
                        "agent": agent,
                        "feature": feature_name,
                    }
                )

        return result

    def _agent_has_mcp(self, agent: str) -> bool:
        """Check if an agent has MCP capability.

        Args:
            agent: Agent name (e.g., "claude", "cursor")

        Returns:
            True if agent manifest has has_mcp=True
        """
        try:
            context = self.agent_service.get_agent_context(agent)
            return bool(context.get("has_mcp", False))
        except (ValueError, KeyError) as e:
            logger.warning(f"Failed to get agent context for {agent}: {e}")
            return False

    def _mcp_is_configured(self, agent: str, feature_name: str) -> bool:
        """Check if MCP server is already configured for an agent.

        Uses the agent's manifest.yaml to determine where MCP config is stored.

        Args:
            agent: Agent name (e.g., "claude", "cursor")
            feature_name: Feature providing the MCP server

        Returns:
            True if MCP server is already registered
        """
        import json

        from open_agent_kit.models.agent_manifest import AgentManifest

        # Load MCP config to get server name
        mcp_config_path = (
            self.package_features_dir / _feature_name_to_dir(feature_name) / "mcp" / "mcp.yaml"
        )
        if not mcp_config_path.exists():
            return False

        try:
            import yaml

            with open(mcp_config_path) as f:
                mcp_config = yaml.safe_load(f)
            server_name = mcp_config.get("name", "oak-ci")
        except Exception:
            return False

        # Load agent manifest to get MCP config location
        try:
            # Path: services/upgrade_service.py -> services/ -> open_agent_kit/
            agents_dir = Path(__file__).parent.parent / "agents"
            manifest = AgentManifest.load(agents_dir / agent / "manifest.yaml")
        except Exception:
            return False

        # Get config file path and servers key from manifest
        if not manifest.mcp:
            # No MCP config defined in manifest
            return False

        config_file = manifest.mcp.config_file
        servers_key = manifest.mcp.servers_key

        # Check if server is registered in the config file
        config_path = self.project_root / config_file
        if not config_path.exists():
            return False

        try:
            with open(config_path) as f:
                config = json.load(f)
            return server_name in config.get(servers_key, {})
        except Exception:
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
        rendered_content = self.template_service.render_command_for_agent(content, agent_type)

        # Ensure directory exists
        ensure_dir(installed_path.parent)

        # Write rendered content to installed location
        write_file(installed_path, rendered_content)

    def _upgrade_agent_settings(self, agent: str) -> None:
        """Upgrade agent auto-approval settings.

        Args:
            agent: Agent name (e.g., "claude", "gemini")
        """
        # Use the agent settings service to install/merge settings
        self.agent_settings_service.install_settings(agent, force=False)

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

    def _remove_obsolete_skill(self, skill_name: str) -> None:
        """Remove an obsolete skill that no longer exists in any feature.

        Args:
            skill_name: Name of the skill to remove
        """
        from open_agent_kit.services.skill_service import SkillService

        skill_service = SkillService(self.project_root)
        result = skill_service.remove_skill(skill_name)

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
        except OSError as e:
            logger.warning(f"Failed to compare files {file1} and {file2}: {e}")
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
            rendered_package = self.template_service.render_command_for_agent(
                package_content, agent_type
            )

            # Read installed file (already rendered)
            installed_content = read_file(installed_path)

            return rendered_package != installed_content
        except (OSError, jinja2.TemplateError) as e:
            logger.warning(f"Failed to check if command needs upgrade {installed_path}: {e}")
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

        # Note: Missing agent settings are handled by InstallAgentSettingsStage
        # which runs idempotently during both init and upgrade flows.
        # No special repair logic needed - declarative reconciliation handles it.

        return repairs

    def _repair_structure(self) -> list[str]:
        """Repair structural issues in the installation.

        Note: .oak/features/ is no longer used - feature assets are read from the package.
        This method now removes obsolete structures and creates missing files.

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
            except OSError as e:
                logger.warning(f"Failed to remove obsolete .oak/features/ directory: {e}")

        # Clean up old .oak/templates/ structure
        old_templates_dir = self.project_root / ".oak" / "templates"
        if old_templates_dir.exists():
            for subdir in ["constitution", "rfc", "commands", "ide"]:
                old_subdir = old_templates_dir / subdir
                if old_subdir.exists():
                    try:
                        shutil.rmtree(old_subdir)
                        repaired.append(f"Removed old .oak/templates/{subdir}/")
                    except OSError as e:
                        logger.warning(f"Failed to remove old .oak/templates/{subdir}/: {e}")

            # Remove templates dir if empty
            try:
                if old_templates_dir.exists() and not any(old_templates_dir.iterdir()):
                    old_templates_dir.rmdir()
                    repaired.append("Removed empty .oak/templates/")
            except OSError as e:
                logger.warning(f"Failed to remove empty .oak/templates/: {e}")

        # Note: Missing agent settings are handled by InstallAgentSettingsStage
        # which runs idempotently during both init and upgrade flows.
        # No special repair logic needed - declarative reconciliation handles it.

        return repaired


def get_upgrade_service(project_root: Path | None = None) -> UpgradeService:
    """Get an UpgradeService instance.

    Args:
        project_root: Project root directory (defaults to current directory)

    Returns:
        UpgradeService instance
    """
    return UpgradeService(project_root)
