"""Tests for pipeline executor."""

from pathlib import Path

from open_agent_kit.pipeline.context import FlowType, PipelineContext, SelectionState
from open_agent_kit.pipeline.executor import (
    Pipeline,
    PipelineBuilder,
    build_init_pipeline,
    build_upgrade_pipeline,
)
from open_agent_kit.pipeline.stage import BaseStage, StageOutcome, StageResult


class MockStage(BaseStage):
    """Mock stage for testing."""

    def __init__(
        self,
        name: str,
        order: int,
        should_run: bool = True,
        outcome: StageOutcome | None = None,
        is_critical: bool = False,
        applicable_flows: set[FlowType] | None = None,
    ):
        self._name = name
        self._display_name = f"Mock: {name}"
        self._order = order
        self._should_run_value = should_run
        self._outcome = outcome or StageOutcome.success(f"{name} completed")
        self._is_critical = is_critical
        self._applicable_flows = applicable_flows

    @property
    def name(self) -> str:
        return self._name

    @property
    def display_name(self) -> str:
        return self._display_name

    @property
    def order(self) -> int:
        return self._order

    @property
    def is_critical(self) -> bool:
        return self._is_critical

    @property
    def applicable_flows(self) -> set[FlowType] | None:
        return self._applicable_flows

    def _should_run(self, context: PipelineContext) -> bool:
        return self._should_run_value

    def _execute(self, context: PipelineContext) -> StageOutcome:
        return self._outcome


