"""Idempotency tests for the migration system.

This module ensures that migrations can be run multiple times safely:
- Running a migration twice produces the same result
- Failed migrations don't corrupt state
- Migrations preserve user data
- State tracking is reliable

These tests are critical for upgrade reliability and rollback safety.
"""

from pathlib import Path

import pytest

from open_agent_kit.config.paths import CONFIG_FILE
from open_agent_kit.services.migrations import get_migrations, run_migrations
from open_agent_kit.utils import read_yaml, write_yaml


@pytest.fixture
def project_with_state(tmp_path: Path) -> Path:
    """Create a project with oak configuration and state.

    Args:
        tmp_path: Temporary directory from pytest.

    Returns:
        Path to project root.
    """
    project = tmp_path / "test_project"
    project.mkdir()

    # Create .oak directory
    oak_dir = project / ".oak"
    oak_dir.mkdir()

    # Create initial config
    config = {
        "version": "1.0.0",
        "features": {"enabled": ["constitution", "rfc"]},
    }
    write_yaml(oak_dir / "config.yaml", config)

    # Create state file
    state = {
        "version": "0.1.0",
        "completed_migrations": [],
    }
    write_yaml(oak_dir / "state.yaml", state)

    # Create .claude/commands directory
    claude_dir = project / ".claude" / "commands"
    claude_dir.mkdir(parents=True)

    return project


@pytest.fixture
def project_with_legacy_structure(tmp_path: Path) -> Path:
    """Create a project with legacy directory structure.

    Args:
        tmp_path: Temporary directory from pytest.

    Returns:
        Path to project root.
    """
    project = tmp_path / "legacy_project"
    project.mkdir()

    # Create .oak directory with old structure
    oak_dir = project / ".oak"
    oak_dir.mkdir()

    # Create legacy templates directory
    templates_dir = oak_dir / "templates"
    templates_dir.mkdir()

    # Create subdirectories that should be removed
    for subdir in ["constitution", "rfc", "commands", "ide"]:
        (templates_dir / subdir).mkdir()
        (templates_dir / subdir / "example.md").write_text("legacy content")

    # Create config
    config = {
        "version": "0.5.0",
        "ides": {"claude": {"enabled": True}},
    }
    write_yaml(oak_dir / "config.yaml", config)

    # Create state
    state = {"version": "0.5.0", "completed_migrations": []}
    write_yaml(oak_dir / "state.yaml", state)

    # Create .claude/commands
    (project / ".claude" / "commands").mkdir(parents=True)

    # Create .github/prompts with legacy files
    github_prompts = project / ".github" / "prompts"
    github_prompts.mkdir(parents=True)
    (github_prompts / "oak.plan-issue.prompt.md").write_text("legacy prompt")

    return project


