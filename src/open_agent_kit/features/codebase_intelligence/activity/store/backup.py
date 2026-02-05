"""Backup and restore operations for activity store.

Functions for exporting and importing database data with support for
multi-machine/multi-user backup and restore with content-based deduplication.
"""

from __future__ import annotations

import getpass
import hashlib
import logging
import platform
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from open_agent_kit.features.codebase_intelligence.activity.store.schema import SCHEMA_VERSION

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.store.core import ActivityStore

logger = logging.getLogger(__name__)


# =============================================================================
# Hash Generation Functions
# =============================================================================


def compute_hash(*parts: str | int | None) -> str:
    """Compute stable hash from parts, ignoring None values.

    Args:
        *parts: Variable parts to include in hash computation.

    Returns:
        16-character hex hash string.
    """
    content = "|".join(str(p) if p is not None else "" for p in parts)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def compute_prompt_batch_hash(session_id: str, prompt_number: int) -> str:
    """Hash for prompt_batches deduplication.

    Uses session_id + prompt_number as unique identifier.
    """
    return compute_hash(session_id, prompt_number)


def compute_observation_hash(observation: str, memory_type: str, context: str | None) -> str:
    """Hash for memory_observations deduplication.

    Uses observation content + type + context as unique identifier.
    """
    return compute_hash(observation, memory_type, context)


def compute_activity_hash(session_id: str, timestamp_epoch: int, tool_name: str) -> str:
    """Hash for activities deduplication.

    Uses session_id + timestamp + tool_name as unique identifier.
    """
    return compute_hash(session_id, timestamp_epoch, tool_name)


# =============================================================================
# Machine Identification
# =============================================================================


def sanitize_identifier(identifier: str) -> str:
    """Sanitize identifier for use in filename.

    Args:
        identifier: Raw identifier string.

    Returns:
        Sanitized string safe for filenames (lowercase, alphanumeric + underscore).
    """
    sanitized = re.sub(r"[^a-zA-Z0-9]", "_", identifier)
    sanitized = re.sub(r"_+", "_", sanitized)
    return sanitized[:40].strip("_").lower()


def get_machine_identifier(project_root: Path | None = None) -> str:
    """Get deterministic, privacy-preserving machine identifier for backup files.

    Format: {github_username}_{short_hash} (e.g., "octocat_a7b3c2")

    The identifier is cached in .oak/ci/machine_id for stability. If MAC address
    or hostname changes, the cached value is still used. Delete the cache file
    to regenerate.

    Args:
        project_root: Project root directory (for cache location). If None, uses cwd.

    Returns:
        Sanitized machine identifier string (e.g., "octocat_a7b3c2").
    """
    from open_agent_kit.config.paths import OAK_DIR
    from open_agent_kit.features.codebase_intelligence.constants import (
        CI_DATA_DIR,
        MACHINE_ID_CACHE_FILENAME,
        MACHINE_ID_SEPARATOR,
    )

    # Try to read from cache first
    if project_root is None:
        project_root = Path.cwd()

    cache_path = project_root / OAK_DIR / CI_DATA_DIR / MACHINE_ID_CACHE_FILENAME

    if cache_path.exists():
        try:
            cached_id: str = cache_path.read_text().strip()
            if cached_id:
                return cached_id
        except OSError:
            pass  # Fall through to compute

    # Compute new identifier
    github_user = _get_github_username()
    machine_hash = _get_machine_hash()
    raw_id = f"{github_user}{MACHINE_ID_SEPARATOR}{machine_hash}"
    machine_id = sanitize_identifier(raw_id)

    # Cache for stability
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(machine_id)
    except OSError:
        pass  # Non-fatal - will recompute next time

    return machine_id


