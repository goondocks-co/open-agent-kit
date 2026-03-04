"""Daemon logging configuration.

Extracted from ``server.py`` -- sets up the CI logger hierarchy, file
rotation, hooks log, and uvicorn suppression.
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING

from open_agent_kit.features.team.constants import (
    CI_HOOKS_LOG_FILE,
)

if TYPE_CHECKING:
    from open_agent_kit.features.team.config import LogRotationConfig

logger = logging.getLogger(__name__)


def configure_logging(
    log_level: str,
    log_file: Path | None = None,
    log_rotation: "LogRotationConfig | None" = None,
) -> None:
    """Configure logging for the daemon.

    Args:
        log_level: Log level (DEBUG, INFO, WARNING, ERROR).
        log_file: Optional log file path.
        log_rotation: Optional log rotation configuration.
    """
    from open_agent_kit.features.team.config import LogRotationConfig

    level = getattr(logging, log_level.upper(), logging.INFO)

    # Configure the CI logger (our application logger)
    ci_logger = logging.getLogger("open_agent_kit.features.team")
    ci_logger.setLevel(level)

    # CRITICAL: Prevent propagation to root logger to avoid duplicates
    # Uvicorn sets up handlers on the root logger before lifespan runs
    ci_logger.propagate = False

    # Clear any existing handlers to avoid duplicates on restart/reconfigure
    ci_logger.handlers.clear()

    # Suppress uvicorn's loggers - we handle our own logging
    # Set to WARNING so only actual errors come through
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    # In debug mode, we might want to see uvicorn errors
    if level == logging.DEBUG:
        logging.getLogger("uvicorn.error").setLevel(logging.INFO)

    # Configure the dedicated hooks logger (separate file for hook lifecycle events)
    # This logger is always INFO level for complete hook visibility
    hooks_logger = logging.getLogger("oak.ci.hooks")
    hooks_logger.setLevel(logging.INFO)  # Always INFO for hooks.log
    hooks_logger.propagate = False  # Don't duplicate to daemon.log
    hooks_logger.handlers.clear()  # Clear existing handlers on restart

    # Create formatter
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

    # Add file handler if log file specified (daemon mode)
    # When file logging is enabled, skip stream handler to avoid duplicates
    # (stdout is redirected to /dev/null by the daemon manager)
    if log_file:
        try:
            rotation = log_rotation or LogRotationConfig()

            # Declare with base Handler type to satisfy mypy for both branches
            file_handler: logging.Handler
            if rotation.enabled:
                # Use RotatingFileHandler to prevent unbounded log growth
                file_handler = RotatingFileHandler(
                    log_file,
                    mode="a",
                    maxBytes=rotation.get_max_bytes(),
                    backupCount=rotation.backup_count,
                    encoding="utf-8",
                )
            else:
                # Rotation disabled - use standard FileHandler
                file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")

            file_handler.setFormatter(formatter)
            ci_logger.addHandler(file_handler)

            # IMPORTANT: Add our handler to uvicorn's error logger
            # This captures uvicorn tracebacks through rotation instead of raw stderr
            # Since subprocess stdout/stderr now goes to /dev/null, this ensures
            # uvicorn errors are still captured in the rotated log file
            uvicorn_error_logger = logging.getLogger("uvicorn.error")
            uvicorn_error_logger.addHandler(file_handler)

            # Set up hooks logger file handler (separate file for hook lifecycle events)
            hooks_log_file = log_file.parent / CI_HOOKS_LOG_FILE
            hooks_handler: logging.Handler
            if rotation.enabled:
                hooks_handler = RotatingFileHandler(
                    hooks_log_file,
                    mode="a",
                    maxBytes=rotation.get_max_bytes(),
                    backupCount=rotation.backup_count,
                    encoding="utf-8",
                )
            else:
                hooks_handler = logging.FileHandler(hooks_log_file, mode="a", encoding="utf-8")
            hooks_handler.setFormatter(formatter)
            hooks_logger.addHandler(hooks_handler)

        except OSError as e:
            ci_logger.warning(f"Could not set up file logging to {log_file}: {e}")
    else:
        # Only add stream handler when NOT running as daemon
        # (avoids duplicates since daemon stdout goes to log file)
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        ci_logger.addHandler(stream_handler)
