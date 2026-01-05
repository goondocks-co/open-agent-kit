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
            "Installed features",
            data={"installed": ["constitution", "rfc"]},
        )

        assert outcome.result == StageResult.SUCCESS
        assert outcome.data == {"installed": ["constitution", "rfc"]}

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


class TestFeatureStages:
    """Tests for feature stages."""

    def test_resolve_dependencies_stage_fresh_init(self, tmp_path: Path):
        """Test ResolveDependenciesStage runs for fresh init with features."""
        from open_agent_kit.pipeline.stages.features import ResolveDependenciesStage

        stage = ResolveDependenciesStage()

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.FRESH_INIT,
            selections=SelectionState(features=["constitution", "rfc"]),
        )
        assert stage.should_run(context) is True

    def test_resolve_dependencies_stage_no_features(self, tmp_path: Path):
        """Test ResolveDependenciesStage doesn't run without features."""
        from open_agent_kit.pipeline.stages.features import ResolveDependenciesStage

        stage = ResolveDependenciesStage()

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.FRESH_INIT,
            selections=SelectionState(features=[]),
        )
        assert stage.should_run(context) is False

    def test_remove_features_stage(self, tmp_path: Path):
        """Test RemoveFeaturesStage runs when features removed."""
        from open_agent_kit.pipeline.stages.features import RemoveFeaturesStage

        stage = RemoveFeaturesStage()

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.UPDATE,
            selections=SelectionState(
                features=["constitution"],
                previous_features=["constitution", "rfc"],
            ),
        )
        assert stage.should_run(context) is True

    def test_install_features_stage_update(self, tmp_path: Path):
        """Test InstallFeaturesStage runs when features added."""
        from open_agent_kit.pipeline.stages.features import InstallFeaturesStage

        stage = InstallFeaturesStage()

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.UPDATE,
            selections=SelectionState(
                features=["constitution", "rfc", "issues"],
                previous_features=["constitution", "rfc"],
            ),
        )
        assert stage.should_run(context) is True


class TestIDEStages:
    """Tests for IDE stages."""

    # Note: test_install_core_ide_assets_fresh_init removed.
    # InstallCoreIDEAssetsStage was removed - IDE assets are read from package.

    def test_remove_ide_settings_stage(self, tmp_path: Path):
        """Test RemoveIDESettingsStage runs when IDEs removed."""
        from open_agent_kit.pipeline.stages.ide import RemoveIDESettingsStage

        stage = RemoveIDESettingsStage()

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.UPDATE,
            selections=SelectionState(
                ides=["vscode"],
                previous_ides=["vscode", "cursor"],
            ),
        )
        assert stage.should_run(context) is True

    def test_install_ide_settings_stage(self, tmp_path: Path):
        """Test InstallIDESettingsStage runs when IDEs configured."""
        from open_agent_kit.pipeline.stages.ide import InstallIDESettingsStage

        stage = InstallIDESettingsStage()

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.FRESH_INIT,
            selections=SelectionState(ides=["vscode"]),
        )
        assert stage.should_run(context) is True

    def test_install_ide_settings_stage_no_ides(self, tmp_path: Path):
        """Test InstallIDESettingsStage doesn't run without IDEs."""
        from open_agent_kit.pipeline.stages.ide import InstallIDESettingsStage

        stage = InstallIDESettingsStage()

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.FRESH_INIT,
            selections=SelectionState(ides=[]),
        )
        assert stage.should_run(context) is False


class TestSkillStages:
    """Tests for skill stages."""

    def test_install_skills_stage_fresh_init(self, tmp_path: Path):
        """Test InstallSkillsStage runs for fresh init with features."""
        from open_agent_kit.pipeline.stages.skills import InstallSkillsStage

        stage = InstallSkillsStage()

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.FRESH_INIT,
            selections=SelectionState(features=["constitution"]),
        )
        assert stage.should_run(context) is True

    def test_install_skills_stage_no_features(self, tmp_path: Path):
        """Test InstallSkillsStage doesn't run without features."""
        from open_agent_kit.pipeline.stages.skills import InstallSkillsStage

        stage = InstallSkillsStage()

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.FRESH_INIT,
            selections=SelectionState(features=[]),
        )
        assert stage.should_run(context) is False

    def test_refresh_skills_stage(self, tmp_path: Path):
        """Test RefreshSkillsStage runs when agents added."""
        from open_agent_kit.pipeline.stages.skills import RefreshSkillsStage

        stage = RefreshSkillsStage()

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.UPDATE,
            selections=SelectionState(
                agents=["claude", "codex"],
                previous_agents=["claude"],
            ),
        )
        assert stage.should_run(context) is True


class TestHookStages:
    """Tests for hook stages."""

    def test_trigger_agents_changed_stage(self, tmp_path: Path):
        """Test TriggerAgentsChangedStage runs when agents changed."""
        from open_agent_kit.pipeline.stages.hooks import TriggerAgentsChangedStage

        stage = TriggerAgentsChangedStage()

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.UPDATE,
            selections=SelectionState(
                agents=["claude", "codex"],
                previous_agents=["claude"],
            ),
        )
        assert stage.should_run(context) is True

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

    def test_run_migrations_stage(self, tmp_path: Path):
        """Test RunMigrationsStage runs when migrations pending."""
        from open_agent_kit.pipeline.stages.upgrade import RunMigrationsStage

        stage = RunMigrationsStage()

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.UPGRADE,
            dry_run=False,
        )
        context.set_result(
            "plan_upgrade",
            {
                "plan": {"migrations": [{"id": "test", "description": "Test migration"}]},
                "has_upgrades": True,
            },
        )

        assert stage.should_run(context) is True

    def test_update_version_stage(self, tmp_path: Path):
        """Test UpdateVersionStage runs when version outdated."""
        from open_agent_kit.pipeline.stages.upgrade import UpdateVersionStage

        stage = UpdateVersionStage()

        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.UPGRADE,
            dry_run=False,
        )
        context.set_result(
            "plan_upgrade",
            {
                "plan": {"version_outdated": True},
                "has_upgrades": True,
            },
        )

        assert stage.should_run(context) is True