def _get_github_username() -> str:
    """Resolve GitHub username through fallback chain.

    Resolution order:
    1. GITHUB_USER environment variable (manual override)
    2. gh CLI: `gh api user --jq .login` (most accurate, requires gh auth)
    3. "anonymous" (final fallback)

    Note: We intentionally do NOT use `git config user.name` because it often
    contains real names (PII) rather than GitHub usernames.

    Returns:
        GitHub username or fallback value.
    """
    import os
    import subprocess

    from open_agent_kit.features.codebase_intelligence.constants import (
        MACHINE_ID_FALLBACK_USERNAME,
        MACHINE_ID_MAX_USERNAME_LENGTH,
        MACHINE_ID_SUBPROCESS_TIMEOUT,
    )

    # 1. Environment variable override
    env_user = os.environ.get("GITHUB_USER", "").strip()
    if env_user:
        return env_user[:MACHINE_ID_MAX_USERNAME_LENGTH]

    # 2. Try gh CLI (requires `gh auth login`)
    try:
        result = subprocess.run(
            ["gh", "api", "user", "--jq", ".login"],
            capture_output=True,
            text=True,
            check=False,
            timeout=MACHINE_ID_SUBPROCESS_TIMEOUT,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()[:MACHINE_ID_MAX_USERNAME_LENGTH]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return MACHINE_ID_FALLBACK_USERNAME


def _get_machine_hash() -> str:
    """Generate short deterministic hash from machine-specific data.

    Uses hostname, username, and MAC address to create a unique identifier
    for this machine. The hash is truncated to 6 characters for readability.

    Returns:
        6-character hex hash string.
    """
    import uuid

    from open_agent_kit.features.codebase_intelligence.constants import (
        MACHINE_ID_HASH_LENGTH,
    )

    raw_machine = f"{platform.node()}:{getpass.getuser()}:{uuid.getnode()}"
    return hashlib.sha256(raw_machine.encode()).hexdigest()[:MACHINE_ID_HASH_LENGTH]


def _compute_legacy_machine_identifier() -> str:
    """Compute the old-format machine identifier for migration purposes.

    This is the original algorithm that exposed PII (hostname_username).
    Used only during migration to identify which records to update.

    Returns:
        Legacy sanitized machine identifier string (e.g., "macbook_chris").
    """
    hostname = platform.node().split(".")[0]  # Short hostname
    username = getpass.getuser()
    raw_id = f"{hostname}_{username}"
    return sanitize_identifier(raw_id)


def get_backup_filename() -> str:
    """Get backup filename for this machine.

    Returns:
        Backup filename with machine identifier (e.g., "octocat_a7b3c2.sql").
    """
    machine_id = get_machine_identifier()
    return f"{machine_id}.sql"


# =============================================================================
# Backup Directory Configuration
# =============================================================================

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


# =============================================================================
# Backup Discovery
# =============================================================================


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


# =============================================================================
# Import Result Tracking
# =============================================================================


@dataclass
class ImportResult:
    """Result statistics from importing a backup file."""

    sessions_imported: int = 0
    sessions_skipped: int = 0
    batches_imported: int = 0
    batches_skipped: int = 0
    observations_imported: int = 0
    observations_skipped: int = 0
    activities_imported: int = 0
    activities_skipped: int = 0
    schedules_imported: int = 0
    schedules_skipped: int = 0
    errors: int = 0
    error_messages: list[str] = field(default_factory=list)

    @property
    def total_imported(self) -> int:
        """Total records imported across all tables."""
        return (
            self.sessions_imported
            + self.batches_imported
            + self.observations_imported
            + self.activities_imported
            + self.schedules_imported
        )

    @property
    def total_skipped(self) -> int:
        """Total records skipped (duplicates) across all tables."""
        return (
            self.sessions_skipped
            + self.batches_skipped
            + self.observations_skipped
            + self.activities_skipped
            + self.schedules_skipped
        )


def export_to_sql(store: ActivityStore, output_path: Path, include_activities: bool = False) -> int:
    """Export valuable tables to SQL dump file with content hashes.

    Exports sessions, prompt_batches, and memory_observations to a SQL file
    that can be used to restore data after feature removal/reinstall.
    The file is text-based and can be committed to git.

    Each record includes a content_hash for cross-machine deduplication,
    allowing multiple developers' backups to be merged without duplicates.

    Origin Tracking: Only exports records that originated on this machine
    (source_machine_id matches current machine). This prevents backup file
    bloat when team members import each other's backups - each developer's
    backup only contains their own original work, not imported data.

    FK Integrity: Only exports records with valid foreign key references.
    Orphaned records (e.g., prompt_batches referencing deleted sessions)
    are skipped to ensure the backup can be cleanly restored.

    Args:
        store: The ActivityStore instance.
        output_path: Path to write SQL dump file.
        include_activities: If True, include activities table (can be large).

    Returns:
        Number of records exported.
    """
    machine_id = get_machine_identifier()
    logger.info(
        f"Exporting database: include_activities={include_activities}, "
        f"machine={machine_id}, path={output_path}"
    )

    conn = store._get_connection()
    total_count = 0
    skipped_orphans = 0
    skipped_foreign = 0

    # Tables to export (order matters for foreign keys)
    # agent_schedules has no FKs - always export user's own schedules
    tables = ["sessions", "prompt_batches", "memory_observations"]
    if include_activities:
        tables.append("activities")
    tables.append("agent_schedules")

    # Build set of valid session IDs for FK validation
    # Only include sessions that originated on this machine (will be exported)
    valid_session_ids = {
        row[0]
        for row in conn.execute(
            "SELECT id FROM sessions WHERE source_machine_id = ?",
            (machine_id,),
        ).fetchall()
    }

    # Build set of valid prompt_batch IDs for FK validation
    # Only include batches that originated on this machine (will be exported)
    valid_batch_ids = {
        row[0]
        for row in conn.execute(
            "SELECT id FROM prompt_batches WHERE source_machine_id = ?",
            (machine_id,),
        ).fetchall()
    }

    # Count records from other machines (imported data that won't be re-exported)
    for table in tables:
        cursor = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE source_machine_id != ?",  # noqa: S608
            (machine_id,),
        )
        count = cursor.fetchone()[0]
        if count > 0:
            skipped_foreign += count
            logger.debug(f"Excluding {count} {table} records imported from other machines")

    # Generate INSERT statements
    lines: list[str] = []
    lines.append("-- OAK Codebase Intelligence History Backup")
    lines.append(f"-- Exported: {datetime.now().isoformat()}")
    lines.append(f"-- Machine: {machine_id}")
    lines.append(f"-- Schema version: {SCHEMA_VERSION}")
    lines.append("")

    for table in tables:
        # Only export records that originated on this machine (origin tracking)
        # This prevents backup file bloat when importing from other team members
        cursor = conn.execute(
            f"SELECT * FROM {table} WHERE source_machine_id = ?",  # noqa: S608
            (machine_id,),
        )
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()

        if rows:
            table_exported = 0
            table_skipped = 0
            table_lines: list[str] = []

            for row in rows:
                # Build row dict for hash computation and FK validation
                row_dict = dict(zip(columns, row, strict=False))

                # FK validation - skip orphaned records
                if table == "prompt_batches":
                    session_id = row_dict.get("session_id")
                    if session_id and session_id not in valid_session_ids:
                        table_skipped += 1
                        continue
                elif table == "memory_observations":
                    session_id = row_dict.get("session_id")
                    batch_id = row_dict.get("prompt_batch_id")
                    if session_id and session_id not in valid_session_ids:
                        table_skipped += 1
                        continue
                    if batch_id is not None and batch_id not in valid_batch_ids:
                        table_skipped += 1
                        continue
                elif table == "activities":
                    session_id = row_dict.get("session_id")
                    batch_id = row_dict.get("prompt_batch_id")
                    if session_id and session_id not in valid_session_ids:
                        table_skipped += 1
                        continue
                    if batch_id is not None and batch_id not in valid_batch_ids:
                        table_skipped += 1
                        continue

                # Compute content hash if not already present
                content_hash = row_dict.get("content_hash")
                if not content_hash and "content_hash" in columns:
                    content_hash = _compute_hash_for_table(table, row_dict)

                values = []
                for col, val in zip(columns, row, strict=False):
                    # Use computed hash if original was None
                    if col == "content_hash" and val is None and content_hash:
                        val = content_hash

                    if val is None:
                        values.append("NULL")
                    elif isinstance(val, (int, float)):
                        values.append(str(val))
                    elif isinstance(val, bool):
                        values.append("1" if val else "0")
                    else:
                        # Escape single quotes for SQL
                        escaped = str(val).replace("'", "''")
                        values.append(f"'{escaped}'")

                cols_str = ", ".join(columns)
                vals_str = ", ".join(values)
                table_lines.append(f"INSERT INTO {table} ({cols_str}) VALUES ({vals_str});")
                table_exported += 1

            # Write table header and records
            if table_exported > 0:
                lines.append(f"-- {table} ({table_exported} records)")
                lines.extend(table_lines)
                lines.append("")

            total_count += table_exported
            skipped_orphans += table_skipped

            if table_skipped > 0:
                logger.warning(
                    f"Skipped {table_skipped} orphaned {table} records with invalid FK references"
                )

        logger.debug(f"Exported {len(rows)} records from {table}")

    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")

    # Log completion with details about skipped records
    skip_details = []
    if skipped_orphans > 0:
        skip_details.append(f"{skipped_orphans} orphaned")
    if skipped_foreign > 0:
        skip_details.append(f"{skipped_foreign} from other machines")

    if skip_details:
        logger.info(
            f"Export complete: {total_count} records to {output_path} "
            f"(skipped: {', '.join(skip_details)})"
        )
    else:
        logger.info(f"Export complete: {total_count} records to {output_path}")
    return total_count


