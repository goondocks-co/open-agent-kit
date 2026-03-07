"""Backup directory configuration and file discovery."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def get_backup_dir(project_root: Path | None = None) -> Path:
    """Get backup directory with priority: user config > default.

    Resolution order:
    1. backup.backup_dir in user override config (.oak/config.{machine_id}.yaml)
    2. Default: project_root / CI_HISTORY_BACKUP_DIR

    If the value is a relative path, it's resolved against project_root.

    Args:
        project_root: Project root directory. If None, uses cwd.

    Returns:
        Resolved Path to backup directory.
    """
    from open_agent_kit.features.team.constants import (
        CI_HISTORY_BACKUP_DIR,
    )

    if project_root is None:
        project_root = Path.cwd()

    # 1. Check user override config
    from open_agent_kit.features.team.config.user_store import read_user_value
    from open_agent_kit.features.team.constants.backup import (
        BACKUP_USER_CONFIG_KEY_DIR,
        BACKUP_USER_CONFIG_SECTION,
    )

    user_value = read_user_value(
        project_root, BACKUP_USER_CONFIG_SECTION, BACKUP_USER_CONFIG_KEY_DIR
    )
    if user_value:
        backup_path = Path(user_value)
        if not backup_path.is_absolute():
            backup_path = project_root / backup_path
        return backup_path.resolve()

    # 2. Default path
    return project_root / CI_HISTORY_BACKUP_DIR


def get_backup_dir_source(project_root: Path | None = None) -> str:
    """Get the source of the backup directory configuration.

    Args:
        project_root: Project root directory. If None, uses cwd.

    Returns:
        "user config" or "default".
    """
    if project_root is None:
        project_root = Path.cwd()

    from open_agent_kit.features.team.config.user_store import read_user_value
    from open_agent_kit.features.team.constants.backup import (
        BACKUP_USER_CONFIG_KEY_DIR,
        BACKUP_USER_CONFIG_SECTION,
    )

    user_value = read_user_value(
        project_root, BACKUP_USER_CONFIG_SECTION, BACKUP_USER_CONFIG_KEY_DIR
    )
    if user_value:
        return "user config"

    return "default"


def validate_backup_dir(backup_dir: Path, create: bool = True) -> tuple[bool, str | None]:
    """Validate that backup directory exists and is writable.

    Args:
        backup_dir: Path to the backup directory.
        create: If True, create the directory if it doesn't exist.

    Returns:
        Tuple of (is_valid, error_message).
        If valid, error_message is None.
    """
    import tempfile

    try:
        if not backup_dir.exists():
            if create:
                backup_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created backup directory: {backup_dir}")
            else:
                return False, f"Backup directory does not exist: {backup_dir}"

        if not backup_dir.is_dir():
            return False, f"Backup path is not a directory: {backup_dir}"

        # Test writability by creating a temporary file
        try:
            with tempfile.NamedTemporaryFile(dir=backup_dir, delete=True):
                pass
        except OSError as e:
            return False, f"Backup directory is not writable: {e}"

        return True, None

    except OSError as e:
        return False, f"Failed to access backup directory: {e}"


def discover_backup_files(backup_dir: Path) -> list[Path]:
    """Find all *.sql backup files, sorted by modified time.

    Args:
        backup_dir: Directory to search for backup files.

    Returns:
        List of backup file paths sorted by modification time (oldest first).
    """
    if not backup_dir.exists():
        return []
    files = list(backup_dir.glob("*.sql"))
    return sorted(files, key=lambda p: p.stat().st_mtime)


def extract_machine_id_from_filename(filename: str) -> str:
    """Extract machine identifier from backup filename.

    Args:
        filename: Backup filename (e.g., "octocat_a7b3c2.sql").

    Returns:
        Machine identifier or "unknown" if not parseable.
    """
    # Current format: {machine_id}.sql
    if filename.endswith(".sql"):
        machine_id = filename[:-4]  # Remove .sql suffix
        if machine_id:
            # Handle legacy ci_history_ prefix (for backwards compatibility)
            if machine_id.startswith("ci_history_"):
                return machine_id[11:]  # Remove "ci_history_" prefix
            # Handle legacy single-file format
            if machine_id == "ci_history":
                return "legacy"
            return machine_id
    return "unknown"
