"""Upgrade stages for the upgrade pipeline.

These stages wrap UpgradeService methods to provide a consistent
pipeline-based upgrade flow.
"""

from typing import Any, cast

from open_agent_kit.pipeline.context import FlowType, PipelineContext
from open_agent_kit.pipeline.models import (
    CollectedUpgradeResults,
    StageResultRegistry,
    plan_has_upgrades,
)
from open_agent_kit.pipeline.ordering import StageOrder
from open_agent_kit.pipeline.stage import BaseStage, StageOutcome
from open_agent_kit.pipeline.utils import format_count_message, process_items


class ValidateUpgradeEnvironmentStage(BaseStage):
    """Validate environment before upgrade."""

    name = "validate_upgrade_environment"
    display_name = "Validating environment"
    order = StageOrder.VALIDATE_ENVIRONMENT
    applicable_flows = {FlowType.UPGRADE}
    is_critical = True

    def _should_run(self, context: PipelineContext) -> bool:
        """Run unless plan is already provided (CLI already validated)."""
        existing_plan = context.get_result(StageResultRegistry.PLAN_UPGRADE)
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
        existing_plan = context.get_result(StageResultRegistry.PLAN_UPGRADE)
        return existing_plan is None

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Create upgrade plan."""
        from open_agent_kit.services.upgrade_service import UpgradeService

        upgrade_service = UpgradeService(context.project_root)

        # Get upgrade options from context (default to True if not specified)
        upgrade_commands = context.stage_results.get("upgrade_commands", True)
        upgrade_templates = context.stage_results.get("upgrade_templates", True)
        upgrade_agent_settings = context.stage_results.get("upgrade_agent_settings", True)
        upgrade_skills = context.stage_results.get("upgrade_skills", True)

        plan = upgrade_service.plan_upgrade(
            commands=upgrade_commands,
            templates=upgrade_templates,
            agent_settings=upgrade_agent_settings,
            skills=upgrade_skills,
        )

        # Check if anything needs upgrading using the utility function
        # Cast to dict[str, Any] for plan_has_upgrades compatibility
        has_upgrades = plan_has_upgrades(cast(dict[str, Any], plan))

        result_data = {"plan": plan, "has_upgrades": has_upgrades}

        if not has_upgrades:
            return StageOutcome.success("Already up to date", data=result_data)

        return StageOutcome.success("Upgrade plan created", data=result_data)


class TriggerPreUpgradeHooksStage(BaseStage):
    """Trigger pre-upgrade hooks before executing upgrade."""

    name = "trigger_pre_upgrade_hooks"
    display_name = "Running pre-upgrade hooks"
    order = 100  # Before upgrade execution
    applicable_flows = {FlowType.UPGRADE}
    is_critical = False

    def _should_run(self, context: PipelineContext) -> bool:
        """Run if there are upgrades to perform."""
        plan_result = context.get_result(StageResultRegistry.PLAN_UPGRADE, {})
        return plan_result.get("has_upgrades", False) and not context.dry_run

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Trigger pre-upgrade hooks."""
        feature_service = self._get_feature_service(context)
        plan_result = context.get_result(StageResultRegistry.PLAN_UPGRADE, {})
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
        plan_result = context.get_result(StageResultRegistry.PLAN_UPGRADE, {})
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


