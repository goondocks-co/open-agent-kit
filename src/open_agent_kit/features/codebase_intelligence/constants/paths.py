"""File names, paths, and data directory constants."""

from typing import Final

# =============================================================================
# File Names and Paths
# =============================================================================

# CI data directory structure (relative to .oak/)
CI_DATA_DIR: Final[str] = "ci"
CI_CHROMA_DIR: Final[str] = "chroma"
CI_ACTIVITIES_DB_FILENAME: Final[str] = "activities.db"
CI_LOG_FILE: Final[str] = "daemon.log"
CI_HOOKS_LOG_FILE: Final[str] = "hooks.log"
CI_PID_FILE: Final[str] = "daemon.pid"
CI_PORT_FILE: Final[str] = "daemon.port"

# Team-shared port configuration (git-tracked, in oak/)
# Priority: 1) .oak/ci/daemon.port (local override), 2) oak/daemon.port (team-shared)
CI_SHARED_PORT_DIR: Final[str] = "oak"
CI_SHARED_PORT_FILE: Final[str] = "daemon.port"

# Activity store schema version
CI_ACTIVITY_SCHEMA_VERSION: Final[int] = 8

# Activity store columns
CI_SESSION_COLUMN_TRANSCRIPT_PATH: Final[str] = "transcript_path"