def _compute_hash_for_table(table: str, row_dict: dict) -> str | None:
    """Compute content hash for a row based on table type.

    Args:
        table: Table name.
        row_dict: Dictionary of column names to values.

    Returns:
        Content hash string or None if table doesn't support hashing.
    """
    if table == "prompt_batches":
        session_id = row_dict.get("session_id", "")
        prompt_number = row_dict.get("prompt_number", 0)
        return compute_prompt_batch_hash(str(session_id), int(prompt_number))
    elif table == "memory_observations":
        observation = row_dict.get("observation", "")
        memory_type = row_dict.get("memory_type", "")
        context = row_dict.get("context")
        return compute_observation_hash(str(observation), str(memory_type), context)
    elif table == "activities":
        session_id = row_dict.get("session_id", "")
        timestamp_epoch = row_dict.get("timestamp_epoch", 0)
        tool_name = row_dict.get("tool_name", "")
        return compute_activity_hash(str(session_id), int(timestamp_epoch), str(tool_name))
    return None


def _parse_backup_schema_version(lines: list[str]) -> int | None:
    """Parse schema version from backup file header comments.

    Looks for a line like: -- Schema version: 11

    Args:
        lines: Lines from the backup file.

    Returns:
        Schema version as int, or None if not found.
    """
    for line in lines[:10]:  # Only check first 10 lines (header area)
        if line.startswith("-- Schema version:"):
            try:
                version_str = line.split(":")[-1].strip()
                return int(version_str)
            except ValueError:
                return None
    return None


def import_from_sql(store: ActivityStore, backup_path: Path) -> int:
    """Import data from SQL backup into existing database (legacy interface).

    This is a wrapper around import_from_sql_with_dedup for backwards compatibility.

    Args:
        store: The ActivityStore instance.
        backup_path: Path to SQL backup file.

    Returns:
        Number of records imported.
    """
    result = import_from_sql_with_dedup(store, backup_path)
    return result.total_imported


