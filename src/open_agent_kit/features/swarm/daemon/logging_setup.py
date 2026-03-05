"""Swarm daemon logging configuration.

Mirrors the team daemon's structured logging so that log lines contain
``[INFO]``, ``[DEBUG]``, etc. tags — making the UI's tag filter chips work.
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from open_agent_kit.features.swarm.constants import (
    SWARM_DAEMON_CONFIG_DIR,
    SWARM_DAEMON_LOG_FILE,
    SWARM_LOG_ROTATION_DEFAULT_BACKUP_COUNT,
    SWARM_LOG_ROTATION_DEFAULT_MAX_SIZE_MB,
)

logger = logging.getLogger(__name__)


def _resolve_log_file(swarm_id: str) -> Path | None:
    """Resolve the daemon log file path for a swarm."""
    if not swarm_id:
        return None
    return Path(SWARM_DAEMON_CONFIG_DIR).expanduser() / swarm_id / SWARM_DAEMON_LOG_FILE


def configure_swarm_logging(
    swarm_id: str,
    log_level: str = "INFO",
    max_size_mb: int = SWARM_LOG_ROTATION_DEFAULT_MAX_SIZE_MB,
    backup_count: int = SWARM_LOG_ROTATION_DEFAULT_BACKUP_COUNT,
    rotation_enabled: bool = True,
) -> None:
    """Configure structured file logging for the swarm daemon.

    Sets up the ``open_agent_kit.features.swarm`` logger hierarchy with a
    ``RotatingFileHandler`` that writes to the swarm's ``daemon.log``.
    Log lines are formatted with ``[LEVEL]`` tags so the UI filter chips work.

    Args:
        swarm_id: Swarm identifier (used to locate the log file).
        log_level: Python log level name (DEBUG, INFO, WARNING, ERROR).
        max_size_mb: Max log file size in MB before rotation.
        backup_count: Number of rotated backup files to keep.
        rotation_enabled: Whether log rotation is enabled.
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    # Configure the swarm logger (our application logger)
    swarm_logger = logging.getLogger("open_agent_kit.features.swarm")
    swarm_logger.setLevel(level)
    swarm_logger.propagate = False
    swarm_logger.handlers.clear()

    # Suppress uvicorn's loggers — we handle our own logging
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    if level == logging.DEBUG:
        logging.getLogger("uvicorn.error").setLevel(logging.INFO)

    # Formatter with [LEVEL] tags
    if level == logging.DEBUG:
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s",
            datefmt="%H:%M:%S",
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S",
        )

    log_file = _resolve_log_file(swarm_id)
    if log_file:
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            max_bytes = max_size_mb * 1024 * 1024 if rotation_enabled else 0
            keep_count = backup_count if rotation_enabled else 0
            file_handler: logging.Handler = RotatingFileHandler(
                log_file,
                mode="a",
                maxBytes=max_bytes,
                backupCount=keep_count,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            swarm_logger.addHandler(file_handler)

            # Capture uvicorn errors through our rotated log
            uvicorn_error_logger = logging.getLogger("uvicorn.error")
            uvicorn_error_logger.addHandler(file_handler)
        except OSError as exc:
            # Fall back to stream handler if file logging fails
            stream_handler = logging.StreamHandler()
            stream_handler.setFormatter(formatter)
            swarm_logger.addHandler(stream_handler)
            swarm_logger.warning("Could not set up file logging to %s: %s", log_file, exc)
    else:
        # No swarm_id — stream only (e.g. dev mode)
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        swarm_logger.addHandler(stream_handler)
