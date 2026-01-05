"""Upgrade stages for the upgrade pipeline.

These stages wrap UpgradeService methods to provide a consistent
pipeline-based upgrade flow.
"""

from open_agent_kit.pipeline.context import FlowType, PipelineContext
from open_agent_kit.pipeline.ordering import StageOrder
from open_agent_kit.pipeline.stage import BaseStage, StageOutcome


class ValidateUpgradeEnvironmentStage(BaseStage):
    """Validate environment before upgrade."""

    name = "validate_upgrade_environment"
    display_name = "Validating environment"
    order = StageOrder.VALIDATE_ENVIRONMENT
    applicable_flows = {FlowType.UPGRADE}
    is_critical = True

    def _should_run(self, context: PipelineContext) -> bool:
        """Run unless plan is already provided (CLI already validated)."""
        existing_plan = context.get_result("plan_upgrade")
        return existing_plan is None

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Validate that open-agent-kit is initialized."""
        from open_agent_kit.services.upgrade_service import UpgradeService

        upgrade_service = UpgradeService(context.project_root)

        if not upgrade_service.is_initialized():
            return StageOutcome.failed(
                "Not initialized",
                error="open-agent-kit is not initialized in this directory",
            )

        return StageOutcome.success("Environment validated")


class PlanUpgradeStage(BaseStage):
    """Plan what needs to be upgraded.

    This stage creates the upgrade plan and stores it in context
    for subsequent stages to execute.

    If a plan is already provided in context (pre-populated by CLI),
    this stage will skip execution and use the existing plan.
    """

    name = "plan_upgrade"
    display_name = "Planning upgrade"
    order = 50  # After validation, before execution
    applicable_flows = {FlowType.UPGRADE}
    is_critical = True

    def _should_run(self, context: PipelineContext) -> bool:
        """Run unless plan is already provided in context."""
        existing_plan = context.get_result("plan_upgrade")
        return existing_plan is None

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Create upgrade plan."""
        from open_agent_kit.services.upgrade_service import UpgradeService

        upgrade_service = UpgradeService(context.project_root)

        # Get upgrade options from context
        upgrade_commands = context.stage_results.get("upgrade_commands", True)
        upgrade_templates = context.stage_results.get("upgrade_templates", True)
        upgrade_ide_settings = context.stage_results.get("upgrade_ide_settings", True)
        upgrade_skills = context.stage_results.get("upgrade_skills", True)

        plan = upgrade_service.plan_upgrade(
            commands=upgrade_commands,
            templates=upgrade_templates,
            ide_settings=upgrade_ide_settings,
            skills=upgrade_skills,
        )

        # Check if anything needs upgrading
        skill_plan = plan["skills"]
        has_upgrades = (
            plan["commands"]
            or plan["templates"]
            or plan["obsolete_templates"]
            or plan["ide_settings"]
            or skill_plan["install"]
            or skill_plan["upgrade"]
            or plan["migrations"]
            or plan["structural_repairs"]
            or plan["version_outdated"]
        )

        if not has_upgrades:
            return StageOutcome.success(
                "Already up to date",
                data={"plan": plan, "has_upgrades": False},
            )

        return StageOutcome.success(
            "Upgrade plan created",
            data={"plan": plan, "has_upgrades": True},
        )


