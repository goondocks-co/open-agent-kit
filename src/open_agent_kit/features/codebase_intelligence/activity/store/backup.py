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


def get_machine_identifier() -> str:
    """Get deterministic machine identifier for backup files.

    Combines hostname and username to create a unique identifier
    that differentiates backups from different developers/machines.

    Returns:
        Sanitized machine identifier string (e.g., "macbook_chris").
    """
    hostname = platform.node().split(".")[0]  # Short hostname
    username = getpass.getuser()
    raw_id = f"{hostname}_{username}"
    return sanitize_identifier(raw_id)


def get_backup_filename() -> str:
    """Get backup filename for this machine.

    Returns:
        Backup filename with machine identifier (e.g., "ci_history_macbook_chris.sql").
    """
    machine_id = get_machine_identifier()
    return f"ci_history_{machine_id}.sql"


# =============================================================================
# Backup Discovery
# =============================================================================


def discover_backup_files(backup_dir: Path) -> list[Path]:
    """Find all ci_history_*.sql files, sorted by modified time.

    Args:
        backup_dir: Directory to search for backup files.

    Returns:
        List of backup file paths sorted by modification time (oldest first).
    """
    if not backup_dir.exists():
        return []
    files = list(backup_dir.glob("ci_history_*.sql"))
    return sorted(files, key=lambda p: p.stat().st_mtime)


def extract_machine_id_from_filename(filename: str) -> str:
    """Extract machine identifier from backup filename.

    Args:
        filename: Backup filename (e.g., "ci_history_macbook_chris.sql").

    Returns:
        Machine identifier or "unknown" if not parseable.
    """
    # Pattern: ci_history_{machine_id}.sql
    match = re.match(r"ci_history_(.+)\.sql$", filename)
    if match:
        return match.group(1)
    # Legacy format without machine ID
    if filename == "ci_history.sql":
        return "legacy"
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
        )

    @property
    def total_skipped(self) -> int:
        """Total records skipped (duplicates) across all tables."""
        return (
            self.sessions_skipped
            + self.batches_skipped
            + self.observations_skipped
            + self.activities_skipped
        )


def export_to_sql(store: ActivityStore, output_path: Path, include_activities: bool = False) -> int:
    """Export valuable tables to SQL dump file with content hashes.

    Exports sessions, prompt_batches, and memory_observations to a SQL file
    that can be used to restore data after feature removal/reinstall.
    The file is text-based and can be committed to git.

    Each record includes a content_hash for cross-machine deduplication,
    allowing multiple developers' backups to be merged without duplicates.

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

    # Tables to export (order matters for foreign keys)
    tables = ["sessions", "prompt_batches", "memory_observations"]
    if include_activities:
        tables.append("activities")

    # Generate INSERT statements
    lines: list[str] = []
    lines.append("-- OAK Codebase Intelligence History Backup")
    lines.append(f"-- Exported: {datetime.now().isoformat()}")
    lines.append(f"-- Machine: {machine_id}")
    lines.append(f"-- Schema version: {SCHEMA_VERSION}")
    lines.append("")

    for table in tables:
        cursor = conn.execute(f"SELECT * FROM {table}")  # noqa: S608 - trusted table names
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()

        if rows:
            lines.append(f"-- {table} ({len(rows)} records)")
            for row in rows:
                # Build row dict for hash computation
                row_dict = dict(zip(columns, row, strict=False))

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
                lines.append(f"INSERT INTO {table} ({cols_str}) VALUES ({vals_str});")

            total_count += len(rows)
            lines.append("")

        logger.debug(f"Exported {len(rows)} records from {table}")

    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")

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

    logger.debug(
        f"Existing records: {len(existing_session_ids)} sessions, "
        f"{len(existing_batch_hashes)} batches, {len(existing_obs_hashes)} observations, "
        f"{len(existing_activity_hashes)} activities"
    )

    # Parse INSERT statements
    statements_by_table: dict[str, list[tuple[str, dict]]] = {
        "sessions": [],
        "prompt_batches": [],
        "memory_observations": [],
        "activities": [],
    }

    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("INSERT INTO"):
            continue

        # Extract table name and parse values
        table_match = re.match(r"INSERT INTO (\w+)", stripped)
        if not table_match:
            continue
        table = table_match.group(1)

        if table not in statements_by_table:
            continue

        # Parse column names and values
        parsed = _parse_insert_statement(stripped)
        if parsed:
            statements_by_table[table].append((stripped, parsed))

    # Process each table in order (sessions first due to foreign keys)
    conn = store._get_connection()

    for table in ["sessions", "prompt_batches", "memory_observations", "activities"]:
        for stmt, row_dict in statements_by_table[table]:
            try:
                should_skip, reason = _should_skip_record(
                    table,
                    row_dict,
                    existing_session_ids,
                    existing_batch_hashes,
                    existing_obs_hashes,
                    existing_activity_hashes,
                )

                if should_skip:
                    _increment_skipped(result, table)
                    logger.debug(f"Skipping {table} record: {reason}")
                    continue

                if not dry_run:
                    # Modify statement for proper import
                    modified_stmt = _prepare_statement_for_import(stmt, table)
                    conn.execute(modified_stmt)

                    # Update existing sets to avoid duplicates within same import
                    _update_existing_sets(
                        table,
                        row_dict,
                        existing_session_ids,
                        existing_batch_hashes,
                        existing_obs_hashes,
                        existing_activity_hashes,
                    )

                _increment_imported(result, table)

            except sqlite3.Error as e:
                result.errors += 1
                error_msg = f"Error importing {table} record: {e}"
                result.error_messages.append(error_msg)
                logger.debug(error_msg)

    if not dry_run:
        conn.commit()

    logger.info(
        f"Import complete: {result.total_imported} imported, "
        f"{result.total_skipped} skipped (duplicates), {result.errors} errors"
    )
    return result


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
) -> tuple[bool, str]:
    """Determine if a record should be skipped due to duplication.

    Args:
        table: Table name.
        row_dict: Parsed row data.
        existing_*: Sets of existing IDs/hashes.

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

    return False, ""


def _update_existing_sets(
    table: str,
    row_dict: dict,
    existing_session_ids: set[str],
    existing_batch_hashes: set[str],
    existing_obs_hashes: set[str],
    existing_activity_hashes: set[str],
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


def _prepare_statement_for_import(stmt: str, table: str) -> str:
    """Modify INSERT statement for proper import.

    For memory_observations, marks embedded=0 to trigger ChromaDB rebuild.
    For prompt_batches, marks plan_embedded=0 for re-indexing.

    Args:
        stmt: Original INSERT statement.
        table: Table name.

    Returns:
        Modified statement ready for execution.
    """
    if table == "memory_observations":
        return _replace_column_value(stmt, "embedded", "0")
    elif table == "prompt_batches":
        return _replace_column_value(stmt, "plan_embedded", "0")
    return stmt


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


def restore_all_backups(
    store: ActivityStore,
    backup_dir: Path,
    dry_run: bool = False,
) -> dict[str, ImportResult]:
    """Restore from all backup files in directory.

    Discovers all ci_history_*.sql files and imports them with deduplication.
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