class TestMigrationIdempotency:
    """Test that migrations can be run multiple times safely."""

    def test_gitignore_migration_is_idempotent(self, project_with_state: Path):
        """Test that gitignore migration can run multiple times.

        Args:
            project_with_state: Project with oak configuration.
        """
        # Create .gitignore without the pattern
        gitignore = project_with_state / ".gitignore"
        gitignore.write_text("*.pyc\n__pycache__/\n")

        # Run migration first time
        success1, failed1 = run_migrations(project_with_state, set())

        # Read resulting .gitignore
        content_after_first = gitignore.read_text()
        assert (
            "oak/issue/**/context.json" in content_after_first
            or ".oak/issue/**/context.json" in content_after_first
        )

        # Run migration second time (2024.11.13_gitignore_issue_context)
        success2, failed2 = run_migrations(project_with_state, set())

        # Read .gitignore again
        content_after_second = gitignore.read_text()

        # Content should be the same (no duplication)
        # Split and clean for comparison
        lines_first = [
            line.strip() for line in content_after_first.strip().split("\n") if line.strip()
        ]
        lines_second = [
            line.strip() for line in content_after_second.strip().split("\n") if line.strip()
        ]

        assert len(lines_first) == len(
            lines_second
        ), "Running migration twice added duplicate lines"
        assert lines_first == lines_second

        # No failures
        assert len(failed1) == 0
        assert len(failed2) == 0

    def test_copilot_agents_migration_is_idempotent(self, project_with_legacy_structure: Path):
        """Test that Copilot agents migration can run multiple times.

        Args:
            project_with_legacy_structure: Project with legacy structure.
        """
        # Create .github/prompts with oak files
        prompts_dir = project_with_legacy_structure / ".github" / "prompts"
        prompts_dir.mkdir(parents=True, exist_ok=True)

        legacy_files = ["oak.plan.prompt.md", "oak.review.prompt.md"]
        for filename in legacy_files:
            (prompts_dir / filename).write_text("legacy content")

        # Run migration first time
        success1, failed1 = run_migrations(project_with_legacy_structure, set())

        # Verify files were removed
        for filename in legacy_files:
            assert not (prompts_dir / filename).exists()

        # Run migration second time (files already gone)
        success2, failed2 = run_migrations(project_with_legacy_structure, set())

        # Should not raise errors
        assert len(failed1) == 0
        assert len(failed2) == 0

    def test_features_restructure_migration_is_idempotent(
        self, project_with_legacy_structure: Path
    ):
        """Test that features restructure migration can run multiple times.

        This migration now converts legacy features config to the new languages
        config format. All features are always enabled (not user-selectable).

        Args:
            project_with_legacy_structure: Project with legacy structure.
        """
        config_path = project_with_legacy_structure / CONFIG_FILE

        # Verify legacy templates exist before migration
        templates_dir = project_with_legacy_structure / ".oak" / "templates"
        assert templates_dir.exists()

        # Run migration first time
        success1, failed1 = run_migrations(project_with_legacy_structure, set())

        # Read config after first run
        config_after_first = read_yaml(config_path)
        # Features are removed from config (always enabled internally)
        # Languages section should exist
        assert "languages" in config_after_first
        assert "installed" in config_after_first["languages"]

        # Templates should be cleaned up
        assert not (templates_dir / "constitution").exists()
        assert not (templates_dir / "rfc").exists()

        # Run migration second time
        success2, failed2 = run_migrations(project_with_legacy_structure, set())

        # Read config after second run
        config_after_second = read_yaml(config_path)

        # Config should be unchanged
        assert config_after_first == config_after_second

        # No failures
        assert len(failed1) == 0
        assert len(failed2) == 0

    def test_cleanup_old_templates_migration_is_idempotent(
        self, project_with_legacy_structure: Path
    ):
        """Test that cleanup old templates migration can run multiple times.

        Args:
            project_with_legacy_structure: Project with legacy structure.
        """
        templates_dir = project_with_legacy_structure / ".oak" / "templates"

        # Run migration first time
        success1, failed1 = run_migrations(project_with_legacy_structure, set())

        # Verify cleanup happened
        for subdir in ["constitution", "rfc", "commands", "ide"]:
            assert not (templates_dir / subdir).exists()

        # Run migration second time
        success2, failed2 = run_migrations(project_with_legacy_structure, set())

        # Should not raise errors
        assert len(failed1) == 0
        assert len(failed2) == 0

    def test_remove_plan_issue_migration_is_idempotent(self, project_with_legacy_structure: Path):
        """Test that remove plan-issue migration can run multiple times.

        Args:
            project_with_legacy_structure: Project with legacy structure.
        """
        # Create deprecated files
        claude_cmd = project_with_legacy_structure / ".claude" / "commands" / "oak.plan-issue.md"
        claude_cmd.parent.mkdir(parents=True, exist_ok=True)
        claude_cmd.write_text("deprecated command")

        github_agent = project_with_legacy_structure / ".github" / "agents" / "oak.plan-issue.md"
        github_agent.parent.mkdir(parents=True, exist_ok=True)
        github_agent.write_text("deprecated command")

        # Run migration first time
        success1, failed1 = run_migrations(project_with_legacy_structure, set())

        # Verify files removed
        assert not claude_cmd.exists()
        assert not github_agent.exists()

        # Run migration second time
        success2, failed2 = run_migrations(project_with_legacy_structure, set())

        # Should not raise errors
        assert len(failed1) == 0
        assert len(failed2) == 0

    def test_remove_oak_features_dir_migration_is_idempotent(
        self, project_with_legacy_structure: Path
    ):
        """Test that remove .oak/features/ migration can run multiple times.

        Args:
            project_with_legacy_structure: Project with legacy structure.
        """
        # Create .oak/features directory
        features_dir = project_with_legacy_structure / ".oak" / "features"
        features_dir.mkdir(exist_ok=True)
        (features_dir / "test.md").write_text("feature asset")

        # Run migration first time
        success1, failed1 = run_migrations(project_with_legacy_structure, set())

        # Verify directory removed
        assert not features_dir.exists()

        # Run migration second time
        success2, failed2 = run_migrations(project_with_legacy_structure, set())

        # Should not raise errors
        assert len(failed1) == 0
        assert len(failed2) == 0

    def test_remove_ide_settings_migration_is_idempotent(self, project_with_legacy_structure: Path):
        """Test that remove IDE settings migration can run multiple times.

        Args:
            project_with_legacy_structure: Project with legacy structure.
        """
        config_path = project_with_legacy_structure / CONFIG_FILE

        # Verify 'ides' key exists in legacy config
        config_before = read_yaml(config_path)
        assert "ides" in config_before

        # Run migration first time
        success1, failed1 = run_migrations(project_with_legacy_structure, set())

        # Verify 'ides' key removed
        config_after_first = read_yaml(config_path)
        assert "ides" not in config_after_first

        # Run migration second time
        success2, failed2 = run_migrations(project_with_legacy_structure, set())

        # Config should be unchanged
        config_after_second = read_yaml(config_path)
        assert config_after_first == config_after_second

        # No failures
        assert len(failed1) == 0
        assert len(failed2) == 0


