"""Pipeline executor for running stages in order."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from open_agent_kit.pipeline.context import PipelineContext
from open_agent_kit.pipeline.stage import Stage, StageOutcome, StageResult

if TYPE_CHECKING:
    from open_agent_kit.utils.step_tracker import StepTracker


@dataclass
class PipelineResult:
    """Result of pipeline execution.

    Attributes:
        success: Whether pipeline completed successfully
        stages_run: List of stage names that executed
        stages_skipped: List of stage names that were skipped
        stages_failed: List of (stage_name, error) tuples for failures
        context: Final pipeline context with all results
    """

    success: bool
    stages_run: list[str] = field(default_factory=list)
    stages_skipped: list[str] = field(default_factory=list)
    stages_failed: list[tuple[str, str]] = field(default_factory=list)
    context: PipelineContext | None = None


class Pipeline:
    """Executes stages in order with progress tracking.

    The pipeline:
    1. Collects all registered stages
    2. Sorts by order
    3. Filters by should_run()
    4. Executes each stage
    5. Tracks progress via StepTracker
    6. Stops on critical stage failure

    Example:
        >>> pipeline = Pipeline()
        >>> pipeline.register(CreateOakDirStage())
        >>> pipeline.register(ConfigStage())
        >>> pipeline.register(AgentSetupStage())
        >>>
        >>> context = PipelineContext(
        ...     project_root=Path.cwd(),
        ...     flow_type=FlowType.FRESH_INIT,
        ... )
        >>> result = pipeline.execute(context)
        >>> if result.success:
        ...     print("Init complete!")
    """

    def __init__(
        self,
        on_stage_start: Callable[[str], None] | None = None,
        on_stage_complete: Callable[[str, StageOutcome], None] | None = None,
    ):
        """Initialize pipeline.

        Args:
            on_stage_start: Callback when stage starts (for custom progress)
            on_stage_complete: Callback when stage completes
        """
        self._stages: list[Stage] = []
        self._on_stage_start = on_stage_start
        self._on_stage_complete = on_stage_complete

    def register(self, stage: Stage) -> "Pipeline":
        """Register a stage with the pipeline.

        Args:
            stage: Stage instance to register

        Returns:
            Self for chaining
        """
        self._stages.append(stage)
        return self

    def register_all(self, stages: list[Stage]) -> "Pipeline":
        """Register multiple stages.

        Args:
            stages: List of stage instances

        Returns:
            Self for chaining
        """
        for stage in stages:
            self.register(stage)
        return self

    def _get_ordered_stages(self) -> list[Stage]:
        """Get stages sorted by execution order."""
        return sorted(self._stages, key=lambda s: s.order)

    def _get_runnable_stages(self, context: PipelineContext) -> list[Stage]:
        """Get stages that should run for this context."""
        ordered = self._get_ordered_stages()
        return [s for s in ordered if s.should_run(context)]

    def execute(
        self,
        context: PipelineContext,
        tracker: "StepTracker | None" = None,
    ) -> PipelineResult:
        """Execute the pipeline.

        Args:
            context: Pipeline context with configuration
            tracker: Optional StepTracker for progress UI

        Returns:
            PipelineResult with execution details
        """
        result = PipelineResult(success=True, context=context)

        # Get stages that will run
        runnable_stages = self._get_runnable_stages(context)
        all_stages = self._get_ordered_stages()

        # Track skipped stages (those that won't run)
        runnable_names = {s.name for s in runnable_stages}
        for stage in all_stages:
            if stage.name not in runnable_names:
                result.stages_skipped.append(stage.name)

        if not runnable_stages:
            return result

        # Execute each stage
        for stage in runnable_stages:
            # Notify start
            if self._on_stage_start:
                self._on_stage_start(stage.name)

            if tracker:
                tracker.start_step(stage.display_name)

            # Execute stage
            outcome = stage.execute(context)

            # Store result in context
            if outcome.data:
                context.set_result(stage.name, outcome.data)

            # Notify completion
            if self._on_stage_complete:
                self._on_stage_complete(stage.name, outcome)

            # Handle outcome
            if outcome.result == StageResult.SUCCESS:
                result.stages_run.append(stage.name)
                if tracker:
                    tracker.complete_step(outcome.message)

            elif outcome.result == StageResult.SKIPPED:
                result.stages_skipped.append(stage.name)
                if tracker:
                    tracker.skip_step(outcome.message)

            elif outcome.result == StageResult.FAILED:
                result.stages_failed.append((stage.name, outcome.error or outcome.message))
                if tracker:
                    tracker.fail_step(outcome.message, outcome.error)

                # Stop on critical stage failure
                if getattr(stage, "is_critical", True):
                    result.success = False
                    break

        return result

    def get_stage_count(self, context: PipelineContext) -> int:
        """Get count of stages that will run for this context.

        Useful for initializing StepTracker with correct step count.
        """
        return len(self._get_runnable_stages(context))


class PipelineBuilder:
    """Builder for constructing pipelines with stage groups.

    Provides a fluent interface for building pipelines with
    logical stage groupings.

    Example:
        >>> builder = PipelineBuilder()
        >>> pipeline = (
        ...     builder
        ...     .with_setup_stages()
        ...     .with_config_stages()
        ...     .with_agent_stages()
        ...     .with_feature_stages()
        ...     .with_skill_stages()
        ...     .with_hook_stages()
        ...     .with_finalization_stages()
        ...     .build()
        ... )
    """

    def __init__(self) -> None:
        self._stages: list[Stage] = []

    def add(self, stage: Stage) -> "PipelineBuilder":
        """Add a single stage."""
        self._stages.append(stage)
        return self

    def add_all(self, stages: Sequence[Stage]) -> "PipelineBuilder":
        """Add multiple stages."""
        self._stages.extend(stages)
        return self

    def with_setup_stages(self) -> "PipelineBuilder":
        """Add setup stages (directory creation, etc.)."""
        from open_agent_kit.pipeline.stages.setup import get_setup_stages

        return self.add_all(get_setup_stages())

    def with_config_stages(self) -> "PipelineBuilder":
        """Add configuration stages."""
        from open_agent_kit.pipeline.stages.config import get_config_stages

        return self.add_all(get_config_stages())

    def with_agent_stages(self) -> "PipelineBuilder":
        """Add agent setup stages."""
        from open_agent_kit.pipeline.stages.agents import get_agent_stages

        return self.add_all(get_agent_stages())

    def with_feature_stages(self) -> "PipelineBuilder":
        """Add feature installation stages."""
        from open_agent_kit.pipeline.stages.features import get_feature_stages

        return self.add_all(get_feature_stages())

    def with_skill_stages(self) -> "PipelineBuilder":
        """Add skill installation stages."""
        from open_agent_kit.pipeline.stages.skills import get_skill_stages

        return self.add_all(get_skill_stages())

    def with_hook_stages(self) -> "PipelineBuilder":
        """Add lifecycle hook stages."""
        from open_agent_kit.pipeline.stages.hooks import get_hook_stages

        return self.add_all(get_hook_stages())

    def with_mcp_stages(self) -> "PipelineBuilder":
        """Add MCP server registration stages."""
        from open_agent_kit.pipeline.stages.mcp import get_mcp_stages

        return self.add_all(get_mcp_stages())

    def with_finalization_stages(self) -> "PipelineBuilder":
        """Add finalization stages (migrations, cleanup)."""
        from open_agent_kit.pipeline.stages.finalization import get_finalization_stages

        return self.add_all(get_finalization_stages())

    def with_upgrade_stages(self) -> "PipelineBuilder":
        """Add upgrade-specific stages."""
        from open_agent_kit.pipeline.stages.upgrade import get_upgrade_stages

        return self.add_all(get_upgrade_stages())

    def with_removal_stages(self) -> "PipelineBuilder":
        """Add removal stages for oak remove."""
        from open_agent_kit.pipeline.stages.removal import get_removal_stages

        return self.add_all(get_removal_stages())

    def validate_lifecycle_pairs(self) -> list[str]:
        """Validate that INSTALL stages have their CLEANUP counterparts.

        Returns:
            List of warning messages for missing counterparts
        """
        from open_agent_kit.pipeline.stage import StageLifecycle

        warnings: list[str] = []
        stage_names = {s.name for s in self._stages}

        for stage in self._stages:
            # Check if this stage has lifecycle and counterpart attributes
            lifecycle = getattr(stage, "lifecycle", StageLifecycle.NEUTRAL)
            counterpart = getattr(stage, "counterpart_stage", None)

            # INSTALL stages must have a counterpart defined
            if lifecycle == StageLifecycle.INSTALL and counterpart is None:
                warnings.append(
                    f"Stage '{stage.name}' has INSTALL lifecycle but no counterpart_stage defined"
                )

            # If counterpart is defined, it must exist in the pipeline
            if counterpart and counterpart not in stage_names:
                warnings.append(
                    f"Stage '{stage.name}' has counterpart '{counterpart}' but it's not in the pipeline"
                )

        return warnings

    def build(
        self,
        on_stage_start: Callable[[str], None] | None = None,
        on_stage_complete: Callable[[str, StageOutcome], None] | None = None,
        validate_pairs: bool = True,
    ) -> Pipeline:
        """Build the pipeline with all registered stages.

        Args:
            on_stage_start: Optional callback when stage starts
            on_stage_complete: Optional callback when stage completes
            validate_pairs: Whether to validate install/cleanup pairs (default True)

        Returns:
            Configured Pipeline instance

        Raises:
            ValueError: If validate_pairs is True and there are missing counterparts
        """
        if validate_pairs:
            warnings = self.validate_lifecycle_pairs()
            if warnings:
                # Log warnings but don't fail - this is a development aid
                import logging

                logger = logging.getLogger(__name__)
                for warning in warnings:
                    logger.warning(f"Pipeline lifecycle warning: {warning}")

        pipeline = Pipeline(
            on_stage_start=on_stage_start,
            on_stage_complete=on_stage_complete,
        )
        pipeline.register_all(self._stages)
        return pipeline


def build_init_pipeline() -> PipelineBuilder:
    """Build the standard init pipeline with all stages.

    Returns a PipelineBuilder pre-configured with all init stages.
    Call .build() to get the Pipeline instance.

    Example:
        >>> pipeline = build_init_pipeline().build()
        >>> result = pipeline.execute(context)
    """
    return (
        PipelineBuilder()
        .with_setup_stages()
        .with_config_stages()
        .with_agent_stages()
        .with_feature_stages()
        .with_skill_stages()
        .with_hook_stages()
        .with_mcp_stages()
        .with_finalization_stages()
    )


def build_upgrade_pipeline() -> PipelineBuilder:
    """Build the upgrade pipeline with upgrade stages + reconciliation.

    Returns a PipelineBuilder pre-configured with all upgrade stages.
    Call .build() to get the Pipeline instance.

    The upgrade pipeline follows the pattern:
        upgrade = migrate() + reconcile(config)

    It handles:
    1. Upgrade-specific work:
       - Environment validation
       - Upgrade planning
       - Pre-upgrade hooks
       - Migrations and structural repairs
       - Post-upgrade hooks
       - Version updates

    2. Reconciliation (same as init):
       - Ensure agent commands match config
       - Ensure agent settings match config
       - Ensure skills match config

    Example:
        >>> pipeline = build_upgrade_pipeline().build()
        >>> result = pipeline.execute(context)
    """
    return (
        PipelineBuilder()
        .with_upgrade_stages()  # Migrate: migrations, structural repairs, version
        .with_agent_stages()  # Reconcile: agent commands and settings
        .with_skill_stages()  # Reconcile: skills
        .with_hook_stages()  # Reconcile: feature hooks
        .with_mcp_stages()  # Reconcile: MCP server registrations
    )


def build_remove_pipeline() -> PipelineBuilder:
    """Build the removal pipeline for oak remove.

    Returns a PipelineBuilder pre-configured with all removal stages.
    Call .build() to get the Pipeline instance.

    The removal pipeline handles:
    - Environment validation
    - Removal planning (via state tracking)
    - Pre-remove hooks
    - Skill removal
    - Created file removal
    - Directory cleanup
    - .oak directory removal

    Example:
        >>> pipeline = build_remove_pipeline().build()
        >>> result = pipeline.execute(context)
    """
    return PipelineBuilder().with_removal_stages()
