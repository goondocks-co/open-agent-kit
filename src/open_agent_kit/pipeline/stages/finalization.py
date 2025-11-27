"""Finalization stages for init pipeline."""

from open_agent_kit.constants import VERSION
from open_agent_kit.pipeline.context import FlowType, PipelineContext
from open_agent_kit.pipeline.ordering import StageOrder
from open_agent_kit.pipeline.stage import BaseStage, StageOutcome


class EnsureGitignoreStage(BaseStage):
    """Ensure .gitignore has appropriate entries."""

    name = "ensure_gitignore"
    display_name = "Updating .gitignore"
    order = StageOrder.ENSURE_GITIGNORE
    applicable_flows = {FlowType.FRESH_INIT, FlowType.FORCE_REINIT}
    is_critical = False

    def _should_run(self, context: PipelineContext) -> bool:
        """Run for fresh installs."""
        return True

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Ensure .gitignore has issue context entries."""
        from open_agent_kit.utils import ensure_gitignore_has_issue_context

        try:
            ensure_gitignore_has_issue_context(context.project_root)
            return StageOutcome.success("Updated .gitignore")
        except Exception as e:
            # Not critical, just log warning
            context.add_warning(self.name, str(e))
            return StageOutcome.success("Skipped .gitignore update")


class UpdateVersionStage(BaseStage):
    """Update config version after changes."""

    name = "update_version"
    display_name = "Updating configuration version"
    order = StageOrder.UPDATE_VERSION
    applicable_flows = {FlowType.UPDATE, FlowType.UPGRADE}
    is_critical = False

    def _should_run(self, context: PipelineContext) -> bool:
        """Run if any changes were made."""
        return context.selections.has_any_changes

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Update config version."""
        config_service = self._get_config_service(context)
        config_service.update_config(version=VERSION)

        return StageOutcome.success(f"Updated to version {VERSION}")


def get_finalization_stages() -> list[BaseStage]:
    """Get all finalization stages."""
    return [
        EnsureGitignoreStage(),
        UpdateVersionStage(),
    ]
