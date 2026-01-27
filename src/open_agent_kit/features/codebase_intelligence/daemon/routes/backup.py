"""Backup and restore routes for CI daemon.

Provides API endpoints for creating and restoring database backups.
Backups preserve valuable session, prompt, and memory data across
feature removal/reinstall cycles.

Supports multi-machine/multi-user backups with content-based deduplication.
"""

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from open_agent_kit.config.paths import OAK_DIR
from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
    ImportResult,
    discover_backup_files,
    extract_machine_id_from_filename,
    get_backup_filename,
    get_machine_identifier,
)
from open_agent_kit.features.codebase_intelligence.constants import (
    CI_ACTIVITIES_DB_FILENAME,
    CI_DATA_DIR,
    CI_HISTORY_BACKUP_DIR,
)
from open_agent_kit.features.codebase_intelligence.daemon.state import get_state

logger = logging.getLogger(__name__)
router = APIRouter(tags=["backup"])


class BackupRequest(BaseModel):
    """Request to create a database backup."""

    include_activities: bool = False
    output_path: str | None = None  # None = use machine-specific default


class RestoreRequest(BaseModel):
    """Request to restore from a database backup."""

    input_path: str | None = None  # None = use machine-specific default
    dry_run: bool = False
    auto_rebuild_chromadb: bool = True  # Rebuild ChromaDB after restore


class RestoreAllRequest(BaseModel):
    """Request to restore from all backup files."""

    dry_run: bool = False
    auto_rebuild_chromadb: bool = True  # Rebuild ChromaDB after restore


class BackupFileInfo(BaseModel):
    """Information about a single backup file."""

    filename: str
    machine_id: str
    size_bytes: int
    last_modified: str


class BackupStatusResponse(BaseModel):
    """Response for backup status check."""

    backup_exists: bool
    backup_path: str
    backup_size_bytes: int | None = None
    last_modified: str | None = None
    machine_id: str  # Current machine identifier
    all_backups: list[BackupFileInfo] = []  # All available backup files


class RestoreResponse(BaseModel):
    """Response for restore operations with deduplication stats."""

    status: str
    message: str
    backup_path: str | None = None
    sessions_imported: int = 0
    sessions_skipped: int = 0
    batches_imported: int = 0
    batches_skipped: int = 0
    observations_imported: int = 0
    observations_skipped: int = 0
    activities_imported: int = 0
    activities_skipped: int = 0
    errors: int = 0
    chromadb_rebuild_started: bool = False

    @classmethod
    def from_import_result(
        cls,
        result: ImportResult,
        backup_path: str | None = None,
        chromadb_rebuild_started: bool = False,
    ) -> "RestoreResponse":
        """Create response from ImportResult."""
        message = (
            f"Restored {result.total_imported} records, skipped {result.total_skipped} duplicates"
        )
        if chromadb_rebuild_started:
            message += ". ChromaDB rebuild started in background."
        return cls(
            status="completed",
            message=message,
            backup_path=backup_path,
            sessions_imported=result.sessions_imported,
            sessions_skipped=result.sessions_skipped,
            batches_imported=result.batches_imported,
            batches_skipped=result.batches_skipped,
            observations_imported=result.observations_imported,
            observations_skipped=result.observations_skipped,
            activities_imported=result.activities_imported,
            activities_skipped=result.activities_skipped,
            errors=result.errors,
            chromadb_rebuild_started=chromadb_rebuild_started,
        )


class RestoreAllResponse(BaseModel):
    """Response for restore-all operations."""

    status: str
    message: str
    files_processed: int
    total_imported: int
    total_skipped: int
    total_errors: int
    per_file: dict[str, RestoreResponse]


