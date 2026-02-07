"""Health and status routes for the CI daemon."""

import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Query

from open_agent_kit.config.paths import OAK_DIR
from open_agent_kit.constants import VERSION
from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
    get_backup_dir,
)
from open_agent_kit.features.codebase_intelligence.activity.store.schema import SCHEMA_VERSION
from open_agent_kit.features.codebase_intelligence.constants import (
    CI_ACTIVITIES_DB_FILENAME,
    CI_CHROMA_DIR,
    CI_DATA_DIR,
    CI_HOOKS_LOG_FILE,
    CI_LOG_FILE,
    CI_STATUS_KEY_TUNNEL,
    DAEMON_STATUS_HEALTHY,
    DAEMON_STATUS_RUNNING,
    LOG_FILE_DAEMON,
    LOG_FILE_DISPLAY_NAMES,
    LOG_FILE_HOOKS,
    LOG_LINES_DEFAULT,
    LOG_LINES_MAX,
    LOG_LINES_MIN,
    TUNNEL_RESPONSE_KEY_ACTIVE,
    TUNNEL_RESPONSE_KEY_PROVIDER,
    TUNNEL_RESPONSE_KEY_PUBLIC_URL,
    TUNNEL_RESPONSE_KEY_STARTED_AT,
    VALID_LOG_FILES,
)
from open_agent_kit.features.codebase_intelligence.daemon.models import HealthResponse
from open_agent_kit.features.codebase_intelligence.daemon.state import get_state

logger = logging.getLogger(__name__)


def _get_directory_size(path: Path) -> int:
    """Get total size of a directory in bytes."""
    if not path.exists():
        return 0
    total = 0
    try:
        for item in path.rglob("*"):
            if item.is_file():
                total += item.stat().st_size
    except (OSError, PermissionError):
        pass
    return total


def _format_size_mb(size_bytes: int) -> str:
    """Format size in bytes to MB string."""
    return f"{size_bytes / (1024 * 1024):.1f}"


router = APIRouter(tags=["health"])


