"""Setup stages for pipeline initialization."""

from open_agent_kit.pipeline.context import FlowType, PipelineContext
from open_agent_kit.pipeline.ordering import StageOrder
from open_agent_kit.pipeline.stage import BaseStage, StageOutcome
from open_agent_kit.utils import dir_exists, ensure_dir


class CreateOakDirStage(BaseStage):
    """Create the .oak directory if it doesn't exist."""

    name = "create_oak_dir"
    display_name = "Creating .oak directory"
    order = StageOrder.CREATE_OAK_DIR
    applicable_flows = {FlowType.FRESH_INIT, FlowType.FORCE_REINIT}
    is_critical = True

    def _should_run(self, context: PipelineContext) -> bool:
        """Run if .oak directory doesn't exist or force reinit."""
        if context.flow_type == FlowType.FORCE_REINIT:
            return True
        return not dir_exists(context.oak_dir)

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Create the .oak directory."""
        ensure_dir(context.oak_dir)
        return StageOutcome.success("Created .oak directory")


class ValidateEnvironmentStage(BaseStage):
    """Validate the environment before proceeding."""

    name = "validate_environment"
    display_name = "Validating environment"
    order = StageOrder.VALIDATE_ENVIRONMENT
    is_critical = True

    def _should_run(self, context: PipelineContext) -> bool:
        """Always run validation."""
        return True

    def _execute(self, context: PipelineContext) -> StageOutcome:
        """Validate project root exists and is writable."""
        if not context.project_root.exists():
            return StageOutcome.failed(
                "Project directory does not exist",
                error=f"Path: {context.project_root}",
            )

        # Check if we can write
        test_file = context.project_root / ".oak_test_write"
        try:
            test_file.touch()
            test_file.unlink()
        except PermissionError:
            return StageOutcome.failed(
                "Cannot write to project directory",
                error="Permission denied",
            )

        return StageOutcome.success("Environment validated")


def get_setup_stages() -> list[BaseStage]:
    """Get all setup stages."""
    return [
        ValidateEnvironmentStage(),
        CreateOakDirStage(),
    ]
