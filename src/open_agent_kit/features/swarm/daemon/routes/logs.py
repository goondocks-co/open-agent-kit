"""Log tailing route for the swarm daemon."""

import logging
from collections import deque
from pathlib import Path

from fastapi import APIRouter, Query

from open_agent_kit.features.swarm.constants import (
    SWARM_DAEMON_API_PATH_LOGS,
    SWARM_DAEMON_CONFIG_DIR,
    SWARM_DAEMON_LOG_FILE,
    SWARM_ROUTE_TAG,
)
from open_agent_kit.features.swarm.daemon.state import get_swarm_state

logger = logging.getLogger(__name__)

router = APIRouter(tags=[SWARM_ROUTE_TAG])


def _find_log_file() -> Path | None:
    """Find the swarm daemon log file."""
    state = get_swarm_state()
    if state.swarm_id:
        log_path = (
            Path(SWARM_DAEMON_CONFIG_DIR).expanduser() / state.swarm_id / SWARM_DAEMON_LOG_FILE
        )
        if log_path.exists():
            return log_path
    # Fallback: search all swarm directories
    config_root = Path(SWARM_DAEMON_CONFIG_DIR).expanduser()
    if config_root.is_dir():
        for log_file in sorted(config_root.glob(f"*/{SWARM_DAEMON_LOG_FILE}")):
            return log_file
    return None


def _tail_lines(path: Path, n: int) -> list[str]:
    """Read the last *n* lines from a file without loading the entire file."""
    try:
        with path.open(encoding="utf-8", errors="replace") as f:
            return list(deque(f, maxlen=n))
    except OSError:
        return []


@router.get(SWARM_DAEMON_API_PATH_LOGS)
async def get_logs(lines: int = Query(default=500, ge=1, le=10000)) -> dict:
    """Tail the daemon log file."""
    log_path = _find_log_file()
    if not log_path or not log_path.exists():
        return {"lines": [], "path": None}
    try:
        tailed = _tail_lines(log_path, lines)
        stripped = [line.rstrip("\n") for line in tailed]
        return {
            "lines": stripped,
            "path": str(log_path),
            "total_lines": len(stripped),
        }
    except OSError as exc:
        logger.error("Failed to read log file: %s", exc)
        return {"lines": [], "path": str(log_path), "total_lines": 0, "error": str(exc)}
