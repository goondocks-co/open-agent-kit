"""Tests for SyncService."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from open_agent_kit.features.codebase_intelligence.sync.models import (
    SyncPlan,
    SyncReason,
)
from open_agent_kit.features.codebase_intelligence.sync.service import SyncService


@pytest.fixture
def sync_service(tmp_path: Path) -> SyncService:
    """Create a SyncService for testing."""
    # Create required directories
    oak_dir = tmp_path / ".oak" / "ci"
    oak_dir.mkdir(parents=True)
    backup_dir = tmp_path / "oak" / "ci" / "history"
    backup_dir.mkdir(parents=True)

    return SyncService(tmp_path)


@pytest.fixture
def mock_daemon_manager():
    """Mock daemon manager."""
    mock = MagicMock()
    mock.is_running.return_value = False
    mock.get_daemon_version.return_value = None
    mock.start.return_value = True
    mock.stop.return_value = True
    return mock


@pytest.fixture
def mock_activity_store():
    """Mock activity store."""
    mock = MagicMock()
    mock.get_schema_version.return_value = 18
    mock.close.return_value = None
    return mock


class TestSyncServiceInit:
    """Test SyncService initialization."""

    def test_init_sets_paths(self, tmp_path: Path):
        """Test that init sets correct paths."""
        service = SyncService(tmp_path)

        assert service.project_root == tmp_path
        assert service.ci_data_dir == tmp_path / ".oak" / "ci"
        assert service.backup_dir == tmp_path / "oak" / "history"
        assert service.chroma_dir == tmp_path / ".oak" / "ci" / "chroma"
        assert service.db_path == tmp_path / ".oak" / "ci" / "activities.db"


class TestDetectChanges:
    """Test SyncService.detect_changes()."""

    def test_detect_no_changes_daemon_not_running(
        self, sync_service: SyncService, mock_daemon_manager
    ):
        """Test detecting no changes when daemon is not running."""
        with patch.object(sync_service, "_get_daemon_manager", return_value=mock_daemon_manager):
            plan = sync_service.detect_changes()

        assert plan.needs_sync is False
        assert SyncReason.NO_CHANGES in plan.reasons

    def test_detect_oak_version_mismatch(self, sync_service: SyncService, mock_daemon_manager):
        """Test detecting OAK version mismatch."""
        mock_daemon_manager.get_daemon_version.return_value = {
            "oak_version": "0.9.0",
            "schema_version": 18,
        }

        with (
            patch.object(sync_service, "_get_daemon_manager", return_value=mock_daemon_manager),
            patch(
                "open_agent_kit.features.codebase_intelligence.sync.service.VERSION",
                "0.10.0",
            ),
        ):
            plan = sync_service.detect_changes()

        assert plan.needs_sync is True
        assert SyncReason.OAK_VERSION_CHANGED in plan.reasons
        assert plan.stop_daemon is True
        assert plan.start_daemon is True
        assert plan.running_oak_version == "0.9.0"
        assert plan.current_oak_version == "0.10.0"

    def test_detect_schema_version_mismatch(self, sync_service: SyncService, mock_daemon_manager):
        """Test detecting schema version mismatch."""
        mock_daemon_manager.get_daemon_version.return_value = {
            "oak_version": "0.10.0",
            "schema_version": 17,
        }

        with (
            patch.object(sync_service, "_get_daemon_manager", return_value=mock_daemon_manager),
            patch(
                "open_agent_kit.features.codebase_intelligence.sync.service.VERSION",
                "0.10.0",
            ),
            patch(
                "open_agent_kit.features.codebase_intelligence.sync.service.SCHEMA_VERSION",
                18,
            ),
        ):
            plan = sync_service.detect_changes()

        assert plan.needs_sync is True
        assert SyncReason.SCHEMA_VERSION_CHANGED in plan.reasons
        assert plan.run_migrations is True
        assert plan.stop_daemon is True
        assert plan.start_daemon is True

    def test_detect_force_full_rebuild(self, sync_service: SyncService, mock_daemon_manager):
        """Test detecting force full rebuild."""
        with patch.object(sync_service, "_get_daemon_manager", return_value=mock_daemon_manager):
            plan = sync_service.detect_changes(force_full=True)

        assert plan.needs_sync is True
        assert SyncReason.MANUAL_FULL_REBUILD in plan.reasons
        assert plan.full_index_rebuild is True
        assert plan.stop_daemon is True
        assert plan.start_daemon is True

    def test_detect_daemon_running_with_old_code(
        self, sync_service: SyncService, mock_daemon_manager
    ):
        """Test detecting daemon running with old code (no version reported)."""
        # Daemon is running but returns None for version (old code)
        mock_daemon_manager.is_running.return_value = True
        mock_daemon_manager.get_daemon_version.return_value = {
            "oak_version": None,
            "schema_version": None,
        }

        with patch.object(sync_service, "_get_daemon_manager", return_value=mock_daemon_manager):
            plan = sync_service.detect_changes()

        assert plan.daemon_running is True
        assert plan.running_oak_version is None
        assert plan.needs_sync is True
        assert SyncReason.OAK_VERSION_CHANGED in plan.reasons
        assert plan.stop_daemon is True
        assert plan.start_daemon is True

    def test_detect_team_backups_available(self, sync_service: SyncService, mock_daemon_manager):
        """Test detecting team backups."""
        # Create mock backup files
        sync_service.backup_dir.mkdir(parents=True, exist_ok=True)
        backup_file = sync_service.backup_dir / "alice_abc123.sql"
        backup_file.write_text("-- schema_version: 18\nINSERT INTO sessions VALUES (...);")

        with (
            patch.object(sync_service, "_get_daemon_manager", return_value=mock_daemon_manager),
            patch(
                "open_agent_kit.features.codebase_intelligence.sync.service.get_backup_filename",
                return_value="mybackup_def456.sql",
            ),
        ):
            plan = sync_service.detect_changes(include_team=True)

        assert plan.needs_sync is True
        assert SyncReason.TEAM_BACKUPS_AVAILABLE in plan.reasons
        assert plan.restore_team_backups is True
        assert plan.team_backup_count == 1
        assert "alice_abc123.sql" in plan.team_backup_files


class TestExecuteSync:
    """Test SyncService.execute_sync()."""

    def test_execute_no_sync_needed(self, sync_service: SyncService):
        """Test executing when no sync is needed."""
        plan = SyncPlan(needs_sync=False, reasons=[SyncReason.NO_CHANGES])

        result = sync_service.execute_sync(plan)

        assert result.success is True
        assert "No sync needed" in result.operations_completed

    def test_execute_dry_run(self, sync_service: SyncService, mock_daemon_manager):
        """Test dry run execution."""
        plan = SyncPlan(
            needs_sync=True,
            reasons=[SyncReason.OAK_VERSION_CHANGED],
            stop_daemon=True,
            start_daemon=True,
        )

        result = sync_service.execute_sync(plan, dry_run=True)

        assert result.success is True
        assert "Dry run" in result.operations_completed[0]
        assert any("Would stop daemon" in op for op in result.operations_completed)
        assert any("Would start daemon" in op for op in result.operations_completed)

    def test_execute_stops_daemon(self, sync_service: SyncService, mock_daemon_manager):
        """Test that sync stops daemon when requested."""
        mock_daemon_manager.is_running.return_value = True

        plan = SyncPlan(
            needs_sync=True,
            reasons=[SyncReason.OAK_VERSION_CHANGED],
            stop_daemon=True,
            start_daemon=True,
        )

        with patch.object(sync_service, "_get_daemon_manager", return_value=mock_daemon_manager):
            result = sync_service.execute_sync(plan)

        assert result.success is True
        mock_daemon_manager.stop.assert_called_once()
        mock_daemon_manager.start.assert_called_once()
        assert "Daemon stopped" in result.operations_completed
        assert "Daemon started" in result.operations_completed

    def test_execute_fails_on_daemon_stop_error(
        self, sync_service: SyncService, mock_daemon_manager
    ):
        """Test that sync fails if daemon stop fails."""
        mock_daemon_manager.is_running.return_value = True
        mock_daemon_manager.stop.return_value = False

        plan = SyncPlan(
            needs_sync=True,
            reasons=[SyncReason.OAK_VERSION_CHANGED],
            stop_daemon=True,
            start_daemon=True,
        )

        with patch.object(sync_service, "_get_daemon_manager", return_value=mock_daemon_manager):
            result = sync_service.execute_sync(plan)

        assert result.success is False
        assert any("Failed to stop daemon" in err for err in result.errors)

    def test_execute_fails_on_daemon_start_error(
        self, sync_service: SyncService, mock_daemon_manager
    ):
        """Test that sync fails if daemon start fails."""
        mock_daemon_manager.is_running.return_value = False
        mock_daemon_manager.start.return_value = False

        plan = SyncPlan(
            needs_sync=True,
            reasons=[SyncReason.OAK_VERSION_CHANGED],
            stop_daemon=False,
            start_daemon=True,
        )

        with patch.object(sync_service, "_get_daemon_manager", return_value=mock_daemon_manager):
            result = sync_service.execute_sync(plan)

        assert result.success is False
        assert any("Failed to start daemon" in err for err in result.errors)

    def test_execute_with_include_activities(self, sync_service: SyncService, mock_daemon_manager):
        """Test that include_activities parameter is passed to backup."""
        mock_daemon_manager.is_running.return_value = False
        mock_activity_store = MagicMock()
        mock_activity_store.export_to_sql.return_value = 100

        plan = SyncPlan(
            needs_sync=True,
            reasons=[SyncReason.TEAM_BACKUPS_AVAILABLE],
            restore_team_backups=True,
            team_backup_files=[],
            start_daemon=True,
        )

        with (
            patch.object(sync_service, "_get_daemon_manager", return_value=mock_daemon_manager),
            patch.object(sync_service, "_get_activity_store", return_value=mock_activity_store),
        ):
            result = sync_service.execute_sync(plan, include_activities=True)

        # Verify export_to_sql was called with include_activities=True
        mock_activity_store.export_to_sql.assert_called_once()
        call_args = mock_activity_store.export_to_sql.call_args
        assert call_args[1]["include_activities"] is True
        assert "(with activities)" in str(result.operations_completed)


class TestExecuteSyncFullRebuild:
    """Test full rebuild scenario."""

    def test_execute_full_rebuild_deletes_chroma(
        self, sync_service: SyncService, mock_daemon_manager
    ):
        """Test that full rebuild deletes ChromaDB directory."""
        # Create chroma directory
        sync_service.chroma_dir.mkdir(parents=True)
        (sync_service.chroma_dir / "test.db").write_text("test")

        plan = SyncPlan(
            needs_sync=True,
            reasons=[SyncReason.MANUAL_FULL_REBUILD],
            full_index_rebuild=True,
            stop_daemon=False,
            start_daemon=True,
        )

        with patch.object(sync_service, "_get_daemon_manager", return_value=mock_daemon_manager):
            result = sync_service.execute_sync(plan)

        assert result.success is True
        assert not sync_service.chroma_dir.exists()
        assert "ChromaDB deleted" in str(result.operations_completed)
