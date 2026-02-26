"""Upgrade service for updating templates and commands.

Plan types and MCP helpers live in ``upgrade_plan.py`` and are re-exported
here for backward compatibility.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, cast

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
from open_agent_kit.services.upgrade_plan import (  # noqa: F401 — re-exports
    McpConfigChecker,
    UpgradeCategoryResults,
    UpgradePlan,
    UpgradePlanCommand,
    UpgradePlanGitignoreItem,
    UpgradePlanHookItem,
    UpgradePlanLegacyCommandItem,
    UpgradePlanLegacyCommandsCleanup,
    UpgradePlanMcpItem,
    UpgradePlanMigration,
    UpgradePlanNotificationItem,
    UpgradePlanObsoleteSkill,
    UpgradePlanSkillItem,
    UpgradePlanSkills,
    UpgradeResults,
    get_hook_target_description,
)
from open_agent_kit.utils import (
    add_gitignore_entries,
    dir_exists,
    ensure_dir,
    read_file,
    write_file,
)
from open_agent_kit.utils.naming import feature_name_to_dir as _feature_name_to_dir

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# UpgradePlanner — one method per upgrade category
# ---------------------------------------------------------------------------


class UpgradePlanner:
    """Builds an UpgradePlan by inspecting each upgrade category."""

    def __init__(
        self,
        project_root: Path,
        config_service: ConfigService,
        agent_service: AgentService,
        agent_settings_service: AgentSettingsService,
        template_service: TemplateService,
        package_features_dir: Path,
    ):
        self._project_root = project_root
        self._config_service = config_service
        self._agent_service = agent_service
        self._agent_settings_service = agent_settings_service
        self._template_service = template_service
        self._package_features_dir = package_features_dir
        self._mcp_checker = McpConfigChecker(project_root, agent_service)

    # -- top-level plan builder --

    def build_plan(
        self,
        commands: bool = True,
        templates: bool = True,
        agent_settings: bool = True,
        skills: bool = True,
    ) -> UpgradePlan:
        """Build a complete upgrade plan.

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

        config = self._config_service.load_config()
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
            "notifications": [],
            "mcp_servers": [],
            "gitignore": [],
            "migrations": [],
            "structural_repairs": [],
            "legacy_commands_cleanup": [],
            "version_outdated": version_outdated,
            "current_version": current_version,
            "package_version": VERSION,
        }

        plan["structural_repairs"] = self._plan_structural_repairs()
        plan["legacy_commands_cleanup"] = self._plan_legacy_commands()

        if commands:
            configured_agents = self._config_service.get_agents()
            for agent in configured_agents:
                plan["commands"].extend(self._plan_commands_for_agent(agent))

        # Templates are read directly from the package — no project copies to upgrade.
        # Fields kept for backward compatibility with consumers of the plan dict.
        plan["templates"] = []
        plan["templates_customized"] = False
        plan["obsolete_templates"] = []

        if agent_settings:
            configured_agents = self._config_service.get_agents()
            plan["agent_settings"] = self._agent_settings_service.get_upgradeable_agents(
                configured_agents
            )

        if skills:
            plan["skills"] = self._plan_skills()

        plan["hooks"] = self._plan_hooks()
        plan["notifications"] = self._plan_notifications()
        plan["mcp_servers"] = self._plan_mcp_servers()
        plan["gitignore"] = self._plan_gitignore()

        completed_migrations = set(self._config_service.get_completed_migrations())
        all_migrations = get_migrations()
        for migration_id, description, _ in all_migrations:
            if migration_id not in completed_migrations:
                plan["migrations"].append({"id": migration_id, "description": description})

        return plan

    # -- per-category planners --

    def _plan_commands_for_agent(self, agent: str) -> list[UpgradePlanCommand]:
        """Get agent commands that can be upgraded."""
        upgradeable: list[UpgradePlanCommand] = []

        try:
            commands_dir = self._agent_service.get_agent_commands_dir(agent)
        except ValueError:
            return []

        enabled_features = SUPPORTED_FEATURES

        for feature_name in enabled_features:
            if feature_name not in FEATURE_CONFIG:
                continue
            command_names = cast(list[str], FEATURE_CONFIG[feature_name]["commands"])
            feature_commands_dir = (
                self._package_features_dir / _feature_name_to_dir(feature_name) / "commands"
            )

            if not feature_commands_dir.exists():
                continue

            for command_name in command_names:
                package_template = feature_commands_dir / f"oak.{command_name}.md"
                if not package_template.exists():
                    continue

                filename = self._agent_service.get_command_filename(agent, command_name)
                installed_file = commands_dir / filename

                if installed_file.exists():
                    if self._command_needs_upgrade(package_template, installed_file, agent):
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

    def _plan_legacy_commands(self) -> list[UpgradePlanLegacyCommandsCleanup]:
        """Get legacy commands that should be removed during upgrade."""
        cleanup: list[UpgradePlanLegacyCommandsCleanup] = []
        configured_agents = self._config_service.get_agents()

        valid_commands: set[str] = set()
        for feature_config in FEATURE_CONFIG.values():
            valid_commands.update(cast(list[str], feature_config.get("commands", [])))

        for agent in configured_agents:
            try:
                commands_dir = self._agent_service.get_agent_commands_dir(agent)
                if not commands_dir.exists():
                    continue
            except ValueError:
                continue

            commands_to_remove: list[UpgradePlanLegacyCommandItem] = []
            for cmd_file in commands_dir.iterdir():
                if cmd_file.is_file() and cmd_file.name.startswith("oak."):
                    filename = cmd_file.name
                    if filename.endswith(".agent.md"):
                        command_name = filename[4:-9]
                    elif filename.endswith(".md"):
                        command_name = filename[4:-3]
                    else:
                        continue

                    if command_name not in valid_commands:
                        commands_to_remove.append({"file": cmd_file.name, "path": cmd_file})

            if commands_to_remove:
                cleanup.append({"agent": agent, "commands": commands_to_remove})

        return cleanup

    def _plan_skills(self) -> UpgradePlanSkills:
        """Get skills that need to be installed, upgraded, or removed."""
        from open_agent_kit.services.skill_service import SkillService

        result: UpgradePlanSkills = {"install": [], "upgrade": [], "obsolete": []}

        skill_service = SkillService(self._project_root)
        if not skill_service.has_skills_capable_agent():
            return result

        enabled_features = SUPPORTED_FEATURES
        installed_skills = set(skill_service.list_installed_skills())

        all_valid_skills: set[str] = set()
        for feature_name in enabled_features:
            feature_skills = skill_service.get_skills_for_feature(feature_name)
            all_valid_skills.update(feature_skills)

        for feature_name in enabled_features:
            feature_skills = skill_service.get_skills_for_feature(feature_name)
            for skill_name in feature_skills:
                if skill_name not in installed_skills:
                    result["install"].append({"skill": skill_name, "feature": feature_name})
                elif self._skill_needs_upgrade(skill_service, skill_name):
                    result["upgrade"].append({"skill": skill_name, "feature": feature_name})

        for skill_name in installed_skills:
            if skill_name not in all_valid_skills:
                result["obsolete"].append(
                    {"skill": skill_name, "reason": "No longer exists in any enabled feature"}
                )

        return result

    def _plan_hooks(self) -> list[UpgradePlanHookItem]:
        """Get feature hooks that need to be upgraded."""
        result: list[UpgradePlanHookItem] = []

        config = self._config_service.load_config()
        configured_agents = config.agents

        for agent in configured_agents:
            try:
                manifest = self._agent_service.get_agent_manifest(agent)
                if not manifest or not manifest.hooks:
                    continue

                from open_agent_kit.features.codebase_intelligence.hooks.installer import (
                    HOOKS_TEMPLATE_DIR,
                    HooksInstaller,
                )

                installer = HooksInstaller(self._project_root, agent)
                if not installer.needs_upgrade():
                    continue

                result.append(
                    {
                        "feature": "codebase-intelligence",
                        "agent": agent,
                        "source_path": HOOKS_TEMPLATE_DIR / agent / manifest.hooks.template_file,
                        "target_description": get_hook_target_description(manifest),
                    }
                )
            except Exception as e:
                logger.debug(f"Skipping hook upgrade planning for {agent}: {e}")

        return result

    def _plan_notifications(self) -> list[UpgradePlanNotificationItem]:
        """Get agent notification handlers that need to be upgraded."""
        result: list[UpgradePlanNotificationItem] = []

        config = self._config_service.load_config()
        configured_agents = config.agents

        for agent in configured_agents:
            try:
                manifest = self._agent_service.get_agent_manifest(agent)
                if not manifest or not manifest.notifications:
                    continue

                notifications_config = manifest.notifications
                if not notifications_config.notify or not notifications_config.notify.enabled:
                    continue

                from open_agent_kit.features.codebase_intelligence.notifications.installer import (
                    NotificationsInstaller,
                )

                installer = NotificationsInstaller(self._project_root, agent)
                if not installer.needs_upgrade():
                    continue

                config_file = notifications_config.config_file
                if config_file:
                    folder = manifest.installation.folder.rstrip("/")
                    target_desc = f"{folder}/{config_file}"
                else:
                    target_desc = f".{agent}/config"

                result.append(
                    {
                        "feature": "codebase-intelligence",
                        "agent": agent,
                        "target_description": target_desc,
                    }
                )
            except Exception as e:
                logger.debug(f"Skipping notification upgrade planning for {agent}: {e}")

        return result

    def _plan_mcp_servers(self) -> list[UpgradePlanMcpItem]:
        """Get MCP servers that need to be installed."""
        result: list[UpgradePlanMcpItem] = []

        config = self._config_service.load_config()
        enabled_features = SUPPORTED_FEATURES
        configured_agents = config.agents

        for feature_name in enabled_features:
            feature_mcp_config = (
                self._package_features_dir / _feature_name_to_dir(feature_name) / "mcp" / "mcp.yaml"
            )
            if not feature_mcp_config.exists():
                continue

            for agent in configured_agents:
                if not self._mcp_checker.agent_has_mcp(agent):
                    continue
                if self._mcp_checker.is_configured(agent, feature_name, self._package_features_dir):
                    continue
                result.append({"agent": agent, "feature": feature_name})

        return result

    def _plan_gitignore(self) -> list[UpgradePlanGitignoreItem]:
        """Get gitignore entries declared by features that are missing from .gitignore."""
        from open_agent_kit.models.feature import FeatureManifest

        missing: list[UpgradePlanGitignoreItem] = []

        gitignore_path = self._project_root / ".gitignore"
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

        enabled_features = SUPPORTED_FEATURES

        for feature_name in enabled_features:
            manifest_path = (
                self._package_features_dir / _feature_name_to_dir(feature_name) / "manifest.yaml"
            )
            if not manifest_path.exists():
                continue

            try:
                manifest = FeatureManifest.load(manifest_path)
                for entry in manifest.gitignore:
                    if entry.strip() not in existing_patterns:
                        missing.append({"feature": feature_name, "entry": entry.strip()})
            except (ValueError, OSError) as e:
                logger.warning(f"Failed to load feature manifest {feature_name}: {e}")
                continue

        return missing

    def _plan_structural_repairs(self) -> list[str]:
        """Check for structural issues that need repair."""
        repairs = []

        features_dir = self._project_root / ".oak" / "features"
        if features_dir.exists():
            repairs.append(
                "Remove obsolete .oak/features/ directory (assets now read from package)"
            )

        old_templates_dir = self._project_root / ".oak" / "templates"
        if old_templates_dir.exists():
            for subdir in ["constitution", "rfc", "commands", "ide"]:
                if (old_templates_dir / subdir).exists():
                    repairs.append(f"Remove old .oak/templates/{subdir}/ directory")
                    break

        return repairs

    # -- helpers used by planners --

    def _command_needs_upgrade(
        self, package_path: Path, installed_path: Path, agent_type: str
    ) -> bool:
        """Check if a command needs upgrading by comparing rendered content."""
        try:
            package_content = read_file(package_path)
            rendered_package = self._template_service.render_command_for_agent(
                package_content, agent_type
            )
            installed_content = read_file(installed_path)
            return rendered_package != installed_content
        except (OSError, jinja2.TemplateError) as e:
            logger.warning(f"Failed to check if command needs upgrade {installed_path}: {e}")
            return False

    def _skill_needs_upgrade(self, skill_service: SkillService, skill_name: str) -> bool:
        """Check if an installed skill differs from the package version."""
        package_skill_dir = skill_service.find_skill_dir_in_features(skill_name)
        if not package_skill_dir:
            return False

        unique_paths = skill_service.get_unique_skills_paths()
        if not unique_paths:
            return False

        for _, skills_dir, _ in unique_paths:
            installed_skill_dir = skills_dir / skill_name
            if not installed_skill_dir.exists():
                return True
            if skill_service.skill_dirs_differ(package_skill_dir, installed_skill_dir):
                return True

        return False


