"""Upgrade service for updating templates and commands."""

from pathlib import Path
from typing import TypedDict

from open_agent_kit.constants import (
    OAK_DIR,
    UPGRADE_COMMAND_NAMES,
    UPGRADE_TEMPLATE_CATEGORIES,
)
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


class UpgradeCategoryResults(TypedDict):
    upgraded: list[str]
    failed: list[str]


class UpgradeResults(TypedDict):
    commands: UpgradeCategoryResults
    templates: UpgradeCategoryResults
    ide_settings: UpgradeCategoryResults
    migrations: UpgradeCategoryResults
    version_updated: bool


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

        # Package templates directory (source of truth)
        self.package_commands_dir = (
            Path(__file__).parent.parent.parent.parent / "templates" / "commands"
        )

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
    ) -> dict:
        """Plan what needs to be upgraded.

        Args:
            commands: Whether to upgrade agent commands
            templates: Whether to upgrade RFC templates
            ide_settings: Whether to upgrade IDE settings

        Returns:
            Dictionary with upgrade plan:
            {
                "commands": [{"agent": "claude", "file": "oak.rfc-create.md", ...}],
                "templates": ["engineering.md", "architecture.md"],
                "templates_customized": bool,
                "ide_settings": ["vscode", "cursor"],
                "migrations": [{"id": "...", "description": "..."}],
                "version_outdated": bool,
                "current_version": str,
                "package_version": str
            }
        """
        from open_agent_kit.constants import VERSION
        from open_agent_kit.services.migrations import get_migrations

        # Check config version
        config = self.config_service.load_config()
        current_version = config.version
        version_outdated = current_version != VERSION

        plan = {
            "commands": [],
            "templates": [],
            "templates_customized": False,
            "ide_settings": [],
            "migrations": [],
            "version_outdated": version_outdated,
            "current_version": current_version,
            "package_version": VERSION,
        }

        # Plan agent command upgrades
        if commands:
            configured_agents = self.config_service.get_agents()
            for agent in configured_agents:
                agent_commands = self._get_upgradeable_commands(agent)
                plan["commands"].extend(agent_commands)

        # Plan RFC template upgrades
        if templates:
            upgradeable_templates = self._get_upgradeable_templates()
            plan["templates"] = upgradeable_templates
            plan["templates_customized"] = self._are_templates_customized()

        # Plan IDE settings upgrades (only for configured IDEs)
        if ide_settings:
            configured_ides = self.config_service.get_ides()
            upgradeable_ide_settings = []
            for ide in configured_ides:
                if self.ide_settings_service.needs_upgrade(ide):
                    upgradeable_ide_settings.append(ide)
            plan["ide_settings"] = upgradeable_ide_settings

        # Plan migrations (one-time upgrade tasks)
        completed_migrations = set(self.config_service.get_completed_migrations())
        all_migrations = get_migrations()
        for migration_id, description, _ in all_migrations:
            if migration_id not in completed_migrations:
                plan["migrations"].append({"id": migration_id, "description": description})

        return plan

    def execute_upgrade(self, plan: dict) -> UpgradeResults:
        """Execute the upgrade plan.

        Updates config version to current package version after successful upgrades.
        Runs any pending migrations as part of the upgrade process.

        Args:
            plan: Upgrade plan from plan_upgrade()

        Returns:
            Dictionary with results:
            {
                "commands": {"upgraded": [...], "failed": [...]},
                "templates": {"upgraded": [...], "failed": [...]},
                "ide_settings": {"upgraded": [...], "failed": [...]},
                "migrations": {"upgraded": [...], "failed": [...]},
                "version_updated": bool
            }
        """
        results: UpgradeResults = {
            "commands": {"upgraded": [], "failed": []},
            "templates": {"upgraded": [], "failed": []},
            "ide_settings": {"upgraded": [], "failed": []},
            "migrations": {"upgraded": [], "failed": []},
            "version_updated": False,
        }

        # Upgrade agent commands
        for cmd in plan["commands"]:
            try:
                self._upgrade_agent_command(cmd)
                results["commands"]["upgraded"].append(cmd["file"])
            except Exception as e:
                results["commands"]["failed"].append(f"{cmd['file']}: {e}")

        # Upgrade RFC templates
        for template in plan["templates"]:
            try:
                self._upgrade_rfc_template(template)
                results["templates"]["upgraded"].append(template)
            except Exception as e:
                results["templates"]["failed"].append(f"{template}: {e}")

        # Upgrade IDE settings
        for ide in plan["ide_settings"]:
            try:
                self._upgrade_ide_settings(ide)
                results["ide_settings"]["upgraded"].append(ide)
            except Exception as e:
                results["ide_settings"]["failed"].append(f"{ide}: {e}")

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
            + len(results["ide_settings"]["upgraded"])
            + len(results["migrations"]["upgraded"])
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

    def _get_upgradeable_commands(self, agent: str) -> list[dict]:
        """Get agent commands that can be upgraded.

        Args:
            agent: Agent type name

        Returns:
            List of command dictionaries with upgrade info
        """
        upgradeable = []

        # Get agent's commands directory
        try:
            commands_dir = self.agent_service.get_agent_commands_dir(agent)
        except ValueError:
            return []

        # Check each command template from package
        for command_name in UPGRADE_COMMAND_NAMES:
            package_template = self.package_commands_dir / f"oak.{command_name}.md"
            if not package_template.exists():
                continue

            # Get installed command file
            filename = self.agent_service.get_command_filename(agent, command_name)
            installed_file = commands_dir / filename

            # Check if needs upgrade (file exists and content differs) OR is new (doesn't exist)
            if installed_file.exists():
                needs_upgrade = self._files_differ(package_template, installed_file)
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

    def _get_upgradeable_templates(self) -> list[str]:
        """Get RFC and other templates that can be upgraded or newly installed.

        Returns:
            List of template names that can be upgraded or installed
        """
        upgradeable = []

        # Template file extensions to check
        extensions = ["*.md", "*.yaml", "*.json"]

        # Only check templates from known categories
        for category in UPGRADE_TEMPLATE_CATEGORIES:
            # Get package templates for this category
            package_category_dir = self.template_service.package_templates_dir / category
            if not package_category_dir.exists():
                continue

            # Check all template file types
            for ext in extensions:
                for package_file in package_category_dir.glob(ext):
                    template_name = f"{category}/{package_file.name}"

                    try:
                        # Get paths
                        package_path = self.template_service.get_template_source_path(template_name)
                        project_path = self.template_service.get_template_project_path(
                            template_name
                        )

                        # Check if needs upgrade (exists and differs) OR is new (doesn't exist)
                        if project_path.exists():
                            if self._files_differ(package_path, project_path):
                                upgradeable.append(template_name)
                        else:
                            # New template that doesn't exist in project yet
                            upgradeable.append(template_name)
                    except Exception:
                        continue

        return upgradeable

    def _are_templates_customized(self) -> bool:
        """Check if any RFC templates have been customized.

        Returns:
            True if any templates differ from package versions
        """
        # For now, if any templates need upgrading, consider them potentially customized
        # In the future, we could add version headers to templates to track this better
        return len(self._get_upgradeable_templates()) > 0

    def _upgrade_agent_command(self, cmd: dict) -> None:
        """Upgrade a single agent command.

        Args:
            cmd: Command dictionary from _get_upgradeable_commands()
        """
        package_path = cmd["package_path"]
        installed_path = cmd["installed_path"]

        # Read package template
        content = read_file(package_path)

        # Ensure directory exists
        ensure_dir(installed_path.parent)

        # Write to installed location
        write_file(installed_path, content)

    def _upgrade_rfc_template(self, template_name: str) -> None:
        """Upgrade a single RFC template.

        Args:
            template_name: Template name (e.g., "rfc/engineering.md")
        """
        # Get source from package templates (not project templates)
        # This ensures we always upgrade from the package source, not copying old to old
        source_path = self.template_service.get_template_source_path(template_name)
        dest_path = self.template_service.get_template_project_path(template_name)

        # Ensure directory exists
        ensure_dir(dest_path.parent)

        # Copy content from package to project
        content = read_file(source_path)
        write_file(dest_path, content)

    def _upgrade_ide_settings(self, ide: str) -> None:
        """Upgrade IDE settings.

        Args:
            ide: IDE name (e.g., "vscode", "cursor")
        """
        # Use the IDE settings service to install/merge settings
        self.ide_settings_service.install_settings(ide, force=False)

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


def get_upgrade_service(project_root: Path | None = None) -> UpgradeService:
    """Get an UpgradeService instance.

    Args:
        project_root: Project root directory (defaults to current directory)

    Returns:
        UpgradeService instance
    """
    return UpgradeService(project_root)
