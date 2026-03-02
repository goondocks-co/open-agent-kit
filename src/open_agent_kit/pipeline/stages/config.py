"""Configuration stages for init pipeline."""

from open_agent_kit.constants import VERSION
from open_agent_kit.pipeline.context import FlowType, PipelineContext
from open_agent_kit.pipeline.models import StageResultRegistry
from open_agent_kit.pipeline.ordering import StageOrder
from open_agent_kit.pipeline.stage import BaseStage, StageOutcome


class LoadExistingConfigStage(BaseStage):
    """Load existing configuration for update flows."""

    name = StageResultRegistry.LOAD_EXISTING_CONFIG
    display_name = "Loading existing configuration"
    order = StageOrder.LOAD_EXISTING_CONFIG
    applicable_flows = {FlowType.UPDATE, FlowType.UPGRADE}
    is_critical = True

    def _should_run(self, context: PipelineContext) -> bool:
        """Run for update/upgrade flows."""
        return True

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Load existing config and populate previous state."""
        config_service = self._get_config_service(context)

        if not config_service.config_exists():
            return StageOutcome.failed(
                "No existing configuration found",
                error="Run 'oak init' first",
            )

        config = config_service.load_config()

        # Store previous state for delta calculations
        context.selections.previous_agents = config.agents.copy()
        context.selections.previous_languages = config.languages.installed.copy()

        return StageOutcome.success(
            "Loaded existing configuration",
            data={
                "agents": config.agents,
                "languages": config.languages.installed,
                "version": config.version,
            },
        )


class CreateConfigStage(BaseStage):
    """Create initial configuration for fresh installs."""

    name = "create_config"
    display_name = "Creating configuration"
    order = StageOrder.CREATE_CONFIG
    applicable_flows = {FlowType.FRESH_INIT, FlowType.FORCE_REINIT}
    is_critical = True

    def _should_run(self, context: PipelineContext) -> bool:
        """Run for fresh installs."""
        return True

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Create default configuration."""
        config_service = self._get_config_service(context)

        # Create config with selections
        # Features are always enabled (not user-selectable)
        # Languages come from selections
        config = config_service.create_default_config(
            agents=context.selections.agents,
            languages=context.selections.languages,
        )
        config_service.save_config(config)

        return StageOutcome.success("Created configuration")


class MarkMigrationsCompleteStage(BaseStage):
    """Mark all migrations as complete for fresh installs."""

    name = "mark_migrations_complete"
    display_name = "Marking migrations complete"
    order = StageOrder.MARK_MIGRATIONS_COMPLETE
    applicable_flows = {FlowType.FRESH_INIT}
    is_critical = False

    def _should_run(self, context: PipelineContext) -> bool:
        """Only for fresh installs."""
        return True

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Mark all migrations as already completed."""
        from open_agent_kit.services.migrations import get_migrations

        config_service = self._get_config_service(context)
        all_migration_ids = [mid for mid, _, _ in get_migrations()]

        if all_migration_ids:
            config_service.add_completed_migrations(all_migration_ids)

        return StageOutcome.success(f"Marked {len(all_migration_ids)} migrations complete")


class UpdateAgentConfigStage(BaseStage):
    """Update agent configuration for update flows."""

    name = "update_config_agents"
    display_name = "Updating agent configuration"
    order = StageOrder.UPDATE_CONFIG_AGENTS
    applicable_flows = {FlowType.UPDATE}
    is_critical = True

    def _should_run(self, context: PipelineContext) -> bool:
        """Run if agents changed."""
        return context.selections.has_agent_changes

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Update agent list in config."""
        config_service = self._get_config_service(context)

        # Update agents list
        config_service.update_agents(context.selections.agents)
        config_service.update_config(version=VERSION)

        return StageOutcome.success(
            f"Updated agent configuration ({len(context.selections.agents)} agents)"
        )


class SyncCliCommandStage(BaseStage):
    """Sync cli_command in CI config to match the invoked binary name.

    Detects sys.argv[0] and persists it to .oak/config.yaml so that
    hook and skill installers (which run later) substitute the correct
    binary name. Handles oak-beta and oak-dev editable installs.
    """

    name = "sync_cli_command"
    display_name = "Syncing CLI command"
    order = StageOrder.SYNC_CLI_COMMAND
    applicable_flows = {
        FlowType.FRESH_INIT,
        FlowType.FORCE_REINIT,
        FlowType.UPDATE,
        FlowType.UPGRADE,
    }
    is_critical = False

    def _should_run(self, context: PipelineContext) -> bool:
        return True

    def _execute(self, context: PipelineContext) -> StageOutcome:
        from open_agent_kit.features.codebase_intelligence.cli_command import (
            detect_invoked_cli_command,
        )
        from open_agent_kit.features.codebase_intelligence.config import (
            load_ci_config,
            save_ci_config,
        )
        from open_agent_kit.features.codebase_intelligence.config.ci_config import CIConfig
        from open_agent_kit.features.codebase_intelligence.constants import (
            CI_CLI_COMMAND_DEFAULT,
        )

        detected = detect_invoked_cli_command()

        try:
            ci_config = load_ci_config(context.project_root)
        except (OSError, ValueError, KeyError):
            ci_config = CIConfig()

        if ci_config.cli_command == detected:
            return StageOutcome.skipped(f"CLI command already set to '{detected}'")

        # When detection fell back to the default (e.g. running inside a
        # daemon process where argv[0] is not a real CLI command), preserve
        # an existing non-default value that looks valid — it was set by a
        # real invocation (e.g. "oak-dev").  Still fix obviously broken
        # values like "__main__.py" from a prior bug.
        if (
            detected == CI_CLI_COMMAND_DEFAULT
            and ci_config.cli_command != CI_CLI_COMMAND_DEFAULT
            and not ci_config.cli_command.endswith(".py")
        ):
            return StageOutcome.skipped(f"Keeping configured CLI command '{ci_config.cli_command}'")

        ci_config.cli_command = detected
        save_ci_config(context.project_root, ci_config)
        return StageOutcome.success(f"CLI command set to '{detected}'")


def get_config_stages() -> list[BaseStage]:
    """Get all configuration stages."""
    return [
        LoadExistingConfigStage(),
        CreateConfigStage(),
        MarkMigrationsCompleteStage(),
        UpdateAgentConfigStage(),
        SyncCliCommandStage(),
    ]
