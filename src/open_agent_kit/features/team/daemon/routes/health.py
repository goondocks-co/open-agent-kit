"""Health and status routes for the CI daemon."""

import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Query

from open_agent_kit.config.paths import OAK_DIR
from open_agent_kit.constants import VERSION
from open_agent_kit.features.team.activity.store.backup import (
    get_backup_dir,
)
from open_agent_kit.features.team.activity.store.schema import SCHEMA_VERSION
from open_agent_kit.features.team.cli_command import (
    resolve_ci_cli_command,
)
from open_agent_kit.features.team.constants import (
    CI_ACP_LOG_FILE,
    CI_ACTIVITIES_DB_FILENAME,
    CI_CHROMA_DIR,
    CI_DATA_DIR,
    CI_HOOKS_LOG_FILE,
    CI_LOG_FILE,
    DAEMON_STATUS_HEALTHY,
    DAEMON_STATUS_RUNNING,
    LOG_FILE_ACP,
    LOG_FILE_DAEMON,
    LOG_FILE_DISPLAY_NAMES,
    LOG_FILE_HOOKS,
    LOG_LINES_DEFAULT,
    LOG_LINES_MAX,
    LOG_LINES_MIN,
    VALID_LOG_FILES,
)
from open_agent_kit.features.team.daemon.models import HealthResponse
from open_agent_kit.features.team.daemon.state import get_state

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

    # Get summarization config for display (use cached config)
    summarization_provider = None
    summarization_model = None
    summarization_enabled = False
    config = state.ci_config
    if config:
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

    # Resolve CLI command alias (e.g. "oak-dev") for UI display
    cli_command = "oak"
    if state.project_root:
        try:
            cli_command = resolve_ci_cli_command(state.project_root)
        except (OSError, ValueError):
            logger.debug("Could not resolve CLI command, using default", exc_info=True)

    return {
        "status": DAEMON_STATUS_RUNNING,
        "machine_id": state.machine_id,
        "cli_command": cli_command,
        "power_state": state.power_state,
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
        "version": {
            "running": VERSION,
            "installed": state.installed_version,
            "update_available": state.update_available,
        },
        "upgrade": {
            "needed": state.upgrade_needed,
            "config_version_outdated": state.config_version_outdated,
            "pending_migrations": state.pending_migration_count,
        },
        "team": _get_team_status(state),
        "cloud_relay": _get_cloud_relay_status(state),
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
    from open_agent_kit.features.team.activity.store.backup import (
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


def _get_team_status(state: object) -> dict | None:
    """Get team sync status for the status endpoint.

    Args:
        state: DaemonState instance.

    Returns:
        Team status dictionary, or None if not configured.
    """
    relay_client = getattr(state, "cloud_relay_client", None)
    sync_worker = getattr(state, "team_sync_worker", None)

    if relay_client is None and sync_worker is None:
        return None

    team_status: dict = {
        "configured": relay_client is not None,
        "connected": relay_client is not None and relay_client.get_status().connected,
        "members_online": len(getattr(relay_client, "online_nodes", [])) if relay_client else 0,
    }

    if sync_worker is not None:
        team_status["sync"] = sync_worker.get_status().model_dump()

    return team_status


def _get_cloud_relay_status(state: object) -> dict | None:
    """Get cloud relay status for the status endpoint.

    Args:
        state: DaemonState instance.

    Returns:
        Cloud relay status dictionary, or None if not connected.
    """
    client = getattr(state, "cloud_relay_client", None)
    if client is None:
        return None

    relay_status = client.get_status()
    if not relay_status.connected:
        return None

    worker_url = relay_status.worker_url
    mcp_endpoint = None
    custom_domain: str | None = None
    worker_name: str | None = None

    # Resolve custom_domain and worker_name from config so we can derive
    # the correct public URL (custom domain takes precedence over workers.dev).
    ci_config = getattr(state, "ci_config", None)
    if ci_config:
        custom_domain = getattr(ci_config.cloud_relay, "custom_domain", None)
        worker_name = getattr(ci_config.cloud_relay, "worker_name", None)

    if worker_url:
        from open_agent_kit.features.team.daemon.routes.cloud_relay import (
            _mcp_endpoint,
        )

        mcp_endpoint = _mcp_endpoint(worker_url, custom_domain, worker_name)

    return {
        "connected": True,
        "worker_url": worker_url,
        "mcp_endpoint": mcp_endpoint,
        "custom_domain": custom_domain,
        "worker_name": worker_name,
    }


@router.get("/api/swarm-advisories")
async def get_swarm_advisories() -> dict:
    """Get swarm advisories from the relay.

    Returns advisories pushed by the swarm during heartbeat responses,
    such as version drift warnings or capability gap notices.
    """
    state = get_state()
    client = getattr(state, "cloud_relay_client", None)
    if client is None:
        return {"advisories": [], "connected": False}

    try:
        advisories = await client.get_swarm_advisories()
    except Exception as exc:
        logger.debug("Failed to fetch swarm advisories: %s", exc)
        advisories = []

    return {"advisories": advisories, "connected": True}


@router.get("/api/logs")
async def get_logs(
    lines: int = Query(
        default=LOG_LINES_DEFAULT,
        ge=LOG_LINES_MIN,
        le=LOG_LINES_MAX,
    ),
    file: str = Query(
        default=LOG_FILE_DAEMON,
        description="Log file to retrieve: 'daemon', 'hooks', or 'acp'",
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
        elif file == LOG_FILE_ACP:
            log_file = ci_data_dir / CI_ACP_LOG_FILE
        else:
            log_file = ci_data_dir / CI_LOG_FILE

    log_lines: list[str] = []
    error: str | None = None
    if log_file and log_file.exists():
        try:
            with open(log_file, encoding="utf-8") as f:
                log_lines = [line.rstrip("\n") for line in f.readlines()[-lines:]]
        except (OSError, UnicodeDecodeError) as e:
            error = f"Error reading log file: {e}"
    else:
        if file == LOG_FILE_HOOKS:
            log_lines = [
                "No hook events logged yet. Hook events will appear here when SessionStart, SessionEnd, etc. fire."
            ]
        elif file == LOG_FILE_ACP:
            log_lines = ["No ACP log yet. Logs will appear here when an editor connects via ACP."]
        else:
            log_lines = ["No log file found"]

    path = str(log_file) if log_file else None
    response: dict = {
        # Normalized fields (shared schema with swarm daemon)
        "lines": log_lines,
        "path": path,
        "total_lines": len(log_lines),
        # Team-daemon-specific extras
        "log_file": path,
        "log_type": file,
        "log_type_display": LOG_FILE_DISPLAY_NAMES.get(file, file),
        "available_logs": [
            {"id": log_id, "name": LOG_FILE_DISPLAY_NAMES[log_id]} for log_id in VALID_LOG_FILES
        ],
    }
    if error:
        response["error"] = error
    return response
