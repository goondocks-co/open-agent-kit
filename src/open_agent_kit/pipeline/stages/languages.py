"""Language parser installation stages for init pipeline."""

from open_agent_kit.pipeline.context import FlowType, PipelineContext
from open_agent_kit.pipeline.ordering import StageOrder
from open_agent_kit.pipeline.stage import BaseStage, StageLifecycle, StageOutcome


class InstallLanguageParsersStage(BaseStage):
    """Install language parsers for code intelligence."""

    name = "install_language_parsers"
    display_name = "Installing language parsers"
    order = StageOrder.INSTALL_FEATURES  # Reuse the feature stage order
    is_critical = False
    lifecycle = StageLifecycle.INSTALL

    def _should_run(self, context: PipelineContext) -> bool:
        """Run if there are languages to install."""
        if context.is_fresh_install or context.is_force_reinit:
            return bool(context.selections.languages)
        return bool(context.selections.languages_added)

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Install language parsers for selected languages."""
        from open_agent_kit.services.language_service import LanguageService

        language_service = LanguageService(context.project_root)

        # Determine which languages to install
        languages_to_install = (
            context.selections.languages
            if context.is_fresh_install or context.is_force_reinit
            else list(context.selections.languages_added)
        )

        if not languages_to_install:
            return StageOutcome.success("No languages to install")

        # Install parsers
        result = language_service.add_languages(languages_to_install)

        if result.get("success"):
            installed = result.get("installed", [])
            return StageOutcome.success(
                f"Installed {len(installed)} language parser(s)",
                data={"installed": installed},
            )
        else:
            # Non-fatal - parsers can be installed later via oak languages add
            return StageOutcome.success(
                "Language parsers installation incomplete (can be retried with 'oak languages add')",
                data=dict(result),
            )


class RemoveLanguageParsersStage(BaseStage):
    """Remove language parsers that were deselected."""

    name = "remove_language_parsers"
    display_name = "Removing deselected language parsers"
    order = StageOrder.REMOVE_FEATURES  # Reuse the feature stage order
    applicable_flows = {FlowType.UPDATE}
    is_critical = False
    lifecycle = StageLifecycle.CLEANUP
    counterpart_stage = "install_language_parsers"

    def _should_run(self, context: PipelineContext) -> bool:
        """Run if languages were removed."""
        return bool(context.selections.languages_removed)

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Remove deselected language parsers."""
        from open_agent_kit.services.language_service import LanguageService

        language_service = LanguageService(context.project_root)

        languages_to_remove = list(context.selections.languages_removed)
        result = language_service.remove_languages(languages_to_remove)

        removed = result.get("removed", [])
        return StageOutcome.success(
            f"Removed {len(removed)} language parser(s)",
            data={"removed": removed},
        )


def get_language_stages() -> list[BaseStage]:
    """Get all language stages."""
    return [
        RemoveLanguageParsersStage(),
        InstallLanguageParsersStage(),
    ]
