"""Tests for pipeline stages."""

from pathlib import Path

from open_agent_kit.pipeline.context import FlowType, PipelineContext, SelectionState
from open_agent_kit.pipeline.stage import StageOutcome, StageResult


class TestStageOutcome:
    """Tests for StageOutcome dataclass."""

    def test_success_outcome(self):
        """Test creating success outcome."""
        outcome = StageOutcome.success("Operation completed")

        assert outcome.result == StageResult.SUCCESS
        assert outcome.message == "Operation completed"
        assert outcome.error is None
        assert outcome.data is None

    def test_success_outcome_with_data(self):
        """Test success outcome with data."""
        outcome = StageOutcome.success(
            "Installed languages",
            data={"installed": ["python", "javascript"]},
        )

        assert outcome.result == StageResult.SUCCESS
        assert outcome.data == {"installed": ["python", "javascript"]}

    def test_skipped_outcome(self):
        """Test creating skipped outcome."""
        outcome = StageOutcome.skipped("Not applicable")

        assert outcome.result == StageResult.SKIPPED
        assert outcome.message == "Not applicable"
        assert outcome.error is None

    def test_failed_outcome(self):
        """Test creating failed outcome."""
        outcome = StageOutcome.failed(
            "Operation failed",
            error="File not found",
        )

        assert outcome.result == StageResult.FAILED
        assert outcome.message == "Operation failed"
        assert outcome.error == "File not found"


class TestBaseStage:
    """Tests for BaseStage abstract class."""

    def test_should_run_checks_flow_type(self, tmp_path: Path):
        """Test that should_run respects applicable_flows."""
        from open_agent_kit.pipeline.stages.config import LoadExistingConfigStage

        stage = LoadExistingConfigStage()

        # UPDATE flow should be applicable
        update_context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.UPDATE,
        )
        assert stage.should_run(update_context) is True

        # FRESH_INIT should not be applicable for LoadExistingConfigStage
        fresh_context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.FRESH_INIT,
        )
        # LoadExistingConfigStage only applies to UPDATE and UPGRADE
        assert stage.should_run(fresh_context) is False


class TestSetupStages:
    """Tests for setup stages."""

    def test_validate_environment_stage(self, tmp_path: Path):
        """Test ValidateEnvironmentStage."""
        from open_agent_kit.pipeline.stages.setup import ValidateEnvironmentStage

        stage = ValidateEnvironmentStage()

        # Should run for fresh init
        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.FRESH_INIT,
        )
        assert stage.should_run(context) is True

    def test_create_oak_dir_stage(self, tmp_path: Path):
        """Test CreateOakDirStage."""
        from open_agent_kit.pipeline.stages.setup import CreateOakDirStage

        stage = CreateOakDirStage()

        # Should run for fresh init
        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.FRESH_INIT,
        )
        assert stage.should_run(context) is True

        # Execute creates directory
        result = stage.execute(context)
        assert result.result == StageResult.SUCCESS
        assert (tmp_path / ".oak").exists()


class TestConfigStages:
    """Tests for config stages."""

    def test_create_config_stage_fresh_init(self, tmp_path: Path):
        """Test CreateConfigStage runs for fresh init."""
        from open_agent_kit.pipeline.stages.config import CreateConfigStage

        stage = CreateConfigStage()

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.FRESH_INIT,
        )
        assert stage.should_run(context) is True

    def test_create_config_stage_update(self, tmp_path: Path):
        """Test CreateConfigStage doesn't run for update."""
        from open_agent_kit.pipeline.stages.config import CreateConfigStage

        stage = CreateConfigStage()

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.UPDATE,
        )
        assert stage.should_run(context) is False

    def test_load_existing_config_stage(self, tmp_path: Path):
        """Test LoadExistingConfigStage runs for update."""
        from open_agent_kit.pipeline.stages.config import LoadExistingConfigStage

        stage = LoadExistingConfigStage()

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.UPDATE,
        )
        assert stage.should_run(context) is True

    def test_update_agent_config_stage_with_changes(self, tmp_path: Path):
        """Test UpdateAgentConfigStage runs when agents changed."""
        from open_agent_kit.pipeline.stages.config import UpdateAgentConfigStage

        stage = UpdateAgentConfigStage()

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.UPDATE,
            selections=SelectionState(
                agents=["claude", "codex"],
                previous_agents=["claude"],
            ),
        )
        assert stage.should_run(context) is True

    def test_update_agent_config_stage_no_changes(self, tmp_path: Path):
        """Test UpdateAgentConfigStage doesn't run when agents unchanged."""
        from open_agent_kit.pipeline.stages.config import UpdateAgentConfigStage

        stage = UpdateAgentConfigStage()

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.UPDATE,
            selections=SelectionState(
                agents=["claude"],
                previous_agents=["claude"],
            ),
        )
        assert stage.should_run(context) is False