def import_from_sql_with_dedup(
    store: ActivityStore,
    backup_path: Path,
    dry_run: bool = False,
) -> ImportResult:
    """Import data from SQL backup with content-based deduplication.

    The database should already have the current schema (via _ensure_schema).
    This method imports data only, not schema. All imported observations
    are marked as unembedded to trigger ChromaDB rebuild.

    Uses content hashes to detect duplicates across machines:
    - Sessions: deduplicated by primary key (session ID)
    - Prompt batches: deduplicated by content_hash (session_id + prompt_number)
    - Observations: deduplicated by content_hash (observation + type + context)
    - Activities: deduplicated by content_hash (session_id + timestamp + tool_name)

    Foreign key handling:
    - prompt_batches: id column removed (auto-generated by SQLite)
    - activities: id column removed, prompt_batch_id remapped to new IDs

    Args:
        store: The ActivityStore instance.
        backup_path: Path to SQL backup file.
        dry_run: If True, preview what would be imported without making changes.

    Returns:
        ImportResult with detailed statistics.
    """
    logger.info(f"Importing from backup: {backup_path} (dry_run={dry_run})")

    result = ImportResult()
    content = backup_path.read_text(encoding="utf-8")
    lines = content.split("\n")

    # Check backup schema version
    backup_schema_version = _parse_backup_schema_version(lines)
    if backup_schema_version is not None and backup_schema_version != SCHEMA_VERSION:
        if backup_schema_version < SCHEMA_VERSION:
            logger.warning(
                f"Backup file is from older schema version {backup_schema_version} "
                f"(current: {SCHEMA_VERSION}). Import will proceed - missing columns "
                "will use default values and hashes will be computed from content."
            )
        else:
            logger.warning(
                f"Backup file is from newer schema version {backup_schema_version} "
                f"(current: {SCHEMA_VERSION}). Import may have issues if backup "
                "contains columns not in current schema."
            )

    # Load existing IDs/hashes for deduplication
    existing_session_ids = store.get_all_session_ids()
    existing_batch_hashes = store.get_all_prompt_batch_hashes()
    existing_obs_hashes = store.get_all_observation_hashes()
    existing_activity_hashes = store.get_all_activity_hashes()
    existing_schedule_names = store.get_all_schedule_task_names()

    # Get current machine ID for schedule filtering
    current_machine_id = get_machine_identifier()

    logger.debug(
        f"Existing records: {len(existing_session_ids)} sessions, "
        f"{len(existing_batch_hashes)} batches, {len(existing_obs_hashes)} observations, "
        f"{len(existing_activity_hashes)} activities, {len(existing_schedule_names)} schedules"
    )

    # Parse INSERT statements - use proper SQL statement extraction for multi-line values
    statements_by_table: dict[str, list[tuple[str, dict]]] = {
        "sessions": [],
        "prompt_batches": [],
        "memory_observations": [],
        "activities": [],
        "agent_schedules": [],
    }

    # Extract complete SQL statements (handles multi-line INSERT with newlines in values)
    sql_statements = _extract_sql_statements(content)
    logger.debug(f"Extracted {len(sql_statements)} SQL statements from backup")

    for stmt in sql_statements:
        # Extract table name
        table_match = re.match(r"INSERT INTO (\w+)", stmt)
        if not table_match:
            continue
        table = table_match.group(1)

        if table not in statements_by_table:
            continue

        # Parse column names and values
        parsed = _parse_insert_statement(stmt)
        if parsed:
            statements_by_table[table].append((stmt, parsed))

    # Process each table in order (sessions first due to foreign keys)
    conn = store._get_connection()

    # Get valid columns for each table (for schema compatibility filtering)
    table_columns: dict[str, set[str]] = {}
    for table in statements_by_table:
        table_columns[table] = _get_table_columns(conn, table)
    logger.debug(f"Schema columns loaded for tables: {list(table_columns.keys())}")

    # Track old prompt_batch_id -> (session_id, prompt_number) from backup file
    # This is needed to remap activities' prompt_batch_id foreign keys
    old_batch_id_to_key: dict[int, tuple[str, int]] = {}
    for _stmt, row_dict in statements_by_table["prompt_batches"]:
        old_id = row_dict.get("id")
        session_id = row_dict.get("session_id")
        prompt_number = row_dict.get("prompt_number")
        if old_id is not None and session_id and prompt_number is not None:
            old_batch_id_to_key[int(old_id)] = (str(session_id), int(prompt_number))

    logger.debug(f"Tracked {len(old_batch_id_to_key)} old prompt_batch_id -> key mappings")

    # Initialize the batch ID mapping (built after prompt_batches import)
    old_to_new_batch_id: dict[int, int] = {}

    # Track imported session IDs for parent validation
    imported_session_ids: set[str] = set()

    # Track columns removed during filtering (for summary logging)
    all_removed_columns: dict[str, set[str]] = {t: set() for t in statements_by_table}

    for table in [
        "sessions",
        "prompt_batches",
        "memory_observations",
        "activities",
        "agent_schedules",
    ]:
        # After importing sessions, validate parent_session_id references
        if table == "prompt_batches" and not dry_run and imported_session_ids:
            _validate_parent_session_ids(conn, imported_session_ids)

        # After importing prompt_batches, build the ID mapping and remap self-references
        if table == "memory_observations" and not dry_run:
            # Build mapping from (session_id, prompt_number) -> new_prompt_batch_id
            new_key_to_batch_id = _build_prompt_batch_id_map(conn)
            # Combine: old_batch_id -> key -> new_batch_id
            for old_id, key in old_batch_id_to_key.items():
                if key in new_key_to_batch_id:
                    old_to_new_batch_id[old_id] = new_key_to_batch_id[key]
            logger.debug(
                f"Built prompt_batch_id remap: {len(old_to_new_batch_id)} mappings "
                f"(from {len(old_batch_id_to_key)} old IDs)"
            )

            # Remap source_plan_batch_id self-references in prompt_batches
            _remap_source_plan_batch_id(conn, old_to_new_batch_id)

        for stmt, row_dict in statements_by_table[table]:
            try:
                # Filter columns for schema compatibility (handles newer backups)
                filtered_stmt, filtered_row_dict, removed_cols = _filter_columns_for_schema(
                    stmt, row_dict, table_columns[table]
                )
                all_removed_columns[table].update(removed_cols)

                should_skip, reason = _should_skip_record(
                    table,
                    filtered_row_dict,
                    existing_session_ids,
                    existing_batch_hashes,
                    existing_obs_hashes,
                    existing_activity_hashes,
                    existing_schedule_names,
                    current_machine_id,
                )

                if should_skip:
                    _increment_skipped(result, table)
                    logger.debug(f"Skipping {table} record: {reason}")
                    continue

                rows_affected = 1  # Default for dry_run
                if not dry_run:
                    # Modify statement for proper import
                    modified_stmt = _prepare_statement_for_import(filtered_stmt, table)

                    # For memory_observations and activities, remap prompt_batch_id to new ID
                    if table in ("memory_observations", "activities"):
                        modified_stmt = _remap_prompt_batch_id(
                            modified_stmt, filtered_row_dict, old_to_new_batch_id
                        )

                    cursor = conn.execute(modified_stmt)
                    rows_affected = cursor.rowcount

                    # Track imported session IDs for parent validation
                    if table == "sessions":
                        session_id = filtered_row_dict.get("id")
                        if session_id:
                            imported_session_ids.add(str(session_id))

                    # Update existing sets to avoid duplicates within same import
                    _update_existing_sets(
                        table,
                        filtered_row_dict,
                        existing_session_ids,
                        existing_batch_hashes,
                        existing_obs_hashes,
                        existing_activity_hashes,
                        existing_schedule_names,
                    )

                # Only count as imported if a row was actually inserted
                # (INSERT OR IGNORE returns rowcount=0 when ignored due to ID collision)
                if rows_affected > 0:
                    _increment_imported(result, table)
                else:
                    _increment_skipped(result, table)
                    logger.debug(f"Skipped {table} record due to ID collision")

            except sqlite3.Error as e:
                result.errors += 1
                error_msg = f"Error importing {table} record: {e}"
                result.error_messages.append(error_msg)
                logger.warning(error_msg)

    if not dry_run:
        conn.commit()

    # Log summary of filtered columns (schema compatibility)
    for table, removed in all_removed_columns.items():
        if removed:
            logger.info(
                f"Schema compatibility: filtered {len(removed)} unknown columns "
                f"from {table}: {sorted(removed)}"
            )

    logger.info(
        f"Import complete: {result.total_imported} imported, "
        f"{result.total_skipped} skipped (duplicates), {result.errors} errors"
    )
    return result


