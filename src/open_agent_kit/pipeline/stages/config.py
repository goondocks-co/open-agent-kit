"""Configuration stages for init pipeline."""

from open_agent_kit.constants import VERSION
from open_agent_kit.models.config import AgentCapabilitiesConfig
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
        agent_service = self._get_agent_service(context)

        # Create config with selections
        # Features are always enabled (not user-selectable)
        # Languages come from selections
        config = config_service.create_default_config(
            agents=context.selections.agents,
            languages=context.selections.languages,
        )

        # Build agent capabilities from manifests
        capabilities: dict[str, AgentCapabilitiesConfig] = {}
        for agent_type in context.selections.agents:
            try:
                caps_dict = agent_service.get_capabilities_config(agent_type)
                capabilities[agent_type] = AgentCapabilitiesConfig(**caps_dict)
            except (ValueError, AttributeError):
                pass

        config.agent_capabilities = capabilities
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
        agent_service = self._get_agent_service(context)

        # Update agents list
        config_service.update_agents(context.selections.agents)
        config_service.update_config(version=VERSION)

        # Update agent capabilities
        config = config_service.load_config()

        # Remove capabilities for removed agents
        for agent_type in context.selections.agents_removed:
            config.agent_capabilities.pop(agent_type, None)

        # Add capabilities for new agents
        for agent_type in context.selections.agents_added:
            if agent_type not in config.agent_capabilities:
                try:
                    caps_dict = agent_service.get_capabilities_config(agent_type)
                    config.agent_capabilities[agent_type] = AgentCapabilitiesConfig(**caps_dict)
                except (ValueError, AttributeError):
                    pass

        config_service.save_config(config)

        return StageOutcome.success(
            f"Updated agent configuration ({len(context.selections.agents)} agents)"
        )


def get_config_stages() -> list[BaseStage]:
    """Get all configuration stages."""
    return [
        LoadExistingConfigStage(),
        CreateConfigStage(),
        MarkMigrationsCompleteStage(),
        UpdateAgentConfigStage(),
    ]
