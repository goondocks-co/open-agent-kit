"""Health and status routes for the CI daemon."""

import logging

from fastapi import APIRouter, Query

from open_agent_kit.features.codebase_intelligence.daemon.models import HealthResponse
from open_agent_kit.features.codebase_intelligence.daemon.state import get_state

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/api/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Check daemon health."""
    state = get_state()
    uptime = state.uptime_seconds
    return HealthResponse(
        status="healthy",
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

    # Get index statistics
    # Get index statistics
    chunks_indexed = 0
    memories_stored = 0
    if state.vector_store:
        stats = state.vector_store.get_stats()
        chunks_indexed = stats.get("code_chunks", 0)
        memories_stored = stats.get("memory_observations", 0)

    # Use accurate file count from state (tracked by watcher/indexer)
    files_indexed = state.index_status.file_count

    # If state is 0 but we have chunks (e.g. restart without reindex), fallback to DB query
    if files_indexed == 0 and chunks_indexed > 0 and state.vector_store:
        # This will update the state for subsequent calls
        files_indexed = state.vector_store.count_unique_files()
        state.index_status.file_count = files_indexed

    return {
        "status": "running",
        "indexing": state.index_status.is_indexing,
        "embedding_provider": embedding_provider,
        "embedding_stats": embedding_stats,
        "uptime_seconds": uptime,
        "project_root": str(state.project_root),
        "index_stats": {
            "files_indexed": files_indexed,
            "chunks_indexed": chunks_indexed,
            "memories_stored": memories_stored,
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
    }


@router.get("/api/logs")
async def get_logs(lines: int = Query(default=50, ge=1, le=500)) -> dict:
    """Get recent daemon logs."""
    state = get_state()
    log_file = state.project_root
    if log_file:
        log_file = log_file / ".oak" / "ci" / "daemon.log"

    log_content = ""
    if log_file and log_file.exists():
        try:
            with open(log_file, encoding="utf-8") as f:
                all_lines = f.readlines()
                log_content = "".join(all_lines[-lines:])
        except (OSError, UnicodeDecodeError) as e:
            log_content = f"Error reading log file: {e}"
    else:
        log_content = "No log file found"

    return {
        "log_file": str(log_file) if log_file else None,
        "lines": lines,
        "content": log_content,
    }
