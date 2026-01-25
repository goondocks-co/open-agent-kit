"""Backup and restore operations for activity store.

Functions for exporting and importing database data.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from open_agent_kit.features.codebase_intelligence.activity.store.schema import SCHEMA_VERSION

if TYPE_CHECKING:
    from open_agent_kit.features.codebase_intelligence.activity.store.core import ActivityStore

logger = logging.getLogger(__name__)


def export_to_sql(store: ActivityStore, output_path: Path, include_activities: bool = False) -> int:
    """Export valuable tables to SQL dump file.

    Exports sessions, prompt_batches, and memory_observations to a SQL file
    that can be used to restore data after feature removal/reinstall.
    The file is text-based and can be committed to git.

    Args:
        store: The ActivityStore instance.
        output_path: Path to write SQL dump file.
        include_activities: If True, include activities table (can be large).

    Returns:
        Number of records exported.
    """
    logger.info(f"Exporting database: include_activities={include_activities}, path={output_path}")

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
    lines.append(f"-- Schema version: {SCHEMA_VERSION}")
    lines.append("")

    for table in tables:
        cursor = conn.execute(f"SELECT * FROM {table}")  # noqa: S608 - trusted table names
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()

        if rows:
            lines.append(f"-- {table} ({len(rows)} records)")
            for row in rows:
                values = []
                for val in row:
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


def import_from_sql(store: ActivityStore, backup_path: Path) -> int:
    """Import data from SQL backup into existing database.

    The database should already have the current schema (via _ensure_schema).
    This method imports data only, not schema. All imported observations
    are marked as unembedded to trigger ChromaDB rebuild.

    Args:
        store: The ActivityStore instance.
        backup_path: Path to SQL backup file.

    Returns:
        Number of records imported.
    """
    logger.info(f"Importing from backup: {backup_path}")

    content = backup_path.read_text(encoding="utf-8")
    lines = content.split("\n")

    # Extract INSERT statements
    insert_statements: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("INSERT INTO"):
            insert_statements.append(stripped)

    logger.debug(f"Found {len(insert_statements)} INSERT statements")

    total_imported = 0
    failed_count = 0

    with store._transaction() as conn:
        for stmt in insert_statements:
            try:
                # For memory_observations, mark as unembedded
                if "INSERT INTO memory_observations" in stmt:
                    # Replace embedded value to FALSE for rebuild
                    # The embedded column is typically the last one
                    stmt = stmt.replace(", 1);", ", 0);")
                    stmt = stmt.replace(", TRUE);", ", FALSE);")

                # For prompt_batches, reset plan_embedded for re-indexing
                if "INSERT INTO prompt_batches" in stmt:
                    # Reset plan_embedded to 0 so plans get re-indexed
                    stmt = re.sub(r"plan_embedded\s*=\s*1", "plan_embedded = 0", stmt)
                    # Also handle column-value format in INSERT
                    stmt = stmt.replace(", 1)", ", 0)")  # Only if plan_embedded is last

                conn.execute(stmt)
                total_imported += 1
            except sqlite3.Error as e:
                # Log but continue - some records may conflict
                logger.debug(f"Skipping duplicate or invalid record: {e}")
                failed_count += 1

    if failed_count > 0:
        logger.warning(f"Skipped {failed_count} records during import (duplicates/conflicts)")

    logger.info(f"Import complete: {total_imported} records restored from {backup_path}")
    return total_imported