@router.get("/api/backup/status")
async def get_backup_status() -> BackupStatusResponse:
    """Get current backup file status including all team backups."""
    state = get_state()

    if not state.project_root:
        raise HTTPException(status_code=503, detail="Project root not initialized")

    from datetime import datetime

    machine_id = get_machine_identifier()
    backup_dir = state.project_root / CI_HISTORY_BACKUP_DIR
    backup_filename = get_backup_filename()
    backup_path = backup_dir / backup_filename

    logger.debug(f"Checking backup status: {backup_path} (machine: {machine_id})")

    # Get all backup files
    all_backups: list[BackupFileInfo] = []
    for bf in discover_backup_files(backup_dir):
        stat = bf.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime).isoformat()
        file_machine_id = extract_machine_id_from_filename(bf.name)
        all_backups.append(
            BackupFileInfo(
                filename=bf.name,
                machine_id=file_machine_id,
                size_bytes=stat.st_size,
                last_modified=mtime,
            )
        )

    # Check this machine's backup
    if backup_path.exists():
        stat = backup_path.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime).isoformat()
        return BackupStatusResponse(
            backup_exists=True,
            backup_path=str(backup_path),
            backup_size_bytes=stat.st_size,
            last_modified=mtime,
            machine_id=machine_id,
            all_backups=all_backups,
        )

    return BackupStatusResponse(
        backup_exists=False,
        backup_path=str(backup_path),
        machine_id=machine_id,
        all_backups=all_backups,
    )


@router.post("/api/backup/create")
async def create_backup(request: BackupRequest) -> dict[str, Any]:
    """Create a backup of the CI database with machine-specific filename."""
    state = get_state()

    if not state.project_root:
        raise HTTPException(status_code=503, detail="Project root not initialized")

    if not state.activity_store:
        raise HTTPException(status_code=503, detail="Activity store not initialized")

    ci_data_dir = state.project_root / OAK_DIR / CI_DATA_DIR
    db_path = ci_data_dir / CI_ACTIVITIES_DB_FILENAME
    if not db_path.exists():
        raise HTTPException(status_code=404, detail="No database to backup")

    if request.output_path:
        backup_path = Path(request.output_path)
    else:
        # Use machine-specific filename
        backup_filename = get_backup_filename()
        backup_path = state.project_root / CI_HISTORY_BACKUP_DIR / backup_filename

    machine_id = get_machine_identifier()
    logger.info(
        f"Creating backup: include_activities={request.include_activities}, "
        f"machine={machine_id}, path={backup_path}"
    )

    backup_path.parent.mkdir(parents=True, exist_ok=True)

    from open_agent_kit.features.codebase_intelligence.activity.store import ActivityStore

    store = ActivityStore(db_path)
    count = store.export_to_sql(backup_path, include_activities=request.include_activities)
    store.close()

    logger.info(f"Backup complete: {count} records exported to {backup_path}")

    return {
        "status": "completed",
        "message": f"Exported {count} records",
        "backup_path": str(backup_path),
        "record_count": count,
        "machine_id": machine_id,
    }


@router.post("/api/backup/restore")
async def restore_backup(
    request: RestoreRequest, background_tasks: BackgroundTasks
) -> RestoreResponse:
    """Restore CI database from backup with deduplication.

    After restore, automatically triggers a ChromaDB rebuild to sync
    the search index with the restored SQLite data.
    """
    state = get_state()

    if not state.project_root:
        raise HTTPException(status_code=503, detail="Project root not initialized")

    if not state.activity_store:
        raise HTTPException(status_code=503, detail="Activity store not initialized")

    ci_data_dir = state.project_root / OAK_DIR / CI_DATA_DIR
    db_path = ci_data_dir / CI_ACTIVITIES_DB_FILENAME
    if not db_path.exists():
        raise HTTPException(status_code=404, detail="No database to restore into")

    backup_dir = state.project_root / CI_HISTORY_BACKUP_DIR

    if request.input_path:
        backup_path = Path(request.input_path)
    else:
        # Default to this machine's backup file
        backup_filename = get_backup_filename()
        backup_path = backup_dir / backup_filename

        # Fall back to legacy filename if machine-specific doesn't exist
        if not backup_path.exists():
            legacy_path = backup_dir / "ci_history.sql"
            if legacy_path.exists():
                backup_path = legacy_path

    if not backup_path.exists():
        raise HTTPException(status_code=404, detail=f"Backup file not found: {backup_path}")

    logger.info(f"Restoring from backup: {backup_path} (dry_run={request.dry_run})")

    from open_agent_kit.features.codebase_intelligence.activity.store import ActivityStore

    store = ActivityStore(db_path)
    result = store.import_from_sql_with_dedup(backup_path, dry_run=request.dry_run)
    store.close()

    logger.info(
        f"Restore complete: {result.total_imported} imported, "
        f"{result.total_skipped} skipped from {backup_path}"
    )

    # Trigger ChromaDB rebuild if not dry run and requested
    chromadb_rebuild_started = False
    if (
        not request.dry_run
        and request.auto_rebuild_chromadb
        and result.total_imported > 0
        and state.activity_processor
    ):
        logger.info("Starting post-restore ChromaDB rebuild in background")
        background_tasks.add_task(
            state.activity_processor.rebuild_chromadb_from_sqlite,
            batch_size=50,
            reset_embedded_flags=True,
            clear_chromadb_first=True,  # Remove orphans before rebuilding
        )
        chromadb_rebuild_started = True

    return RestoreResponse.from_import_result(
        result, str(backup_path), chromadb_rebuild_started=chromadb_rebuild_started
    )