def _extract_sql_statements(content: str) -> list[str]:
    """Extract complete SQL INSERT statements from backup content.

    Handles multi-line statements where values contain newlines.
    A statement ends with ');' not inside a quoted string.

    Args:
        content: Full backup file content.

    Returns:
        List of complete INSERT statements.
    """
    statements = []
    current_stmt = ""
    in_string = False
    in_comment = False
    i = 0

    while i < len(content):
        char = content[i]

        # Handle SQL comments (-- to end of line)
        if not in_string and not in_comment and char == "-":
            if i + 1 < len(content) and content[i + 1] == "-":
                in_comment = True
                i += 2
                continue

        # End of comment at newline
        if in_comment:
            if char == "\n":
                in_comment = False
            i += 1
            continue

        # Skip whitespace/newlines when not in a statement
        if not current_stmt and char in " \t\n\r":
            i += 1
            continue

        current_stmt += char

        if char == "'" and not in_string:
            in_string = True
        elif char == "'" and in_string:
            # Check for escaped quote ''
            if i + 1 < len(content) and content[i + 1] == "'":
                # Escaped quote - add it and skip next char
                current_stmt += content[i + 1]
                i += 1
            else:
                in_string = False
        elif char == ";" and not in_string:
            # Statement complete
            stmt = current_stmt.strip()
            if stmt.startswith("INSERT INTO"):
                statements.append(stmt)
            current_stmt = ""

        i += 1

    return statements


def _parse_insert_statement(stmt: str) -> dict | None:
    """Parse INSERT statement to extract column names and values.

    Args:
        stmt: SQL INSERT statement.

    Returns:
        Dictionary of column names to values, or None if parsing fails.
    """
    # Pattern: INSERT INTO table (col1, col2, ...) VALUES (val1, val2, ...);
    match = re.match(
        r"INSERT INTO \w+ \(([^)]+)\) VALUES \((.+)\);?$",
        stmt,
        re.DOTALL,
    )
    if not match:
        return None

    columns_str = match.group(1)
    values_str = match.group(2)

    columns = [c.strip() for c in columns_str.split(",")]

    # Parse values (handling quoted strings with commas)
    values = _parse_sql_values(values_str)
    if len(values) != len(columns):
        return None

    return dict(zip(columns, values, strict=False))


def _parse_sql_values(values_str: str) -> list:
    """Parse SQL VALUES clause, handling quoted strings with commas.

    Args:
        values_str: The values portion of an INSERT statement.

    Returns:
        List of parsed values.
    """
    values = []
    current = ""
    in_string = False
    i = 0

    while i < len(values_str):
        char = values_str[i]

        if char == "'" and not in_string:
            in_string = True
            current += char
        elif char == "'" and in_string:
            # Check for escaped quote
            if i + 1 < len(values_str) and values_str[i + 1] == "'":
                current += "''"
                i += 1
            else:
                in_string = False
                current += char
        elif char == "," and not in_string:
            values.append(_parse_sql_value(current.strip()))
            current = ""
        else:
            current += char
        i += 1

    # Don't forget the last value
    if current.strip():
        values.append(_parse_sql_value(current.strip()))

    return values


def _parse_sql_value(val_str: str) -> str | int | float | bool | None:
    """Parse a single SQL value string to Python type.

    Args:
        val_str: SQL value string.

    Returns:
        Parsed Python value (str, int, float, None, or bool).
    """
    if val_str == "NULL":
        return None
    if val_str.startswith("'") and val_str.endswith("'"):
        # Unescape single quotes
        return val_str[1:-1].replace("''", "'")
    try:
        if "." in val_str:
            return float(val_str)
        return int(val_str)
    except ValueError:
        return val_str


def _should_skip_record(
    table: str,
    row_dict: dict,
    existing_session_ids: set[str],
    existing_batch_hashes: set[str],
    existing_obs_hashes: set[str],
    existing_activity_hashes: set[str],
    existing_schedule_names: set[str] | None = None,
    current_machine_id: str | None = None,
) -> tuple[bool, str]:
    """Determine if a record should be skipped due to duplication.

    Args:
        table: Table name.
        row_dict: Parsed row data.
        existing_*: Sets of existing IDs/hashes.
        existing_schedule_names: Set of existing schedule instance names.
        current_machine_id: Current machine identifier (for schedule filtering).

    Returns:
        Tuple of (should_skip, reason).
    """
    if table == "sessions":
        session_id = row_dict.get("id", "")
        if session_id in existing_session_ids:
            return True, f"session {session_id} already exists"

    elif table == "prompt_batches":
        # Check content hash first, then compute if missing
        content_hash = row_dict.get("content_hash")
        if not content_hash:
            session_id = str(row_dict.get("session_id", ""))
            prompt_number = int(row_dict.get("prompt_number", 0))
            content_hash = compute_prompt_batch_hash(session_id, prompt_number)
        if content_hash in existing_batch_hashes:
            return True, f"prompt_batch with hash {content_hash} already exists"

    elif table == "memory_observations":
        content_hash = row_dict.get("content_hash")
        if not content_hash:
            observation = str(row_dict.get("observation", ""))
            memory_type = str(row_dict.get("memory_type", ""))
            context = row_dict.get("context")
            content_hash = compute_observation_hash(observation, memory_type, context)
        if content_hash in existing_obs_hashes:
            return True, f"observation with hash {content_hash} already exists"

    elif table == "activities":
        content_hash = row_dict.get("content_hash")
        if not content_hash:
            session_id = str(row_dict.get("session_id", ""))
            timestamp_epoch = int(row_dict.get("timestamp_epoch", 0))
            tool_name = str(row_dict.get("tool_name", ""))
            content_hash = compute_activity_hash(session_id, timestamp_epoch, tool_name)
        if content_hash in existing_activity_hashes:
            return True, f"activity with hash {content_hash} already exists"

    elif table == "agent_schedules":
        # Schedules are user preferences - only import from same machine
        # This prevents team backups from overwriting personal schedule settings
        backup_machine_id = row_dict.get("source_machine_id")
        if current_machine_id and backup_machine_id and backup_machine_id != current_machine_id:
            return True, f"schedule from different machine ({backup_machine_id})"

        # Check if schedule already exists by task_name (primary key)
        task_name = row_dict.get("task_name", "")
        if existing_schedule_names and task_name in existing_schedule_names:
            return True, f"schedule {task_name} already exists"

    return False, ""