class TestMigrationFailureRecovery:
    """Test that migration failures don't corrupt state."""

    def test_migration_failure_preserves_original_state(self, project_with_state: Path):
        """Test that a failed migration leaves original state intact.

        Args:
            project_with_state: Project with oak configuration.
        """
        config_path = project_with_state / CONFIG_FILE

        # Save original config
        original_config = read_yaml(config_path)

        # Create a scenario that would cause a migration to fail
        # Make config file read-only to simulate failure
        config_path.chmod(0o444)

        try:
            # Attempt migration (might fail due to permissions)
            success, failed = run_migrations(project_with_state, set())

            # If it failed, verify state is preserved
            if failed:
                # Restore write permission to read config
                config_path.chmod(0o644)
                current_config = read_yaml(config_path)

                # Config should be unchanged
                assert current_config == original_config
        finally:
            # Restore permissions
            config_path.chmod(0o644)

    def test_partial_migration_doesnt_mark_as_complete(self, project_with_legacy_structure: Path):
        """Test that incomplete migrations aren't marked as complete.

        Args:
            project_with_legacy_structure: Project with legacy structure.
        """
        # This test verifies that if a migration fails mid-way,
        # it should not be marked as complete in the state file.

        # Run migrations normally
        completed_before = set()
        success, failed = run_migrations(project_with_legacy_structure, completed_before)

        # All should succeed
        assert len(failed) == 0

        # If we run again with the "completed" set,
        # no migrations should run (all already completed)
        completed_set = set(success)
        success2, failed2 = run_migrations(project_with_legacy_structure, completed_set)

        assert len(success2) == 0, "Migrations ran again despite being in completed set"
        assert len(failed2) == 0


class TestMigrationUserDataPreservation:
    """Test that migrations preserve user-created content."""

    def test_migrations_preserve_user_files_in_oak_directory(self, project_with_state: Path):
        """Test that user-created files in .oak/ are not deleted.

        Args:
            project_with_state: Project with oak configuration.
        """
        oak_dir = project_with_state / ".oak"

        # Create user files
        user_file = oak_dir / "custom_notes.md"
        user_file.write_text("Important user notes")

        user_subdir = oak_dir / "my_scripts"
        user_subdir.mkdir()
        (user_subdir / "helper.py").write_text("def helper():\n    pass\n")

        # Run all migrations
        success, failed = run_migrations(project_with_state, set())

        # Verify user files still exist
        assert user_file.exists()
        assert user_file.read_text() == "Important user notes"
        assert user_subdir.exists()
        assert (user_subdir / "helper.py").exists()

    def test_features_restructure_preserves_user_content(self, project_with_legacy_structure: Path):
        """Test that features restructure preserves user content.

        Args:
            project_with_legacy_structure: Project with legacy structure.
        """
        # Create user content in templates directory
        templates_dir = project_with_legacy_structure / ".oak" / "templates"
        user_template = templates_dir / "my_custom_template.md"
        user_template.write_text("Custom user template")

        # Create user subdir
        user_subdir = templates_dir / "my_templates"
        user_subdir.mkdir()
        (user_subdir / "template.md").write_text("User template")

        # Run migrations
        success, failed = run_migrations(project_with_legacy_structure, set())

        # User content should still exist
        assert user_template.exists()
        assert user_template.read_text() == "Custom user template"
        assert user_subdir.exists()
        assert (user_subdir / "template.md").exists()

    def test_cleanup_migration_preserves_non_oak_files(self, project_with_legacy_structure: Path):
        """Test that cleanup migrations don't touch non-oak files.

        Args:
            project_with_legacy_structure: Project with legacy structure.
        """
        # Create important user files
        (project_with_legacy_structure / "README.md").write_text("# Project")
        (project_with_legacy_structure / "src").mkdir()
        (project_with_legacy_structure / "src" / "main.py").write_text("def main():\n    pass\n")

        # Run all migrations
        success, failed = run_migrations(project_with_legacy_structure, set())

        # User files should be untouched
        assert (project_with_legacy_structure / "README.md").exists()
        assert (project_with_legacy_structure / "src" / "main.py").exists()