class CleanupLegacyCommandsStage(BaseStage):
    """Clean up legacy commands that no longer exist in feature config.

    Removes oak.* command files that don't match any current valid command
    from FEATURE_CONFIG. This cleans up commands that were removed or renamed
    during feature updates (e.g., legacy skill-fallback commands).
    """

    name = "cleanup_legacy_commands"
    display_name = "Cleaning up legacy commands"
    order = 195  # Before UpgradeCommandsStage
    applicable_flows = {FlowType.UPGRADE}
    is_critical = False

    def _should_run(self, context: PipelineContext) -> bool:
        """Run if there are legacy commands to clean up."""
        if context.dry_run:
            return False
        plan_result = context.get_result(StageResultRegistry.PLAN_UPGRADE, {})
        plan = plan_result.get("plan", {})
        return bool(plan.get("legacy_commands_cleanup"))

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Remove legacy commands for skills-capable agents."""
        from open_agent_kit.services.upgrade_service import UpgradeService

        upgrade_service = UpgradeService(context.project_root)
        plan_result = context.get_result(StageResultRegistry.PLAN_UPGRADE, {})
        plan: dict[str, Any] = plan_result.get("plan", {})

        cleanup_items = plan.get("legacy_commands_cleanup", [])
        removed_total = 0

        for item in cleanup_items:
            agent = item["agent"]
            commands = item["commands"]
            for cmd_info in commands:
                try:
                    upgrade_service._remove_legacy_command(agent, cmd_info["file"])
                    removed_total += 1
                except Exception:
                    pass  # Best effort cleanup

        if removed_total > 0:
            return StageOutcome.success(
                f"Removed {removed_total} legacy command(s) for skills-capable agents",
                data={"removed_count": removed_total},
            )

        return StageOutcome.success("No legacy commands to clean up")


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
        plan_result = context.get_result(StageResultRegistry.PLAN_UPGRADE, {})
        plan = plan_result.get("plan", {})
        return bool(plan.get("commands"))

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Upgrade agent commands."""
        from open_agent_kit.services.upgrade_service import UpgradeService

        upgrade_service = UpgradeService(context.project_root)
        plan_result = context.get_result(StageResultRegistry.PLAN_UPGRADE, {})
        plan: dict[str, Any] = plan_result.get("plan", {})

        result = process_items(
            plan.get("commands", []),
            upgrade_service._upgrade_agent_command,
            lambda cmd: cmd["file"],
        )

        message = format_count_message(
            "Upgraded", result.success_count, result.failure_count, "command"
        )

        return StageOutcome.success(
            message, data={"upgraded": result.succeeded, "failed": result.failed}
        )


# Note: UpgradeTemplatesStage and RemoveObsoleteTemplatesStage were removed.
# Templates are now read directly from the installed package - no project copies to upgrade.


class UpgradeAgentSettingsStage(BaseStage):
    """Upgrade agent auto-approval settings."""

    name = "upgrade_agent_settings"
    display_name = "Upgrading agent settings"
    order = 231
    applicable_flows = {FlowType.UPGRADE}
    is_critical = False

    def _should_run(self, context: PipelineContext) -> bool:
        """Run if there are agent settings to upgrade."""
        if context.dry_run:
            return False
        plan_result = context.get_result(StageResultRegistry.PLAN_UPGRADE, {})
        plan = plan_result.get("plan", {})
        return bool(plan.get("agent_settings"))

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Upgrade agent settings."""
        from open_agent_kit.services.upgrade_service import UpgradeService

        upgrade_service = UpgradeService(context.project_root)
        plan_result = context.get_result(StageResultRegistry.PLAN_UPGRADE, {})
        plan: dict[str, Any] = plan_result.get("plan", {})

        result = process_items(
            plan.get("agent_settings", []),
            upgrade_service._upgrade_agent_settings,
        )

        message = format_count_message(
            "Upgraded", result.success_count, result.failure_count, "agent setting"
        )

        return StageOutcome.success(
            message, data={"upgraded": result.succeeded, "failed": result.failed}
        )


class UpgradeGitignoreStage(BaseStage):
    """Add missing gitignore entries from feature manifests."""

    name = "upgrade_gitignore"
    display_name = "Updating gitignore"
    order = 235
    applicable_flows = {FlowType.UPGRADE}
    is_critical = False

    def _should_run(self, context: PipelineContext) -> bool:
        """Run if there are gitignore entries to add."""
        if context.dry_run:
            return False
        plan_result = context.get_result(StageResultRegistry.PLAN_UPGRADE, {})
        plan = plan_result.get("plan", {})
        return bool(plan.get("gitignore"))

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Add missing gitignore entries."""
        from pathlib import Path

        from open_agent_kit.config.paths import FEATURES_DIR
        from open_agent_kit.models.feature import FeatureManifest
        from open_agent_kit.utils import add_gitignore_entries

        plan_result = context.get_result(StageResultRegistry.PLAN_UPGRADE, {})
        plan: dict[str, Any] = plan_result.get("plan", {})
        gitignore_plan = plan.get("gitignore", [])

        # Group entries by feature
        entries_by_feature: dict[str, list[str]] = {}
        for item in gitignore_plan:
            feature = item["feature"]
            entries_by_feature.setdefault(feature, []).append(item["entry"])

        # Package features directory for manifest lookup
        # Path: pipeline/stages/upgrade.py -> stages/ -> pipeline/ -> open_agent_kit/
        package_features_dir = Path(__file__).parent.parent.parent / FEATURES_DIR

        upgraded: list[str] = []
        failed: list[str] = []

        for feature_name, entries in entries_by_feature.items():
            try:
                # Get feature display name for comment
                # Convert hyphenated name to underscored directory name
                feature_dir = feature_name.replace("-", "_")
                manifest_path = package_features_dir / feature_dir / "manifest.yaml"
                display_name = feature_name
                if manifest_path.exists():
                    try:
                        manifest = FeatureManifest.load(manifest_path)
                        display_name = manifest.display_name
                    except Exception:
                        pass

                added = add_gitignore_entries(
                    context.project_root,
                    entries,
                    section_comment=f"open-agent-kit: {display_name}",
                )
                if added:
                    upgraded.extend(f"{feature_name}: {entry}" for entry in added)
            except Exception as e:
                failed.extend(f"{feature_name}: {entry}: {e}" for entry in entries)

        message = format_count_message("Added", len(upgraded), len(failed), "gitignore pattern")

        return StageOutcome.success(message, data={"upgraded": upgraded, "failed": failed})