def _update_existing_sets(
    table: str,
    row_dict: dict,
    existing_session_ids: set[str],
    existing_batch_hashes: set[str],
    existing_obs_hashes: set[str],
    existing_activity_hashes: set[str],
    existing_schedule_names: set[str] | None = None,
) -> None:
    """Update existing sets after successful import to prevent duplicates within batch.

    Args:
        table: Table name.
        row_dict: Imported row data.
        existing_*: Sets to update.
    """
    if table == "sessions":
        existing_session_ids.add(str(row_dict.get("id", "")))

    elif table == "prompt_batches":
        content_hash = row_dict.get("content_hash")
        if not content_hash:
            session_id = str(row_dict.get("session_id", ""))
            prompt_number = int(row_dict.get("prompt_number", 0))
            content_hash = compute_prompt_batch_hash(session_id, prompt_number)
        existing_batch_hashes.add(content_hash)

    elif table == "memory_observations":
        content_hash = row_dict.get("content_hash")
        if not content_hash:
            observation = str(row_dict.get("observation", ""))
            memory_type = str(row_dict.get("memory_type", ""))
            context = row_dict.get("context")
            content_hash = compute_observation_hash(observation, memory_type, context)
        existing_obs_hashes.add(content_hash)

    elif table == "activities":
        content_hash = row_dict.get("content_hash")
        if not content_hash:
            session_id = str(row_dict.get("session_id", ""))
            timestamp_epoch = int(row_dict.get("timestamp_epoch", 0))
            tool_name = str(row_dict.get("tool_name", ""))
            content_hash = compute_activity_hash(session_id, timestamp_epoch, tool_name)
        existing_activity_hashes.add(content_hash)

    elif table == "agent_schedules":
        if existing_schedule_names is not None:
            task_name = str(row_dict.get("task_name", ""))
            existing_schedule_names.add(task_name)


def _prepare_statement_for_import(stmt: str, table: str) -> str:
    """Modify INSERT statement for proper import.

    For memory_observations, marks embedded=0 to trigger ChromaDB rebuild.
    For prompt_batches, marks plan_embedded=0 for re-indexing and removes id column.
    For activities, removes id column to avoid PRIMARY KEY conflicts.
    For agent_schedules, uses INSERT OR IGNORE for TEXT primary key handling.

    The id column is removed for prompt_batches and activities because these use
    auto-increment INTEGER PRIMARY KEY, which would conflict when importing from
    different machines that have overlapping id sequences.

    Args:
        stmt: Original INSERT statement.
        table: Table name.

    Returns:
        Modified statement ready for execution.
    """
    if table == "memory_observations":
        # Use INSERT OR IGNORE to handle rare UUID collisions gracefully
        # (if ID exists but content_hash is different, skip the import)
        stmt = stmt.replace("INSERT INTO", "INSERT OR IGNORE INTO", 1)
        return _replace_column_value(stmt, "embedded", "0")
    elif table == "prompt_batches":
        # Remove id column to let SQLite auto-generate, and mark unembedded
        stmt = _remove_column_from_insert(stmt, "id")
        stmt = _replace_column_value(stmt, "plan_embedded", "0")
        return stmt
    elif table == "activities":
        # Remove id column to let SQLite auto-generate
        return _remove_column_from_insert(stmt, "id")
    elif table == "sessions":
        # Use INSERT OR IGNORE to handle potential session ID collisions
        return stmt.replace("INSERT INTO", "INSERT OR IGNORE INTO", 1)
    elif table == "agent_schedules":
        # Use INSERT OR IGNORE for TEXT primary key (task_name)
        # Schedules are already filtered by machine in _should_skip_record
        return stmt.replace("INSERT INTO", "INSERT OR IGNORE INTO", 1)
    return stmt


def _build_prompt_batch_id_map(conn: sqlite3.Connection) -> dict[tuple[str, int], int]:
    """Build mapping from (session_id, prompt_number) to prompt_batch id.

    Used to remap activities' prompt_batch_id foreign keys after importing
    prompt_batches with auto-generated IDs.

    Args:
        conn: SQLite connection.

    Returns:
        Dictionary mapping (session_id, prompt_number) tuples to prompt_batch id.
    """
    cursor = conn.execute("SELECT id, session_id, prompt_number FROM prompt_batches")
    return {(row[1], row[2]): row[0] for row in cursor.fetchall()}


def _remap_prompt_batch_id(
    stmt: str,
    row_dict: dict,
    old_to_new_batch_id: dict[int, int],
) -> str:
    """Remap prompt_batch_id to the correct new ID.

    After prompt_batches are imported with auto-generated IDs, activities
    and memory_observations still reference the OLD prompt_batch_id from
    the source machine. This function looks up the correct new ID using
    the pre-computed mapping.

    Args:
        stmt: The INSERT statement for the record.
        row_dict: Parsed row data from the record.
        old_to_new_batch_id: Mapping from old prompt_batch_id to new id.

    Returns:
        Modified statement with corrected prompt_batch_id, or original if lookup fails.
    """
    old_batch_id = row_dict.get("prompt_batch_id")
    if old_batch_id is None:
        return stmt

    old_batch_id_int = int(old_batch_id)
    new_batch_id = old_to_new_batch_id.get(old_batch_id_int)

    if new_batch_id is None:
        logger.warning(
            f"No mapping found for old prompt_batch_id {old_batch_id}, "
            f"activity may reference wrong batch"
        )
        return stmt

    logger.debug(f"Remapped activity prompt_batch_id: {old_batch_id} -> {new_batch_id}")
    return _replace_column_value(stmt, "prompt_batch_id", str(new_batch_id))


