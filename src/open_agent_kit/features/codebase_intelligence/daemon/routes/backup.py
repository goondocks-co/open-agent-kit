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
    _parse_backup_schema_version,
    discover_backup_files,
    extract_machine_id_from_filename,
    get_backup_filename,
    get_machine_identifier,
)
from open_agent_kit.features.codebase_intelligence.activity.store.schema import SCHEMA_VERSION
from open_agent_kit.features.codebase_intelligence.constants import (
    CI_ACTIVITIES_DB_FILENAME,
    CI_BACKUP_HEADER_MAX_LINES,
    CI_BACKUP_PATH_INVALID_ERROR,
    CI_DATA_DIR,
    CI_HISTORY_BACKUP_DIR,
    CI_HISTORY_BACKUP_FILE,
    CI_LINE_SEPARATOR,
    CI_TEXT_ENCODING,
)
from open_agent_kit.features.codebase_intelligence.daemon.state import get_state

logger = logging.getLogger(__name__)
router = APIRouter(tags=["backup"])


def _ensure_backup_path_within_dir(backup_dir: Path, candidate: Path) -> Path:
    """Ensure backup path stays within the allowed backup directory."""
    resolved_candidate = candidate.resolve()
    resolved_backup_dir = backup_dir.resolve()
    if not resolved_candidate.is_relative_to(resolved_backup_dir):
        raise HTTPException(
            status_code=400,
            detail=CI_BACKUP_PATH_INVALID_ERROR.format(backup_dir=backup_dir),
        )
    return candidate


def _read_backup_header_lines(backup_path: Path, max_lines: int) -> list[str]:
    """Read only the header lines from a backup file."""
    try:
        with backup_path.open("r", encoding=CI_TEXT_ENCODING) as handle:
            lines: list[str] = []
            for _ in range(max_lines):
                line = handle.readline()
                if not line:
                    break
                lines.append(line.rstrip(CI_LINE_SEPARATOR))
            return lines
    except (OSError, UnicodeDecodeError):
        return []


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
    schema_version: int | None = None  # Schema version from backup file header
    schema_compatible: bool = True  # Compatible with current schema?
    schema_warning: str | None = None  # Warning message if not fully compatible


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
    error_messages: list[str] = []  # Detailed error messages for debugging
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
        if result.errors > 0:
            message += f" ({result.errors} errors)"
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
            error_messages=result.error_messages,
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

        # Parse schema version from backup file header
        backup_schema: int | None = None
        schema_compatible = True
        schema_warning: str | None = None
        try:
            lines = _read_backup_header_lines(bf, CI_BACKUP_HEADER_MAX_LINES)
            backup_schema = _parse_backup_schema_version(lines)
            if backup_schema is not None:
                if backup_schema > SCHEMA_VERSION:
                    schema_compatible = False
                    schema_warning = (
                        f"Backup schema v{backup_schema} is newer than current v{SCHEMA_VERSION}. "
                        "Some data may not be imported. Upgrade OAK to import fully."
                    )
                elif backup_schema < SCHEMA_VERSION:
                    schema_warning = (
                        f"Backup schema v{backup_schema} is older than current v{SCHEMA_VERSION}. "
                        "Import will use default values for new fields."
                    )
        except (OSError, UnicodeDecodeError):
            pass

        all_backups.append(
            BackupFileInfo(
                filename=bf.name,
                machine_id=file_machine_id,
                size_bytes=stat.st_size,
                last_modified=mtime,
                schema_version=backup_schema,
                schema_compatible=schema_compatible,
                schema_warning=schema_warning,
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

    backup_dir = state.project_root / CI_HISTORY_BACKUP_DIR

    if request.output_path:
        backup_path = _ensure_backup_path_within_dir(
            backup_dir,
            Path(request.output_path),
        )
    else:
        # Use machine-specific filename
        backup_filename = get_backup_filename()
        backup_path = backup_dir / backup_filename

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
        backup_path = _ensure_backup_path_within_dir(
            backup_dir,
            Path(request.input_path),
        )
    else:
        # Default to this machine's backup file
        backup_filename = get_backup_filename()
        backup_path = backup_dir / backup_filename

        # Fall back to legacy filename if machine-specific doesn't exist
        if not backup_path.exists():
            legacy_path = backup_dir / CI_HISTORY_BACKUP_FILE
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

        # Also re-embed session summaries for the suggestion system
        if state.vector_store:
            from open_agent_kit.features.codebase_intelligence.activity.processor.session_index import (
                reembed_session_summaries,
            )

            background_tasks.add_task(
                reembed_session_summaries,
                activity_store=state.activity_store,
                vector_store=state.vector_store,
                clear_first=True,
            )
            logger.info("Starting post-restore session summary re-embedding in background")

    return RestoreResponse.from_import_result(
        result, str(backup_path), chromadb_rebuild_started=chromadb_rebuild_started
    )


@router.post("/api/backup/restore-all")
async def restore_all_backups_endpoint(
    request: RestoreAllRequest, background_tasks: BackgroundTasks
) -> RestoreAllResponse:
    """Restore from all backup files in the history directory with deduplication.

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

        # Also re-embed session summaries for the suggestion system
        if state.vector_store:
            from open_agent_kit.features.codebase_intelligence.activity.processor.session_index import (
                reembed_session_summaries,
            )

            background_tasks.add_task(
                reembed_session_summaries,
                activity_store=state.activity_store,
                vector_store=state.vector_store,
                clear_first=True,
            )
            logger.info("Starting post-restore session summary re-embedding in background")

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