@router.post("/api/backup/restore-all")
async def restore_all_backups_endpoint(
    request: RestoreAllRequest, background_tasks: BackgroundTasks
) -> RestoreAllResponse:
    """Restore from all backup files in oak/data/ with deduplication.

    Merges all team members' backups into the current database.
    Each record is only imported once based on its content hash.

    After restore, automatically triggers a ChromaDB rebuild to sync
    the search index with the restored SQLite data.
    """
    state = get_state()

    if not state.project_root:
        raise HTTPException(status_code=503, detail="Project root not initialized")

    if not state.activity_store:
        raise HTTPException(status_code=503, detail="Activity store not initialized")

    ci_data_dir = state.project_root / OAK_DIR / CI_DATA_DIR
    db_path = ci_data_dir / CI_ACTIVITIES_DB_FILENAME
    if not db_path.exists():
        raise HTTPException(status_code=404, detail="No database to restore into")

    backup_dir = state.project_root / CI_HISTORY_BACKUP_DIR
    backup_files = discover_backup_files(backup_dir)

    if not backup_files:
        raise HTTPException(status_code=404, detail=f"No backup files found in {backup_dir}")

    logger.info(f"Restoring from {len(backup_files)} backup files (dry_run={request.dry_run})")

    from open_agent_kit.features.codebase_intelligence.activity.store import ActivityStore

    store = ActivityStore(db_path)
    results = store.restore_all_backups(backup_dir, dry_run=request.dry_run)
    store.close()

    # Build per-file responses
    per_file: dict[str, RestoreResponse] = {}
    for filename, result in results.items():
        per_file[filename] = RestoreResponse.from_import_result(result, filename)

    total_imported = sum(r.total_imported for r in results.values())
    total_skipped = sum(r.total_skipped for r in results.values())
    total_errors = sum(r.errors for r in results.values())

    # Trigger ChromaDB rebuild if not dry run and requested
    chromadb_rebuild_started = False
    if (
        not request.dry_run
        and request.auto_rebuild_chromadb
        and total_imported > 0
        and state.activity_processor
    ):
        logger.info("Starting post-restore ChromaDB rebuild in background")
        background_tasks.add_task(
            state.activity_processor.rebuild_chromadb_from_sqlite,
            batch_size=50,
            reset_embedded_flags=True,
            clear_chromadb_first=True,  # Remove orphans before rebuilding
        )
        chromadb_rebuild_started = True

    logger.info(
        f"Restore all complete: {total_imported} imported, "
        f"{total_skipped} skipped, {total_errors} errors"
    )

    message = (
        f"Restored {total_imported} records from {len(backup_files)} files, "
        f"skipped {total_skipped} duplicates"
    )
    if chromadb_rebuild_started:
        message += ". ChromaDB rebuild started in background."

    return RestoreAllResponse(
        status="completed",
        message=message,
        files_processed=len(backup_files),
        total_imported=total_imported,
        total_skipped=total_skipped,
        total_errors=total_errors,
        per_file=per_file,
    )
