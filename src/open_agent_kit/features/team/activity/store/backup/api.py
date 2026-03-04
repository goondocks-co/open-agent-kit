"""Public API for backup and restore operations."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from open_agent_kit.features.team.activity.store.backup.exporter import (
    export_to_sql,
)
from open_agent_kit.features.team.activity.store.backup.importer import (
    import_from_sql_with_dedup,
)
from open_agent_kit.features.team.activity.store.backup.machine_id import (
    get_backup_filename,
    get_machine_identifier,
)
from open_agent_kit.features.team.activity.store.backup.models import (
    BackupResult,
    ImportResult,
    RestoreAllResult,
    RestoreResult,
)
from open_agent_kit.features.team.activity.store.backup.paths import (
    discover_backup_files,
    get_backup_dir,
)

if TYPE_CHECKING:
    from open_agent_kit.features.team.activity.store.core import ActivityStore

logger = logging.getLogger(__name__)


def create_backup(
    project_root: Path,
    db_path: Path,
    *,
    include_activities: bool | None = None,
    output_path: Path | None = None,
    activity_store: ActivityStore | None = None,
) -> BackupResult:
    """Single entry point for all backup operations.

    When include_activities is None, the value is loaded from BackupConfig.
    Explicit True/False overrides the config value.

    When *activity_store* is provided it is used directly instead of
    creating a new ``ActivityStore``.  The caller retains ownership --
    the store is **not** closed by this function in that case.

    Args:
        project_root: Project root directory.
        db_path: Path to the SQLite database.
        include_activities: Whether to include activities table.
            None means load from config.
        output_path: Custom output path. None means use default
            backup directory with machine-id filename.
        activity_store: Optional pre-existing ActivityStore to reuse.

    Returns:
        BackupResult with operation details.
    """
    from open_agent_kit.features.team.activity.store.core import ActivityStore

    # Resolve include_activities from config if not explicitly set
    if include_activities is None:
        try:
            from open_agent_kit.features.team.config import load_ci_config

            config = load_ci_config(project_root)
            include_activities = config.backup.include_activities
        except (OSError, ValueError, KeyError, AttributeError):
            from open_agent_kit.features.team.constants import (
                BACKUP_INCLUDE_ACTIVITIES_DEFAULT,
            )

            include_activities = BACKUP_INCLUDE_ACTIVITIES_DEFAULT

    # Check db exists
    if not db_path.exists():
        return BackupResult(
            success=False,
            include_activities=include_activities,
            error=f"Database not found: {db_path}",
        )

    # Resolve machine_id, backup_dir, backup_path
    machine_id = get_machine_identifier(project_root)
    if output_path is None:
        backup_dir = get_backup_dir(project_root)
        backup_dir.mkdir(parents=True, exist_ok=True)
        output_path = backup_dir / get_backup_filename(machine_id)

    # Reuse existing store or create a new one
    store_provided = activity_store is not None
    store: ActivityStore | None = activity_store
    try:
        if store is None:
            store = ActivityStore(db_path, machine_id)
        record_count = export_to_sql(store, output_path, include_activities=include_activities)
        return BackupResult(
            success=True,
            backup_path=output_path,
            record_count=record_count,
            machine_id=machine_id,
            include_activities=include_activities,
        )
    except (OSError, ValueError, RuntimeError) as exc:
        return BackupResult(
            success=False,
            backup_path=output_path,
            machine_id=machine_id,
            include_activities=include_activities,
            error=str(exc),
        )
    finally:
        # Only close if we created the store ourselves
        if not store_provided and store is not None:
            store.close()


def restore_backup(
    project_root: Path,
    db_path: Path,
    *,
    input_path: Path | None = None,
    dry_run: bool = False,
) -> RestoreResult:
    """Single entry point for single-file restore.

    If input_path is None, resolves the backup file for the current machine.
    Falls back to the legacy CI_HISTORY_BACKUP_FILE if the machine-specific
    file does not exist.

    Args:
        project_root: Project root directory.
        db_path: Path to the SQLite database.
        input_path: Explicit backup file to restore. None means auto-resolve.
        dry_run: If True, preview what would be imported without changes.

    Returns:
        RestoreResult with operation details.
    """
    from open_agent_kit.features.team.activity.store.core import ActivityStore
    from open_agent_kit.features.team.constants import (
        CI_HISTORY_BACKUP_FILE,
    )

    if not db_path.exists():
        return RestoreResult(
            success=False,
            error=f"Database not found: {db_path}",
        )

    machine_id = get_machine_identifier(project_root)

    # Resolve backup path
    if input_path is None:
        backup_dir = get_backup_dir(project_root)
        machine_backup = backup_dir / get_backup_filename(machine_id)
        legacy_backup = backup_dir / CI_HISTORY_BACKUP_FILE

        if machine_backup.exists():
            input_path = machine_backup
        elif legacy_backup.exists():
            input_path = legacy_backup
        else:
            return RestoreResult(
                success=False,
                machine_id=machine_id,
                error=f"No backup file found in {backup_dir}",
            )

    if not input_path.exists():
        return RestoreResult(
            success=False,
            backup_path=input_path,
            machine_id=machine_id,
            error=f"Backup file not found: {input_path}",
        )

    store: ActivityStore | None = None
    try:
        store = ActivityStore(db_path, machine_id)
        import_result = import_from_sql_with_dedup(store, input_path, dry_run=dry_run)
        return RestoreResult(
            success=True,
            backup_path=input_path,
            import_result=import_result,
            machine_id=machine_id,
        )
    except (OSError, ValueError, RuntimeError) as exc:
        return RestoreResult(
            success=False,
            backup_path=input_path,
            machine_id=machine_id,
            error=str(exc),
        )
    finally:
        if store is not None:
            store.close()


def restore_all(
    project_root: Path,
    db_path: Path,
    *,
    backup_files: list[Path] | None = None,
    dry_run: bool = False,
    replace_machine: bool = False,
    vector_store: Any | None = None,
) -> RestoreAllResult:
    """Single entry point for multi-file restore.

    If backup_files is None, discovers all .sql files in the backup directory
    via discover_backup_files().

    Args:
        project_root: Project root directory.
        db_path: Path to the SQLite database.
        backup_files: Explicit list of backup files. None means auto-discover.
        dry_run: If True, preview what would be imported without changes.
        replace_machine: If True, delete all existing records from the backup's
            source machine before importing (drop-and-replace semantics).
        vector_store: Optional vector store for ChromaDB cleanup during replace.

    Returns:
        RestoreAllResult with per-file details.
    """
    from open_agent_kit.features.team.activity.store.core import ActivityStore

    if not db_path.exists():
        return RestoreAllResult(
            success=False,
            error=f"Database not found: {db_path}",
        )

    machine_id = get_machine_identifier(project_root)

    # Discover backup files if not provided
    if backup_files is None:
        backup_dir = get_backup_dir(project_root)
        backup_files = discover_backup_files(backup_dir)

    if not backup_files:
        return RestoreAllResult(
            success=True,
            machine_id=machine_id,
        )

    store: ActivityStore | None = None
    try:
        store = ActivityStore(db_path, machine_id)
        per_file: dict[str, ImportResult] = {}
        for backup_file in backup_files:
            result = import_from_sql_with_dedup(
                store,
                backup_file,
                dry_run=dry_run,
                replace_machine=replace_machine,
                vector_store=vector_store,
            )
            per_file[backup_file.name] = result

        # Replay unapplied resolution events from imported backups
        if not dry_run:
            try:
                from open_agent_kit.features.team.activity.store.resolution_events import (
                    replay_unapplied_events,
                )

                applied = replay_unapplied_events(store, vector_store)
                if applied:
                    logger.info(f"Post-restore: replayed {applied} resolution events")
            except Exception:  # noqa: BLE001
                logger.debug("Post-restore resolution event replay failed", exc_info=True)

        # After large delete+insert cycles the query planner statistics go
        # stale.  ANALYZE is cheap (reads index pages) and keeps subsequent
        # queries using optimal plans.  Only needed when we actually mutated.
        if replace_machine and not dry_run and any(r.total_deleted > 0 for r in per_file.values()):
            try:
                store._get_connection().execute("ANALYZE")
                logger.debug("Post-restore ANALYZE complete")
            except Exception:  # noqa: BLE001
                logger.debug("Post-restore ANALYZE failed (non-critical)", exc_info=True)

        return RestoreAllResult(
            success=True,
            per_file=per_file,
            machine_id=machine_id,
        )
    except (OSError, ValueError, RuntimeError) as exc:
        return RestoreAllResult(
            success=False,
            machine_id=machine_id,
            error=str(exc),
        )
    finally:
        if store is not None:
            store.close()
