"""SyncService for orchestrating CI sync operations."""

from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path
from typing import TYPE_CHECKING

from open_agent_kit.config.paths import OAK_DIR

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.store import ActivityStore
    from open_agent_kit.features.codebase_intelligence.daemon.manager import DaemonManager
from open_agent_kit.constants import VERSION
from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
    discover_backup_files,
    get_backup_dir,
    get_backup_filename,
)
from open_agent_kit.features.codebase_intelligence.activity.store.schema import SCHEMA_VERSION
from open_agent_kit.features.codebase_intelligence.constants import (
    CI_ACTIVITIES_DB_FILENAME,
    CI_CHROMA_DIR,
    CI_DATA_DIR,
)
from open_agent_kit.features.codebase_intelligence.sync.models import (
    SyncPlan,
    SyncReason,
    SyncResult,
)

logger = logging.getLogger(__name__)


class SyncService:
    """Service for orchestrating CI sync operations.

    Handles the complete sync workflow with proper ordering:
    1. Stop daemon gracefully
    2. First restore pass (compatible backups only)
    3. Delete ChromaDB if full rebuild requested
    4. Start daemon (runs migrations)
    5. Create fresh backup
    6. Second restore pass (previously skipped files)
    7. Re-embed/re-index automatically on daemon startup
    """

    def __init__(self, project_root: Path):
        """Initialize the sync service.

        Args:
            project_root: Root directory of the project.
        """
        self.project_root = project_root
        self.ci_data_dir = project_root / OAK_DIR / CI_DATA_DIR
        self.backup_dir = get_backup_dir(project_root)
        self.chroma_dir = self.ci_data_dir / CI_CHROMA_DIR
        self.db_path = self.ci_data_dir / CI_ACTIVITIES_DB_FILENAME

    def _get_daemon_manager(self) -> DaemonManager:
        """Get daemon manager instance."""
        from open_agent_kit.features.codebase_intelligence.daemon.manager import (
            DaemonManager,
            get_project_port,
        )

        port = get_project_port(self.project_root, self.ci_data_dir)
        return DaemonManager(
            project_root=self.project_root,
            port=port,
            ci_data_dir=self.ci_data_dir,
        )

    def _get_activity_store(self) -> ActivityStore:
        """Get activity store instance."""
        from open_agent_kit.features.codebase_intelligence.activity.store import ActivityStore
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            get_machine_identifier,
        )

        return ActivityStore(self.db_path, machine_id=get_machine_identifier(self.project_root))

    def detect_changes(
        self,
        include_team: bool = False,
        force_full: bool = False,
    ) -> SyncPlan:
        """Detect what changes need to be synced.

        Args:
            include_team: Include team backup restoration.
            force_full: Force full index rebuild.

        Returns:
            SyncPlan describing what operations are needed.
        """
        plan = SyncPlan(
            needs_sync=False,
            current_oak_version=VERSION,
            current_schema_version=SCHEMA_VERSION,
        )

        manager = self._get_daemon_manager()

        # Check if daemon is running
        plan.daemon_running = manager.is_running()

        # Get running daemon version info
        daemon_version = manager.get_daemon_version()
        if daemon_version:
            plan.running_oak_version = daemon_version.get("oak_version")
            plan.running_schema_version = daemon_version.get("schema_version")

        # Get current database schema version
        if self.db_path.exists():
            store = self._get_activity_store()
            plan.db_schema_version = store.get_schema_version()
            store.close()

        # Check for OAK version mismatch
        if plan.running_oak_version and plan.running_oak_version != VERSION:
            plan.needs_sync = True
            plan.reasons.append(SyncReason.OAK_VERSION_CHANGED)
            plan.stop_daemon = True
            plan.start_daemon = True
            logger.info(f"OAK version mismatch: daemon={plan.running_oak_version}, code={VERSION}")
        elif plan.daemon_running and not plan.running_oak_version:
            # Daemon running with old code that doesn't report version
            plan.needs_sync = True
            plan.reasons.append(SyncReason.OAK_VERSION_CHANGED)
            plan.stop_daemon = True
            plan.start_daemon = True
            logger.info("Daemon running with old code (no version reported), restart needed")

        # Check for schema version mismatch (daemon vs code)
        if (
            plan.running_schema_version is not None
            and plan.running_schema_version != SCHEMA_VERSION
        ):
            plan.needs_sync = True
            plan.reasons.append(SyncReason.SCHEMA_VERSION_CHANGED)
            plan.run_migrations = True
            plan.stop_daemon = True
            plan.start_daemon = True
            logger.info(
                f"Schema version mismatch: daemon={plan.running_schema_version}, code={SCHEMA_VERSION}"
            )

        # Check for team backups
        if include_team:
            from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
                get_machine_identifier,
            )

            machine_id = get_machine_identifier(self.project_root)
            own_backup = get_backup_filename(machine_id)
            backup_files = discover_backup_files(self.backup_dir)

            # Filter to team backups (not our own)
            team_files = [f for f in backup_files if f.name != own_backup]
            plan.team_backup_count = len(team_files)
            plan.team_backup_files = [f.name for f in team_files]

            if team_files:
                plan.needs_sync = True
                plan.reasons.append(SyncReason.TEAM_BACKUPS_AVAILABLE)
                plan.restore_team_backups = True
                plan.stop_daemon = True
                plan.start_daemon = True
                logger.info(f"Team backups: {len(team_files)} files found")

        # Force full rebuild
        if force_full:
            plan.needs_sync = True
            plan.reasons.append(SyncReason.MANUAL_FULL_REBUILD)
            plan.full_index_rebuild = True
            plan.stop_daemon = True
            plan.start_daemon = True
            logger.info("Full index rebuild requested")

        # Add NO_CHANGES if nothing else
        if not plan.reasons:
            plan.reasons.append(SyncReason.NO_CHANGES)

        return plan

    def execute_sync(
        self,
        plan: SyncPlan,
        dry_run: bool = False,
        include_activities: bool = False,
    ) -> SyncResult:
        """Execute the sync plan.

        Args:
            plan: The sync plan to execute.
            dry_run: If True, preview without making changes.
            include_activities: If True, include activities table in backup.

        Returns:
            SyncResult with operation outcomes.
        """
        result = SyncResult(success=True)

        if not plan.needs_sync:
            result.operations_completed.append("No sync needed")
            return result

        if dry_run:
            result.operations_completed.append("Dry run - no changes made")
            if plan.stop_daemon:
                result.operations_completed.append("Would stop daemon")
            if plan.restore_team_backups:
                result.operations_completed.append(
                    f"Would restore {len(plan.compatible_backup_files)} compatible backups"
                )
                if plan.skipped_backup_files:
                    result.warnings.append(
                        f"Would skip {len(plan.skipped_backup_files)} backups "
                        "with newer schema (will import after upgrade)"
                    )
            if plan.full_index_rebuild:
                result.operations_completed.append("Would delete ChromaDB for full rebuild")
            if plan.start_daemon:
                result.operations_completed.append("Would start daemon")
            return result

        manager = self._get_daemon_manager()

        # Step 1: Stop daemon if needed
        if plan.stop_daemon and manager.is_running():
            logger.info("Stopping daemon...")
            if manager.stop():
                result.operations_completed.append("Daemon stopped")
            else:
                result.success = False
                result.errors.append("Failed to stop daemon")
                return result
            time.sleep(0.5)  # Brief pause

        # Step 2: First restore pass (all team backups)
        if plan.restore_team_backups and plan.team_backup_files:
            logger.info(f"Restoring {len(plan.team_backup_files)} team backups...")
            try:
                from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
                    restore_all,
                )

                team_paths = [self.backup_dir / f for f in plan.team_backup_files]
                restore_result = restore_all(
                    project_root=self.project_root,
                    db_path=self.db_path,
                    backup_files=team_paths,
                )
                if restore_result.success:
                    result.records_imported += restore_result.total_imported
                    result.records_skipped += restore_result.total_skipped
                result.operations_completed.append(
                    f"First restore pass: {len(plan.team_backup_files)} files"
                )
            except Exception as e:
                result.warnings.append(f"First restore pass error: {e}")
                logger.warning(f"First restore pass error: {e}")

        # Step 3: Delete ChromaDB if full rebuild
        if plan.full_index_rebuild and self.chroma_dir.exists():
            logger.info("Deleting ChromaDB for full rebuild...")
            try:
                shutil.rmtree(self.chroma_dir)
                result.operations_completed.append("ChromaDB deleted for rebuild")
            except OSError as e:
                result.warnings.append(f"Failed to delete ChromaDB: {e}")
                logger.warning(f"Failed to delete ChromaDB: {e}")

        # Step 4: Start daemon (runs migrations on startup)
        if plan.start_daemon:
            logger.info("Starting daemon...")
            if manager.start(wait=True):
                result.operations_completed.append("Daemon started")
                if plan.run_migrations:
                    result.migrations_applied = SCHEMA_VERSION - (plan.db_schema_version or 0)
                    result.operations_completed.append(
                        f"Migrations applied (v{plan.db_schema_version or 0} -> v{SCHEMA_VERSION})"
                    )
            else:
                result.success = False
                result.errors.append("Failed to start daemon")
                return result

        # Step 5: Create fresh backup with current schema
        if plan.restore_team_backups:
            logger.info("Creating fresh backup...")
            try:
                from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
                    create_backup,
                )

                backup_result = create_backup(
                    project_root=self.project_root,
                    db_path=self.db_path,
                    include_activities=include_activities,
                )
                if backup_result.success:
                    activities_note = " (with activities)" if include_activities else ""
                    result.operations_completed.append(
                        f"Backup created: {backup_result.record_count} records{activities_note}"
                    )
            except Exception as e:
                result.warnings.append(f"Backup creation error: {e}")
                logger.warning(f"Backup creation error: {e}")

        # Step 6: Second restore pass (all team backups again after migrations)
        if plan.restore_team_backups and plan.team_backup_files:
            logger.info(f"Second restore pass: {len(plan.team_backup_files)} files...")
            try:
                from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
                    restore_all,
                )

                team_paths = [self.backup_dir / f for f in plan.team_backup_files]
                restore_result = restore_all(
                    project_root=self.project_root,
                    db_path=self.db_path,
                    backup_files=team_paths,
                )
                if restore_result.success:
                    result.records_imported += restore_result.total_imported
                    result.records_skipped += restore_result.total_skipped
                result.operations_completed.append(
                    f"Second restore pass: {len(plan.team_backup_files)} files"
                )
            except Exception as e:
                result.warnings.append(f"Second restore pass error: {e}")
                logger.warning(f"Second restore pass error: {e}")

        # Re-embed/re-index happens automatically on daemon startup if needed
        if plan.full_index_rebuild:
            result.operations_completed.append("Full index rebuild in progress (background)")

        return result