def _remove_column_from_insert(stmt: str, column_name: str) -> str:
    """Remove a column and its value from an INSERT statement.

    Used to strip auto-increment id columns so SQLite generates new IDs,
    avoiding PRIMARY KEY conflicts when importing from different machines.

    Args:
        stmt: INSERT INTO table (cols) VALUES (vals); statement.
        column_name: Name of the column to remove.

    Returns:
        Modified statement without the column.
    """
    # Parse column list
    cols_match = re.search(r"\(([^)]+)\)\s*VALUES\s*\(", stmt, re.IGNORECASE)
    if not cols_match:
        return stmt

    cols_str = cols_match.group(1)
    columns = [c.strip() for c in cols_str.split(",")]

    # Find target column index
    try:
        col_idx = columns.index(column_name)
    except ValueError:
        return stmt  # Column not in statement

    # Find VALUES section
    values_start = stmt.upper().find("VALUES")
    if values_start == -1:
        return stmt

    # Find the opening paren after VALUES
    paren_start = stmt.find("(", values_start)
    if paren_start == -1:
        return stmt

    # Parse values as raw SQL strings (handling quoted strings with commas)
    values_section = stmt[paren_start + 1 :]
    values = _parse_sql_values_as_strings(values_section.rstrip(");"))

    if col_idx >= len(values):
        return stmt

    # Remove the column and value
    new_columns = columns[:col_idx] + columns[col_idx + 1 :]
    new_values = values[:col_idx] + values[col_idx + 1 :]

    # Get table name
    table_match = re.match(r"INSERT INTO (\w+)", stmt)
    if not table_match:
        return stmt
    table_name = table_match.group(1)

    # Rebuild the statement
    return f"INSERT INTO {table_name} ({', '.join(new_columns)}) VALUES ({', '.join(new_values)});"


def _replace_column_value(stmt: str, column_name: str, new_value: str) -> str:
    """Replace a column's value in an INSERT statement.

    Parses the INSERT statement to find the column index in the column list,
    then replaces the corresponding value in the VALUES section.

    Args:
        stmt: INSERT INTO table (cols) VALUES (vals); statement.
        column_name: Name of the column to modify.
        new_value: New value to set.

    Returns:
        Modified statement with the column's value replaced.
    """
    # Parse column list
    cols_match = re.search(r"\(([^)]+)\)\s*VALUES\s*\(", stmt, re.IGNORECASE)
    if not cols_match:
        return stmt

    cols_str = cols_match.group(1)
    columns = [c.strip() for c in cols_str.split(",")]

    # Find target column index
    try:
        col_idx = columns.index(column_name)
    except ValueError:
        return stmt  # Column not in statement

    # Find VALUES section
    values_start = stmt.upper().find("VALUES")
    if values_start == -1:
        return stmt

    # Find the opening paren after VALUES
    paren_start = stmt.find("(", values_start)
    if paren_start == -1:
        return stmt

    # Parse values as raw SQL strings (handling quoted strings with commas)
    values_section = stmt[paren_start + 1 :]
    values = _parse_sql_values_as_strings(values_section.rstrip(");"))

    if col_idx >= len(values):
        return stmt

    # Replace the value
    values[col_idx] = new_value

    # Rebuild the statement
    prefix = stmt[: paren_start + 1]
    return f"{prefix}{', '.join(values)});"


def _parse_sql_values_as_strings(values_str: str) -> list[str]:
    """Parse SQL VALUES section into list of raw SQL value strings.

    Handles quoted strings with embedded commas and parentheses.
    Returns original SQL representation (e.g., 'text', NULL, 123).

    Args:
        values_str: The content inside VALUES (...) without outer parens.

    Returns:
        List of SQL value strings.
    """
    values: list[str] = []
    current = ""
    in_string = False
    depth = 0

    for char in values_str:
        if char == "'" and not in_string:
            in_string = True
            current += char
        elif char == "'" and in_string:
            # Check for escaped quote ('')
            if current.endswith("'"):
                current += char
            else:
                in_string = False
                current += char
        elif char == "(" and not in_string:
            depth += 1
            current += char
        elif char == ")" and not in_string:
            depth -= 1
            current += char
        elif char == "," and not in_string and depth == 0:
            values.append(current.strip())
            current = ""
        else:
            current += char

    # Don't forget the last value
    if current.strip():
        values.append(current.strip())

    return values


def _increment_imported(result: ImportResult, table: str) -> None:
    """Increment the appropriate imported counter."""
    if table == "sessions":
        result.sessions_imported += 1
    elif table == "prompt_batches":
        result.batches_imported += 1
    elif table == "memory_observations":
        result.observations_imported += 1
    elif table == "activities":
        result.activities_imported += 1
    elif table == "agent_schedules":
        result.schedules_imported += 1


def _increment_skipped(result: ImportResult, table: str) -> None:
    """Increment the appropriate skipped counter."""
    if table == "sessions":
        result.sessions_skipped += 1
    elif table == "prompt_batches":
        result.batches_skipped += 1
    elif table == "memory_observations":
        result.observations_skipped += 1
    elif table == "activities":
        result.activities_skipped += 1
    elif table == "agent_schedules":
        result.schedules_skipped += 1


# =============================================================================
# Schema-Aware Import Functions (for forward/backward compatibility)
# =============================================================================


def _get_table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    """Get column names for a table from the current schema.

    Args:
        conn: SQLite connection.
        table: Table name.

    Returns:
        Set of column names in the table.
    """
    cursor = conn.execute(f"PRAGMA table_info({table})")  # noqa: S608 - trusted table name
    return {row[1] for row in cursor.fetchall()}