class TriggerPreUpgradeHooksStage(BaseStage):
    """Trigger pre-upgrade hooks before executing upgrade."""

    name = "trigger_pre_upgrade_hooks"
    display_name = "Running pre-upgrade hooks"
    order = 100  # Before upgrade execution
    applicable_flows = {FlowType.UPGRADE}
    is_critical = False

    def _should_run(self, context: PipelineContext) -> bool:
        """Run if there are upgrades to perform."""
        plan_result = context.get_result("plan_upgrade", {})
        return plan_result.get("has_upgrades", False) and not context.dry_run

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Trigger pre-upgrade hooks."""
        feature_service = self._get_feature_service(context)
        plan_result = context.get_result("plan_upgrade", {})
        plan = plan_result.get("plan", {})

        try:
            results = feature_service.trigger_pre_upgrade_hooks(dict(plan))
            successful = sum(1 for r in results.values() if r.get("success"))
            return StageOutcome.success(
                f"Ran {successful}/{len(results)} pre-upgrade hooks",
                data={"hook_results": results},
            )
        except Exception as e:
            # Hook failures are not fatal
            return StageOutcome.success(
                "Pre-upgrade hooks completed with warnings",
                data={"error": str(e)},
            )


class UpgradeStructuralRepairsStage(BaseStage):
    """Repair structural issues (missing directories, old structure)."""

    name = "upgrade_structural_repairs"
    display_name = "Repairing structural issues"
    order = 150
    applicable_flows = {FlowType.UPGRADE}
    is_critical = False

    def _should_run(self, context: PipelineContext) -> bool:
        """Run if there are structural repairs needed."""
        if context.dry_run:
            return False
        plan_result = context.get_result("plan_upgrade", {})
        plan = plan_result.get("plan", {})
        return bool(plan.get("structural_repairs"))

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Repair structural issues."""
        from open_agent_kit.services.upgrade_service import UpgradeService

        upgrade_service = UpgradeService(context.project_root)
        repaired = upgrade_service._repair_structure()

        return StageOutcome.success(
            f"Repaired {len(repaired)} structural issue(s)",
            data={"repaired": repaired},
        )


class UpgradeCommandsStage(BaseStage):
    """Upgrade agent command templates."""

    name = "upgrade_commands"
    display_name = "Upgrading agent commands"
    order = 200
    applicable_flows = {FlowType.UPGRADE}
    is_critical = False

    def _should_run(self, context: PipelineContext) -> bool:
        """Run if there are commands to upgrade."""
        if context.dry_run:
            return False
        plan_result = context.get_result("plan_upgrade", {})
        plan = plan_result.get("plan", {})
        return bool(plan.get("commands"))

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Upgrade agent commands."""
        from open_agent_kit.services.upgrade_service import UpgradeService

        upgrade_service = UpgradeService(context.project_root)
        plan_result = context.get_result("plan_upgrade", {})
        plan = plan_result.get("plan", {})

        upgraded = []
        failed = []

        for cmd in plan["commands"]:
            try:
                upgrade_service._upgrade_agent_command(cmd)
                upgraded.append(cmd["file"])
            except Exception as e:
                failed.append(f"{cmd['file']}: {e}")

        if failed:
            return StageOutcome.success(
                f"Upgraded {len(upgraded)} command(s), {len(failed)} failed",
                data={"upgraded": upgraded, "failed": failed},
            )

        return StageOutcome.success(
            f"Upgraded {len(upgraded)} command(s)",
            data={"upgraded": upgraded, "failed": []},
        )


# Note: UpgradeTemplatesStage and RemoveObsoleteTemplatesStage were removed.
# Templates are now read directly from the installed package - no project copies to upgrade.


class UpgradeIDESettingsStage(BaseStage):
    """Upgrade IDE settings."""

    name = "upgrade_ide_settings"
    display_name = "Upgrading IDE settings"
    order = 230
    applicable_flows = {FlowType.UPGRADE}
    is_critical = False

    def _should_run(self, context: PipelineContext) -> bool:
        """Run if there are IDE settings to upgrade."""
        if context.dry_run:
            return False
        plan_result = context.get_result("plan_upgrade", {})
        plan = plan_result.get("plan", {})
        return bool(plan.get("ide_settings"))

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Upgrade IDE settings."""
        from open_agent_kit.services.upgrade_service import UpgradeService

        upgrade_service = UpgradeService(context.project_root)
        plan_result = context.get_result("plan_upgrade", {})
        plan = plan_result.get("plan", {})

        upgraded = []
        failed = []

        for ide in plan["ide_settings"]:
            try:
                upgrade_service._upgrade_ide_settings(ide)
                upgraded.append(ide)
            except Exception as e:
                failed.append(f"{ide}: {e}")

        if failed:
            return StageOutcome.success(
                f"Upgraded {len(upgraded)} IDE setting(s), {len(failed)} failed",
                data={"upgraded": upgraded, "failed": failed},
            )

        return StageOutcome.success(
            f"Upgraded {len(upgraded)} IDE setting(s)",
            data={"upgraded": upgraded, "failed": []},
        )


