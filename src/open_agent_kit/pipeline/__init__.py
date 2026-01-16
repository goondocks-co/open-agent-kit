"""Stage-based pipeline for init/upgrade flows.

This module provides a clean, extensible architecture for the init and upgrade
commands using a stage-based pipeline pattern.

Example:
    >>> from open_agent_kit.pipeline import (
    ...     PipelineContext,
    ...     FlowType,
    ...     build_init_pipeline,
    ... )
    >>>
    >>> context = PipelineContext(
    ...     project_root=Path.cwd(),
    ...     flow_type=FlowType.FRESH_INIT,
    ... )
    >>> context.selections.agents = ["claude", "cursor"]
    >>> context.selections.features = ["rfc", "plan"]
    >>>
    >>> pipeline = build_init_pipeline().build()
    >>> result = pipeline.execute(context)
    >>> if result.success:
    ...     print("Init complete!")
"""

from open_agent_kit.pipeline.context import (
    FlowType,
    PipelineContext,
    SelectionState,
)
from open_agent_kit.pipeline.executor import (
    Pipeline,
    PipelineBuilder,
    PipelineResult,
    build_init_pipeline,
)
from open_agent_kit.pipeline.models import (
    CategoryResult,
    CollectedUpgradeResults,
    PlanUpgradeData,
    ProcessingResult,
    UpgradeStageData,
    plan_has_upgrades,
)
from open_agent_kit.pipeline.ordering import StageOrder
from open_agent_kit.pipeline.stage import (
    BaseStage,
    Stage,
    StageLifecycle,
    StageOutcome,
    StageResult,
)
from open_agent_kit.pipeline.utils import format_count_message, process_items

__all__ = [
    # Context
    "FlowType",
    "PipelineContext",
    "SelectionState",
    # Executor
    "Pipeline",
    "PipelineBuilder",
    "PipelineResult",
    "build_init_pipeline",
    # Stage
    "BaseStage",
    "Stage",
    "StageLifecycle",
    "StageOutcome",
    "StageResult",
    # Ordering
    "StageOrder",
    # Models
    "CategoryResult",
    "CollectedUpgradeResults",
    "PlanUpgradeData",
    "ProcessingResult",
    "UpgradeStageData",
    "plan_has_upgrades",
    # Utils
    "format_count_message",
    "process_items",
]