def _filter_columns_for_schema(
    stmt: str,
    row_dict: dict,
    valid_columns: set[str],
) -> tuple[str, dict, list[str]]:
    """Filter INSERT statement to only include columns in current schema.

    This enables importing backups from newer schema versions by stripping
    columns that don't exist in the current schema.

    Args:
        stmt: Original INSERT statement.
        row_dict: Parsed row data.
        valid_columns: Set of valid column names from current schema.

    Returns:
        Tuple of (filtered_stmt, filtered_row_dict, removed_columns).
    """
    # Parse the statement to get columns and values
    cols_match = re.search(r"INSERT INTO (\w+) \(([^)]+)\) VALUES \(", stmt, re.IGNORECASE)
    if not cols_match:
        return stmt, row_dict, []

    table_name = cols_match.group(1)
    cols_str = cols_match.group(2)
    columns = [c.strip() for c in cols_str.split(",")]

    # Find columns to remove
    removed_columns = [c for c in columns if c not in valid_columns]
    if not removed_columns:
        return stmt, row_dict, []

    # Parse values
    values_start = stmt.upper().find("VALUES")
    paren_start = stmt.find("(", values_start)
    values_section = stmt[paren_start + 1 :].rstrip(");")
    values = _parse_sql_values_as_strings(values_section)

    if len(values) != len(columns):
        logger.warning(f"Column/value count mismatch, skipping column filter for {table_name}")
        return stmt, row_dict, []

    # Build filtered columns and values
    filtered_columns = []
    filtered_values = []
    filtered_row_dict = {}

    for col, val in zip(columns, values, strict=False):
        if col in valid_columns:
            filtered_columns.append(col)
            filtered_values.append(val)
            if col in row_dict:
                filtered_row_dict[col] = row_dict[col]

    # Rebuild statement
    filtered_stmt = (
        f"INSERT INTO {table_name} ({', '.join(filtered_columns)}) "
        f"VALUES ({', '.join(filtered_values)});"
    )

    logger.debug(
        f"Filtered {len(removed_columns)} unknown columns from {table_name}: {removed_columns}"
    )
    return filtered_stmt, filtered_row_dict, removed_columns


def _remap_source_plan_batch_id(
    conn: sqlite3.Connection,
    old_to_new_batch_id: dict[int, int],
) -> int:
    """Remap source_plan_batch_id FKs in prompt_batches after import.

    Since prompt_batches.id is auto-generated during import, any
    source_plan_batch_id values reference old IDs that no longer exist.
    This function updates them to point to the correct new IDs.

    Args:
        conn: SQLite connection.
        old_to_new_batch_id: Mapping from old prompt_batch_id to new id.

    Returns:
        Number of records updated.
    """
    if not old_to_new_batch_id:
        return 0

    # Find all prompt_batches with source_plan_batch_id set
    cursor = conn.execute(
        "SELECT id, source_plan_batch_id FROM prompt_batches WHERE source_plan_batch_id IS NOT NULL"
    )
    rows = cursor.fetchall()

    updated = 0
    for batch_id, old_source_id in rows:
        new_source_id = old_to_new_batch_id.get(old_source_id)
        if new_source_id is not None and new_source_id != old_source_id:
            conn.execute(
                "UPDATE prompt_batches SET source_plan_batch_id = ? WHERE id = ?",
                (new_source_id, batch_id),
            )
            updated += 1
            logger.debug(
                f"Remapped prompt_batch {batch_id} source_plan_batch_id: "
                f"{old_source_id} -> {new_source_id}"
            )
        elif new_source_id is None and old_source_id not in old_to_new_batch_id:
            # Old source batch wasn't imported - set to NULL to avoid FK violation
            conn.execute(
                "UPDATE prompt_batches SET source_plan_batch_id = NULL WHERE id = ?",
                (batch_id,),
            )
            logger.warning(
                f"prompt_batch {batch_id} references unknown source_plan_batch_id "
                f"{old_source_id}, setting to NULL"
            )
            updated += 1

    if updated > 0:
        logger.info(f"Remapped {updated} source_plan_batch_id references")
    return updated


def _validate_parent_session_ids(
    conn: sqlite3.Connection,
    imported_session_ids: set[str],
) -> int:
    """Validate parent_session_id references after session import.

    Sets parent_session_id to NULL for sessions that reference
    parent sessions not included in the import or existing data.

    Args:
        conn: SQLite connection.
        imported_session_ids: Set of session IDs that were imported.

    Returns:
        Number of orphaned references fixed.
    """
    # Get all existing session IDs (includes both imported and pre-existing)
    cursor = conn.execute("SELECT id FROM sessions")
    all_session_ids = {row[0] for row in cursor.fetchall()}

    # Find sessions with orphaned parent references
    cursor = conn.execute(
        "SELECT id, parent_session_id FROM sessions WHERE parent_session_id IS NOT NULL"
    )
    rows = cursor.fetchall()

    fixed = 0
    for session_id, parent_id in rows:
        if parent_id not in all_session_ids:
            conn.execute(
                "UPDATE sessions SET parent_session_id = NULL, parent_session_reason = NULL "
                "WHERE id = ?",
                (session_id,),
            )
            logger.warning(
                f"Session {session_id} references non-existent parent {parent_id}, "
                f"unlinking (parent may not have been included in backup)"
            )
            fixed += 1

    if fixed > 0:
        logger.info(f"Fixed {fixed} orphaned parent_session_id references")
    return fixed


def restore_all_backups(
    store: ActivityStore,
    backup_dir: Path,
    dry_run: bool = False,
) -> dict[str, ImportResult]:
    """Restore from all backup files in directory.

    Discovers all *.sql files and imports them with deduplication.
    Files are processed in order of modification time (oldest first).

    Args:
        store: The ActivityStore instance.
        backup_dir: Directory containing backup files.
        dry_run: If True, preview what would be imported.

    Returns:
        Dictionary mapping filename to ImportResult.
    """
    results: dict[str, ImportResult] = {}
    backup_files = discover_backup_files(backup_dir)

    if not backup_files:
        logger.info(f"No backup files found in {backup_dir}")
        return results

    logger.info(f"Found {len(backup_files)} backup files to restore")

    for backup_file in backup_files:
        logger.info(f"Processing: {backup_file.name}")
        result = import_from_sql_with_dedup(store, backup_file, dry_run=dry_run)
        results[backup_file.name] = result

    # Log summary
    total_imported = sum(r.total_imported for r in results.values())
    total_skipped = sum(r.total_skipped for r in results.values())
    logger.info(
        f"Restore all complete: {total_imported} imported, "
        f"{total_skipped} skipped across {len(backup_files)} files"
    )

    return results