class UpgradeSkillsStage(BaseStage):
    """Install and upgrade skills."""

    name = "upgrade_skills"
    display_name = "Upgrading skills"
    order = 240
    applicable_flows = {FlowType.UPGRADE}
    is_critical = False

    def _should_run(self, context: PipelineContext) -> bool:
        """Run if there are skills to install or upgrade."""
        if context.dry_run:
            return False
        plan_result = context.get_result("plan_upgrade", {})
        plan = plan_result.get("plan", {})
        skill_plan = plan.get("skills", {})
        return bool(skill_plan.get("install") or skill_plan.get("upgrade"))

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Install and upgrade skills."""
        from open_agent_kit.services.upgrade_service import UpgradeService

        upgrade_service = UpgradeService(context.project_root)
        plan_result = context.get_result("plan_upgrade", {})
        plan = plan_result.get("plan", {})
        skill_plan = plan.get("skills", {})

        upgraded = []
        failed = []

        # Install new skills
        for skill_info in skill_plan.get("install", []):
            try:
                upgrade_service._install_skill(skill_info["skill"], skill_info["feature"])
                upgraded.append(skill_info["skill"])
            except Exception as e:
                failed.append(f"{skill_info['skill']}: {e}")

        # Upgrade existing skills
        for skill_info in skill_plan.get("upgrade", []):
            try:
                upgrade_service._upgrade_skill(skill_info["skill"])
                upgraded.append(skill_info["skill"])
            except Exception as e:
                failed.append(f"{skill_info['skill']}: {e}")

        if failed:
            return StageOutcome.success(
                f"Upgraded {len(upgraded)} skill(s), {len(failed)} failed",
                data={"upgraded": upgraded, "failed": failed},
            )

        return StageOutcome.success(
            f"Upgraded {len(upgraded)} skill(s)",
            data={"upgraded": upgraded, "failed": []},
        )


class RunMigrationsStage(BaseStage):
    """Run pending migrations."""

    name = "run_migrations"
    display_name = "Running migrations"
    order = 250
    applicable_flows = {FlowType.UPGRADE}
    is_critical = False

    def _should_run(self, context: PipelineContext) -> bool:
        """Run if there are migrations to run."""
        if context.dry_run:
            return False
        plan_result = context.get_result("plan_upgrade", {})
        plan = plan_result.get("plan", {})
        return bool(plan.get("migrations"))

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Run pending migrations."""
        from open_agent_kit.services.config_service import ConfigService
        from open_agent_kit.services.migrations import run_migrations

        config_service = ConfigService(context.project_root)
        completed_migrations = set(config_service.get_completed_migrations())

        successful_migrations, failed_migrations = run_migrations(
            context.project_root, completed_migrations
        )

        # Track successful migrations
        if successful_migrations:
            config_service.add_completed_migrations(successful_migrations)

        # Format failed migrations
        failed = [f"{mid}: {error}" for mid, error in failed_migrations]

        if failed:
            return StageOutcome.success(
                f"Ran {len(successful_migrations)} migration(s), {len(failed)} failed",
                data={"completed": successful_migrations, "failed": failed},
            )

        return StageOutcome.success(
            f"Completed {len(successful_migrations)} migration(s)",
            data={"completed": successful_migrations, "failed": []},
        )


