"""ACP server management routes for the CI daemon.

Provides API endpoints for starting, stopping, and checking the status
of the ACP (Agent Client Protocol) server process.
"""

import logging
import subprocess
from collections import deque
from http import HTTPStatus
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from open_agent_kit.config.paths import OAK_DIR
from open_agent_kit.features.codebase_intelligence.cli_command import (
    resolve_ci_cli_command,
)
from open_agent_kit.features.codebase_intelligence.constants import (
    CI_ACP_API_PATH_LOGS,
    CI_ACP_API_PATH_START,
    CI_ACP_API_PATH_STATUS,
    CI_ACP_API_PATH_STOP,
    CI_ACP_ERROR_ALREADY_RUNNING,
    CI_ACP_ERROR_NO_PROJECT_ROOT,
    CI_ACP_ERROR_NOT_RUNNING,
    CI_ACP_ERROR_START_FAILED,
    CI_ACP_LOG_FILE,
    CI_ACP_LOG_LINES_DEFAULT,
    CI_ACP_LOG_STARTING,
    CI_ACP_LOG_STOP_FAILED,
    CI_ACP_LOG_STOPPED,
    CI_ACP_ROUTE_TAG,
    CI_ACP_STATUS_RUNNING,
    CI_ACP_STATUS_STOPPED,
    CI_DATA_DIR,
)
from open_agent_kit.features.codebase_intelligence.daemon.state import get_state
from open_agent_kit.utils.platform import (
    get_process_detach_kwargs,
    is_process_running,
    terminate_process,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=[CI_ACP_ROUTE_TAG])


def _is_acp_running() -> bool:
    """Check if the ACP server process is alive."""
    state = get_state()
    if state.acp_server_pid is None:
        return False
    if not is_process_running(state.acp_server_pid):
        # Process died — clean up stale state
        state.acp_server_pid = None
        state.acp_server_transport = None
        return False
    return True


def _get_log_path() -> Path:
    """Get the ACP log file path."""
    state = get_state()
    if not state.project_root:
        return Path(CI_ACP_LOG_FILE)
    return state.project_root / OAK_DIR / CI_DATA_DIR / CI_ACP_LOG_FILE


@router.get(CI_ACP_API_PATH_STATUS)
async def get_acp_status() -> dict:
    """Get current ACP server status.

    Returns:
        Status including running state, PID, and transport.
    """
    state = get_state()
    running = _is_acp_running()

    return {
        "running": running,
        "pid": state.acp_server_pid if running else None,
        "transport": state.acp_server_transport if running else None,
    }


@router.post(CI_ACP_API_PATH_START)
async def start_acp() -> dict:
    """Start the ACP server as a detached subprocess.

    Resolves the CLI command and spawns ``<cli_command> acp serve``
    as a detached process.

    Returns:
        Status confirmation with PID.
    """
    state = get_state()

    if not state.project_root:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=CI_ACP_ERROR_NO_PROJECT_ROOT,
        )

    if _is_acp_running():
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail=CI_ACP_ERROR_ALREADY_RUNNING,
        )

    cli_command = resolve_ci_cli_command(state.project_root)
    log_path = _get_log_path()

    # Ensure log directory exists
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(CI_ACP_LOG_STARTING)

    try:
        proc = subprocess.Popen(
            [cli_command, "acp", "serve"],
            cwd=str(state.project_root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            **get_process_detach_kwargs(),
        )
        state.acp_server_pid = proc.pid
        state.acp_server_transport = "stdio"
    except OSError as exc:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=CI_ACP_ERROR_START_FAILED.format(error=exc),
        ) from exc

    return {
        "status": CI_ACP_STATUS_RUNNING,
        "pid": state.acp_server_pid,
        "transport": state.acp_server_transport,
    }


@router.post(CI_ACP_API_PATH_STOP)
async def stop_acp() -> dict:
    """Stop the ACP server process.

    Sends SIGTERM to the ACP server and cleans up state.

    Returns:
        Status confirmation.
    """
    state = get_state()

    if not _is_acp_running():
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=CI_ACP_ERROR_NOT_RUNNING,
        )

    pid = state.acp_server_pid

    if pid is None:
        state.acp_server_transport = None
        return {"status": CI_ACP_STATUS_STOPPED}

    try:
        terminate_process(pid)
    except OSError as exc:
        logger.warning(CI_ACP_LOG_STOP_FAILED.format(error=exc))
    finally:
        state.acp_server_pid = None
        state.acp_server_transport = None

    logger.info(CI_ACP_LOG_STOPPED)
    return {"status": CI_ACP_STATUS_STOPPED}


@router.get(CI_ACP_API_PATH_LOGS)
async def get_acp_logs(
    lines: int | None = Query(default=None),
) -> dict:
    """Get recent ACP server log lines.

    Args:
        lines: Number of lines to return (default 100).

    Returns:
        Log lines and log file path.
    """
    num_lines = lines if lines is not None else CI_ACP_LOG_LINES_DEFAULT
    log_path = _get_log_path()

    if not log_path.exists():
        return {"lines": [], "log_file": str(log_path)}

    try:
        # Read last N lines efficiently using a deque
        with open(log_path, encoding="utf-8", errors="replace") as f:
            last_lines = list(deque(f, maxlen=num_lines))
        # Strip trailing newlines
        last_lines = [line.rstrip("\n") for line in last_lines]
    except OSError:
        last_lines = []

    return {"lines": last_lines, "log_file": str(log_path)}
