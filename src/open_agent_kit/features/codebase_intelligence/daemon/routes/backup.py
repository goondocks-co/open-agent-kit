"""Backup and restore routes for CI daemon.

Provides API endpoints for creating and restoring database backups.
Backups preserve valuable session, prompt, and memory data across
feature removal/reinstall cycles.
"""

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from open_agent_kit.config.paths import OAK_DIR
from open_agent_kit.features.codebase_intelligence.constants import (
    CI_ACTIVITIES_DB_FILENAME,
    CI_DATA_DIR,
    CI_HISTORY_BACKUP_DIR,
    CI_HISTORY_BACKUP_FILE,
)
from open_agent_kit.features.codebase_intelligence.daemon.state import get_state

logger = logging.getLogger(__name__)
router = APIRouter(tags=["backup"])


class BackupRequest(BaseModel):
    """Request to create a database backup."""

    include_activities: bool = False
    output_path: str | None = None  # None = use default


class RestoreRequest(BaseModel):
    """Request to restore from a database backup."""

    input_path: str | None = None  # None = use default


class BackupStatusResponse(BaseModel):
    """Response for backup status check."""

    backup_exists: bool
    backup_path: str
    backup_size_bytes: int | None = None
    last_modified: str | None = None


@router.get("/api/backup/status")
async def get_backup_status() -> BackupStatusResponse:
    """Get current backup file status."""
    state = get_state()

    if not state.project_root:
        raise HTTPException(status_code=503, detail="Project root not initialized")

    backup_path = state.project_root / CI_HISTORY_BACKUP_DIR / CI_HISTORY_BACKUP_FILE

    logger.debug(f"Checking backup status: {backup_path}")

    if backup_path.exists():
        stat = backup_path.stat()
        from datetime import datetime

        mtime = datetime.fromtimestamp(stat.st_mtime).isoformat()
        return BackupStatusResponse(
            backup_exists=True,
            backup_path=str(backup_path),
            backup_size_bytes=stat.st_size,
            last_modified=mtime,
        )

    return BackupStatusResponse(
        backup_exists=False,
        backup_path=str(backup_path),
    )


@router.post("/api/backup/create")
async def create_backup(request: BackupRequest) -> dict[str, Any]:
    """Create a backup of the CI database."""
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
        backup_path = state.project_root / CI_HISTORY_BACKUP_DIR / CI_HISTORY_BACKUP_FILE

    logger.info(
        f"Creating backup: include_activities={request.include_activities}, path={backup_path}"
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
    }


@router.post("/api/backup/restore")
async def restore_backup(request: RestoreRequest) -> dict[str, Any]:
    """Restore CI database from backup."""
    state = get_state()

    if not state.project_root:
        raise HTTPException(status_code=503, detail="Project root not initialized")

    if not state.activity_store:
        raise HTTPException(status_code=503, detail="Activity store not initialized")

    ci_data_dir = state.project_root / OAK_DIR / CI_DATA_DIR
    db_path = ci_data_dir / CI_ACTIVITIES_DB_FILENAME
    if not db_path.exists():
        raise HTTPException(status_code=404, detail="No database to restore into")

    if request.input_path:
        backup_path = Path(request.input_path)
    else:
        backup_path = state.project_root / CI_HISTORY_BACKUP_DIR / CI_HISTORY_BACKUP_FILE

    if not backup_path.exists():
        raise HTTPException(status_code=404, detail=f"Backup file not found: {backup_path}")

    logger.info(f"Restoring from backup: {backup_path}")

    from open_agent_kit.features.codebase_intelligence.activity.store import ActivityStore

    store = ActivityStore(db_path)
    count = store.import_from_sql(backup_path)
    store.close()

    logger.info(f"Restore complete: {count} records imported from {backup_path}")

    return {
        "status": "completed",
        "message": f"Restored {count} records. ChromaDB will rebuild on next startup.",
        "backup_path": str(backup_path),
        "record_count": count,
    }