class UpgradeSkillsStage(BaseStage):
    """Install, upgrade, and remove obsolete skills."""

    name = "upgrade_skills"
    display_name = "Upgrading skills"
    order = 240
    applicable_flows = {FlowType.UPGRADE}
    is_critical = False

    def _should_run(self, context: PipelineContext) -> bool:
        """Run if there are skills to install, upgrade, or remove."""
        if context.dry_run:
            return False
        plan_result = context.get_result(StageResultRegistry.PLAN_UPGRADE, {})
        plan = plan_result.get("plan", {})
        skill_plan = plan.get("skills", {})
        return bool(
            skill_plan.get("install") or skill_plan.get("upgrade") or skill_plan.get("obsolete")
        )

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Install, upgrade, and remove obsolete skills."""
        from open_agent_kit.services.upgrade_service import UpgradeService

        upgrade_service = UpgradeService(context.project_root)
        plan_result = context.get_result(StageResultRegistry.PLAN_UPGRADE, {})
        plan: dict[str, Any] = plan_result.get("plan", {})
        skill_plan = plan.get("skills", {})

        # Process obsolete skill removals first (cleanup renamed/removed skills)
        remove_result = process_items(
            skill_plan.get("obsolete", []),
            lambda info: upgrade_service._remove_obsolete_skill(info["skill"]),
            lambda info: info["skill"],
        )

        # Process skill installations
        install_result = process_items(
            skill_plan.get("install", []),
            lambda info: upgrade_service._install_skill(info["skill"], info["feature"]),
            lambda info: info["skill"],
        )

        # Process skill upgrades
        upgrade_result = process_items(
            skill_plan.get("upgrade", []),
            lambda info: upgrade_service._upgrade_skill(info["skill"]),
            lambda info: info["skill"],
        )

        # Combine results
        all_succeeded = (
            install_result.succeeded + upgrade_result.succeeded + remove_result.succeeded
        )
        all_failed = install_result.failed + upgrade_result.failed + remove_result.failed

        message = format_count_message("Processed", len(all_succeeded), len(all_failed), "skill")

        return StageOutcome.success(
            message,
            data={
                "installed": install_result.succeeded,
                "upgraded": upgrade_result.succeeded,
                "removed": remove_result.succeeded,
                "failed": all_failed,
            },
        )


class UpgradeHooksStage(BaseStage):
    """Upgrade feature hooks for agents."""

    name = "upgrade_hooks"
    display_name = "Upgrading hooks"
    order = 245
    applicable_flows = {FlowType.UPGRADE}
    is_critical = False

    def _should_run(self, context: PipelineContext) -> bool:
        """Run if there are hooks to upgrade."""
        if context.dry_run:
            return False
        plan_result = context.get_result(StageResultRegistry.PLAN_UPGRADE, {})
        plan = plan_result.get("plan", {})
        return bool(plan.get("hooks"))

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Upgrade feature hooks by calling feature services."""
        plan_result = context.get_result(StageResultRegistry.PLAN_UPGRADE, {})
        plan: dict[str, Any] = plan_result.get("plan", {})
        hooks_plan = plan.get("hooks", [])

        upgraded: list[str] = []
        failed: list[str] = []

        # Group hooks by feature for efficient processing
        hooks_by_feature: dict[str, list[str]] = {}
        for hook_info in hooks_plan:
            feature = hook_info["feature"]
            agent = hook_info["agent"]
            hooks_by_feature.setdefault(feature, []).append(agent)

        # Call each feature's hook update method
        for feature_name, agents in hooks_by_feature.items():
            try:
                # Trigger the feature's update_agent_hooks action
                from open_agent_kit.features.codebase_intelligence.service import execute_hook

                result = execute_hook(
                    "update_agent_hooks",
                    context.project_root,
                    agents=agents,
                )
                if result.get("status") == "success":
                    upgraded.extend(f"{agent} ({feature_name})" for agent in agents)
                else:
                    error_msg = result.get("message", "unknown error")
                    failed.extend(f"{agent} ({feature_name}): {error_msg}" for agent in agents)
            except Exception as e:
                failed.extend(f"{agent} ({feature_name}): {e}" for agent in agents)

        message = format_count_message("Upgraded", len(upgraded), len(failed), "hook")

        return StageOutcome.success(message, data={"upgraded": upgraded, "failed": failed})


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
        plan_result = context.get_result(StageResultRegistry.PLAN_UPGRADE, {})
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
        plan_result = context.get_result(StageResultRegistry.PLAN_UPGRADE, {})
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
        plan_result = context.get_result(StageResultRegistry.PLAN_UPGRADE, {})
        return plan_result.get("has_upgrades", False) and not context.dry_run

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Trigger post-upgrade hooks."""
        feature_service = self._get_feature_service(context)

        # Collect results from all upgrade stages using the typed model
        results = CollectedUpgradeResults.from_context(context)

        try:
            hook_results = feature_service.trigger_post_upgrade_hooks(results.to_dict())
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


def get_upgrade_stages() -> list[BaseStage]:
    """Get upgrade-specific stages (migration work).

    Note: Reconciliation stages (agent commands, settings, skills, hooks) are
    added separately via with_agent_stages(), with_skill_stages(), and
    with_hook_stages() in the upgrade pipeline builder.

    The pattern is: upgrade = migrate() + reconcile(config)
    """
    return [
        ValidateUpgradeEnvironmentStage(),
        PlanUpgradeStage(),
        TriggerPreUpgradeHooksStage(),
        UpgradeStructuralRepairsStage(),
        CleanupLegacyCommandsStage(),  # Remove commands for skills-capable agents
        UpgradeCommandsStage(),  # Upgrades outdated command templates
        # Note: Template upgrade stages removed - templates are read from package
        # Note: UpgradeAgentSettingsStage removed - handled by reconciliation
        # Note: UpgradeHooksStage removed - handled by reconciliation
        UpgradeGitignoreStage(),
        UpgradeSkillsStage(),  # Upgrades outdated skill files
        RunMigrationsStage(),
        UpdateVersionStage(),
        TriggerPostUpgradeHooksStage(),
    ]
