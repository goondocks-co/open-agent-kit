"""Backup and restore routes for CI daemon.

Provides API endpoints for creating and restoring database backups.
Backups preserve valuable session, prompt, and memory data across
feature removal/reinstall cycles.

Supports multi-machine/multi-user backups with content-based deduplication.
"""

import logging
from datetime import datetime
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
    get_backup_dir,
    get_backup_dir_source,
    get_backup_filename,
)
from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
    create_backup as do_create_backup,
)
from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
    restore_all as do_restore_all,
)
from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
    restore_backup as do_restore_backup,
)
from open_agent_kit.features.codebase_intelligence.activity.store.schema import SCHEMA_VERSION
from open_agent_kit.features.codebase_intelligence.constants import (
    BACKUP_TRIGGER_MANUAL,
    BACKUP_TRIGGER_ON_TRANSITION,
    CI_ACTIVITIES_DB_FILENAME,
    CI_BACKUP_HEADER_MAX_LINES,
    CI_BACKUP_PATH_INVALID_ERROR,
    CI_DATA_DIR,
    CI_LINE_SEPARATOR,
    CI_TEXT_ENCODING,
)
from open_agent_kit.features.codebase_intelligence.daemon.state import DaemonState, get_state

logger = logging.getLogger(__name__)
router = APIRouter(tags=["backup"])


def get_last_backup_epoch(state: DaemonState, backup_path: Path | None = None) -> float | None:
    """Resolve last backup time: prefer in-memory timestamp, fall back to file mtime.

    Args:
        state: Current daemon state.
        backup_path: Pre-resolved backup file path. If None, resolves from state.

    Returns:
        Epoch timestamp of the last backup, or None if no backup exists.
    """
    if state.last_auto_backup is not None:
        return state.last_auto_backup

    # Fall back to backup file mtime
    if backup_path is None and state.project_root:
        from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
            get_backup_dir,
            get_backup_filename,
            get_machine_identifier,
        )

        machine_id = state.machine_id or get_machine_identifier(state.project_root)
        backup_path = get_backup_dir(state.project_root) / get_backup_filename(machine_id)

    if backup_path is not None and backup_path.exists():
        return backup_path.stat().st_mtime

    return None


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

    include_activities: bool | None = None  # None = use config default
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
    replace_machine: bool = True  # Drop-and-replace: delete stale data before import


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
    backup_dir: str  # The backup directory path
    backup_dir_source: str  # "environment variable" or "default"
    backup_size_bytes: int | None = None
    last_modified: str | None = None
    machine_id: str  # Current machine identifier
    all_backups: list[BackupFileInfo] = []  # All available backup files
    auto_backup_enabled: bool = False
    last_auto_backup: str | None = None
    backup_trigger: str = BACKUP_TRIGGER_MANUAL  # "manual" or "on_transition"


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
    sessions_deleted: int = 0
    batches_deleted: int = 0
    observations_deleted: int = 0
    activities_deleted: int = 0
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
        parts: list[str] = []
        if result.total_deleted > 0:
            parts.append(f"replaced {result.total_deleted}")
        parts.append(f"imported {result.total_imported}")
        parts.append(f"skipped {result.total_skipped} duplicates")
        message = ", ".join(parts)
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
            sessions_deleted=result.sessions_deleted,
            batches_deleted=result.batches_deleted,
            observations_deleted=result.observations_deleted,
            activities_deleted=result.activities_deleted,
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
    total_deleted: int = 0
    total_errors: int
    per_file: dict[str, RestoreResponse]


