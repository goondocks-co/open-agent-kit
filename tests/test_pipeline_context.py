"""Tests for pipeline context and selection state."""

from pathlib import Path

from open_agent_kit.pipeline.context import FlowType, PipelineContext, SelectionState


class TestFlowType:
    """Tests for FlowType enum."""

    def test_flow_type_values(self):
        """Test flow type enum values."""
        assert FlowType.FRESH_INIT.value == "fresh_init"
        assert FlowType.UPDATE.value == "update"
        assert FlowType.UPGRADE.value == "upgrade"
        assert FlowType.FORCE_REINIT.value == "force_reinit"


class TestSelectionState:
    """Tests for SelectionState dataclass."""

    def test_default_empty_state(self):
        """Test default empty state."""
        state = SelectionState()

        assert state.agents == []
        assert state.languages == []
        assert state.previous_agents == []
        assert state.previous_languages == []

    def test_agents_added(self):
        """Test agents_added property."""
        state = SelectionState(
            agents=["claude", "codex"],
            previous_agents=["claude"],
        )

        assert state.agents_added == {"codex"}

    def test_agents_removed(self):
        """Test agents_removed property."""
        state = SelectionState(
            agents=["claude"],
            previous_agents=["claude", "vscode-copilot"],
        )

        assert state.agents_removed == {"vscode-copilot"}

    def test_agents_no_change(self):
        """Test when no agents changed."""
        state = SelectionState(
            agents=["claude", "codex"],
            previous_agents=["codex", "claude"],  # Same agents, different order
        )

        assert state.agents_added == set()
        assert state.agents_removed == set()
        assert not state.has_agent_changes

    def test_languages_added(self):
        """Test languages_added property."""
        state = SelectionState(
            languages=["python", "javascript", "typescript"],
            previous_languages=["python"],
        )

        assert state.languages_added == {"javascript", "typescript"}

    def test_languages_removed(self):
        """Test languages_removed property."""
        state = SelectionState(
            languages=["python"],
            previous_languages=["python", "javascript"],
        )

        assert state.languages_removed == {"javascript"}

    def test_has_agent_changes_true(self):
        """Test has_agent_changes when agents changed."""
        state = SelectionState(
            agents=["claude", "codex"],
            previous_agents=["claude"],
        )

        assert state.has_agent_changes is True

    def test_has_agent_changes_false(self):
        """Test has_agent_changes when agents unchanged."""
        state = SelectionState(
            agents=["claude"],
            previous_agents=["claude"],
        )

        assert state.has_agent_changes is False

    def test_has_language_changes_true(self):
        """Test has_language_changes when languages changed."""
        state = SelectionState(
            languages=["python", "javascript"],
            previous_languages=["python"],
        )

        assert state.has_language_changes is True

    def test_has_any_changes_true(self):
        """Test has_any_changes when any configuration changed."""
        state = SelectionState(
            agents=["claude"],
            previous_agents=["claude"],
            languages=["python", "javascript"],  # Languages changed
            previous_languages=["python"],
        )

        assert state.has_any_changes is True

    def test_has_any_changes_false(self):
        """Test has_any_changes when nothing changed."""
        state = SelectionState(
            agents=["claude"],
            previous_agents=["claude"],
            languages=["python"],
            previous_languages=["python"],
        )

        assert state.has_any_changes is False


class TestPipelineContext:
    """Tests for PipelineContext dataclass."""

    def test_basic_initialization(self, tmp_path: Path):
        """Test basic context initialization."""
        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.FRESH_INIT,
        )

        assert context.project_root == tmp_path
        assert context.flow_type == FlowType.FRESH_INIT
        assert context.force is False
        assert context.interactive is True
        assert context.dry_run is False

    def test_oak_dir_property(self, tmp_path: Path):
        """Test oak_dir property."""
        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.FRESH_INIT,
        )

        assert context.oak_dir == tmp_path / ".oak"

    def test_is_fresh_install(self, tmp_path: Path):
        """Test is_fresh_install property."""
        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.FRESH_INIT,
        )

        assert context.is_fresh_install is True
        assert context.is_update is False
        assert context.is_upgrade is False
        assert context.is_force_reinit is False

    def test_is_update(self, tmp_path: Path):
        """Test is_update property."""
        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.UPDATE,
        )

        assert context.is_fresh_install is False
        assert context.is_update is True
        assert context.is_upgrade is False
        assert context.is_force_reinit is False

    def test_is_upgrade(self, tmp_path: Path):
        """Test is_upgrade property."""
        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.UPGRADE,
        )

        assert context.is_fresh_install is False
        assert context.is_update is False
        assert context.is_upgrade is True
        assert context.is_force_reinit is False

    def test_is_force_reinit(self, tmp_path: Path):
        """Test is_force_reinit property."""
        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.FORCE_REINIT,
        )

        assert context.is_fresh_install is False
        assert context.is_update is False
        assert context.is_upgrade is False
        assert context.is_force_reinit is True

    def test_add_error(self, tmp_path: Path):
        """Test add_error method."""
        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.FRESH_INIT,
        )

        context.add_error("test_stage", "Something went wrong")

        assert len(context.errors) == 1
        assert context.errors[0] == ("test_stage", "Something went wrong")

    def test_add_warning(self, tmp_path: Path):
        """Test add_warning method."""
        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.FRESH_INIT,
        )

        context.add_warning("test_stage", "Something might be wrong")

        assert len(context.warnings) == 1
        assert context.warnings[0] == ("test_stage", "Something might be wrong")

    def test_set_and_get_result(self, tmp_path: Path):
        """Test set_result and get_result methods."""
        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.FRESH_INIT,
        )

        context.set_result("stage_a", {"key": "value"})

        assert context.get_result("stage_a") == {"key": "value"}
        assert context.get_result("nonexistent") is None
        assert context.get_result("nonexistent", "default") == "default"

    def test_selections_defaults(self, tmp_path: Path):
        """Test that selections has default empty state."""
        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.FRESH_INIT,
        )

        assert context.selections.agents == []
        assert context.selections.languages == []

    def test_custom_selections(self, tmp_path: Path):
        """Test context with custom selections."""
        context = PipelineContext(
            project_root=tmp_path,
            flow_type=FlowType.UPDATE,
            selections=SelectionState(
                agents=["claude", "codex"],
                languages=["python", "javascript"],
                previous_agents=["claude"],
                previous_languages=["python"],
            ),
        )

        assert context.selections.agents == ["claude", "codex"]
        assert context.selections.agents_added == {"codex"}
        assert context.selections.languages_added == {"javascript"}
        assert context.selections.has_agent_changes is True
        assert context.selections.has_language_changes is True
