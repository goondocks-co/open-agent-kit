"""Tests for the cleanup-builtin-agent-tasks migration."""

from pathlib import Path

from open_agent_kit.features.codebase_intelligence.constants import (
    AGENT_PROJECT_CONFIG_DIR,
    AGENT_PROJECT_CONFIG_EXTENSION,
)
from open_agent_kit.services.migrations import _cleanup_builtin_agent_tasks

BUILTIN_TASK_CONTENT = """\
name: architecture-docs
description: Generate architecture documentation
is_builtin: true
agent_type: documentation
default_task: Analyze the codebase architecture
"""

USER_TASK_CONTENT = """\
name: my-custom-task
description: A user-created task
agent_type: documentation
default_task: Do something custom
"""

USER_TASK_EXPLICIT_FALSE = """\
name: my-other-task
description: A user task with explicit is_builtin false
is_builtin: false
agent_type: analysis
default_task: Analyze something
"""


def _write_task(agents_dir: Path, name: str, content: str) -> Path:
    """Write a task YAML to the agents directory."""
    agents_dir.mkdir(parents=True, exist_ok=True)
    path = agents_dir / f"{name}{AGENT_PROJECT_CONFIG_EXTENSION}"
    path.write_text(content, encoding="utf-8")
    return path


class TestCleanupBuiltinAgentTasks:
    """Tests for _cleanup_builtin_agent_tasks migration."""

    def test_removes_builtin_files(self, tmp_path: Path) -> None:
        """Files with is_builtin: true should be deleted."""
        agents_dir = tmp_path / AGENT_PROJECT_CONFIG_DIR
        path = _write_task(agents_dir, "architecture-docs", BUILTIN_TASK_CONTENT)

        _cleanup_builtin_agent_tasks(tmp_path)

        assert not path.exists()

    def test_preserves_user_files_no_builtin_key(self, tmp_path: Path) -> None:
        """Files without is_builtin key should be preserved."""
        agents_dir = tmp_path / AGENT_PROJECT_CONFIG_DIR
        path = _write_task(agents_dir, "my-custom-task", USER_TASK_CONTENT)

        _cleanup_builtin_agent_tasks(tmp_path)

        assert path.exists()

    def test_preserves_user_files_builtin_false(self, tmp_path: Path) -> None:
        """Files with is_builtin: false should be preserved."""
        agents_dir = tmp_path / AGENT_PROJECT_CONFIG_DIR
        path = _write_task(agents_dir, "my-other-task", USER_TASK_EXPLICIT_FALSE)

        _cleanup_builtin_agent_tasks(tmp_path)

        assert path.exists()

    def test_removes_directory_when_empty(self, tmp_path: Path) -> None:
        """oak/agents/ should be removed when empty after cleanup."""
        agents_dir = tmp_path / AGENT_PROJECT_CONFIG_DIR
        _write_task(agents_dir, "architecture-docs", BUILTIN_TASK_CONTENT)

        _cleanup_builtin_agent_tasks(tmp_path)

        assert not agents_dir.exists()

    def test_preserves_directory_when_user_files_remain(self, tmp_path: Path) -> None:
        """oak/agents/ should be preserved when user files remain."""
        agents_dir = tmp_path / AGENT_PROJECT_CONFIG_DIR
        _write_task(agents_dir, "architecture-docs", BUILTIN_TASK_CONTENT)
        user_path = _write_task(agents_dir, "my-custom-task", USER_TASK_CONTENT)

        _cleanup_builtin_agent_tasks(tmp_path)

        assert agents_dir.is_dir()
        assert user_path.exists()

    def test_idempotent(self, tmp_path: Path) -> None:
        """Running the migration twice should be safe."""
        agents_dir = tmp_path / AGENT_PROJECT_CONFIG_DIR
        _write_task(agents_dir, "architecture-docs", BUILTIN_TASK_CONTENT)

        _cleanup_builtin_agent_tasks(tmp_path)
        # Second run — directory is gone, should not raise
        _cleanup_builtin_agent_tasks(tmp_path)

        assert not agents_dir.exists()

    def test_noop_when_no_agents_dir(self, tmp_path: Path) -> None:
        """No-op when oak/agents/ doesn't exist."""
        # Should not raise
        _cleanup_builtin_agent_tasks(tmp_path)

    def test_mixed_builtin_and_user_files(self, tmp_path: Path) -> None:
        """Only built-in files removed; user files and directory preserved."""
        agents_dir = tmp_path / AGENT_PROJECT_CONFIG_DIR
        builtin_path = _write_task(agents_dir, "architecture-docs", BUILTIN_TASK_CONTENT)
        user_path = _write_task(agents_dir, "my-custom-task", USER_TASK_CONTENT)
        user_false_path = _write_task(agents_dir, "my-other-task", USER_TASK_EXPLICIT_FALSE)

        _cleanup_builtin_agent_tasks(tmp_path)

        assert not builtin_path.exists()
        assert user_path.exists()
        assert user_false_path.exists()
        assert agents_dir.is_dir()