class TestPipeline:
    """Tests for Pipeline class."""

    def test_register_stage(self, tmp_path: Path):
        """Test registering a single stage."""
        pipeline = Pipeline()
        stage = MockStage("test", 100)

        pipeline.register(stage)

        assert len(pipeline._stages) == 1

    def test_register_all_stages(self, tmp_path: Path):
        """Test registering multiple stages."""
        pipeline = Pipeline()
        stages = [
            MockStage("stage_a", 100),
            MockStage("stage_b", 200),
            MockStage("stage_c", 150),
        ]

        pipeline.register_all(stages)

        assert len(pipeline._stages) == 3

    def test_stages_sorted_by_order(self, tmp_path: Path):
        """Test that stages are sorted by order when executing."""
        pipeline = Pipeline()
        pipeline.register(MockStage("stage_c", 300))
        pipeline.register(MockStage("stage_a", 100))
        pipeline.register(MockStage("stage_b", 200))

        ordered = pipeline._get_ordered_stages()

        assert [s.name for s in ordered] == ["stage_a", "stage_b", "stage_c"]

    def test_execute_all_stages(self, tmp_path: Path):
        """Test executing pipeline with all stages running."""
        pipeline = Pipeline()
        pipeline.register(MockStage("stage_a", 100))
        pipeline.register(MockStage("stage_b", 200))

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.FRESH_INIT,
        )

        result = pipeline.execute(context)

        assert result.success is True
        assert "stage_a" in result.stages_run
        assert "stage_b" in result.stages_run
        assert len(result.stages_skipped) == 0
        assert len(result.stages_failed) == 0

    def test_skip_stages_that_shouldnt_run(self, tmp_path: Path):
        """Test that stages that shouldn't run are skipped."""
        pipeline = Pipeline()
        pipeline.register(MockStage("stage_a", 100, should_run=True))
        pipeline.register(MockStage("stage_b", 200, should_run=False))

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.FRESH_INIT,
        )

        result = pipeline.execute(context)

        assert result.success is True
        assert "stage_a" in result.stages_run
        assert "stage_b" in result.stages_skipped

    def test_critical_stage_failure_stops_pipeline(self, tmp_path: Path):
        """Test that critical stage failure stops pipeline."""
        pipeline = Pipeline()
        pipeline.register(MockStage("stage_a", 100))
        pipeline.register(
            MockStage(
                "stage_b",
                200,
                outcome=StageOutcome.failed("Critical failure", error="Something broke"),
                is_critical=True,
            )
        )
        pipeline.register(MockStage("stage_c", 300))

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.FRESH_INIT,
        )

        result = pipeline.execute(context)

        assert result.success is False
        assert "stage_a" in result.stages_run
        assert ("stage_b", "Something broke") in result.stages_failed
        assert "stage_c" not in result.stages_run

    def test_non_critical_failure_continues(self, tmp_path: Path):
        """Test that non-critical stage failure doesn't stop pipeline."""
        pipeline = Pipeline()
        pipeline.register(MockStage("stage_a", 100))
        pipeline.register(
            MockStage(
                "stage_b",
                200,
                outcome=StageOutcome.failed("Non-critical failure", error="Minor issue"),
                is_critical=False,
            )
        )
        pipeline.register(MockStage("stage_c", 300))

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.FRESH_INIT,
        )

        result = pipeline.execute(context)

        assert result.success is True  # Continues despite non-critical failure
        assert "stage_a" in result.stages_run
        assert "stage_c" in result.stages_run

    def test_skipped_outcome(self, tmp_path: Path):
        """Test stage returning skipped outcome."""
        pipeline = Pipeline()
        pipeline.register(
            MockStage(
                "stage_a",
                100,
                outcome=StageOutcome.skipped("Not needed"),
            )
        )

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.FRESH_INIT,
        )

        result = pipeline.execute(context)

        assert result.success is True
        assert "stage_a" in result.stages_skipped

    def test_stage_results_stored_in_context(self, tmp_path: Path):
        """Test that stage results are stored in context."""
        pipeline = Pipeline()
        pipeline.register(
            MockStage(
                "stage_a",
                100,
                outcome=StageOutcome.success("Done", data={"key": "value"}),
            )
        )

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.FRESH_INIT,
        )

        pipeline.execute(context)

        assert context.get_result("stage_a") == {"key": "value"}

    def test_get_stage_count(self, tmp_path: Path):
        """Test get_stage_count method."""
        pipeline = Pipeline()
        pipeline.register(MockStage("stage_a", 100, should_run=True))
        pipeline.register(MockStage("stage_b", 200, should_run=False))
        pipeline.register(MockStage("stage_c", 300, should_run=True))

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.FRESH_INIT,
        )

        assert pipeline.get_stage_count(context) == 2

    def test_callbacks(self, tmp_path: Path):
        """Test on_stage_start and on_stage_complete callbacks."""
        started = []
        completed = []

        def on_start(name: str):
            started.append(name)

        def on_complete(name: str, outcome: StageOutcome):
            completed.append((name, outcome.result))

        pipeline = Pipeline(on_stage_start=on_start, on_stage_complete=on_complete)
        pipeline.register(MockStage("stage_a", 100))
        pipeline.register(MockStage("stage_b", 200))

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.FRESH_INIT,
        )

        pipeline.execute(context)

        assert started == ["stage_a", "stage_b"]
        assert len(completed) == 2
        assert completed[0] == ("stage_a", StageResult.SUCCESS)
        assert completed[1] == ("stage_b", StageResult.SUCCESS)

    def test_empty_pipeline(self, tmp_path: Path):
        """Test executing empty pipeline."""
        pipeline = Pipeline()

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.FRESH_INIT,
        )

        result = pipeline.execute(context)

        assert result.success is True
        assert len(result.stages_run) == 0


