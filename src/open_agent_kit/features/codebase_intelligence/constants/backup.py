"""Backup configuration and machine identifier constants."""

from typing import Final

# =============================================================================
# Backup Configuration
# =============================================================================

# Backup behavior defaults (used by BackupConfig dataclass)
BACKUP_AUTO_ENABLED_DEFAULT: Final[bool] = False
BACKUP_INCLUDE_ACTIVITIES_DEFAULT: Final[bool] = True
BACKUP_INTERVAL_MINUTES_DEFAULT: Final[int] = 30
BACKUP_INTERVAL_MINUTES_MIN: Final[int] = 5
BACKUP_INTERVAL_MINUTES_MAX: Final[int] = 1440
BACKUP_ON_UPGRADE_DEFAULT: Final[bool] = True
BACKUP_CONFIG_KEY: Final[str] = "backup"

# Backup trigger types (how backups are initiated)
BACKUP_TRIGGER_MANUAL: Final[str] = "manual"
BACKUP_TRIGGER_ON_TRANSITION: Final[str] = "on_transition"

# Backup file location (in preserved oak/ directory, committed to git)
CI_HISTORY_BACKUP_DIR: Final[str] = "oak/history"
CI_HISTORY_BACKUP_FILE: Final[str] = "ci_history.sql"  # Legacy single-file backup

# Multi-machine backup file pattern
# Format: {github_username}_{machine_hash}.sql (in oak/history/)
CI_HISTORY_BACKUP_FILE_PATTERN: Final[str] = "*.sql"
CI_HISTORY_BACKUP_FILE_PREFIX: Final[str] = ""  # No prefix - directory provides context
CI_HISTORY_BACKUP_FILE_SUFFIX: Final[str] = ".sql"
CI_BACKUP_HEADER_MAX_LINES: Final[int] = 10
CI_BACKUP_PATH_INVALID_ERROR: Final[str] = "Backup path must be within {backup_dir}"

# Environment variable for backup directory override
# Allows teams to store backups in external locations (shared drives, separate repos)
OAK_CI_BACKUP_DIR_ENV: Final[str] = "OAK_CI_BACKUP_DIR"

# =============================================================================
# Machine Identifier Configuration (privacy-preserving)
# =============================================================================
# Machine identifiers use format: {github_username}_{6_char_hash}
# This avoids exposing PII (hostname, system username) in git-tracked backup files.
# The hash is derived from hostname:username:MAC for uniqueness per machine.

MACHINE_ID_HASH_LENGTH: Final[int] = 6
MACHINE_ID_SEPARATOR: Final[str] = "_"
MACHINE_ID_FALLBACK_USERNAME: Final[str] = "anonymous"
MACHINE_ID_MAX_USERNAME_LENGTH: Final[int] = 30
MACHINE_ID_SUBPROCESS_TIMEOUT: Final[int] = 5
MACHINE_ID_CACHE_FILENAME: Final[str] = "machine_id"
