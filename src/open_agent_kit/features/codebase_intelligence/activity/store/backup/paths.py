"""Backup directory configuration and file discovery."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Name of the dotenv file checked for OAK_CI_BACKUP_DIR
_DOTENV_FILENAME = ".env"


def _read_dotenv_value(dotenv_path: Path, key: str) -> str | None:
    """Read a single value from a .env file.

    Simple parser that handles:
    - Comments (lines starting with #)
    - Empty lines
    - KEY=VALUE (unquoted)
    - KEY="VALUE" or KEY='VALUE' (quoted)
    - Inline comments after unquoted values

    Args:
        dotenv_path: Path to the .env file.
        key: The variable name to look for.

    Returns:
        The value if found and non-empty, None otherwise.
    """
    if not dotenv_path.is_file():
        return None

    try:
        with dotenv_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue
                # Must contain =
                if "=" not in line:
                    continue
                var_name, _, raw_value = line.partition("=")
                var_name = var_name.strip()
                if var_name != key:
                    continue
                # Parse value: strip quotes, handle inline comments
                raw_value = raw_value.strip()
                if (raw_value.startswith('"') and raw_value.endswith('"')) or (
                    raw_value.startswith("'") and raw_value.endswith("'")
                ):
                    raw_value = raw_value[1:-1]
                else:
                    # Strip inline comments for unquoted values
                    comment_idx = raw_value.find(" #")
                    if comment_idx >= 0:
                        raw_value = raw_value[:comment_idx].rstrip()
                return raw_value if raw_value else None
    except (OSError, UnicodeDecodeError):
        return None

    return None


def get_backup_dir(project_root: Path | None = None) -> Path:
    """Get backup directory with priority: env var > .env file > default.

    Resolution order:
    1. OAK_CI_BACKUP_DIR shell environment variable
    2. OAK_CI_BACKUP_DIR in project root .env file
    3. Default: project_root / CI_HISTORY_BACKUP_DIR

    If the value is a relative path, it's resolved against project_root.

    Args:
        project_root: Project root directory. If None, uses cwd.

    Returns:
        Resolved Path to backup directory.
    """
    import os

    from open_agent_kit.features.codebase_intelligence.constants import (
        CI_HISTORY_BACKUP_DIR,
        OAK_CI_BACKUP_DIR_ENV,
    )

    if project_root is None:
        project_root = Path.cwd()

    # 1. Check shell environment variable
    env_backup_dir = os.environ.get(OAK_CI_BACKUP_DIR_ENV, "").strip()
    if env_backup_dir:
        backup_path = Path(env_backup_dir)
        if not backup_path.is_absolute():
            backup_path = project_root / backup_path
        return backup_path.resolve()

    # 2. Check .env file in project root
    dotenv_value = _read_dotenv_value(project_root / _DOTENV_FILENAME, OAK_CI_BACKUP_DIR_ENV)
    if dotenv_value:
        backup_path = Path(dotenv_value)
        if not backup_path.is_absolute():
            backup_path = project_root / backup_path
        return backup_path.resolve()

    # 3. Default path
    return project_root / CI_HISTORY_BACKUP_DIR


def get_backup_dir_source(project_root: Path | None = None) -> str:
    """Get the source of the backup directory configuration.

    Args:
        project_root: Project root directory. If None, uses cwd.

    Returns:
        "environment variable", "dotenv file (.env)", or "default".
    """
    import os

    from open_agent_kit.features.codebase_intelligence.constants import (
        OAK_CI_BACKUP_DIR_ENV,
    )

    if project_root is None:
        project_root = Path.cwd()

    # Check shell env var first
    env_backup_dir = os.environ.get(OAK_CI_BACKUP_DIR_ENV, "").strip()
    if env_backup_dir:
        return "environment variable"

    # Check .env file
    dotenv_value = _read_dotenv_value(project_root / _DOTENV_FILENAME, OAK_CI_BACKUP_DIR_ENV)
    if dotenv_value:
        return "dotenv file (.env)"

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