class UpdateVersionStage(BaseStage):
    """Update config version after upgrade."""

    name = "update_upgrade_version"
    display_name = "Updating version"
    order = 300
    applicable_flows = {FlowType.UPGRADE}
    is_critical = False

    def _should_run(self, context: PipelineContext) -> bool:
        """Run if version is outdated or upgrades were performed."""
        if context.dry_run:
            return False
        plan_result = context.get_result("plan_upgrade", {})
        plan: dict = plan_result.get("plan", {})  # type: ignore[assignment]
        return bool(plan.get("version_outdated", False) or plan.get("has_upgrades", False))

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Update config version."""
        from open_agent_kit.constants import VERSION

        config_service = self._get_config_service(context)

        try:
            config_service.update_config(version=VERSION)
            return StageOutcome.success(
                f"Updated to version {VERSION}",
                data={"version": VERSION},
            )
        except Exception as e:
            return StageOutcome.success(
                "Version update skipped",
                data={"error": str(e)},
            )


class TriggerPostUpgradeHooksStage(BaseStage):
    """Trigger post-upgrade hooks after upgrade completes."""

    name = "trigger_post_upgrade_hooks"
    display_name = "Running post-upgrade hooks"
    order = 350
    applicable_flows = {FlowType.UPGRADE}
    is_critical = False

    def _should_run(self, context: PipelineContext) -> bool:
        """Run if upgrades were performed."""
        plan_result = context.get_result("plan_upgrade", {})
        return plan_result.get("has_upgrades", False) and not context.dry_run

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Trigger post-upgrade hooks."""
        feature_service = self._get_feature_service(context)

        # Collect results from all upgrade stages
        results = self._collect_upgrade_results(context)

        try:
            hook_results = feature_service.trigger_post_upgrade_hooks(results)
            successful = sum(1 for r in hook_results.values() if r.get("success"))
            return StageOutcome.success(
                f"Ran {successful}/{len(hook_results)} post-upgrade hooks",
                data={"hook_results": hook_results},
            )
        except Exception as e:
            return StageOutcome.success(
                "Post-upgrade hooks completed with warnings",
                data={"error": str(e)},
            )

    def _collect_upgrade_results(self, context: PipelineContext) -> dict:
        """Collect results from all upgrade stages."""
        from typing import Any

        results: dict[str, Any] = {
            "commands": {"upgraded": [], "failed": []},
            "templates": {"upgraded": [], "failed": []},
            "obsolete_removed": {"upgraded": [], "failed": []},
            "ide_settings": {"upgraded": [], "failed": []},
            "skills": {"upgraded": [], "failed": []},
            "migrations": {"upgraded": [], "failed": []},
            "structural_repairs": [],
            "version_updated": False,
        }

        # Collect from each stage result
        cmd_result = context.get_result("upgrade_commands", {})
        if cmd_result:
            results["commands"]["upgraded"] = cmd_result.get("upgraded", [])
            results["commands"]["failed"] = cmd_result.get("failed", [])

        tpl_result = context.get_result("upgrade_templates", {})
        if tpl_result:
            results["templates"]["upgraded"] = tpl_result.get("upgraded", [])
            results["templates"]["failed"] = tpl_result.get("failed", [])

        obsolete_result = context.get_result("remove_obsolete_templates", {})
        if obsolete_result:
            results["obsolete_removed"]["upgraded"] = obsolete_result.get("removed", [])
            results["obsolete_removed"]["failed"] = obsolete_result.get("failed", [])

        ide_result = context.get_result("upgrade_ide_settings", {})
        if ide_result:
            results["ide_settings"]["upgraded"] = ide_result.get("upgraded", [])
            results["ide_settings"]["failed"] = ide_result.get("failed", [])

        skill_result = context.get_result("upgrade_skills", {})
        if skill_result:
            results["skills"]["upgraded"] = skill_result.get("upgraded", [])
            results["skills"]["failed"] = skill_result.get("failed", [])

        migration_result = context.get_result("run_migrations", {})
        if migration_result:
            results["migrations"]["upgraded"] = migration_result.get("completed", [])
            results["migrations"]["failed"] = migration_result.get("failed", [])

        repair_result = context.get_result("upgrade_structural_repairs", {})
        if repair_result:
            results["structural_repairs"] = repair_result.get("repaired", [])

        version_result = context.get_result("update_upgrade_version", {})
        if version_result and version_result.get("version"):
            results["version_updated"] = True

        return results


def get_upgrade_stages() -> list[BaseStage]:
    """Get all upgrade stages."""
    return [
        ValidateUpgradeEnvironmentStage(),
        PlanUpgradeStage(),
        TriggerPreUpgradeHooksStage(),
        UpgradeStructuralRepairsStage(),
        UpgradeCommandsStage(),
        # Note: Template upgrade stages removed - templates are read from package
        UpgradeIDESettingsStage(),
        UpgradeSkillsStage(),
        RunMigrationsStage(),
        UpdateVersionStage(),
        TriggerPostUpgradeHooksStage(),
    ]
