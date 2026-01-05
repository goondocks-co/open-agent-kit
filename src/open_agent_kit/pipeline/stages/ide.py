"""IDE settings stages for init pipeline."""

from open_agent_kit.pipeline.context import FlowType, PipelineContext
from open_agent_kit.pipeline.ordering import StageOrder
from open_agent_kit.pipeline.stage import BaseStage, StageLifecycle, StageOutcome

# Note: InstallCoreIDEAssetsStage was removed.
# IDE assets are now read directly from the installed package - no copying to .oak/ needed.


class RemoveIDESettingsStage(BaseStage):
    """Remove settings for deselected IDEs."""

    name = "remove_ide_settings"
    display_name = "Removing deselected IDE settings"
    order = StageOrder.REMOVE_IDE_SETTINGS
    applicable_flows = {FlowType.UPDATE}
    is_critical = False
    lifecycle = StageLifecycle.CLEANUP
    counterpart_stage = "install_ide_settings"  # Pairs with InstallIDESettingsStage

    def _should_run(self, context: PipelineContext) -> bool:
        """Run if IDEs were removed."""
        return bool(context.selections.ides_removed)

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Remove settings for removed IDEs."""
        from open_agent_kit.constants import IDE_DISPLAY_NAMES

        ide_service = self._get_ide_settings_service(context)

        removed = []
        for ide_type in context.selections.ides_removed:
            if ide_service.remove_settings(ide_type):
                ide_name = IDE_DISPLAY_NAMES.get(ide_type, ide_type.capitalize())
                removed.append(ide_name)

        return StageOutcome.success(
            f"Removed settings for {len(removed)} IDE(s)",
            data={"removed": removed},
        )


class InstallIDESettingsStage(BaseStage):
    """Install settings for selected IDEs."""

    name = "install_ide_settings"
    display_name = "Installing IDE settings"
    order = StageOrder.INSTALL_IDE_SETTINGS
    is_critical = False
    lifecycle = StageLifecycle.INSTALL
    counterpart_stage = "remove_ide_settings"  # Pairs with RemoveIDESettingsStage

    def _should_run(self, context: PipelineContext) -> bool:
        """Run if there are IDEs to configure."""
        return bool(context.selections.ides)

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Install settings for selected IDEs."""
        ide_service = self._get_ide_settings_service(context)

        installed_count = 0
        for ide_type in context.selections.ides:
            if ide_service.install_settings(ide_type):
                installed_count += 1

        if installed_count > 0:
            return StageOutcome.success(f"Installed settings for {installed_count} IDE(s)")
        else:
            return StageOutcome.success("IDE settings already up to date")


def get_ide_stages() -> list[BaseStage]:
    """Get all IDE stages."""
    return [
        RemoveIDESettingsStage(),
        InstallIDESettingsStage(),
    ]
