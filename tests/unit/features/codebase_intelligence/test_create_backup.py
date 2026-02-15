"""Tests for unified backup functions: create_backup, restore_backup, restore_all.

Tests cover:
- create_backup() config resolution, explicit override, missing db, custom output
- restore_backup() missing db/backup, legacy fallback, dry run
- restore_all() discovery, explicit file list, dry run
"""

from unittest.mock import MagicMock, patch

import pytest

from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
    BackupResult,
    RestoreAllResult,
    RestoreResult,
    create_backup,
    restore_all,
    restore_backup,
)
from open_agent_kit.features.codebase_intelligence.constants import (
    BACKUP_INCLUDE_ACTIVITIES_DEFAULT,
    CI_HISTORY_BACKUP_FILE,
)

MOCK_MACHINE_ID = "testuser_abc123"


@pytest.fixture
def mock_machine_id(monkeypatch):
    """Patch get_machine_identifier to return a stable test value."""
    monkeypatch.setattr(
        "open_agent_kit.features.codebase_intelligence.activity.store.backup.get_machine_identifier",
        lambda *_args, **_kwargs: MOCK_MACHINE_ID,
    )


# =============================================================================
# create_backup() Tests
# =============================================================================


class TestCreateBackup:
    """Test create_backup() unified function."""

    def test_missing_db_returns_failure(self, tmp_path, mock_machine_id):
        """Test that missing database returns a failure result."""
        db_path = tmp_path / "nonexistent.db"
        result = create_backup(tmp_path, db_path)

        assert isinstance(result, BackupResult)
        assert result.success is False
        assert "not found" in result.error

    def test_explicit_include_activities_true(self, tmp_path, mock_machine_id):
        """Test that explicit include_activities=True is passed through."""
        db_path = tmp_path / "test.db"

        # create_backup should fail (no real db) but we verify the flag is set
        result = create_backup(tmp_path, db_path, include_activities=True)
        assert result.success is False
        assert result.include_activities is True

    def test_explicit_include_activities_false(self, tmp_path, mock_machine_id):
        """Test that explicit include_activities=False is passed through."""
        db_path = tmp_path / "test.db"
        result = create_backup(tmp_path, db_path, include_activities=False)
        assert result.success is False
        assert result.include_activities is False

    def test_config_resolution_when_none(self, tmp_path, mock_machine_id):
        """Test that include_activities=None loads from config."""
        db_path = tmp_path / "test.db"

        # When no config file exists, should fall back to default
        result = create_backup(tmp_path, db_path, include_activities=None)
        assert result.success is False
        assert result.include_activities is BACKUP_INCLUDE_ACTIVITIES_DEFAULT

    def test_custom_output_path(self, tmp_path, mock_machine_id):
        """Test that custom output_path is used when provided."""
        db_path = tmp_path / "test.db"
        custom_path = tmp_path / "custom_backup.sql"

        result = create_backup(tmp_path, db_path, output_path=custom_path)
        assert result.success is False  # db doesn't exist
        # backup_path is not set on early db-not-found return
        assert result.backup_path is None

    @patch("open_agent_kit.features.codebase_intelligence.activity.store.core.ActivityStore")
    @patch("open_agent_kit.features.codebase_intelligence.activity.store.backup.export_to_sql")
    def test_successful_backup(self, mock_export, mock_store_cls, tmp_path, mock_machine_id):
        """Test successful backup creates file and returns correct result."""
        db_path = tmp_path / "test.db"
        db_path.touch()

        mock_store = MagicMock()
        mock_store_cls.return_value = mock_store
        mock_export.return_value = 42

        result = create_backup(tmp_path, db_path, include_activities=True)

        assert result.success is True
        assert result.record_count == 42
        assert result.machine_id == MOCK_MACHINE_ID
        assert result.include_activities is True
        assert result.backup_path is not None
        mock_store.close.assert_called_once()

    @patch("open_agent_kit.features.codebase_intelligence.activity.store.core.ActivityStore")
    @patch("open_agent_kit.features.codebase_intelligence.activity.store.backup.export_to_sql")
    def test_export_exception_returns_failure(
        self, mock_export, mock_store_cls, tmp_path, mock_machine_id
    ):
        """Test that export exceptions are caught and returned as failure."""
        db_path = tmp_path / "test.db"
        db_path.touch()

        mock_store = MagicMock()
        mock_store_cls.return_value = mock_store
        mock_export.side_effect = RuntimeError("disk full")

        result = create_backup(tmp_path, db_path, include_activities=False)

        assert result.success is False
        assert "disk full" in result.error
        mock_store.close.assert_called_once()


# =============================================================================
# restore_backup() Tests
# =============================================================================