# ---------------------------------------------------------------------------
# UpgradeService — facade
# ---------------------------------------------------------------------------


class UpgradeService:
    """Service for upgrading open-agent-kit templates and commands."""

    def __init__(self, project_root: Path | None = None):
        self.project_root = project_root or Path.cwd()
        self.config_service = ConfigService(project_root)
        self.agent_service = AgentService(project_root)
        self.template_service = TemplateService(project_root=project_root)
        self.agent_settings_service = AgentSettingsService(project_root=project_root)

        # Package features directory (source of truth for commands)
        self.package_features_dir = Path(__file__).parent.parent / FEATURES_DIR

        self._planner = UpgradePlanner(
            project_root=self.project_root,
            config_service=self.config_service,
            agent_service=self.agent_service,
            agent_settings_service=self.agent_settings_service,
            template_service=self.template_service,
            package_features_dir=self.package_features_dir,
        )

    def is_initialized(self) -> bool:
        """Check if open-agent-kit is initialized."""
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
        return self._planner.build_plan(
            commands=commands,
            templates=templates,
            agent_settings=agent_settings,
            skills=skills,
        )

    def execute_upgrade(self, plan: UpgradePlan) -> UpgradeResults:
        """Execute the upgrade plan.

        Updates config version to current package version after successful upgrades.
        Runs any pending migrations as part of the upgrade process.
        """
        from open_agent_kit.services.skill_service import SkillService

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

        # Repair structural issues first
        if plan.get("structural_repairs"):
            results["structural_repairs"] = self._repair_structure()

        # Upgrade agent commands
        for cmd in plan["commands"]:
            try:
                self._upgrade_agent_command(cmd)
                results["commands"]["upgraded"].append(cmd["file"])
            except Exception as e:
                logger.debug("Command upgrade failed: %s", cmd["file"], exc_info=True)
                results["commands"]["failed"].append(f"{cmd['file']}: {e}")

        # Upgrade agent auto-approval settings
        for agent in plan.get("agent_settings", []):
            try:
                self.agent_settings_service.install_settings(agent, force=False)
                results["agent_settings"]["upgraded"].append(agent)
            except Exception as e:
                logger.debug("Agent settings upgrade failed: %s", agent, exc_info=True)
                results["agent_settings"]["failed"].append(f"{agent}: {e}")

        # Install and upgrade skills — call SkillService directly
        skill_service = SkillService(self.project_root)
        skill_plan = plan["skills"]

        for skill_info in skill_plan["install"]:
            try:
                result = skill_service.install_skill(skill_info["skill"], skill_info["feature"])
                if "error" in result:
                    raise ValueError(result["error"])
                results["skills"]["upgraded"].append(skill_info["skill"])
            except Exception as e:
                logger.debug("Skill install failed: %s", skill_info["skill"], exc_info=True)
                results["skills"]["failed"].append(f"{skill_info['skill']}: {e}")

        for skill_info in skill_plan["upgrade"]:
            try:
                upgrade_result = skill_service.upgrade_skill(skill_info["skill"])
                if "error" in upgrade_result:
                    raise ValueError(upgrade_result["error"])
                results["skills"]["upgraded"].append(skill_info["skill"])
            except Exception as e:
                logger.debug("Skill upgrade failed: %s", skill_info["skill"], exc_info=True)
                results["skills"]["failed"].append(f"{skill_info['skill']}: {e}")

        for obsolete_info in skill_plan["obsolete"]:
            try:
                remove_result = skill_service.remove_skill(obsolete_info["skill"])
                if "error" in remove_result:
                    raise ValueError(remove_result["error"])
                results["obsolete_removed"]["upgraded"].append(obsolete_info["skill"])
            except Exception as e:
                logger.debug(
                    "Obsolete skill removal failed: %s", obsolete_info["skill"], exc_info=True
                )
                results["obsolete_removed"]["failed"].append(f"{obsolete_info['skill']}: {e}")

        # Add missing gitignore entries
        gitignore_plan = plan.get("gitignore", [])
        if gitignore_plan:
            entries_by_feature: dict[str, list[str]] = {}
            for item in gitignore_plan:
                feature = item["feature"]
                if feature not in entries_by_feature:
                    entries_by_feature[feature] = []
                entries_by_feature[feature].append(item["entry"])

            for feature_name, entries in entries_by_feature.items():
                try:
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
                    logger.debug("Gitignore update failed: %s", feature_name, exc_info=True)
                    for entry in entries:
                        results["gitignore"]["failed"].append(f"{feature_name}: {entry}: {e}")

        # Run migrations
        completed_migrations = set(self.config_service.get_completed_migrations())
        successful_migrations, failed_migrations = run_migrations(
            self.project_root, completed_migrations
        )

        if successful_migrations:
            self.config_service.add_completed_migrations(successful_migrations)
            results["migrations"]["upgraded"] = successful_migrations

        if failed_migrations:
            results["migrations"]["failed"] = [
                f"{migration_id}: {error}" for migration_id, error in failed_migrations
            ]

        # Update config version
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
                logger.warning(f"Failed to update config version: {e}")

        return results

    # -- execute helpers --

    def _upgrade_agent_command(self, cmd: UpgradePlanCommand) -> None:
        """Upgrade a single agent command."""
        package_path = cmd["package_path"]
        installed_path = cmd["installed_path"]
        agent_type = cmd["agent"]

        content = read_file(package_path)
        rendered_content = self.template_service.render_command_for_agent(content, agent_type)
        ensure_dir(installed_path.parent)
        write_file(installed_path, rendered_content)

    def _remove_legacy_command(self, agent: str, filename: str) -> bool:
        """Remove a legacy command file for a skills-capable agent."""
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

    def _repair_structure(self) -> list[str]:
        """Repair structural issues in the installation."""
        import shutil

        repaired = []

        features_dir = self.project_root / ".oak" / "features"
        if features_dir.exists():
            try:
                shutil.rmtree(features_dir)
                repaired.append("Removed obsolete .oak/features/ directory")
            except OSError as e:
                logger.warning(f"Failed to remove obsolete .oak/features/ directory: {e}")

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

            try:
                if old_templates_dir.exists() and not any(old_templates_dir.iterdir()):
                    old_templates_dir.rmdir()
                    repaired.append("Removed empty .oak/templates/")
            except OSError as e:
                logger.warning(f"Failed to remove empty .oak/templates/: {e}")

        return repaired
