"""Tests for sync models (SyncReason, SyncPlan, SyncResult)."""

from open_agent_kit.features.codebase_intelligence.sync.models import (
    SyncPlan,
    SyncReason,
    SyncResult,
)


class TestSyncReason:
    """Test SyncReason enum."""

    def test_sync_reason_values(self):
        """Test that SyncReason has expected values."""
        assert SyncReason.OAK_VERSION_CHANGED == "oak_version_changed"
        assert SyncReason.SCHEMA_VERSION_CHANGED == "schema_version_changed"
        assert SyncReason.TEAM_BACKUPS_AVAILABLE == "team_backups_available"
        assert SyncReason.MANUAL_FULL_REBUILD == "manual_full_rebuild"
        assert SyncReason.NO_CHANGES == "no_changes"

    def test_sync_reason_is_string(self):
        """Test that SyncReason values are strings."""
        for reason in SyncReason:
            assert isinstance(reason.value, str)


class TestSyncPlan:
    """Test SyncPlan dataclass."""

    def test_sync_plan_defaults(self):
        """Test SyncPlan default values."""
        plan = SyncPlan(needs_sync=False)

        assert plan.needs_sync is False
        assert plan.reasons == []
        assert plan.daemon_running is False
        assert plan.running_oak_version is None
        assert plan.current_oak_version == ""
        assert plan.running_schema_version is None
        assert plan.current_schema_version == 0
        assert plan.db_schema_version is None
        assert plan.stop_daemon is False
        assert plan.run_migrations is False
        assert plan.start_daemon is False
        assert plan.restore_team_backups is False
        assert plan.full_index_rebuild is False
        assert plan.team_backup_count == 0
        assert plan.team_backup_files == []
        assert plan.compatible_backup_files == []
        assert plan.skipped_backup_files == []

    def test_sync_plan_with_version_mismatch(self):
        """Test SyncPlan with version mismatch."""
        plan = SyncPlan(
            needs_sync=True,
            reasons=[SyncReason.OAK_VERSION_CHANGED],
            running_oak_version="0.9.0",
            current_oak_version="0.10.0",
            stop_daemon=True,
            start_daemon=True,
        )

        assert plan.needs_sync is True
        assert SyncReason.OAK_VERSION_CHANGED in plan.reasons
        assert plan.running_oak_version == "0.9.0"
        assert plan.current_oak_version == "0.10.0"
        assert plan.stop_daemon is True
        assert plan.start_daemon is True

    def test_sync_plan_with_team_backups(self):
        """Test SyncPlan with team backups."""
        plan = SyncPlan(
            needs_sync=True,
            reasons=[SyncReason.TEAM_BACKUPS_AVAILABLE],
            restore_team_backups=True,
            team_backup_count=3,
            team_backup_files=["alice_abc123.sql", "bob_def456.sql", "charlie_ghi789.sql"],
        )

        assert plan.restore_team_backups is True
        assert plan.team_backup_count == 3
        assert len(plan.team_backup_files) == 3

    def test_sync_plan_with_full_rebuild(self):
        """Test SyncPlan with full rebuild."""
        plan = SyncPlan(
            needs_sync=True,
            reasons=[SyncReason.MANUAL_FULL_REBUILD],
            full_index_rebuild=True,
            stop_daemon=True,
            start_daemon=True,
        )

        assert plan.full_index_rebuild is True
        assert SyncReason.MANUAL_FULL_REBUILD in plan.reasons


class TestSyncResult:
    """Test SyncResult dataclass."""

    def test_sync_result_defaults(self):
        """Test SyncResult default values."""
        result = SyncResult(success=True)

        assert result.success is True
        assert result.operations_completed == []
        assert result.warnings == []
        assert result.errors == []
        assert result.records_imported == 0
        assert result.records_skipped == 0
        assert result.migrations_applied == 0

    def test_sync_result_with_operations(self):
        """Test SyncResult with completed operations."""
        result = SyncResult(
            success=True,
            operations_completed=[
                "Daemon stopped",
                "First restore pass: 2 files",
                "Daemon started",
            ],
            records_imported=150,
            records_skipped=25,
        )

        assert result.success is True
        assert len(result.operations_completed) == 3
        assert result.records_imported == 150
        assert result.records_skipped == 25

    def test_sync_result_with_errors(self):
        """Test SyncResult with errors."""
        result = SyncResult(
            success=False,
            operations_completed=["Daemon stopped"],
            errors=["Failed to start daemon"],
        )

        assert result.success is False
        assert len(result.operations_completed) == 1
        assert len(result.errors) == 1
        assert "Failed to start daemon" in result.errors

    def test_sync_result_with_warnings(self):
        """Test SyncResult with warnings."""
        result = SyncResult(
            success=True,
            operations_completed=["Sync complete"],
            warnings=["Some backups had newer schema"],
        )

        assert result.success is True
        assert len(result.warnings) == 1

    def test_sync_result_with_migrations(self):
        """Test SyncResult with migrations applied."""
        result = SyncResult(
            success=True,
            operations_completed=["Migrations applied"],
            migrations_applied=3,
        )

        assert result.migrations_applied == 3
