"""Lifecycle hook stages for init pipeline."""

from open_agent_kit.pipeline.context import PipelineContext
from open_agent_kit.pipeline.ordering import StageOrder
from open_agent_kit.pipeline.stage import BaseStage, StageOutcome


class ReconcileFeatureHooksStage(BaseStage):
    """Reconcile feature hook configurations for all agents.

    This stage ensures all configured agents have the required feature
    hook configurations in their instruction files. It's idempotent -
    existing configs are preserved, missing ones are created.

    This is part of the declarative reconciliation pattern:
    ensure reality matches desired config state.
    """

    name = "reconcile_feature_hooks"
    display_name = "Reconciling feature hooks"
    order = StageOrder.TRIGGER_AGENTS_CHANGED
    # Runs for all flows - reconciles actual state to match config
    is_critical = False

    def _should_run(self, context: PipelineContext) -> bool:
        """Run if there are agents and codebase-intelligence is installed.

        We check if codebase-intelligence is in the INSTALLED features (from config),
        not just in selections. This prevents creating hooks when feature installation
        failed (e.g., pip packages failed to install).
        """
        if not context.selections.agents:
            return False

        # Check if codebase-intelligence is actually installed
        config_service = self._get_config_service(context)
        config = config_service.load_config()
        return "codebase-intelligence" in config.features.enabled

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Reconcile feature hooks for all configured agents."""
        # Use the codebase-intelligence hook update mechanism
        # This ensures hook configs exist for all agents
        try:
            from open_agent_kit.features.codebase_intelligence.service import execute_hook

            result = execute_hook(
                "update_agent_hooks",
                context.project_root,
                agents=list(context.selections.agents),
            )

            if result.get("status") == "success":
                updated = result.get("updated", [])
                created = result.get("created", [])
                if updated or created:
                    return StageOutcome.success(
                        f"Reconciled hooks ({len(created)} created, {len(updated)} updated)",
                        data={"created": created, "updated": updated},
                    )
                else:
                    return StageOutcome.success("Feature hooks up to date")
            else:
                return StageOutcome.success(
                    "Feature hooks reconciliation skipped",
                    data={"message": result.get("message", "")},
                )
        except ImportError:
            # Codebase intelligence not available
            return StageOutcome.skipped("No feature hooks to reconcile")


class TriggerInitCompleteStage(BaseStage):
    """Trigger init complete hooks at the end of initialization."""

    name = "trigger_init_complete"
    display_name = "Running initialization hooks"
    order = StageOrder.TRIGGER_INIT_COMPLETE
    is_critical = False

    def _should_run(self, context: PipelineContext) -> bool:
        """Always run at end of init/update."""
        return True

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Trigger on_init_complete hooks."""
        feature_service = self._get_feature_service(context)

        results = feature_service.trigger_init_complete_hooks(
            is_fresh_install=context.is_fresh_install or context.is_force_reinit,
            agents=context.selections.agents,
            features=context.selections.features,
        )

        successful = sum(1 for r in results.values() if r.get("success"))

        return StageOutcome.success(
            f"Ran {successful}/{len(results)} init hooks",
            data={"hook_results": results},
        )


def get_hook_stages() -> list[BaseStage]:
    """Get all hook stages."""
    return [
        ReconcileFeatureHooksStage(),
        TriggerInitCompleteStage(),
    ]