class TestAgentStages:
    """Tests for agent stages."""

    def test_remove_agent_commands_stage(self, tmp_path: Path):
        """Test RemoveAgentCommandsStage runs when agents removed."""
        from open_agent_kit.pipeline.stages.agents import RemoveAgentCommandsStage

        stage = RemoveAgentCommandsStage()

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.UPDATE,
            selections=SelectionState(
                agents=["claude"],
                previous_agents=["claude", "copilot"],
            ),
        )
        assert stage.should_run(context) is True

    def test_install_agent_commands_stage(self, tmp_path: Path):
        """Test InstallAgentCommandsStage runs when agents added."""
        from open_agent_kit.pipeline.stages.agents import InstallAgentCommandsStage

        stage = InstallAgentCommandsStage()

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.UPDATE,
            selections=SelectionState(
                agents=["claude", "codex"],
                previous_agents=["claude"],
            ),
        )
        assert stage.should_run(context) is True


class TestLanguageStages:
    """Tests for language stages."""

    def test_install_language_parsers_stage_fresh_init(self, tmp_path: Path):
        """Test InstallLanguageParsersStage runs for fresh init with languages."""
        from open_agent_kit.pipeline.stages.languages import InstallLanguageParsersStage

        stage = InstallLanguageParsersStage()

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.FRESH_INIT,
            selections=SelectionState(languages=["python", "javascript"]),
        )
        assert stage.should_run(context) is True

    def test_install_language_parsers_stage_no_languages(self, tmp_path: Path):
        """Test InstallLanguageParsersStage doesn't run without languages."""
        from open_agent_kit.pipeline.stages.languages import InstallLanguageParsersStage

        stage = InstallLanguageParsersStage()

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.FRESH_INIT,
            selections=SelectionState(languages=[]),
        )
        assert stage.should_run(context) is False

    def test_remove_language_parsers_stage(self, tmp_path: Path):
        """Test RemoveLanguageParsersStage runs when languages removed."""
        from open_agent_kit.pipeline.stages.languages import RemoveLanguageParsersStage

        stage = RemoveLanguageParsersStage()

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.UPDATE,
            selections=SelectionState(
                languages=["python"],
                previous_languages=["python", "javascript"],
            ),
        )
        assert stage.should_run(context) is True

    def test_install_language_parsers_stage_update(self, tmp_path: Path):
        """Test InstallLanguageParsersStage runs when languages added."""
        from open_agent_kit.pipeline.stages.languages import InstallLanguageParsersStage

        stage = InstallLanguageParsersStage()

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.UPDATE,
            selections=SelectionState(
                languages=["python", "javascript", "typescript"],
                previous_languages=["python", "javascript"],
            ),
        )
        assert stage.should_run(context) is True


class TestSkillStages:
    """Tests for skill stages."""

    def test_reconcile_skills_stage_with_agents(self, tmp_path: Path):
        """Test ReconcileSkillsStage runs when agents are configured.

        All features are always enabled, so we just check for agents.
        """
        from open_agent_kit.pipeline.stages.skills import ReconcileSkillsStage

        stage = ReconcileSkillsStage()

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.FRESH_INIT,
            selections=SelectionState(agents=["claude"]),
        )
        assert stage.should_run(context) is True

    def test_reconcile_skills_stage_no_agents(self, tmp_path: Path):
        """Test ReconcileSkillsStage doesn't run without agents."""
        from open_agent_kit.pipeline.stages.skills import ReconcileSkillsStage

        stage = ReconcileSkillsStage()

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.FRESH_INIT,
            selections=SelectionState(agents=[]),
        )
        assert stage.should_run(context) is False

    def test_reconcile_skills_stage_runs_for_all_flows(self, tmp_path: Path):
        """Test ReconcileSkillsStage runs for any flow type with agents."""
        from open_agent_kit.pipeline.stages.skills import ReconcileSkillsStage

        stage = ReconcileSkillsStage()

        # Should run for UPDATE flow as well (declarative reconciliation)
        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.UPDATE,
            selections=SelectionState(agents=["claude"]),
        )
        assert stage.should_run(context) is True