def _trigger_chromadb_rebuild(
    background_tasks: BackgroundTasks,
    incremental: bool = False,
) -> bool:
    """Trigger ChromaDB rebuild and session re-embedding in background.

    Args:
        background_tasks: FastAPI background tasks handle.
        incremental: When True, only embed pending (``embedded=0``) records
            instead of wiping and re-embedding everything.  Used after
            drop-and-replace restore where local embeddings are still valid.

    Returns True if rebuild was started, False otherwise.
    """
    state = get_state()
    if not state.activity_processor:
        return False

    if incremental:
        logger.info("Starting incremental post-restore embedding in background")
        background_tasks.add_task(
            state.activity_processor.embed_pending_observations,
            batch_size=50,
        )
        background_tasks.add_task(
            state.activity_processor.index_pending_plans,
            batch_size=10,
        )
    else:
        logger.info("Starting post-restore ChromaDB full rebuild in background")
        background_tasks.add_task(
            state.activity_processor.rebuild_chromadb_from_sqlite,
            batch_size=50,
            reset_embedded_flags=True,
            clear_chromadb_first=True,
        )

    if state.vector_store and state.activity_store:
        from open_agent_kit.features.codebase_intelligence.activity.processor.session_index import (
            reembed_session_summaries,
        )

        store = state.activity_store  # narrowed by guard above
        clear_first = not incremental
        background_tasks.add_task(
            reembed_session_summaries,
            activity_store=store,
            vector_store=state.vector_store,
            clear_first=clear_first,
        )
        mode = "incremental" if incremental else "full"
        logger.info(f"Starting post-restore session summary re-embedding ({mode}) in background")

    return True


