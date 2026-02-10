"""Tests for state tracking in AgentRegistry.install_builtin_tasks().

Verifies that installed/updated agent task YAMLs are recorded via
StateService so they can be cleaned up by `oak remove`.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from open_agent_kit.features.codebase_intelligence.agents.registry import AgentRegistry
from open_agent_kit.features.codebase_intelligence.constants import (
    AGENT_PROJECT_CONFIG_DIR,
    AGENT_PROJECT_CONFIG_EXTENSION,
)


class TestInstallBuiltinTasksTracking:
    """Tests for state tracking during install_builtin_tasks()."""

    def test_records_created_files_on_install(self, tmp_path: Path) -> None:
        """record_created_file() should be called for each installed task YAML."""
        registry = AgentRegistry(project_root=tmp_path)
        registry.load_all()

        mock_state = MagicMock()
        with patch.object(registry, "_get_state_service", return_value=mock_state):
            results = registry.install_builtin_tasks()

        installed = [name for name, status in results.items() if status == "installed"]
        assert len(installed) >= 1, "Expected at least one task to be installed"

        # record_created_file should be called once per installed task
        target_dir = tmp_path / AGENT_PROJECT_CONFIG_DIR
        recorded_paths = [call.args[0] for call in mock_state.record_created_file.call_args_list]
        for task_name in installed:
            expected_path = target_dir / f"{task_name}{AGENT_PROJECT_CONFIG_EXTENSION}"
            assert expected_path in recorded_paths, f"Expected {expected_path} to be tracked"

    def test_records_directory_on_install(self, tmp_path: Path) -> None:
        """record_created_directory() should be called for oak/agents/."""
        registry = AgentRegistry(project_root=tmp_path)
        registry.load_all()

        mock_state = MagicMock()
        with patch.object(registry, "_get_state_service", return_value=mock_state):
            registry.install_builtin_tasks()

        target_dir = tmp_path / AGENT_PROJECT_CONFIG_DIR
        mock_state.record_created_directory.assert_called_once_with(target_dir)

    def test_skipped_tasks_are_not_re_recorded(self, tmp_path: Path) -> None:
        """Skipped tasks (already exist, no force) should not call record_created_file()."""
        registry = AgentRegistry(project_root=tmp_path)
        registry.load_all()

        # First install to create files
        registry.install_builtin_tasks()

        # Second install without force - all should be skipped
        mock_state = MagicMock()
        with patch.object(registry, "_get_state_service", return_value=mock_state):
            results = registry.install_builtin_tasks(force=False)

        skipped = [name for name, status in results.items() if status == "skipped"]
        assert len(skipped) >= 1, "Expected at least one task to be skipped"

        # record_created_file should NOT be called for skipped tasks
        mock_state.record_created_file.assert_not_called()

    def test_updated_tasks_are_tracked(self, tmp_path: Path) -> None:
        """Updated tasks (force=True) should call record_created_file()."""
        registry = AgentRegistry(project_root=tmp_path)
        registry.load_all()

        # First install to create files
        registry.install_builtin_tasks()

        # Second install with force - all should be updated
        mock_state = MagicMock()
        with patch.object(registry, "_get_state_service", return_value=mock_state):
            results = registry.install_builtin_tasks(force=True)

        updated = [name for name, status in results.items() if status == "updated"]
        assert len(updated) >= 1, "Expected at least one task to be updated"

        target_dir = tmp_path / AGENT_PROJECT_CONFIG_DIR
        recorded_paths = [call.args[0] for call in mock_state.record_created_file.call_args_list]
        for task_name in updated:
            expected_path = target_dir / f"{task_name}{AGENT_PROJECT_CONFIG_EXTENSION}"
            assert (
                expected_path in recorded_paths
            ), f"Expected {expected_path} to be tracked on update"

    def test_state_service_failure_does_not_break_install(self, tmp_path: Path) -> None:
        """State tracking failure should not prevent task installation."""
        registry = AgentRegistry(project_root=tmp_path)
        registry.load_all()

        mock_state = MagicMock()
        mock_state.record_created_file.side_effect = RuntimeError("state broken")
        mock_state.record_created_directory.side_effect = RuntimeError("state broken")

        with patch.object(registry, "_get_state_service", return_value=mock_state):
            results = registry.install_builtin_tasks()

        installed = [name for name, status in results.items() if status == "installed"]
        assert len(installed) >= 1, "Install should succeed despite state tracking failure"

    def test_no_state_service_does_not_break_install(self, tmp_path: Path) -> None:
        """None state service (no project root) should not break installation."""
        registry = AgentRegistry(project_root=tmp_path)
        registry.load_all()

        with patch.object(registry, "_get_state_service", return_value=None):
            results = registry.install_builtin_tasks()

        installed = [name for name, status in results.items() if status == "installed"]
        assert len(installed) >= 1, "Install should succeed without state service"