@router.get("/api/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Check daemon health."""
    state = get_state()
    uptime = state.uptime_seconds
    return HealthResponse(
        status=DAEMON_STATUS_HEALTHY,
        oak_version=VERSION,
        schema_version=SCHEMA_VERSION,
        uptime_seconds=uptime,
        project_root=str(state.project_root) if state.project_root else None,
    )


@router.get("/api/status")
async def get_status() -> dict:
    """Get detailed daemon status (UI-compatible format)."""
    from open_agent_kit.features.codebase_intelligence.config import load_ci_config

    state = get_state()
    uptime = state.uptime_seconds

    # Get embedding chain status with usage stats
    embedding_provider = None
    embedding_stats = None
    if state.embedding_chain:
        chain_status = state.embedding_chain.get_status()
        # Use primary_provider (most successful) if available, else active_provider
        embedding_provider = chain_status.get("primary_provider") or chain_status.get(
            "active_provider"
        )
        embedding_stats = {
            "providers": chain_status.get("providers", []),
            "total_embeds": chain_status.get("total_embeds", 0),
        }

    # Get summarization config for display
    summarization_provider = None
    summarization_model = None
    summarization_enabled = False
    if state.project_root:
        config = load_ci_config(state.project_root)
        summarization_enabled = config.summarization.enabled
        if summarization_enabled:
            summarization_provider = config.summarization.provider
            summarization_model = config.summarization.model

    # Get index statistics
    chunks_indexed = 0
    memories_chromadb = 0
    if state.vector_store:
        stats = state.vector_store.get_stats()
        chunks_indexed = stats.get("code_chunks", 0)
        memories_chromadb = stats.get("memory_observations", 0)

    # Get memory stats from SQLite (source of truth)
    memories_sqlite = 0
    memories_unembedded = 0
    if state.activity_store:
        memories_sqlite = state.activity_store.count_observations()
        memories_unembedded = state.activity_store.count_unembedded_observations()

    # Use accurate file count from state (tracked by watcher/indexer)
    files_indexed = state.index_status.file_count

    # If state is 0 but we have chunks (e.g. restart without reindex), fallback to DB query
    if files_indexed == 0 and chunks_indexed > 0 and state.vector_store:
        # This will update the state for subsequent calls
        files_indexed = state.vector_store.count_unique_files()
        state.index_status.file_count = files_indexed

    return {
        "status": DAEMON_STATUS_RUNNING,
        "indexing": state.index_status.is_indexing,
        "embedding_provider": embedding_provider,
        "embedding_stats": embedding_stats,
        "summarization": {
            "enabled": summarization_enabled,
            "provider": summarization_provider,
            "model": summarization_model,
        },
        "uptime_seconds": uptime,
        "project_root": str(state.project_root),
        "index_stats": {
            "files_indexed": files_indexed,
            "chunks_indexed": chunks_indexed,
            "memories_stored": memories_sqlite,  # SQLite is source of truth
            "memories_chromadb": memories_chromadb,
            "memories_unembedded": memories_unembedded,
            "last_indexed": state.index_status.last_indexed,
            "duration_seconds": state.index_status.duration_seconds,
            "status": state.index_status.status,
            "progress": state.index_status.progress,
            "total": state.index_status.total,
            "ast_stats": state.index_status.ast_stats,
        },
        "file_watcher": {
            "enabled": state.file_watcher is not None,
            "running": state.file_watcher.is_running if state.file_watcher else False,
            "pending_changes": (
                state.file_watcher.get_pending_count() if state.file_watcher else 0
            ),
        },
        "storage": _get_storage_stats(state.project_root),
        "backup": _get_backup_summary(state.project_root),
        CI_STATUS_KEY_TUNNEL: _get_tunnel_status(state),
    }


def _get_storage_stats(project_root: Path | None) -> dict:
    """Get database storage statistics."""
    if not project_root:
        return {"sqlite_size_bytes": 0, "chromadb_size_bytes": 0}

    ci_data_dir = project_root / OAK_DIR / CI_DATA_DIR
    sqlite_path = ci_data_dir / CI_ACTIVITIES_DB_FILENAME
    chroma_path = ci_data_dir / CI_CHROMA_DIR

    sqlite_size = sqlite_path.stat().st_size if sqlite_path.exists() else 0
    chromadb_size = _get_directory_size(chroma_path)

    return {
        "sqlite_size_bytes": sqlite_size,
        "chromadb_size_bytes": chromadb_size,
        "sqlite_size_mb": _format_size_mb(sqlite_size),
        "chromadb_size_mb": _format_size_mb(chromadb_size),
        "total_size_mb": _format_size_mb(sqlite_size + chromadb_size),
    }


def _get_backup_summary(project_root: Path | None) -> dict:
    """Get quick backup status summary for dashboard."""
    from open_agent_kit.features.codebase_intelligence.activity.store.backup import (
        get_backup_filename,
    )

    if not project_root:
        return {"exists": False, "last_backup": None, "age_hours": None}

    state = get_state()
    backup_dir = get_backup_dir(project_root)
    backup_path = backup_dir / get_backup_filename(state.machine_id or "")

    if not backup_path.exists():
        return {"exists": False, "last_backup": None, "age_hours": None}

    stat = backup_path.stat()
    mtime = datetime.fromtimestamp(stat.st_mtime)
    age_hours = (datetime.now() - mtime).total_seconds() / 3600

    return {
        "exists": True,
        "last_backup": mtime.isoformat(),
        "age_hours": round(age_hours, 1),
        "size_bytes": stat.st_size,
    }


def _get_tunnel_status(state: object) -> dict:
    """Get tunnel status for the status endpoint.

    Args:
        state: DaemonState instance.

    Returns:
        Tunnel status dictionary.
    """
    # Avoid circular import by accessing attribute dynamically
    tunnel_provider = getattr(state, "tunnel_provider", None)
    if tunnel_provider is None:
        return {
            TUNNEL_RESPONSE_KEY_ACTIVE: False,
            TUNNEL_RESPONSE_KEY_PUBLIC_URL: None,
            TUNNEL_RESPONSE_KEY_PROVIDER: None,
            TUNNEL_RESPONSE_KEY_STARTED_AT: None,
        }

    status = tunnel_provider.get_status()
    return {
        TUNNEL_RESPONSE_KEY_ACTIVE: status.active,
        TUNNEL_RESPONSE_KEY_PUBLIC_URL: status.public_url,
        TUNNEL_RESPONSE_KEY_PROVIDER: status.provider_name,
        TUNNEL_RESPONSE_KEY_STARTED_AT: status.started_at,
    }


@router.get("/api/logs")
async def get_logs(
    lines: int = Query(
        default=LOG_LINES_DEFAULT,
        ge=LOG_LINES_MIN,
        le=LOG_LINES_MAX,
    ),
    file: str = Query(
        default=LOG_FILE_DAEMON,
        description="Log file to retrieve: 'daemon' or 'hooks'",
    ),
) -> dict:
    """Get recent logs from specified log file.

    Args:
        lines: Number of lines to retrieve (1-500)
        file: Which log file to read ('daemon' or 'hooks')
    """
    state = get_state()

    # Validate file parameter
    if file not in VALID_LOG_FILES:
        file = LOG_FILE_DAEMON

    # Get the appropriate log file path
    log_file = None
    if state.project_root:
        ci_data_dir = state.project_root / OAK_DIR / CI_DATA_DIR
        if file == LOG_FILE_HOOKS:
            log_file = ci_data_dir / CI_HOOKS_LOG_FILE
        else:
            log_file = ci_data_dir / CI_LOG_FILE

    log_content = ""
    if log_file and log_file.exists():
        try:
            with open(log_file, encoding="utf-8") as f:
                all_lines = f.readlines()
                log_content = "".join(all_lines[-lines:])
        except (OSError, UnicodeDecodeError) as e:
            log_content = f"Error reading log file: {e}"
    else:
        if file == LOG_FILE_HOOKS:
            log_content = "No hook events logged yet. Hook events will appear here when SessionStart, SessionEnd, etc. fire."
        else:
            log_content = "No log file found"

    return {
        "log_file": str(log_file) if log_file else None,
        "log_type": file,
        "log_type_display": LOG_FILE_DISPLAY_NAMES.get(file, file),
        "lines": lines,
        "content": log_content,
        "available_logs": [
            {"id": log_id, "name": LOG_FILE_DISPLAY_NAMES[log_id]} for log_id in VALID_LOG_FILES
        ],
    }