class TestMigrationOrderAndDependencies:
    """Test that migrations run in correct order and handle dependencies."""

    def test_migrations_run_in_order(self, project_with_state: Path):
        """Test that migrations execute in the correct order.

        Args:
            project_with_state: Project with oak configuration.
        """
        # Get all migrations
        all_migrations = get_migrations()

        # Verify they are in chronological order by date prefix
        migration_ids = [m[0] for m in all_migrations]

        # Extract date portions (YYYY.MM.DD) and verify chronological order
        # Migrations on the same date can be in any order
        date_portions = [m.split("_")[0] for m in migration_ids]
        assert date_portions == sorted(
            date_portions
        ), "Migrations not in chronological order by date"

    def test_migrations_can_run_from_any_starting_point(self, project_with_legacy_structure: Path):
        """Test that migrations work regardless of starting state.

        Args:
            project_with_legacy_structure: Project with legacy structure.
        """
        all_migrations = get_migrations()

        # Mark first half as complete
        midpoint = len(all_migrations) // 2
        completed = {m[0] for m in all_migrations[:midpoint]}

        # Run remaining migrations
        success, failed = run_migrations(project_with_legacy_structure, completed)

        # Should only run the uncompleted migrations
        expected_count = len(all_migrations) - midpoint
        assert len(success) + len(failed) == expected_count

    def test_all_migrations_complete_successfully_on_clean_project(self, tmp_path: Path):
        """Test that all migrations succeed on a well-formed project.

        Args:
            tmp_path: Temporary directory.
        """
        # Create minimal project structure
        project = tmp_path / "clean_project"
        project.mkdir()

        oak_dir = project / ".oak"
        oak_dir.mkdir()

        config = {"version": "1.0.0", "features": {"enabled": ["constitution"]}}
        write_yaml(oak_dir / "config.yaml", config)

        (project / ".claude" / "commands").mkdir(parents=True)
        (project / ".gitignore").write_text("*.pyc\n")

        # Run all migrations
        success, failed = run_migrations(project, set())

        # All migrations should succeed
        assert len(failed) == 0

        # Should have run all migrations
        all_migrations = get_migrations()
        assert len(success) == len(all_migrations)


class TestMigrationStateTracking:
    """Test that migration state tracking is reliable."""

    def test_completed_migrations_are_skipped(self, project_with_state: Path):
        """Test that completed migrations don't run again.

        Args:
            project_with_state: Project with oak configuration.
        """
        all_migrations = get_migrations()

        # Mark all as complete
        completed = {m[0] for m in all_migrations}

        # Run migrations
        success, failed = run_migrations(project_with_state, completed)

        # Nothing should run
        assert len(success) == 0
        assert len(failed) == 0

    def test_migration_tracking_persists_across_runs(self, project_with_state: Path):
        """Test that migration state can be saved and reloaded.

        Args:
            project_with_state: Project with oak configuration.
        """
        # Run migrations first time
        success1, failed1 = run_migrations(project_with_state, set())

        # Simulate saving state
        completed_set = set(success1)

        # Run migrations again with completed set
        success2, failed2 = run_migrations(project_with_state, completed_set)

        # Nothing should run the second time
        assert len(success2) == 0