class TestHookStages:
    """Tests for hook stages."""

    def test_reconcile_feature_hooks_stage(self, tmp_path: Path):
        """Test ReconcileFeatureHooksStage runs when agents are configured.

        All features including codebase-intelligence are always enabled,
        so we just need to check if agents are present.
        """
        from open_agent_kit.pipeline.stages.hooks import ReconcileFeatureHooksStage

        stage = ReconcileFeatureHooksStage()

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.UPDATE,
            selections=SelectionState(
                agents=["claude", "codex"],
            ),
        )
        assert stage.should_run(context) is True

    def test_reconcile_feature_hooks_stage_no_agents(self, tmp_path: Path):
        """Test ReconcileFeatureHooksStage doesn't run without agents."""
        from open_agent_kit.pipeline.stages.hooks import ReconcileFeatureHooksStage

        stage = ReconcileFeatureHooksStage()

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.UPDATE,
            selections=SelectionState(
                agents=[],
            ),
        )
        assert stage.should_run(context) is False

    def test_trigger_init_complete_stage(self, tmp_path: Path):
        """Test TriggerInitCompleteStage always runs."""
        from open_agent_kit.pipeline.stages.hooks import TriggerInitCompleteStage

        stage = TriggerInitCompleteStage()

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.FRESH_INIT,
        )
        assert stage.should_run(context) is True


class TestUpgradeStages:
    """Tests for upgrade stages."""

    def test_validate_upgrade_environment_stage(self, tmp_path: Path):
        """Test ValidateUpgradeEnvironmentStage."""
        from open_agent_kit.pipeline.stages.upgrade import ValidateUpgradeEnvironmentStage

        stage = ValidateUpgradeEnvironmentStage()

        # Should run when no plan is pre-populated
        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.UPGRADE,
        )
        assert stage.should_run(context) is True

        # Should skip when plan is pre-populated
        context.set_result("plan_upgrade", {"plan": {}, "has_upgrades": True})
        assert stage.should_run(context) is False

    def test_plan_upgrade_stage(self, tmp_path: Path):
        """Test PlanUpgradeStage."""
        from open_agent_kit.pipeline.stages.upgrade import PlanUpgradeStage

        stage = PlanUpgradeStage()

        # Should run when no plan is pre-populated
        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.UPGRADE,
        )
        assert stage.should_run(context) is True

        # Should skip when plan is pre-populated
        context.set_result("plan_upgrade", {"plan": {}, "has_upgrades": True})
        assert stage.should_run(context) is False

    def test_upgrade_commands_stage_dry_run(self, tmp_path: Path):
        """Test UpgradeCommandsStage skips in dry-run mode."""
        from open_agent_kit.pipeline.stages.upgrade import UpgradeCommandsStage

        stage = UpgradeCommandsStage()

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.UPGRADE,
            dry_run=True,
        )
        context.set_result(
            "plan_upgrade",
            {
                "plan": {"commands": [{"file": "test.md"}]},
                "has_upgrades": True,
            },
        )

        assert stage.should_run(context) is False

    def test_upgrade_commands_stage_no_dry_run(self, tmp_path: Path):
        """Test UpgradeCommandsStage runs when not dry-run."""
        from open_agent_kit.pipeline.stages.upgrade import UpgradeCommandsStage

        stage = UpgradeCommandsStage()

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.UPGRADE,
            dry_run=False,
        )
        context.set_result(
            "plan_upgrade",
            {
                "plan": {"commands": [{"file": "test.md"}]},
                "has_upgrades": True,
            },
        )

        assert stage.should_run(context) is True

    def test_upgrade_commands_stage_no_commands(self, tmp_path: Path):
        """Test UpgradeCommandsStage skips when no commands to upgrade."""
        from open_agent_kit.pipeline.stages.upgrade import UpgradeCommandsStage

        stage = UpgradeCommandsStage()

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.UPGRADE,
            dry_run=False,
        )
        context.set_result(
            "plan_upgrade",
            {
                "plan": {"commands": []},
                "has_upgrades": True,
            },
        )

        assert stage.should_run(context) is False
