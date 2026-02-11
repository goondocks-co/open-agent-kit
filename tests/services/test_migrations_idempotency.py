"""Tests for the migration framework.

Verifies that registered migrations are well-formed and that the
framework correctly executes, skips, and captures failures.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from open_agent_kit.services.migrations import get_migrations, run_migrations


class TestMigrationRegistry:
    """Verify the migration registry contains well-formed entries."""

    def test_get_migrations_returns_list_of_tuples(self) -> None:
        """Each migration entry should be a (id, description, callable) tuple."""
        migrations = get_migrations()
        for entry in migrations:
            assert len(entry) == 3
            migration_id, description, func = entry
            assert isinstance(migration_id, str)
            assert isinstance(description, str)
            assert callable(func)

    def test_migration_ids_are_unique(self) -> None:
        """All migration IDs must be unique."""
        migrations = get_migrations()
        ids = [m[0] for m in migrations]
        assert len(ids) == len(set(ids))


class TestMigrationFramework:
    """Verify the migration framework still works for future use."""

    def test_framework_executes_migration(self, tmp_path: Path) -> None:
        """A registered migration should execute and appear in successful list."""
        marker = tmp_path / "marker.txt"

        def sample_migration(project_root: Path) -> None:
            (project_root / "marker.txt").write_text("migrated")

        fake_registry = [("2099.01.01_sample", "Sample migration", sample_migration)]

        with patch(
            "open_agent_kit.services.migrations.get_migrations",
            return_value=fake_registry,
        ):
            successful, failed = run_migrations(tmp_path, set())

        assert successful == ["2099.01.01_sample"]
        assert failed == []
        assert marker.read_text() == "migrated"

    def test_framework_skips_completed_migration(self, tmp_path: Path) -> None:
        """Completed migrations should be skipped."""

        def should_not_run(project_root: Path) -> None:
            raise AssertionError("This migration should have been skipped")

        fake_registry = [("2099.01.01_done", "Already done", should_not_run)]

        with patch(
            "open_agent_kit.services.migrations.get_migrations",
            return_value=fake_registry,
        ):
            successful, failed = run_migrations(tmp_path, {"2099.01.01_done"})

        assert successful == []
        assert failed == []

    def test_framework_captures_migration_failure(self, tmp_path: Path) -> None:
        """Failed migrations should appear in the failed list."""

        def broken_migration(project_root: Path) -> None:
            raise RuntimeError("something went wrong")

        fake_registry = [("2099.01.01_broken", "Broken migration", broken_migration)]

        with patch(
            "open_agent_kit.services.migrations.get_migrations",
            return_value=fake_registry,
        ):
            successful, failed = run_migrations(tmp_path, set())

        assert successful == []
        assert len(failed) == 1
        assert failed[0][0] == "2099.01.01_broken"
        assert "something went wrong" in failed[0][1]