class TestPipelineBuilder:
    """Tests for PipelineBuilder class."""

    def test_add_single_stage(self):
        """Test adding a single stage."""
        builder = PipelineBuilder()
        stage = MockStage("test", 100)

        builder.add(stage)

        assert len(builder._stages) == 1

    def test_add_all_stages(self):
        """Test adding multiple stages."""
        builder = PipelineBuilder()
        stages = [MockStage("a", 100), MockStage("b", 200)]

        builder.add_all(stages)

        assert len(builder._stages) == 2

    def test_fluent_interface(self):
        """Test fluent interface for chaining."""
        builder = PipelineBuilder().add(MockStage("a", 100)).add(MockStage("b", 200))

        assert len(builder._stages) == 2

    def test_build_returns_pipeline(self):
        """Test build returns Pipeline instance."""
        builder = PipelineBuilder()
        builder.add(MockStage("test", 100))

        pipeline = builder.build()

        assert isinstance(pipeline, Pipeline)
        assert len(pipeline._stages) == 1

    def test_with_setup_stages(self):
        """Test with_setup_stages method."""
        builder = PipelineBuilder().with_setup_stages()

        assert len(builder._stages) > 0

    def test_with_config_stages(self):
        """Test with_config_stages method."""
        builder = PipelineBuilder().with_config_stages()

        assert len(builder._stages) > 0

    def test_with_upgrade_stages(self):
        """Test with_upgrade_stages method."""
        builder = PipelineBuilder().with_upgrade_stages()

        assert len(builder._stages) > 0


class TestBuildInitPipeline:
    """Tests for build_init_pipeline function."""

    def test_returns_pipeline_builder(self):
        """Test that build_init_pipeline returns PipelineBuilder."""
        builder = build_init_pipeline()

        assert isinstance(builder, PipelineBuilder)

    def test_builds_pipeline_with_stages(self):
        """Test that built pipeline has stages."""
        pipeline = build_init_pipeline().build()

        assert len(pipeline._stages) > 0

    def test_stages_are_properly_ordered(self):
        """Test that stages are in correct order."""
        pipeline = build_init_pipeline().build()
        ordered = pipeline._get_ordered_stages()

        # Verify order is monotonically increasing
        prev_order = -1
        for stage in ordered:
            assert stage.order >= prev_order
            prev_order = stage.order

    def test_stage_count_for_fresh_init(self, tmp_path: Path):
        """Test stage count for fresh init flow."""
        pipeline = build_init_pipeline().build()

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.FRESH_INIT,
            selections=SelectionState(
                agents=["claude"],
                ides=["vscode"],
                features=["constitution"],
            ),
        )

        count = pipeline.get_stage_count(context)

        # Should have multiple stages for fresh init
        assert count > 5

    def test_stage_count_for_update(self, tmp_path: Path):
        """Test stage count for update flow with changes."""
        pipeline = build_init_pipeline().build()

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.UPDATE,
            selections=SelectionState(
                agents=["claude", "codex"],
                ides=["vscode"],
                features=["constitution"],
                previous_agents=["claude"],
                previous_ides=["vscode"],
                previous_features=["constitution"],
            ),
        )

        count = pipeline.get_stage_count(context)

        # Should have stages for update flow
        assert count > 0


class TestBuildUpgradePipeline:
    """Tests for build_upgrade_pipeline function."""

    def test_returns_pipeline_builder(self):
        """Test that build_upgrade_pipeline returns PipelineBuilder."""
        builder = build_upgrade_pipeline()

        assert isinstance(builder, PipelineBuilder)

    def test_builds_pipeline_with_stages(self):
        """Test that built pipeline has stages."""
        pipeline = build_upgrade_pipeline().build()

        assert len(pipeline._stages) > 0

    def test_upgrade_stages_present(self):
        """Test that upgrade-specific stages are present."""
        pipeline = build_upgrade_pipeline().build()
        stage_names = {s.name for s in pipeline._stages}

        # Check for key upgrade stages
        assert "plan_upgrade" in stage_names
        assert "upgrade_commands" in stage_names
        # Note: upgrade_templates stage removed - templates are read from package
        assert "upgrade_skills" in stage_names
        assert "run_migrations" in stage_names

    def test_stage_count_for_upgrade(self, tmp_path: Path):
        """Test stage count for upgrade flow."""
        pipeline = build_upgrade_pipeline().build()

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.UPGRADE,
        )

        count = pipeline.get_stage_count(context)

        # Should have multiple upgrade stages
        assert count > 0