class TestRestoreBackup:
    """Test restore_backup() unified function."""

    def test_missing_db_returns_failure(self, tmp_path, mock_machine_id):
        """Test that missing database returns a failure result."""
        db_path = tmp_path / "nonexistent.db"
        result = restore_backup(tmp_path, db_path)

        assert isinstance(result, RestoreResult)
        assert result.success is False
        assert "not found" in result.error

    def test_no_backup_file_returns_failure(self, tmp_path, mock_machine_id):
        """Test that missing backup file returns a failure result."""
        db_path = tmp_path / "test.db"
        db_path.touch()

        # Create backup dir but no files
        backup_dir = tmp_path / "oak" / "history"
        backup_dir.mkdir(parents=True)

        result = restore_backup(tmp_path, db_path)

        assert result.success is False
        assert "No backup file found" in result.error

    def test_explicit_input_path_not_found(self, tmp_path, mock_machine_id):
        """Test that explicit non-existent input_path returns failure."""
        db_path = tmp_path / "test.db"
        db_path.touch()
        missing_file = tmp_path / "missing.sql"

        result = restore_backup(tmp_path, db_path, input_path=missing_file)

        assert result.success is False
        assert "not found" in result.error
        assert result.backup_path == missing_file

    def test_legacy_fallback(self, tmp_path, mock_machine_id):
        """Test fallback to legacy CI_HISTORY_BACKUP_FILE when machine-specific file is absent."""
        db_path = tmp_path / "test.db"
        db_path.touch()

        backup_dir = tmp_path / "oak" / "history"
        backup_dir.mkdir(parents=True)
        legacy_file = backup_dir / CI_HISTORY_BACKUP_FILE
        legacy_file.write_text("-- empty backup\n")

        with patch(
            "open_agent_kit.features.codebase_intelligence.activity.store.core.ActivityStore"
        ) as mock_store_cls:
            mock_store = MagicMock()
            mock_store_cls.return_value = mock_store

            with patch(
                "open_agent_kit.features.codebase_intelligence.activity.store.backup.import_from_sql_with_dedup"
            ) as mock_import:
                from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
                    ImportResult,
                )

                mock_import.return_value = ImportResult()

                result = restore_backup(tmp_path, db_path)

        assert result.success is True
        assert result.backup_path == legacy_file
        assert result.machine_id == MOCK_MACHINE_ID

    @patch("open_agent_kit.features.codebase_intelligence.activity.store.core.ActivityStore")
    @patch(
        "open_agent_kit.features.codebase_intelligence.activity.store.backup.import_from_sql_with_dedup"
    )
    def test_successful_restore(self, mock_import, mock_store_cls, tmp_path, mock_machine_id):
        """Test successful restore with explicit input_path."""
        db_path = tmp_path / "test.db"
        db_path.touch()
        backup_file = tmp_path / "backup.sql"
        backup_file.write_text("-- backup data\n")

        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            ImportResult,
        )

        expected_result = ImportResult(sessions_imported=5)
        mock_import.return_value = expected_result
        mock_store = MagicMock()
        mock_store_cls.return_value = mock_store

        result = restore_backup(tmp_path, db_path, input_path=backup_file)

        assert result.success is True
        assert result.import_result is expected_result
        assert result.backup_path == backup_file
        mock_store.close.assert_called_once()

    @patch("open_agent_kit.features.codebase_intelligence.activity.store.core.ActivityStore")
    @patch(
        "open_agent_kit.features.codebase_intelligence.activity.store.backup.import_from_sql_with_dedup"
    )
    def test_dry_run_passed_through(self, mock_import, mock_store_cls, tmp_path, mock_machine_id):
        """Test that dry_run flag is passed to import function."""
        db_path = tmp_path / "test.db"
        db_path.touch()
        backup_file = tmp_path / "backup.sql"
        backup_file.write_text("-- backup data\n")

        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            ImportResult,
        )

        mock_import.return_value = ImportResult()
        mock_store = MagicMock()
        mock_store_cls.return_value = mock_store

        restore_backup(tmp_path, db_path, input_path=backup_file, dry_run=True)

        mock_import.assert_called_once_with(mock_store, backup_file, dry_run=True)

    @patch("open_agent_kit.features.codebase_intelligence.activity.store.core.ActivityStore")
    @patch(
        "open_agent_kit.features.codebase_intelligence.activity.store.backup.import_from_sql_with_dedup"
    )
    def test_import_exception_returns_failure(
        self, mock_import, mock_store_cls, tmp_path, mock_machine_id
    ):
        """Test that import exceptions are caught and returned as failure."""
        db_path = tmp_path / "test.db"
        db_path.touch()
        backup_file = tmp_path / "backup.sql"
        backup_file.write_text("-- corrupt\n")

        mock_store = MagicMock()
        mock_store_cls.return_value = mock_store
        mock_import.side_effect = RuntimeError("corrupt file")

        result = restore_backup(tmp_path, db_path, input_path=backup_file)

        assert result.success is False
        assert "corrupt file" in result.error
        mock_store.close.assert_called_once()


# =============================================================================
# restore_all() Tests
# =============================================================================