@router.get("/api/backup/status")
async def get_backup_status() -> BackupStatusResponse:
    """Get current backup file status including all team backups."""
    state = get_state()

    if not state.project_root:
        raise HTTPException(status_code=503, detail="Project root not initialized")

    machine_id = state.machine_id or ""
    backup_dir = get_backup_dir(state.project_root)
    backup_dir_source = get_backup_dir_source(state.project_root)
    backup_filename = get_backup_filename(machine_id)
    backup_path = backup_dir / backup_filename

    logger.debug(
        f"Checking backup status: {backup_path} (machine: {machine_id}, source: {backup_dir_source})"
    )

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

    # Compute auto-backup status from config
    auto_backup_enabled = False
    last_auto_backup_iso: str | None = None

    config = state.ci_config
    if config:
        auto_backup_enabled = config.backup.auto_enabled

    # Determine backup trigger type
    backup_trigger = BACKUP_TRIGGER_ON_TRANSITION if auto_backup_enabled else BACKUP_TRIGGER_MANUAL

    # Check this machine's backup (also used as fallback for last-backup time)
    backup_file_mtime: float | None = None
    backup_file_mtime_iso: str | None = None
    backup_size_bytes: int = 0
    if backup_path.exists():
        stat = backup_path.stat()
        backup_file_mtime = stat.st_mtime
        backup_file_mtime_iso = datetime.fromtimestamp(stat.st_mtime).isoformat()
        backup_size_bytes = stat.st_size

    # Resolve last backup display time (file mtime fallback for "last backup" label)
    if auto_backup_enabled:
        last_backup_epoch = get_last_backup_epoch(state, backup_path)
        if last_backup_epoch is not None:
            last_auto_backup_iso = datetime.fromtimestamp(last_backup_epoch).isoformat()

    if backup_file_mtime is not None:
        return BackupStatusResponse(
            backup_exists=True,
            backup_path=str(backup_path),
            backup_dir=str(backup_dir),
            backup_dir_source=backup_dir_source,
            backup_size_bytes=backup_size_bytes,
            last_modified=backup_file_mtime_iso,
            machine_id=machine_id,
            all_backups=all_backups,
            auto_backup_enabled=auto_backup_enabled,
            last_auto_backup=last_auto_backup_iso,
            backup_trigger=backup_trigger,
        )

    return BackupStatusResponse(
        backup_exists=False,
        backup_path=str(backup_path),
        backup_dir=str(backup_dir),
        backup_dir_source=backup_dir_source,
        machine_id=machine_id,
        all_backups=all_backups,
        auto_backup_enabled=auto_backup_enabled,
        last_auto_backup=last_auto_backup_iso,
        backup_trigger=backup_trigger,
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

    # Validate output_path stays within backup directory (path traversal protection)
    output_path: Path | None = None
    if request.output_path:
        backup_dir = get_backup_dir(state.project_root)
        output_path = _ensure_backup_path_within_dir(backup_dir, Path(request.output_path))

    result = do_create_backup(
        project_root=state.project_root,
        db_path=db_path,
        include_activities=request.include_activities,
        output_path=output_path,
    )
    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)

    logger.info(f"Backup complete: {result.record_count} records exported to {result.backup_path}")

    return {
        "status": "completed",
        "message": f"Exported {result.record_count} records",
        "backup_path": str(result.backup_path),
        "record_count": result.record_count,
        "machine_id": result.machine_id,
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

    # Validate input_path stays within backup directory (path traversal protection)
    input_path: Path | None = None
    if request.input_path:
        backup_dir = get_backup_dir(state.project_root)
        input_path = _ensure_backup_path_within_dir(backup_dir, Path(request.input_path))

    result = do_restore_backup(
        project_root=state.project_root,
        db_path=db_path,
        input_path=input_path,
        dry_run=request.dry_run,
    )

    if not result.success:
        error_msg = result.error or "Restore failed"
        # Unified function returns "No backup file found in ..." or
        # "Backup file not found: ..." for missing files
        if "file found" in error_msg or "file not found" in error_msg:
            raise HTTPException(status_code=404, detail=error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

    import_result = result.import_result
    if import_result is None:
        raise HTTPException(status_code=500, detail="Restore returned no import result")

    logger.info(
        f"Restore complete: {import_result.total_imported} imported, "
        f"{import_result.total_skipped} skipped from {result.backup_path}"
    )

    # Trigger ChromaDB rebuild if not dry run and requested
    chromadb_rebuild_started = False
    if not request.dry_run and request.auto_rebuild_chromadb and import_result.total_imported > 0:
        chromadb_rebuild_started = _trigger_chromadb_rebuild(background_tasks)

    return RestoreResponse.from_import_result(
        import_result, str(result.backup_path), chromadb_rebuild_started=chromadb_rebuild_started
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

    result = do_restore_all(
        project_root=state.project_root,
        db_path=db_path,
        dry_run=request.dry_run,
        replace_machine=request.replace_machine,
        vector_store=state.vector_store if request.replace_machine else None,
    )

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)

    # Build per-file responses
    per_file: dict[str, RestoreResponse] = {}
    for filename, import_result in result.per_file.items():
        per_file[filename] = RestoreResponse.from_import_result(import_result, filename)

    total_imported = result.total_imported
    total_skipped = result.total_skipped
    total_deleted = result.total_deleted
    total_errors = sum(r.errors for r in result.per_file.values())

    # Trigger ChromaDB rebuild if not dry run and requested
    chromadb_rebuild_started = False
    if not request.dry_run and request.auto_rebuild_chromadb and total_imported > 0:
        chromadb_rebuild_started = _trigger_chromadb_rebuild(
            background_tasks,
            incremental=request.replace_machine,
        )

    logger.info(
        f"Restore all complete: {total_deleted} deleted, {total_imported} imported, "
        f"{total_skipped} skipped, {total_errors} errors"
    )

    parts: list[str] = []
    if total_deleted > 0:
        parts.append(f"replaced {total_deleted}")
    parts.append(f"imported {total_imported} records from {len(result.per_file)} files")
    parts.append(f"skipped {total_skipped} duplicates")
    message = ", ".join(parts)
    if chromadb_rebuild_started:
        message += ". ChromaDB rebuild started in background."

    return RestoreAllResponse(
        status="completed",
        message=message,
        files_processed=len(result.per_file),
        total_imported=total_imported,
        total_skipped=total_skipped,
        total_deleted=total_deleted,
        total_errors=total_errors,
        per_file=per_file,
    )
