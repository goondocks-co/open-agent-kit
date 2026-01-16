"""Agent setup stages for init pipeline."""

from open_agent_kit.pipeline.context import FlowType, PipelineContext
from open_agent_kit.pipeline.models import StageResultRegistry
from open_agent_kit.pipeline.ordering import StageOrder
from open_agent_kit.pipeline.stage import BaseStage, StageLifecycle, StageOutcome


class RemoveAgentCommandsStage(BaseStage):
    """Remove commands for deselected agents."""

    name = StageResultRegistry.REMOVE_AGENT_COMMANDS
    display_name = "Removing deselected agent commands"
    order = StageOrder.REMOVE_AGENT_COMMANDS
    applicable_flows = {FlowType.UPDATE}
    is_critical = False
    lifecycle = StageLifecycle.CLEANUP
    counterpart_stage = StageResultRegistry.INSTALL_AGENT_COMMANDS

    def _should_run(self, context: PipelineContext) -> bool:
        """Run if agents were removed."""
        return bool(context.selections.agents_removed)

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Remove commands for removed agents."""
        agent_service = self._get_agent_service(context)

        removed_count = 0
        for agent_type in context.selections.agents_removed:
            count = agent_service.remove_agent_commands(agent_type)
            removed_count += count

        return StageOutcome.success(
            f"Removed {removed_count} command(s) for {len(context.selections.agents_removed)} agent(s)",
            data={"removed_count": removed_count},
        )


class CleanupObsoleteCommandsStage(BaseStage):
    """Remove obsolete oak commands that no longer exist in feature config.

    When commands are renamed or removed from features, this stage cleans up
    the old command files from agent directories. Only removes oak.* prefixed
    files that don't match any current feature command.
    """

    name = StageResultRegistry.CLEANUP_OBSOLETE_COMMANDS
    display_name = "Cleaning up obsolete commands"
    order = StageOrder.REMOVE_AGENT_COMMANDS + 1  # After agent removal, before install
    # Runs for all flows - ensures obsolete commands are cleaned up
    is_critical = False
    lifecycle = StageLifecycle.CLEANUP

    def _should_run(self, context: PipelineContext) -> bool:
        """Run if there are agents configured."""
        return bool(context.selections.agents)

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Remove obsolete commands from all configured agents."""
        agent_service = self._get_agent_service(context)

        # Get all valid command names from feature config
        valid_commands = set(agent_service.get_all_command_names())

        removed_total = 0
        for agent_type in context.selections.agents:
            removed = agent_service.remove_obsolete_commands(agent_type, valid_commands)
            removed_total += len(removed)

        if removed_total > 0:
            return StageOutcome.success(
                f"Removed {removed_total} obsolete command(s)",
                data={"removed_count": removed_total},
            )

        return StageOutcome.success("No obsolete commands found")


class InstallAgentCommandsStage(BaseStage):
    """Install feature commands for all configured agents.

    This stage ensures all configured agents have the required feature commands.
    It's idempotent - existing commands are preserved, missing ones are created.
    """

    name = StageResultRegistry.INSTALL_AGENT_COMMANDS
    display_name = "Installing agent commands"
    order = StageOrder.INSTALL_AGENT_COMMANDS
    # Runs for all flows - reconciles actual state to match config
    is_critical = False
    lifecycle = StageLifecycle.INSTALL
    counterpart_stage = StageResultRegistry.REMOVE_AGENT_COMMANDS

    def _should_run(self, context: PipelineContext) -> bool:
        """Run if there are agents to configure."""
        return bool(context.selections.agents)

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Install feature commands for all configured agents."""
        config_service = self._get_config_service(context)
        feature_service = self._get_feature_service(context)

        # Get installed features
        installed_features = config_service.get_features()

        # Reconcile: ensure all agents have commands for all features
        # install_feature is idempotent - skips existing commands
        for feature_name in installed_features:
            feature_service.install_feature(feature_name, list(context.selections.agents))

        return StageOutcome.success(
            f"Reconciled commands for {len(context.selections.agents)} agent(s)",
            data={
                "agents": list(context.selections.agents),
                "features": installed_features,
            },
        )


class RemoveAgentSettingsStage(BaseStage):
    """Remove auto-approval settings for deselected agents."""

    name = StageResultRegistry.REMOVE_AGENT_SETTINGS
    display_name = "Removing deselected agent settings"
    order = StageOrder.REMOVE_AGENT_SETTINGS
    applicable_flows = {FlowType.UPDATE}
    is_critical = False
    lifecycle = StageLifecycle.CLEANUP
    counterpart_stage = StageResultRegistry.INSTALL_AGENT_SETTINGS

    def _should_run(self, context: PipelineContext) -> bool:
        """Run if agents were removed."""
        return bool(context.selections.agents_removed)

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Remove settings for removed agents."""
        agent_settings_service = self._get_agent_settings_service(context)

        results = agent_settings_service.remove_settings_for_agents(
            list(context.selections.agents_removed)
        )

        removed_count = sum(1 for success in results.values() if success)

        return StageOutcome.success(
            f"Removed settings for {removed_count} agent(s)",
            data={"removed": [a for a, s in results.items() if s]},
        )


class InstallAgentSettingsStage(BaseStage):
    """Install auto-approval settings for selected agents.

    This installs OAK command auto-approval settings in each agent's
    native settings file (e.g., .claude/settings.local.json).
    """

    name = StageResultRegistry.INSTALL_AGENT_SETTINGS
    display_name = "Installing agent settings"
    order = StageOrder.INSTALL_AGENT_SETTINGS
    is_critical = False
    lifecycle = StageLifecycle.INSTALL
    counterpart_stage = StageResultRegistry.REMOVE_AGENT_SETTINGS

    def _should_run(self, context: PipelineContext) -> bool:
        """Run if there are agents to configure."""
        return bool(context.selections.agents)

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Install settings for selected agents."""
        agent_settings_service = self._get_agent_settings_service(context)

        results = agent_settings_service.install_settings_for_agents(
            list(context.selections.agents)
        )

        installed_count = sum(1 for success in results.values() if success)

        if installed_count > 0:
            return StageOutcome.success(
                f"Installed auto-approval settings for {installed_count} agent(s)",
                data={"installed": [a for a, s in results.items() if s]},
            )
        else:
            return StageOutcome.success("Agent settings already up to date")


def get_agent_stages() -> list[BaseStage]:
    """Get all agent stages."""
    return [
        RemoveAgentCommandsStage(),
        CleanupObsoleteCommandsStage(),
        InstallAgentCommandsStage(),
        RemoveAgentSettingsStage(),
        InstallAgentSettingsStage(),
    ]