class TestRestoreAll:
    """Test restore_all() unified function."""

    def test_missing_db_returns_failure(self, tmp_path, mock_machine_id):
        """Test that missing database returns a failure result."""
        db_path = tmp_path / "nonexistent.db"
        result = restore_all(tmp_path, db_path)

        assert isinstance(result, RestoreAllResult)
        assert result.success is False
        assert "not found" in result.error

    def test_empty_backup_dir_returns_success(self, tmp_path, mock_machine_id):
        """Test that empty backup directory returns success with no files."""
        db_path = tmp_path / "test.db"
        db_path.touch()

        result = restore_all(tmp_path, db_path)

        assert result.success is True
        assert len(result.per_file) == 0
        assert result.total_imported == 0
        assert result.total_skipped == 0

    @patch("open_agent_kit.features.codebase_intelligence.activity.store.core.ActivityStore")
    @patch(
        "open_agent_kit.features.codebase_intelligence.activity.store.backup.import_from_sql_with_dedup"
    )
    def test_explicit_file_list(self, mock_import, mock_store_cls, tmp_path, mock_machine_id):
        """Test restore_all with explicit backup_files list."""
        db_path = tmp_path / "test.db"
        db_path.touch()

        file_a = tmp_path / "a.sql"
        file_b = tmp_path / "b.sql"
        file_a.write_text("-- a\n")
        file_b.write_text("-- b\n")

        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            ImportResult,
        )

        mock_import.side_effect = [
            ImportResult(sessions_imported=3),
            ImportResult(sessions_imported=2),
        ]
        mock_store = MagicMock()
        mock_store_cls.return_value = mock_store

        result = restore_all(tmp_path, db_path, backup_files=[file_a, file_b])

        assert result.success is True
        assert len(result.per_file) == 2
        assert "a.sql" in result.per_file
        assert "b.sql" in result.per_file
        assert result.total_imported == 5
        mock_store.close.assert_called_once()

    @patch("open_agent_kit.features.codebase_intelligence.activity.store.core.ActivityStore")
    @patch(
        "open_agent_kit.features.codebase_intelligence.activity.store.backup.import_from_sql_with_dedup"
    )
    def test_dry_run_passed_through(self, mock_import, mock_store_cls, tmp_path, mock_machine_id):
        """Test that dry_run flag is passed to each import call."""
        db_path = tmp_path / "test.db"
        db_path.touch()

        file_a = tmp_path / "a.sql"
        file_a.write_text("-- a\n")

        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            ImportResult,
        )

        mock_import.return_value = ImportResult()
        mock_store = MagicMock()
        mock_store_cls.return_value = mock_store

        restore_all(tmp_path, db_path, backup_files=[file_a], dry_run=True)

        mock_import.assert_called_once_with(
            mock_store, file_a, dry_run=True, replace_machine=False, vector_store=None
        )

    @patch("open_agent_kit.features.codebase_intelligence.activity.store.core.ActivityStore")
    @patch(
        "open_agent_kit.features.codebase_intelligence.activity.store.backup.import_from_sql_with_dedup"
    )
    def test_exception_returns_failure(
        self, mock_import, mock_store_cls, tmp_path, mock_machine_id
    ):
        """Test that exceptions during restore_all are caught."""
        db_path = tmp_path / "test.db"
        db_path.touch()

        file_a = tmp_path / "a.sql"
        file_a.write_text("-- a\n")

        mock_store = MagicMock()
        mock_store_cls.return_value = mock_store
        mock_import.side_effect = RuntimeError("import failed")

        result = restore_all(tmp_path, db_path, backup_files=[file_a])

        assert result.success is False
        assert "import failed" in result.error
        mock_store.close.assert_called_once()

    def test_empty_explicit_file_list(self, tmp_path, mock_machine_id):
        """Test restore_all with empty explicit file list returns success."""
        db_path = tmp_path / "test.db"
        db_path.touch()

        result = restore_all(tmp_path, db_path, backup_files=[])

        assert result.success is True
        assert len(result.per_file) == 0


# =============================================================================
# Result Dataclass Tests
# =============================================================================


class TestResultDataclasses:
    """Test result dataclass properties and defaults."""

    def test_backup_result_defaults(self):
        """Test BackupResult default values."""
        result = BackupResult(success=True)
        assert result.backup_path is None
        assert result.record_count == 0
        assert result.machine_id == ""
        assert result.include_activities is False
        assert result.error is None

    def test_restore_result_defaults(self):
        """Test RestoreResult default values."""
        result = RestoreResult(success=True)
        assert result.backup_path is None
        assert result.import_result is None
        assert result.machine_id == ""
        assert result.error is None

    def test_restore_all_result_defaults(self):
        """Test RestoreAllResult default values."""
        result = RestoreAllResult(success=True)
        assert result.per_file == {}
        assert result.machine_id == ""
        assert result.error is None
        assert result.total_imported == 0
        assert result.total_skipped == 0

    def test_restore_all_result_totals(self):
        """Test RestoreAllResult computed totals."""
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            ImportResult,
        )

        result = RestoreAllResult(
            success=True,
            per_file={
                "a.sql": ImportResult(sessions_imported=3, sessions_skipped=1),
                "b.sql": ImportResult(sessions_imported=2, batches_skipped=4),
            },
        )
        assert result.total_imported == 5
        assert result.total_skipped == 5
